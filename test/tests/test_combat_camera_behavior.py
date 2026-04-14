import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.camera_director import CameraDirector


def _pos(x, y, z):
    return SimpleNamespace(x=float(x), y=float(y), z=float(z))


class _CombatPlayerDummy:
    def __init__(self, anim_state="idle", combat_event=None):
        self.actor = object()
        self._is_aiming = False
        self._anim_state = str(anim_state)
        self._combat_event = dict(combat_event) if isinstance(combat_event, dict) else None
        self.brain = SimpleNamespace(mental={"fear": 0.0})
        self.cs = SimpleNamespace(health=100.0, maxHealth=100.0, inWater=False)

    def get_hud_combat_event(self):
        if isinstance(self._combat_event, dict):
            return dict(self._combat_event)
        return None


class _CombatCameraAppDummy:
    def __init__(self, anim_state="idle", combat_event=None, aim_target=None):
        self.data_mgr = SimpleNamespace(camera_profiles={})
        self.event_bus = None
        self.player = _CombatPlayerDummy(anim_state=anim_state, combat_event=combat_event)
        self.char_state = SimpleNamespace(position=_pos(0.0, 0.0, 0.0))
        self.state_mgr = SimpleNamespace(current_state=SimpleNamespace(name="playing"))
        self.boss_manager = SimpleNamespace(any_engaged=lambda: False)
        self.dragon_boss = None
        self.vehicle_mgr = None
        self.movement_tutorial = None
        self._cam_dist = 22.0
        self._cam_pitch = -20.0
        self._cam_yaw = 0.0
        self._cam_zoom_offset = 0.0
        self._aim_target_info = dict(aim_target) if isinstance(aim_target, dict) else None


class CombatCameraBehaviorTests(unittest.TestCase):
    def test_locked_enemy_target_counts_as_combat_context(self):
        app = _CombatCameraAppDummy(
            anim_state="idle",
            aim_target={
                "locked": True,
                "kind": "enemy",
                "position": _pos(6.0, 10.0, 1.5),
            },
        )
        director = CameraDirector(app)

        self.assertEqual("combat", director._resolve_profile())

    def test_combat_camera_biases_to_shoulder_and_pulls_back_for_locked_target(self):
        app = _CombatCameraAppDummy(
            anim_state="attack_light",
            combat_event={"type": "physical", "amount": 18, "label": "melee"},
            aim_target={
                "locked": True,
                "kind": "enemy",
                "position": _pos(4.0, 9.0, 1.4),
            },
        )
        director = CameraDirector(app)

        cfg = director.update(1.0, manual_look=False)

        self.assertGreater(float(cfg.get("side", 0.0)), 0.8)
        self.assertGreater(app._cam_dist, 17.5)

    def test_combat_camera_adds_mild_screen_emphasis_even_at_full_health(self):
        app = _CombatCameraAppDummy(
            anim_state="attack_heavy",
            combat_event={"type": "physical", "amount": 24, "label": "melee"},
            aim_target={
                "locked": True,
                "kind": "enemy",
                "position": _pos(-3.0, 8.0, 1.4),
            },
        )
        director = CameraDirector(app)

        director.update(0.016, manual_look=False)
        fx = director.get_screen_effect_state()

        self.assertGreater(float(fx.get("vignette_boost", 0.0)), 0.08)


if __name__ == "__main__":
    unittest.main()
