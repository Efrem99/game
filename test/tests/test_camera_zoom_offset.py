import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp
from managers.camera_director import CameraDirector


class _ZoomAppDummy:
    _zoom_camera = XBotApp._zoom_camera

    def __init__(self):
        self._cam_dist = 22.0
        self._cam_zoom_offset = 0.0
        self.state_mgr = SimpleNamespace(is_playing=lambda: True)

    def _video_bot_input_locked(self):
        return False


class _DirectorAppDummy:
    def __init__(self):
        self.data_mgr = SimpleNamespace(camera_profiles={})
        self.event_bus = None
        self.player = SimpleNamespace(_is_aiming=False, _anim_state="idle")
        self.state_mgr = SimpleNamespace(current_state=SimpleNamespace(name="playing"))
        self.boss_manager = SimpleNamespace(any_engaged=lambda: False)
        self.dragon_boss = None
        self.vehicle_mgr = None
        self.movement_tutorial = None
        self._cam_dist = 22.0
        self._cam_pitch = -20.0
        self._cam_zoom_offset = -6.0


class CameraZoomOffsetTests(unittest.TestCase):
    def test_zoom_camera_tracks_user_offset_separately_from_runtime_distance(self):
        app = _ZoomAppDummy()

        app._zoom_camera(-2.0)
        app._zoom_camera(-2.0)

        self.assertEqual(-4.0, app._cam_zoom_offset)
        self.assertEqual(18.0, app._cam_dist)

    def test_camera_director_respects_user_zoom_offset_in_profile_distance(self):
        app = _DirectorAppDummy()
        director = CameraDirector(app)

        director.update(1.0, manual_look=False)

        self.assertAlmostEqual(16.0, app._cam_dist, places=4)


if __name__ == "__main__":
    unittest.main()
