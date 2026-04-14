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
            return 10.0

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


class _MoveStub:
    def __init__(self, length=1.0, x=0.0, y=1.0, z=0.0):
        self._length = float(length)
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def len(self):
        return self._length

    def normalized(self):
        return self


class _ActorStub:
    def __init__(self):
        self.heading = 0.0
        self._pos = SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def getPos(self, *_args, **_kwargs):
        return SimpleNamespace(x=float(self._pos.x), y=float(self._pos.y), z=float(self._pos.z))

    def setH(self, heading):
        self.heading = float(heading)


class _DodgeDummy:
    _emit_evasion_camera_impulse = PlayerMovementMixin._emit_evasion_camera_impulse
    _resolve_dodge_direction_token = PlayerMovementMixin._resolve_dodge_direction_token
    _trigger_ground_dodge = PlayerMovementMixin._trigger_ground_dodge

    def __init__(self, axes=(0.0, 1.0)):
        self._axes = axes
        self.hints = []
        self.triggers = []
        self.blur_calls = []
        self.camera_impacts = []
        director = SimpleNamespace(
            emit_impact=lambda kind, intensity=0.0, direction_deg=0.0: self.camera_impacts.append(
                (str(kind or ""), float(intensity), float(direction_deg))
            )
        )
        self.app = SimpleNamespace(camera_director=SimpleNamespace(camera_director=director))

    def _get_move_axes(self):
        return self._axes

    def _apply_state_anim_hint_tokens(self, state, tokens):
        self.hints.append((state, list(tokens)))

    def _trigger_dash_blur_fx(self, move, intensity=0.0):
        self.blur_calls.append(float(intensity))

    def _queue_state_trigger(self, trigger):
        self.triggers.append(str(trigger))


class _GroundRoutingDummy:
    _coerce_finite_scalar = PlayerMovementMixin._coerce_finite_scalar
    _emit_evasion_camera_impulse = PlayerMovementMixin._emit_evasion_camera_impulse
    _resolve_dodge_direction_token = PlayerMovementMixin._resolve_dodge_direction_token
    _trigger_ground_dodge = PlayerMovementMixin._trigger_ground_dodge
    _trigger_ground_roll = PlayerMovementMixin._trigger_ground_roll
    _trigger_air_dash = PlayerMovementMixin._trigger_air_dash
    _trigger_flight_dash = PlayerMovementMixin._trigger_flight_dash
    _update_ground = PlayerMovementMixin._update_ground
    _update_flight = PlayerMovementMixin._update_flight

    def __init__(self, *, axes=(0.0, 1.0), grounded=True, flying=False, once_actions=None):
        self._axes = tuple(float(v) for v in axes)
        self._once = {str(token).strip().lower() for token in (once_actions or set())}
        self._get_actions = set()
        self._stealth_crouch = False
        self._is_flying = bool(flying)
        self.flight_speed = 15.0
        self.walk_speed = 5.0
        self.run_speed = 9.0
        self._footstep_timer = 0.0
        self._flight_airdash_until = 0.0
        self._air_dash_until = 0.0
        self._motion_plan = {}
        self._visual_height_offset = 0.0
        self._drawn_hold_timer = 0.0
        self._weapon_drawn = False
        self._last_landing_impact_speed = 0.0
        self._landing_anim_hold = 0.0
        self._was_grounded = bool(grounded)
        self.hints = []
        self.triggers = []
        self.blur_calls = []
        self.camera_impacts = []
        self.footstep_updates = []
        self.air_dash_calls = []
        director = SimpleNamespace(
            emit_impact=lambda kind, intensity=0.0, direction_deg=0.0: self.camera_impacts.append(
                (str(kind or ""), float(intensity), float(direction_deg))
            )
        )
        self.app = SimpleNamespace(
            render=object(),
            world=None,
            camera_director=SimpleNamespace(camera_director=director),
        )
        self.actor = _ActorStub()
        self.cs = SimpleNamespace(
            grounded=bool(grounded),
            inWater=False,
            velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            facingDir=None,
        )
        self.data_mgr = SimpleNamespace(get_move_param=lambda *_args, **_kwargs: 9.5)
        self.parkour = SimpleNamespace(
            tryAirDash=lambda *_args, **_kwargs: self.air_dash_calls.append("air") or True,
            tryLedgeGrab=lambda *_args, **_kwargs: False,
            tryWallRun=lambda *_args, **_kwargs: False,
            update=lambda *_args, **_kwargs: None,
        )
        self.ps = SimpleNamespace()
        self.phys = SimpleNamespace(applyJump=lambda *_args, **_kwargs: None)

    def _get_move_axes(self):
        return self._axes

    def _get_action(self, action):
        return str(action or "").strip().lower() in self._get_actions

    def _once_action(self, action):
        token = str(action or "").strip().lower()
        if token in self._once:
            self._once.remove(token)
            return True
        return False

    def _apply_state_anim_hint_tokens(self, state, tokens):
        self.hints.append((state, list(tokens)))

    def _trigger_dash_blur_fx(self, move, intensity=0.0):
        self.blur_calls.append(float(intensity))

    def _queue_state_trigger(self, trigger):
        self.triggers.append(str(trigger))

    def _set_flight_fx(self, *_args, **_kwargs):
        return None

    def _set_stealth_crouch(self, value):
        self._stealth_crouch = bool(value)

    def _sync_wall_contact_state(self):
        return None

    def _update_footsteps(self, dt, moving=False, running=False, in_water=False):
        self.footstep_updates.append((float(dt), bool(moving), bool(running), bool(in_water)))

    def _update_flight_pose_and_fx(self, *_args, **_kwargs):
        return None

    def _play_sfx(self, *_args, **_kwargs):
        return None

    def _get_ground_height(self, *_args, **_kwargs):
        return 0.0

    def _update_weapon_sheath(self, *_args, **_kwargs):
        return None

    def _update_sword_trail(self):
        return None

    def _drive_animations(self, *_args, **_kwargs):
        return None

    def _tick_anim_blend(self, *_args, **_kwargs):
        return None


class PlayerDodgeRoutingTests(unittest.TestCase):
    def test_trigger_ground_dodge_queues_dodge_and_directional_hint(self):
        dummy = _DodgeDummy(axes=(-0.9, 0.0))

        result = dummy._trigger_ground_dodge(_MoveStub(1.0), running=False, blur_intensity=0.82)

        self.assertTrue(result)
        self.assertEqual(["dodge"], dummy.triggers)
        self.assertEqual([0.82], dummy.blur_calls)
        self.assertEqual(("dodging", ["dash_left", "dodging"]), dummy.hints[0])

    def test_trigger_ground_dodge_uses_back_hint_for_backward_input(self):
        dummy = _DodgeDummy(axes=(0.0, -1.0))

        result = dummy._trigger_ground_dodge(_MoveStub(1.0), running=True, blur_intensity=1.04)

        self.assertTrue(result)
        self.assertEqual(("dodging", ["dash_back", "dodging"]), dummy.hints[0])
        self.assertEqual(["dodge"], dummy.triggers)
        self.assertEqual([1.04], dummy.blur_calls)

    def test_trigger_ground_dodge_ignores_zero_length_motion(self):
        dummy = _DodgeDummy(axes=(0.0, 1.0))

        result = dummy._trigger_ground_dodge(_MoveStub(0.0), running=False)

        self.assertFalse(result)
        self.assertEqual([], dummy.triggers)
        self.assertEqual([], dummy.hints)
        self.assertEqual([], dummy.blur_calls)

    def test_trigger_ground_dodge_emits_light_camera_impulse(self):
        dummy = _DodgeDummy(axes=(0.0, 1.0))

        result = dummy._trigger_ground_dodge(_MoveStub(1.0), running=True, blur_intensity=1.04)

        self.assertTrue(result)
        self.assertEqual("near_miss", dummy.camera_impacts[0][0])
        self.assertGreater(dummy.camera_impacts[0][1], 0.15)

    def test_update_ground_roll_prefers_roll_hint_instead_of_directional_dash(self):
        dummy = _GroundRoutingDummy(axes=(0.0, 1.0), grounded=True, once_actions={"roll"})

        dummy._update_ground(0.016, _MoveStub(1.0, x=0.0, y=1.0))

        self.assertEqual(("dodging", ["dodge_roll", "dodging"]), dummy.hints[0])
        self.assertEqual(["dodge"], dummy.triggers)

    def test_update_ground_dash_keeps_directional_dash_hint(self):
        dummy = _GroundRoutingDummy(axes=(1.0, 0.0), grounded=True, once_actions={"dash"})

        dummy._update_ground(0.016, _MoveStub(1.0, x=1.0, y=0.0))

        self.assertEqual(("dodging", ["dash_right", "dodging"]), dummy.hints[0])
        self.assertEqual(["dodge", "dash"], dummy.triggers)

    def test_update_ground_air_dash_marks_jump_chain_instead_of_ground_dodge(self):
        dummy = _GroundRoutingDummy(axes=(0.0, 1.0), grounded=False, once_actions={"dash"})

        dummy._update_ground(0.016, _MoveStub(1.0, x=0.0, y=1.0))

        self.assertEqual(["air"], dummy.air_dash_calls)
        self.assertEqual(("jumping", ["jump_dash", "jumping", "falling"]), dummy.hints[0])

    def test_update_flight_dash_sets_flight_airdash_window(self):
        dummy = _GroundRoutingDummy(axes=(0.0, 1.0), grounded=False, flying=True, once_actions={"dash"})

        dummy._update_flight(_MoveStub(1.0, x=0.0, y=1.0))

        self.assertGreater(dummy._flight_airdash_until, 0.2)
        self.assertEqual(("flying", ["flight_airdash", "flying"]), dummy.hints[0])
        self.assertEqual("near_miss", dummy.camera_impacts[0][0])


if __name__ == "__main__":
    unittest.main()
