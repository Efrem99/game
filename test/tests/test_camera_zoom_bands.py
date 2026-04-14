import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.camera_director import CameraDirector


class _VelocityAppDummy:
    def __init__(
        self,
        *,
        aiming=False,
        mounted=False,
        mounted_kind="horse",
        zoom_offset=0.0,
        velocity=(0.0, 0.0, 0.0),
    ):
        self.data_mgr = SimpleNamespace(camera_profiles={})
        self.event_bus = None
        self.player = SimpleNamespace(
            _is_aiming=bool(aiming),
            _anim_state="idle",
            _is_flying=False,
            walk_speed=5.0,
            run_speed=9.0,
            flight_speed=15.0,
        )
        self.char_state = SimpleNamespace(
            position=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            velocity=SimpleNamespace(x=float(velocity[0]), y=float(velocity[1]), z=float(velocity[2])),
            health=100.0,
            maxHealth=100.0,
            inWater=False,
        )
        self.state_mgr = SimpleNamespace(current_state=SimpleNamespace(name="playing"))
        self.boss_manager = SimpleNamespace(any_engaged=lambda: False)
        self.dragon_boss = None
        self.vehicle_mgr = SimpleNamespace(
            is_mounted=bool(mounted),
            mounted_vehicle=lambda: {"kind": mounted_kind},
        ) if mounted else None
        self.movement_tutorial = None
        self._cam_dist = 22.0
        self._cam_pitch = -20.0
        self._cam_yaw = 0.0
        self._cam_zoom_offset = float(zoom_offset)
        self._aim_target_info = None


class CameraZoomBandTests(unittest.TestCase):
    def test_aim_profile_clamps_zoom_out_to_tight_band(self):
        app = _VelocityAppDummy(aiming=True, zoom_offset=40.0)
        director = CameraDirector(app)

        director.update(1.0, manual_look=False)

        self.assertLessEqual(app._cam_dist, 13.5)

    def test_mounted_profile_clamps_zoom_in_to_wide_band_floor(self):
        app = _VelocityAppDummy(mounted=True, mounted_kind="horse", zoom_offset=-40.0)
        director = CameraDirector(app)

        director.update(1.0, manual_look=False)

        self.assertGreaterEqual(app._cam_dist, 16.0)

    def test_exploration_speed_adds_trailing_distance(self):
        app = _VelocityAppDummy(velocity=(8.0, 0.0, 0.0))
        director = CameraDirector(app)

        director.update(1.0, manual_look=False)

        self.assertGreater(app._cam_dist, 22.0)

    def test_flight_profile_keeps_zoom_tighter_under_fast_forward_motion(self):
        app = _VelocityAppDummy(velocity=(18.0, 0.0, 0.0))
        app.player._is_flying = True
        director = CameraDirector(app)

        director.update(1.0, manual_look=False)

        self.assertLessEqual(app._cam_dist, 24.5)


if __name__ == "__main__":
    unittest.main()
