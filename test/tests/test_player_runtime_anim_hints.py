import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import types

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_global_clock = types.SimpleNamespace(getFrameTime=lambda: 1.0)
_showbase_global = types.ModuleType("direct.showbase.ShowBaseGlobal")
_showbase_global.globalClock = _global_clock
_showbase = types.ModuleType("direct.showbase")
_showbase.ShowBaseGlobal = _showbase_global
_direct = types.ModuleType("direct")
_direct.showbase = _showbase
sys.modules.setdefault("direct", _direct)
sys.modules.setdefault("direct.showbase", _showbase)
sys.modules.setdefault("direct.showbase.ShowBaseGlobal", _showbase_global)

from entities.player_state_machine_mixin import PlayerStateMachineMixin


class _RuntimeHintDummy:
    _sync_parkour_runtime_hints = PlayerStateMachineMixin._sync_parkour_runtime_hints
    _parkour_action_token = PlayerStateMachineMixin._parkour_action_token
    _parkour_action_profile = PlayerStateMachineMixin._parkour_action_profile
    _update_parkour_ik = PlayerStateMachineMixin._update_parkour_ik
    _set_state_anim_hints = PlayerStateMachineMixin._set_state_anim_hints

    def __init__(self):
        self.walk_speed = 4.0
        self.run_speed = 8.0
        self.flight_speed = 10.0
        self._is_flying = False
        self._env_flags = set()
        self._state_anim_hints = {}
        self._parkour_last_action = ""
        self._parkour_exit_hint_until = -1.0
        self._parkour_ik_alpha = 0.0
        self._flight_takeoff_until = 0.0
        self._actions = {}
        self._action = ""
        self.ps = SimpleNamespace(timer=0.0)
        self.cs = SimpleNamespace(
            velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            inWater=False,
        )

    def _parkour_action_name(self):
        return self._action

    def _get_action(self, action):
        return bool(self._actions.get(action, False))

    def _set_state_anim_hints(self, state_name, tokens):
        key = str(state_name or "").strip().lower()
        cleaned = [str(token or "").strip().lower() for token in (tokens or []) if str(token or "").strip()]
        if cleaned:
            self._state_anim_hints[key] = cleaned
        else:
            self._state_anim_hints.pop(key, None)


class _IKNode:
    def __init__(self):
        self.last_hpr = (0.0, 0.0, 0.0)

    def setHpr(self, h, p, r):
        self.last_hpr = (float(h), float(p), float(r))


class PlayerRuntimeAnimHintTests(unittest.TestCase):
    def test_stationary_flight_prefers_hover_variant(self):
        actor = _RuntimeHintDummy()
        actor._is_flying = True

        actor._sync_parkour_runtime_hints()

        self.assertIn("flying", actor._state_anim_hints)
        self.assertEqual("flight_hover", actor._state_anim_hints["flying"][0])

    def test_fast_flight_prefers_glide_variant(self):
        actor = _RuntimeHintDummy()
        actor._is_flying = True
        actor.cs.velocity.x = 4.6
        actor.cs.velocity.y = 3.4

        actor._sync_parkour_runtime_hints()

        self.assertIn("flying", actor._state_anim_hints)
        self.assertEqual("flight_glide", actor._state_anim_hints["flying"][0])

    def test_idle_swim_prefers_surface_variant(self):
        actor = _RuntimeHintDummy()
        actor.cs.inWater = True

        actor._sync_parkour_runtime_hints()

        self.assertIn("swim", actor._state_anim_hints)
        self.assertEqual("swim_surface", actor._state_anim_hints["swim"][0])

    def test_wallrun_start_prefers_wallrun_start_variant(self):
        actor = _RuntimeHintDummy()
        actor._action = "wallrun"
        actor.ps.timer = 0.10

        actor._sync_parkour_runtime_hints()

        self.assertIn("wallrun", actor._state_anim_hints)
        self.assertEqual("wallrun_start", actor._state_anim_hints["wallrun"][0])

    def test_wallrun_exit_sets_recovering_hint(self):
        actor = _RuntimeHintDummy()
        actor._parkour_last_action = "wallrun"
        actor._action = ""

        actor._sync_parkour_runtime_hints()

        self.assertIn("recovering", actor._state_anim_hints)
        self.assertEqual("wallrun_exit", actor._state_anim_hints["recovering"][0])

    def test_vault_high_action_keeps_explicit_variant_hint(self):
        actor = _RuntimeHintDummy()
        actor._action = "vault_high"

        actor._sync_parkour_runtime_hints()

        self.assertIn("vaulting", actor._state_anim_hints)
        self.assertEqual("vault_high", actor._state_anim_hints["vaulting"][0])

    def test_obstacle_ahead_at_running_speed_prefers_fast_vault_hint(self):
        actor = _RuntimeHintDummy()
        actor._action = "vault"
        actor._env_flags = {"obstacle_ahead"}
        actor.cs.velocity.x = 6.4
        actor.cs.velocity.y = 0.0

        actor._sync_parkour_runtime_hints()

        self.assertIn("vaulting", actor._state_anim_hints)
        self.assertEqual("vault_speed", actor._state_anim_hints["vaulting"][0])

    def test_obstacle_ahead_at_walk_speed_prefers_low_vault_hint(self):
        actor = _RuntimeHintDummy()
        actor._action = "vault"
        actor._env_flags = {"obstacle_ahead"}
        actor.cs.velocity.x = 1.4
        actor.cs.velocity.y = 0.0

        actor._sync_parkour_runtime_hints()

        self.assertIn("vaulting", actor._state_anim_hints)
        self.assertEqual("vault_low", actor._state_anim_hints["vaulting"][0])

    def test_grab_ledge_action_prefers_grab_ledge_hint(self):
        actor = _RuntimeHintDummy()
        actor._action = "grab_ledge"

        actor._sync_parkour_runtime_hints()

        self.assertIn("climbing", actor._state_anim_hints)
        self.assertEqual("grab_ledge", actor._state_anim_hints["climbing"][0])

    def test_grab_ledge_action_activates_parkour_ik(self):
        actor = _RuntimeHintDummy()
        actor._action = "grab_ledge"
        actor._parkour_ik_controls = {
            "right_hand": _IKNode(),
            "left_hand": _IKNode(),
            "right_foot": _IKNode(),
            "left_foot": _IKNode(),
            "spine": _IKNode(),
        }

        actor._update_parkour_ik(0.2)

        self.assertGreater(actor._parkour_ik_alpha, 0.1)
        self.assertLess(actor._parkour_ik_controls["right_hand"].last_hpr[1], -1.0)


if __name__ == "__main__":
    unittest.main()
