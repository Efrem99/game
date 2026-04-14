import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_movement_mixin import PlayerMovementMixin
from entities.player_state_machine_mixin import PlayerStateMachineMixin


class _FlightPhaseDummy:
    _resolve_flight_phase = PlayerStateMachineMixin._resolve_flight_phase

    def __init__(self, anim_state=""):
        self._anim_state = str(anim_state or "")
        self._flight_phase_cache = ""
        self._flight_takeoff_until = 0.0


class _DriveAnimationsDummy:
    _drive_animations = PlayerMovementMixin._drive_animations

    def __init__(self):
        self.actor = SimpleNamespace(
            loop=lambda *_args, **_kwargs: None,
            getCurrentAnim=lambda: "run",
        )
        self.app = SimpleNamespace(vehicle_mgr=None)
        self.cs = SimpleNamespace(grounded=True)
        self._landing_anim_hold = 0.24
        self._is_flying = False
        self._anim_state = "running"
        self._anim_clip = "run"
        self._anim_blend_transition = None
        self._anim_no_clip_time = 0.0
        self._anim_dropout_logged = None
        self.set_anim_calls = []
        self.blend_ticks = []
        self.fsm_ticks = 0

    def _sync_parkour_runtime_hints(self):
        return None

    def _run_animation_state_machine(self):
        self.fsm_ticks += 1

    def _set_anim(self, state_name, loop=True, **_kwargs):
        self.set_anim_calls.append((str(state_name or ""), bool(loop)))
        return True

    def _tick_anim_blend(self, dt):
        self.blend_ticks.append(float(dt or 0.0))
        return None


class _FlightRuntimeRuleDummy:
    _apply_runtime_rules = PlayerStateMachineMixin._apply_runtime_rules
    _sort_rules = PlayerStateMachineMixin._sort_rules
    _rule_priority = PlayerStateMachineMixin._rule_priority
    _transition_from_matches = PlayerStateMachineMixin._transition_from_matches
    _eval_transition_condition = PlayerStateMachineMixin._eval_transition_condition

    def __init__(self):
        self._state_rules = []
        self.entered_states = []

    def _transition_allowed(self, _current_state, _target_state, trigger=None, force=False):
        return True

    def _enter_state(self, state_name):
        self.entered_states.append(str(state_name or ""))
        return True


class PlayerLandingAndFlightGuardsTests(unittest.TestCase):
    def test_drive_animations_does_not_reapply_landing_over_resumed_locomotion(self):
        dummy = _DriveAnimationsDummy()

        dummy._drive_animations(0.05)

        self.assertEqual(1, dummy.fsm_ticks)
        self.assertEqual([], dummy.set_anim_calls)
        self.assertAlmostEqual(0.24, dummy._landing_anim_hold, places=3)

    def test_resolve_flight_phase_keeps_glide_near_threshold_when_already_gliding(self):
        dummy = _FlightPhaseDummy(anim_state="flight_glide")

        resolved = dummy._resolve_flight_phase(
            {
                "is_flying": True,
                "speed": 2.2,
                "vertical_speed": 0.08,
            }
        )

        self.assertEqual("flight_glide", resolved)

    def test_resolve_flight_phase_keeps_dive_near_threshold_when_already_diving(self):
        dummy = _FlightPhaseDummy(anim_state="flight_dive")

        resolved = dummy._resolve_flight_phase(
            {
                "is_flying": True,
                "speed": 1.1,
                "vertical_speed": -0.72,
            }
        )

        self.assertEqual("flight_dive", resolved)

    def test_resolve_flight_phase_keeps_hover_near_threshold_when_already_hovering(self):
        dummy = _FlightPhaseDummy(anim_state="flight_hover")

        resolved = dummy._resolve_flight_phase(
            {
                "is_flying": True,
                "speed": 2.9,
                "vertical_speed": 0.06,
            }
        )

        self.assertEqual("flight_hover", resolved)

    def test_runtime_flight_rule_uses_explicit_flight_phase_instead_of_generic_flying(self):
        dummy = _FlightRuntimeRuleDummy()
        dummy._state_rules = [
            {
                "name": "flight_context",
                "from": ["*"],
                "to": "flying",
                "condition": "is_flying && !mounted",
                "priority": 22,
            }
        ]

        applied = dummy._apply_runtime_rules(
            "flight_glide",
            {
                "is_flying": True,
                "mounted": False,
                "flight_phase": "flight_glide",
            },
            [],
        )

        self.assertTrue(applied)
        self.assertEqual(["flight_glide"], dummy.entered_states)


if __name__ == "__main__":
    unittest.main()
