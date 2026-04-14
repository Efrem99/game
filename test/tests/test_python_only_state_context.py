import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_state_machine_mixin import PlayerStateMachineMixin


class _PythonCtxDummy:
    _build_state_context = PlayerStateMachineMixin._build_state_context

    def __init__(self):
        self.cs = None
        self.walk_speed = 5.0
        self.run_speed = 9.0
        self._anim_state = "idle"
        self._mount_anim_kind = ""
        self._is_flying = False
        self._context_flags = set()
        self._last_landing_impact_speed = 0.0
        self._was_grounded = True
        self._block_pressed = False
        self._stealth_crouch = False
        self._was_wallrun = False
        self._py_grounded = True
        self._py_velocity_z = 0.0
        self._py_in_water = False
        self.combat = None
        self.app = SimpleNamespace(vehicle_mgr=None)
        self._run_pressed = False
        self._axes = (0.0, 0.0)

    def _get_action(self, action):
        if str(action) == "run":
            return bool(self._run_pressed)
        return False

    def _get_move_axes(self):
        return self._axes

    def _parkour_action_name(self):
        return ""


class PythonOnlyStateContextTests(unittest.TestCase):
    def test_context_infers_speed_from_input_axes_when_core_state_is_missing(self):
        actor = _PythonCtxDummy()
        actor._run_pressed = True
        actor._axes = (0.0, 1.0)
        ctx = actor._build_state_context()
        self.assertGreater(float(ctx.get("speed", 0.0) or 0.0), 8.5)
        self.assertTrue(bool(ctx.get("shift_pressed", False)))

    def test_context_uses_python_ground_and_vertical_flags(self):
        actor = _PythonCtxDummy()
        actor._py_grounded = False
        actor._py_velocity_z = -3.25
        ctx = actor._build_state_context()
        self.assertFalse(bool(ctx.get("on_ground", True)))
        self.assertLess(float(ctx.get("vertical_speed", 0.0) or 0.0), -3.0)

    def test_context_reports_in_water_from_python_fallback_flag(self):
        actor = _PythonCtxDummy()
        actor._py_in_water = True
        ctx = actor._build_state_context()
        self.assertTrue(bool(ctx.get("in_water", False)))


if __name__ == "__main__":
    unittest.main()
