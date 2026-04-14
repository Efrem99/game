import math
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


if "utils.core_runtime" not in sys.modules:
    core_runtime_mod = types.ModuleType("utils.core_runtime")
    core_runtime_mod.gc = None
    core_runtime_mod.HAS_CORE = False
    sys.modules["utils.core_runtime"] = core_runtime_mod

if "direct.showbase.ShowBaseGlobal" not in sys.modules:
    direct_mod = types.ModuleType("direct")
    showbase_mod = types.ModuleType("direct.showbase")
    showbase_global_mod = types.ModuleType("direct.showbase.ShowBaseGlobal")

    class _Clock:
        @staticmethod
        def getFrameTime():
            return 0.0

        @staticmethod
        def getDt():
            return 0.016

    showbase_global_mod.globalClock = _Clock()
    sys.modules.setdefault("direct", direct_mod)
    sys.modules.setdefault("direct.showbase", showbase_mod)
    sys.modules["direct.showbase.ShowBaseGlobal"] = showbase_global_mod

if "panda3d.core" not in sys.modules:
    panda_mod = types.ModuleType("panda3d")
    panda_core_mod = types.ModuleType("panda3d.core")

    class _Vec3:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x = float(x)
            self.y = float(y)
            self.z = float(z)

    panda_core_mod.Vec3 = _Vec3
    sys.modules.setdefault("panda3d", panda_mod)
    sys.modules["panda3d.core"] = panda_core_mod


from entities.player_movement_mixin import PlayerMovementMixin


class _ActorStub:
    def __init__(self, pos):
        self._x = float(pos[0])
        self._y = float(pos[1])
        self._z = float(pos[2])
        self._h = 0.0

    def getX(self):
        return self._x

    def getY(self):
        return self._y

    def getZ(self):
        return self._z

    def setPos(self, x, y, z):
        values = (float(x), float(y), float(z))
        if not all(math.isfinite(value) for value in values):
            raise AssertionError(f"non-finite setPos: {values}")
        self._x, self._y, self._z = values

    def setH(self, heading):
        self._h = float(heading)


class _FlightClampDummy:
    _update_flight_python = PlayerMovementMixin._update_flight_python
    _final_step = PlayerMovementMixin._final_step
    _get_ground_height = PlayerMovementMixin._get_ground_height
    _get_terrain_height = PlayerMovementMixin._get_terrain_height
    _coerce_finite_scalar = PlayerMovementMixin._coerce_finite_scalar

    def __init__(self, *, actor_z=0.3, terrain_height=0.5):
        self.actor = _ActorStub((1.0, 2.0, actor_z))
        self.app = SimpleNamespace(
            world=SimpleNamespace(
                colliders=[],
                _th=lambda _x, _y: float(terrain_height),
            ),
            render=object(),
        )
        self.cs = SimpleNamespace(
            grounded=False,
            inWater=False,
            velocity=SimpleNamespace(x=0.0, y=0.0, z=-6.0),
            position=SimpleNamespace(x=1.0, y=2.0, z=actor_z),
        )
        self.flight_speed = 15.0
        self.flight_shift_mult = 1.45
        self._visual_height_offset = 0.0
        self._is_flying = True
        self._motion_plan = {}
        self._last_landing_impact_speed = 0.0
        self._landing_anim_hold = 0.0
        self._was_grounded = False
        self.phys = SimpleNamespace(step=lambda *_args, **_kwargs: None)
        self._pressed_actions = set()

    def _get_action(self, action):
        return str(action or "").strip().lower() in self._pressed_actions

    def _once_action(self, _action):
        return False

    def _update_flight_pose_and_fx(self, *_args, **_kwargs):
        return None

    def _check_collision(self, *_args, **_kwargs):
        return False

    def _queue_state_trigger(self, *_args, **_kwargs):
        return None

    def _play_sfx(self, *_args, **_kwargs):
        return None

    def _update_sword_trail(self):
        return None

    def _update_weapon_sheath(self, _dt):
        return None

    def _drive_animations(self, _dt=0.0):
        return None

    def _tick_anim_blend(self, _dt):
        return None


class PlayerFlightGroundClampTests(unittest.TestCase):
    def test_update_flight_python_clamps_actor_above_terrain(self):
        dummy = _FlightClampDummy(actor_z=0.2, terrain_height=0.75)

        dummy._update_flight_python(0.016, 0.0, 0.0, 0.0, 0.0)

        self.assertGreaterEqual(dummy.actor.getZ(), 0.75)
        self.assertGreaterEqual(dummy.cs.position.z, 0.75)

    def test_final_step_clamps_core_flight_position_back_to_terrain(self):
        dummy = _FlightClampDummy(actor_z=-1.25, terrain_height=2.0)

        dummy._final_step(0.016)

        self.assertGreaterEqual(dummy.cs.position.z, 2.0)
        self.assertGreaterEqual(dummy.actor.getZ(), 2.0)
        self.assertTrue(dummy.cs.grounded)

    def test_update_flight_python_uses_tunable_shift_multiplier_instead_of_hardcoded_double_speed(self):
        dummy = _FlightClampDummy(actor_z=1.0, terrain_height=0.0)
        dummy._pressed_actions.add("run")

        dummy._update_flight_python(1.0, 1.0, 0.0, 1.0, 0.0)

        self.assertAlmostEqual(1.0 + (15.0 * 1.45), dummy.actor.getX(), places=3)


if __name__ == "__main__":
    unittest.main()
