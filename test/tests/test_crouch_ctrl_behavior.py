import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player
from entities.player_state_machine_mixin import PlayerStateMachineMixin


class _CrouchDummy:
    _set_stealth_crouch = Player._set_stealth_crouch
    _sync_stealth_input = Player._sync_stealth_input

    def __init__(self):
        self._stealth_crouch = False
        self._stealth_crouch_hold_latched = False
        self._is_flying = False
        self._pending_damage_ratio = 0.0
        self.brain = None
        self.app = SimpleNamespace(
            vehicle_mgr=SimpleNamespace(is_mounted=False),
            time_fx=None,
        )
        self._once_actions = set()
        self._hold_actions = set()

    def _once_action(self, action):
        if action in self._once_actions:
            self._once_actions.remove(action)
            return True
        return False

    def _get_action(self, action):
        return action in self._hold_actions


class CrouchCtrlBehaviorTests(unittest.TestCase):
    def test_ctrl_hold_enables_crouch(self):
        actor = _CrouchDummy()
        actor._hold_actions.add("crouch_hold")
        actor._sync_stealth_input()
        self.assertTrue(actor._stealth_crouch)
        self.assertTrue(actor._stealth_crouch_hold_latched)

    def test_releasing_ctrl_disables_only_hold_crouch(self):
        actor = _CrouchDummy()
        actor._stealth_crouch = True
        actor._stealth_crouch_hold_latched = True
        actor._sync_stealth_input()
        self.assertFalse(actor._stealth_crouch)
        self.assertFalse(actor._stealth_crouch_hold_latched)

    def test_toggle_crouch_persists_without_ctrl_hold(self):
        actor = _CrouchDummy()
        actor._once_actions.add("crouch_toggle")
        actor._sync_stealth_input()
        self.assertTrue(actor._stealth_crouch)
        self.assertFalse(actor._stealth_crouch_hold_latched)
        actor._sync_stealth_input()
        self.assertTrue(actor._stealth_crouch)

    def test_state_machine_prefers_crouch_states_when_crouched(self):
        dummy = SimpleNamespace()
        idle = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {"is_crouched": True, "speed": 0.02, "on_ground": True},
        )
        moving = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {"is_crouched": True, "speed": 0.55, "on_ground": True},
        )
        self.assertEqual("crouch_idle", idle)
        self.assertEqual("crouch_move", moving)

    def test_controls_bind_ctrl_to_crouch_hold(self):
        payload = json.loads((ROOT / "data" / "controls.json").read_text(encoding="utf-8-sig"))
        bindings = payload.get("bindings", {})
        self.assertEqual("lcontrol", str(bindings.get("crouch_hold", "")).strip().lower())


if __name__ == "__main__":
    unittest.main()
