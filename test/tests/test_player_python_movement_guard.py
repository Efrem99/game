import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_input_mixin import PlayerInputMixin
from entities.player_movement_mixin import PlayerMovementMixin


class _Vec3:
    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def len(self):
        return math.sqrt((self.x * self.x) + (self.y * self.y) + (self.z * self.z))

    def normalized(self):
        length = self.len()
        if length <= 1e-8:
            return _Vec3(0.0, 0.0, 0.0)
        return _Vec3(self.x / length, self.y / length, self.z / length)


class _ActorStub:
    def __init__(self, pos):
        self._pos = _Vec3(*pos)
        self.heading = 0.0

    def getPos(self, *_args, **_kwargs):
        return _Vec3(self._pos.x, self._pos.y, self._pos.z)

    def setPos(self, x, y, z):
        values = (float(x), float(y), float(z))
        if not all(math.isfinite(value) for value in values):
            raise AssertionError(f"non-finite setPos: {values}")
        self._pos = _Vec3(*values)

    def setH(self, heading):
        value = float(heading)
        if not math.isfinite(value):
            raise AssertionError(f"non-finite setH: {value}")
        self.heading = value


class _WorldStub:
    def __init__(self, ground_height):
        self._ground_height = ground_height
        self.colliders = []

    def sample_water_height(self, _x, _y):
        return -1.5

    def _th(self, x, y):
        return self._ground_height(x, y)


class _MovementDummy:
    _update_ground = PlayerMovementMixin._update_ground
    _update_python_movement = PlayerMovementMixin._update_python_movement
    _final_step = PlayerMovementMixin._final_step
    _get_ground_height = PlayerMovementMixin._get_ground_height
    _get_terrain_height = PlayerMovementMixin._get_terrain_height
    _camera_move_vector = PlayerInputMixin._camera_move_vector
    if hasattr(PlayerMovementMixin, "_coerce_finite_scalar"):
        _coerce_finite_scalar = PlayerMovementMixin._coerce_finite_scalar

    def __init__(self, *, ground_height):
        self.actor = _ActorStub((0.0, 0.0, 7.2))
        self.app = SimpleNamespace(world=_WorldStub(ground_height), render=object())
        self._motion_plan = {}
        self._stealth_crouch = False
        self._is_flying = False
        self._movement_mode = "walk"
        self._py_velocity_z = 0.0
        self._py_grounded = True
        self._py_landing_timer = 0.0
        self._py_in_water = False
        self.walk_speed = 5.0
        self.run_speed = 9.0
        self.flight_speed = 15.0
        self.cs = None
        self.phys = SimpleNamespace(step=lambda *_args, **_kwargs: None)
        self.footstep_updates = []
        self.state_machine_ticks = 0
        self._motion_plan = {}
        self._last_landing_impact_speed = 0.0
        self._landing_anim_hold = 0.0
        self._was_grounded = True
        self._visual_height_offset = 0.0
        self.ps = SimpleNamespace()
        self.data_mgr = SimpleNamespace(get_move_param=lambda _key: 9.5)
        self._last_turn_trigger_time = -999.0
        self.parkour = SimpleNamespace(
            tryLedgeGrab=lambda *_args, **_kwargs: None,
            tryVault=lambda *_args, **_kwargs: None,
            tryAirDash=lambda *_args, **_kwargs: None,
            tryWallRun=lambda *_args, **_kwargs: False,
            update=lambda *_args, **_kwargs: None,
        )

    def _set_flight_fx(self, _enabled):
        return None

    def _get_action(self, _action):
        return False

    def _once_action(self, _action):
        return False

    def _check_collision(self, *_args):
        return False

    def _sync_wall_contact_state(self):
        return None

    def _queue_state_trigger(self, _trigger):
        return None

    def _play_sfx(self, *_args, **_kwargs):
        return None

    def _run_animation_state_machine(self):
        self.state_machine_ticks += 1

    def _update_footsteps(self, dt, moving, running, in_water=False):
        self.footstep_updates.append((float(dt), bool(moving), bool(running), bool(in_water)))

    def _tick_anim_blend(self, _dt):
        return None

    def _set_stealth_crouch(self, _enabled):
        return None

    def _update_flight_python(self, *_args, **_kwargs):
        raise AssertionError("flight update should not run in ground movement test")

    def _update_sword_trail(self):
        return None

    def _update_weapon_sheath(self, _dt):
        return None

    def _drive_animations(self, _dt=0.0):
        return None

    def _tick_anim_blend(self, _dt):
        return None

    def _trigger_ground_dodge(self, *_args, **_kwargs):
        return None


class PlayerPythonMovementGuardTests(unittest.TestCase):
    def test_python_movement_sanitizes_non_finite_camera_yaw(self):
        dummy = _MovementDummy(ground_height=lambda _x, _y: 5.0)

        dummy._update_python_movement(0.016, math.nan, mx=0.0, my=1.0)

        pos = dummy.actor.getPos()
        self.assertTrue(all(math.isfinite(value) for value in (pos.x, pos.y, pos.z)))
        self.assertTrue(math.isfinite(dummy.actor.heading))
        self.assertGreater(pos.y, 0.0)

    def test_python_movement_sanitizes_non_finite_ground_height(self):
        dummy = _MovementDummy(ground_height=lambda _x, _y: float("inf"))

        dummy._update_python_movement(0.016, 0.0, mx=0.0, my=1.0)

        pos = dummy.actor.getPos()
        self.assertTrue(all(math.isfinite(value) for value in (pos.x, pos.y, pos.z)))
        self.assertTrue(math.isfinite(dummy.actor.heading))
        self.assertLess(abs(pos.z), 100.0)

    def test_ground_height_keeps_platform_snap_while_actor_is_inside_platform_volume(self):
        dummy = _MovementDummy(ground_height=lambda _x, _y: 0.0)
        dummy.app.world.colliders = [
            {
                "min_x": -40.0,
                "max_x": 40.0,
                "min_y": -40.0,
                "max_y": 40.0,
                "min_z": 3.8,
                "max_z": 5.0,
            }
        ]

        h = dummy._get_ground_height(0.0, 0.0, 4.2)

        self.assertAlmostEqual(5.0, h, places=3)

    def test_ground_height_does_not_snap_back_to_platform_when_actor_is_far_below_it(self):
        dummy = _MovementDummy(ground_height=lambda _x, _y: 0.0)
        dummy.app.world.colliders = [
            {
                "min_x": -40.0,
                "max_x": 40.0,
                "min_y": -40.0,
                "max_y": 40.0,
                "min_z": 3.8,
                "max_z": 5.0,
            }
        ]

        h = dummy._get_ground_height(0.0, 0.0, 0.2)

        self.assertAlmostEqual(0.0, h, places=3)

    def test_final_step_clamps_core_position_back_to_terrain_height_when_core_step_falls_below_ground(self):
        dummy = _MovementDummy(ground_height=lambda _x, _y: 4.0)
        dummy.cs = SimpleNamespace(
            grounded=False,
            inWater=False,
            velocity=SimpleNamespace(x=0.0, y=0.0, z=-8.0),
            position=SimpleNamespace(x=2.0, y=3.0, z=-1.5),
        )
        dummy.actor = _ActorStub((2.0, 3.0, -1.5))

        dummy._final_step(0.016)

        self.assertGreaterEqual(dummy.cs.position.z, 4.0)
        self.assertAlmostEqual(4.0, dummy.actor.getPos().z, places=3)
        self.assertTrue(dummy.cs.grounded)

    def test_update_ground_does_not_mark_core_player_as_in_water_only_from_global_z(self):
        dummy = _MovementDummy(ground_height=lambda _x, _y: 0.0)
        dummy.actor = _ActorStub((4.0, 36.0, -1.0))
        dummy.cs = SimpleNamespace(
            grounded=True,
            inWater=False,
            velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            facingDir=None,
            position=SimpleNamespace(x=4.0, y=36.0, z=-1.0),
        )
        dummy.app.data_mgr = SimpleNamespace(water_config={"water_level": -0.4})

        dummy._update_ground(0.016, _Vec3(0.0, 0.0, 0.0))

        self.assertFalse(dummy.cs.inWater)


if __name__ == "__main__":
    unittest.main()
