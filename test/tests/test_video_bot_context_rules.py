import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.video_bot_rules import (
    build_default_video_bot_context_rules,
    evaluate_video_bot_verdict_status,
    should_trigger_video_bot_context_rule,
)


class VideoBotContextRuleTests(unittest.TestCase):
    def test_default_ground_rules_include_unstick_recovery(self):
        rules = build_default_video_bot_context_rules("ground")
        rule_ids = {str(row.get("id", "")).strip().lower() for row in rules if isinstance(row, dict)}
        self.assertIn("unstick_jump", rule_ids)
        self.assertIn("unstick_strafe", rule_ids)

    def test_combat_plans_gain_enemy_reaction_rules(self):
        rules = build_default_video_bot_context_rules("combat_magic_probe")
        rule_ids = {str(row.get("id", "")).strip().lower() for row in rules if isinstance(row, dict)}
        self.assertIn("enemy_close_block", rule_ids)
        self.assertIn("enemy_close_attack", rule_ids)
        self.assertIn("enemy_midrange_spell", rule_ids)

    def test_flight_and_parkour_plans_get_domain_specific_recovery_rules(self):
        flight_rules = build_default_video_bot_context_rules("flight")
        parkour_rules = build_default_video_bot_context_rules("parkour")
        flight_ids = {str(row.get("id", "")).strip().lower() for row in flight_rules if isinstance(row, dict)}
        parkour_ids = {str(row.get("id", "")).strip().lower() for row in parkour_rules if isinstance(row, dict)}
        self.assertIn("flight_recover_lift", flight_ids)
        self.assertIn("unstick_jump", parkour_ids)
        self.assertIn("unstick_strafe", parkour_ids)

    def test_rule_matches_stuck_movement_context(self):
        rule = {
            "when": {
                "movement_requested": True,
                "stuck_for_sec_gte": 0.8,
                "is_flying": False,
            },
            "cooldown_sec": 1.2,
        }
        context = {
            "movement_requested": True,
            "stuck_for_sec": 1.05,
            "is_flying": False,
            "in_water": False,
            "enemy_distance": math.inf,
            "active_location": "Ultimate Sandbox",
        }

        self.assertTrue(
            should_trigger_video_bot_context_rule(
                rule,
                context,
                now_sec=4.0,
                last_trigger_at=1.0,
                trigger_count=0,
            )
        )

    def test_rule_respects_cooldown_and_enemy_distance_predicates(self):
        rule = {
            "when": {
                "enemy_distance_lte": 3.0,
                "movement_requested": False,
            },
            "cooldown_sec": 1.5,
        }
        context = {
            "movement_requested": False,
            "stuck_for_sec": 0.0,
            "is_flying": False,
            "in_water": False,
            "enemy_distance": 2.4,
            "active_location": "Dragon Arena",
        }

        self.assertFalse(
            should_trigger_video_bot_context_rule(
                rule,
                context,
                now_sec=5.0,
                last_trigger_at=4.2,
                trigger_count=0,
            )
        )

    def test_rule_supports_npc_distance_predicates_for_dialogue_probes(self):
        rule = {
            "when": {
                "npc_distance_lte": 2.5,
                "movement_requested": False,
            },
            "cooldown_sec": 0.8,
        }
        context = {
            "movement_requested": False,
            "stuck_for_sec": 0.0,
            "is_flying": False,
            "in_water": False,
            "enemy_distance": math.inf,
            "npc_distance": 1.8,
            "active_location": "Castle Interior",
        }

        self.assertTrue(
            should_trigger_video_bot_context_rule(
                rule,
                context,
                now_sec=3.0,
                last_trigger_at=1.0,
                trigger_count=0,
            )
        )

    def test_rule_supports_nested_all_any_not_conditions(self):
        rule = {
            "when": {
                "all_of": [
                    {"movement_requested": True},
                    {
                        "any_of": [
                            {"enemy_distance_lte": 3.0},
                            {"active_location_contains": "sandbox"},
                        ]
                    },
                    {"not": {"in_water": True}},
                ]
            },
        }
        context = {
            "movement_requested": True,
            "stuck_for_sec": 0.2,
            "is_flying": False,
            "in_water": False,
            "enemy_distance": 7.5,
            "active_location": "Ultimate Sandbox",
            "player_z_min": 0.2,
            "plan_cycle_count": 0,
            "plan_completed": False,
            "executed_actions": [],
            "executed_event_types": [],
            "teleport_targets": [],
            "visited_locations": ["Ultimate Sandbox"],
            "triggered_rule_ids": [],
        }

        self.assertTrue(
            should_trigger_video_bot_context_rule(
                rule,
                context,
                now_sec=2.0,
                last_trigger_at=None,
                trigger_count=0,
            )
        )

    def test_rule_rejects_nested_not_condition_when_inner_predicate_matches(self):
        rule = {
            "when": {
                "not": {"in_water": True},
            },
        }
        context = {
            "movement_requested": False,
            "stuck_for_sec": 0.0,
            "is_flying": False,
            "in_water": True,
            "enemy_distance": math.inf,
            "active_location": "Training Grounds",
            "player_z_min": -0.4,
            "plan_cycle_count": 0,
            "plan_completed": False,
            "executed_actions": [],
            "executed_event_types": [],
            "teleport_targets": [],
            "visited_locations": ["Training Grounds"],
            "triggered_rule_ids": [],
        }

        self.assertFalse(
            should_trigger_video_bot_context_rule(
                rule,
                context,
                now_sec=1.0,
                last_trigger_at=None,
                trigger_count=0,
            )
        )

    def test_verdict_prefers_fail_if_over_success_if_and_supports_history_predicates(self):
        context = {
            "movement_requested": False,
            "stuck_for_sec": 0.0,
            "is_flying": False,
            "in_water": False,
            "enemy_distance": 4.0,
            "active_location": "Ultimate Sandbox",
            "player_y": 8.6,
            "player_z": 7.2,
            "player_z_min": -2.1,
            "player_z_max": 12.4,
            "plan_cycle_count": 1,
            "plan_completed": True,
            "executed_actions": ["interact", "jump"],
            "executed_event_types": ["teleport", "camera_shot", "tap"],
            "teleport_targets": ["sandbox_story_book_approach"],
            "visited_locations": ["Ultimate Sandbox"],
            "triggered_rule_ids": ["sandbox_story_focus"],
        }
        success_if = {
            "all_of": [
                {"plan_completed": True},
                {"teleport_target_contains": "sandbox_story_book_approach"},
                {"executed_action_contains": "interact"},
            ]
        }
        fail_if = {"player_z_min_lte": -1.5}

        status, reason = evaluate_video_bot_verdict_status(
            success_if=success_if,
            fail_if=fail_if,
            context=context,
        )

        self.assertEqual("failure", status)
        self.assertEqual("fail_if", reason)

    def test_verdict_can_report_success_from_plan_completion_and_history(self):
        context = {
            "movement_requested": False,
            "stuck_for_sec": 0.0,
            "is_flying": False,
            "in_water": False,
            "enemy_distance": 4.0,
            "active_location": "Ultimate Sandbox",
            "player_y": 8.6,
            "player_z": 7.2,
            "player_z_min": 0.3,
            "player_z_max": 12.4,
            "plan_cycle_count": 1,
            "plan_completed": True,
            "executed_actions": ["interact", "jump"],
            "executed_event_types": ["teleport", "camera_shot", "tap"],
            "teleport_targets": ["sandbox_story_book_approach"],
            "visited_locations": ["Ultimate Sandbox"],
            "triggered_rule_ids": ["sandbox_story_focus"],
        }
        success_if = {
            "all_of": [
                {"plan_completed": True},
                {"teleport_target_contains": "sandbox_story_book_approach"},
                {"executed_action_contains": "interact"},
                {"visited_location_contains": "sandbox"},
            ]
        }

        status, reason = evaluate_video_bot_verdict_status(
            success_if=success_if,
            fail_if=None,
            context=context,
        )

        self.assertEqual("success", status)
        self.assertEqual("success_if", reason)


if __name__ == "__main__":
    unittest.main()
