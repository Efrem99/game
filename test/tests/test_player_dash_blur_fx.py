import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from direct.showbase.ShowBaseGlobal import globalClock

from entities.player import Player
from entities.player_movement_mixin import PlayerMovementMixin


class _VisualNode:
    def __init__(self, name="node"):
        self.name = name
        self.visible = False
        self.pos = None
        self.h = 0.0
        self.scale = None
        self.color_scale = None

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def setPos(self, *value):
        self.pos = tuple(value)

    def setH(self, *value):
        self.h = float(value[-1])

    def setScale(self, *value):
        self.scale = value if len(value) != 1 else value[0]

    def setColorScale(self, *value):
        self.color_scale = tuple(value)


class _ActorNode(_VisualNode):
    def __init__(self):
        super().__init__("actor")
        self.world_pos = SimpleNamespace(x=3.0, y=4.0, z=1.2)
        self.h = 15.0

    def getPos(self, *_args, **_kwargs):
        return self.world_pos

    def getH(self, *_args, **_kwargs):
        return self.h


class _DashFxDummy:
    _trigger_dash_blur_fx = Player._trigger_dash_blur_fx
    _update_dash_blur_fx = Player._update_dash_blur_fx

    def __init__(self):
        self.render = object()
        self.actor = _ActorNode()
        self._anim_state = "idle"
        self._dash_fx_root = _VisualNode("dash_root")
        self._dash_fx_left = _VisualNode("dash_left")
        self._dash_fx_right = _VisualNode("dash_right")
        self._dash_fx_center = _VisualNode("dash_center")
        self._dash_fx_until = 0.0
        self._dash_fx_alpha = 0.0
        self._dash_fx_heading = 0.0


class _Move:
    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0

    def len(self):
        return (self.x * self.x + self.y * self.y) ** 0.5

    def normalized(self):
        length = self.len()
        if length <= 1e-8:
            return _Move(0.0, 0.0)
        return _Move(self.x / length, self.y / length)


class _GroundDashDummy:
    _update_ground = PlayerMovementMixin._update_ground

    def __init__(self):
        self.app = SimpleNamespace(render=object(), data_mgr=SimpleNamespace(water_config={}))
        self.actor = SimpleNamespace(
            getPos=lambda _render=None: SimpleNamespace(x=0.0, y=0.0, z=0.0),
            setH=lambda *_args, **_kwargs: None,
        )
        self.cs = SimpleNamespace(
            inWater=False,
            grounded=True,
            velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            facingDir=None,
        )
        self.walk_speed = 4.0
        self.run_speed = 7.5
        self._motion_plan = {}
        self._last_turn_trigger_time = -999.0
        self._stealth_crouch = False
        self._is_flying = False
        self.ps = SimpleNamespace()
        self.phys = SimpleNamespace(applyJump=lambda *_args, **_kwargs: None)
        self.parkour = SimpleNamespace(
            tryLedgeGrab=lambda *_args, **_kwargs: None,
            tryVault=lambda *_args, **_kwargs: None,
            tryAirDash=lambda *_args, **_kwargs: True,
            tryWallRun=lambda *_args, **_kwargs: False,
            update=lambda *_args, **_kwargs: None,
        )
        self.data_mgr = SimpleNamespace(get_move_param=lambda _key: 9.5)
        self.triggers = []
        self.dash_blur_calls = []

    def _set_flight_fx(self, _active):
        return None

    def _get_action(self, _action):
        return False

    def _once_action(self, action):
        return str(action) == "dash"

    def _queue_state_trigger(self, token):
        self.triggers.append(str(token or "").strip().lower())

    def _play_sfx(self, *_args, **_kwargs):
        return None

    def _set_stealth_crouch(self, enabled):
        self._stealth_crouch = bool(enabled)

    def _sync_wall_contact_state(self):
        return None

    def _update_footsteps(self, *_args, **_kwargs):
        return None

    def _trigger_dash_blur_fx(self, move, intensity=1.0):
        self.dash_blur_calls.append((float(getattr(move, "x", 0.0)), float(getattr(move, "y", 0.0)), float(intensity)))


class PlayerDashBlurFxTests(unittest.TestCase):
    def test_trigger_dash_blur_fx_sets_heading_and_window(self):
        actor = _DashFxDummy()

        actor._trigger_dash_blur_fx(SimpleNamespace(x=1.0, y=0.0), intensity=0.9)

        self.assertGreater(actor._dash_fx_until, float(globalClock.getFrameTime()))
        self.assertAlmostEqual(90.0, actor._dash_fx_heading, delta=0.01)

    def test_update_dash_blur_fx_shows_active_effect_and_hides_after_expiry(self):
        actor = _DashFxDummy()
        actor._trigger_dash_blur_fx(SimpleNamespace(x=0.0, y=1.0), intensity=1.0)

        actor._update_dash_blur_fx(0.016)

        self.assertTrue(actor._dash_fx_root.visible)
        self.assertGreater(actor._dash_fx_alpha, 0.1)
        self.assertIsNotNone(actor._dash_fx_root.color_scale)

        actor._dash_fx_until = float(globalClock.getFrameTime()) - 1.0
        actor._anim_state = "idle"
        actor._update_dash_blur_fx(0.25)

        self.assertFalse(actor._dash_fx_root.visible)
        self.assertLessEqual(actor._dash_fx_alpha, 0.05)

    def test_update_ground_dash_triggers_dash_blur_fx(self):
        actor = _GroundDashDummy()

        actor._update_ground(0.016, _Move(0.0, 1.0))

        self.assertIn("dash", actor.triggers)
        self.assertIn("dodge", actor.triggers)
        self.assertTrue(actor.dash_blur_calls)


if __name__ == "__main__":
    unittest.main()
