import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from panda3d.core import LPoint3


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.camera_director import CameraDirector


class _NodeStub:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self._pos = LPoint3(float(x), float(y), float(z))

    def getPos(self, _render=None):
        return LPoint3(float(self._pos.x), float(self._pos.y), float(self._pos.z))


class _CameraDebugAppDummy:
    def __init__(self, camera_profiles=None, active_location=""):
        self.data_mgr = SimpleNamespace(camera_profiles=camera_profiles or {})
        self.event_bus = None
        self.player = SimpleNamespace(_is_aiming=False, _anim_state="idle")
        self.camera = _NodeStub(0.0, -18.0, 12.0)
        self.render = object()
        self.world = SimpleNamespace(active_location=str(active_location or ""))
        self.state_mgr = SimpleNamespace(current_state=SimpleNamespace(name="playing"))
        self.boss_manager = SimpleNamespace(any_engaged=lambda: False)
        self.dragon_boss = None
        self.vehicle_mgr = None
        self.movement_tutorial = None
        self.char_state = SimpleNamespace(
            position=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0),
        )
        self._cam_yaw = 0.0
        self._cam_pitch = -20.0
        self._cam_dist = 22.0


class CameraDirectorDebugFlagsTests(unittest.TestCase):
    def test_env_flag_disables_auto_boss_intro(self):
        old = os.environ.get("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO")
        os.environ["XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO"] = "1"
        try:
            director = CameraDirector(_CameraDebugAppDummy())
        finally:
            if old is None:
                os.environ.pop("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO", None)
            else:
                os.environ["XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO"] = old

        self.assertFalse(director._auto_boss_intro)

    def test_env_flag_disables_location_and_zone_camera_context_rules(self):
        old = os.environ.get("XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES")
        os.environ["XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES"] = "1"
        try:
            director = CameraDirector(
                _CameraDebugAppDummy(
                    camera_profiles={
                        "locations": {
                            "training grounds": {
                                "profile": "shoulder_right",
                                "enter_sequence": "location_reveal",
                            }
                        },
                        "zones": [
                            {
                                "id": "training_pool_anchor",
                                "location": "training grounds",
                                "center": [6.0, 46.0, 1.0],
                                "radius": 8.0,
                                "profile": "stealth",
                                "priority": 82,
                                "enter_sequence": "portal_arrival",
                            }
                        ],
                    },
                    active_location="Training Grounds",
                )
            )
            director.app.char_state.position = SimpleNamespace(x=6.0, y=46.0, z=1.0)
            director.update(0.016, manual_look=False)
        finally:
            if old is None:
                os.environ.pop("XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES", None)
            else:
                os.environ["XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES"] = old

        self.assertTrue(director._debug_disable_camera_context_rules)
        self.assertEqual("exploration", director._active_profile)
        self.assertFalse(director.is_cutscene_active())
        self.assertEqual({}, director._zone_inside)


if __name__ == "__main__":
    unittest.main()
