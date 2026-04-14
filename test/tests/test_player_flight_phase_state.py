import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import types


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if "direct.showbase.ShowBaseGlobal" not in sys.modules:
    direct_mod = types.ModuleType("direct")
    showbase_mod = types.ModuleType("direct.showbase")
    showbase_global_mod = types.ModuleType("direct.showbase.ShowBaseGlobal")

    class _Clock:
        @staticmethod
        def getFrameTime():
            return 0.0

    showbase_global_mod.globalClock = _Clock()
    sys.modules["direct"] = direct_mod
    sys.modules["direct.showbase"] = showbase_mod
    sys.modules["direct.showbase.ShowBaseGlobal"] = showbase_global_mod

from entities.player_state_machine_mixin import PlayerStateMachineMixin


class FlightPhaseStateTests(unittest.TestCase):
    def test_compute_default_state_prefers_explicit_flight_takeoff_phase(self):
        dummy = SimpleNamespace()
        state = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": True,
                "flight_phase": "flight_takeoff",
                "speed": 0.0,
                "on_ground": False,
            },
        )
        self.assertEqual("flight_takeoff", state)

    def test_compute_default_state_prefers_hover_glide_and_dive_phases(self):
        dummy = SimpleNamespace()
        hover = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": True,
                "flight_phase": "flight_hover",
                "speed": 0.0,
                "on_ground": False,
            },
        )
        glide = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": True,
                "flight_phase": "flight_glide",
                "speed": 4.0,
                "on_ground": False,
            },
        )
        dive = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": True,
                "flight_phase": "flight_dive",
                "speed": 6.0,
                "on_ground": False,
            },
        )
        self.assertEqual("flight_hover", hover)
        self.assertEqual("flight_glide", glide)
        self.assertEqual("flight_dive", dive)

    def test_compute_default_state_prefers_flight_land_when_recently_touching_ground(self):
        dummy = SimpleNamespace()
        landing = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": False,
                "flight_landing": True,
                "speed": 0.0,
                "on_ground": True,
            },
        )
        self.assertEqual("flight_land", landing)

    def test_compute_default_state_uses_hover_instead_of_generic_flying_when_phase_is_unknown(self):
        dummy = SimpleNamespace()
        state = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": True,
                "flight_phase": "",
                "speed": 0.0,
                "on_ground": False,
            },
        )
        self.assertEqual("flight_hover", state)

    def test_compute_default_state_keeps_jump_chain_from_falling_back_to_walking(self):
        dummy = SimpleNamespace(_anim_state="jumping")
        state = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": False,
                "flight_landing": False,
                "speed": 4.0,
                "vertical_speed": 0.0,
                "on_ground": True,
                "in_water": False,
                "mounted": False,
            },
        )
        self.assertEqual("landing", state)

    def test_compute_default_state_keeps_recent_flight_from_snapping_to_idle(self):
        dummy = SimpleNamespace(_anim_state="flight_glide")
        state = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": False,
                "flight_landing": False,
                "flight_phase": "",
                "speed": 0.0,
                "on_ground": True,
                "in_water": False,
                "mounted": False,
            },
        )
        self.assertEqual("flight_land", state)

    def test_compute_default_state_does_not_rearm_jump_once_fall_has_started(self):
        dummy = SimpleNamespace(_anim_state="falling")
        state = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": False,
                "flight_landing": False,
                "speed": 3.0,
                "vertical_speed": 0.2,
                "on_ground": False,
                "in_water": False,
                "mounted": False,
            },
        )
        self.assertEqual("falling", state)

    def test_compute_default_state_keeps_falling_when_airborne_phase_cache_already_descends(self):
        dummy = SimpleNamespace(_anim_state="idle", _airborne_phase_cache="falling")
        state = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": False,
                "flight_landing": False,
                "speed": 3.0,
                "vertical_speed": 0.25,
                "on_ground": False,
                "in_water": False,
                "mounted": False,
            },
        )
        self.assertEqual("falling", state)
        self.assertEqual("falling", dummy._airborne_phase_cache)

    def test_compute_default_state_uses_falling_when_flight_mode_ends_midair(self):
        dummy = SimpleNamespace(_anim_state="flight_glide")
        state = PlayerStateMachineMixin._compute_default_state(
            dummy,
            {
                "is_flying": False,
                "flight_landing": False,
                "flight_phase": "",
                "speed": 4.0,
                "vertical_speed": 0.15,
                "on_ground": False,
                "in_water": False,
                "mounted": False,
            },
        )
        self.assertEqual("falling", state)


if __name__ == "__main__":
    unittest.main()
