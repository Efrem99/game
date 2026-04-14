import json
import sys
import tempfile
import unittest
from pathlib import Path

import msgpack


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.video_bot_verdict import VideoBotVerdictTracker, parse_video_bot_rule


class VideoBotVerdictRuntimeTests(unittest.TestCase):
    def test_parse_video_bot_rule_accepts_loose_powershell_object_literal(self):
        payload = parse_video_bot_rule(
            "{all_of:[{plan_completed:true},{teleport_target_contains:sandbox_story_book_approach},{executed_action_contains:interact}]}"
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(
            "sandbox_story_book_approach",
            payload["all_of"][1]["teleport_target_contains"],
        )
        self.assertEqual("interact", payload["all_of"][2]["executed_action_contains"])

    def test_tracker_persists_success_with_plan_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            verdict_path = Path(tmp) / "video_bot_verdict.msgpack"
            tracker = VideoBotVerdictTracker(
                verdict_path=verdict_path,
                plan_name="ultimate_sandbox_probe",
                success_if={
                    "all_of": [
                        {"plan_completed": True},
                        {"executed_action_contains": "interact"},
                        {"teleport_target_contains": "sandbox_story_book_approach"},
                    ]
                },
            )

            tracker.note_event({"type": "tap", "action": "interact"})
            tracker.note_event({"type": "teleport", "target": "sandbox_story_book_approach"})
            tracker.note_context({"active_location": "Ultimate Sandbox", "player_z": 7.2})

            status = tracker.update(
                {
                    "movement_requested": False,
                    "stuck_for_sec": 0.0,
                    "is_flying": False,
                    "in_water": False,
                    "enemy_distance": 4.0,
                    "npc_distance": 2.0,
                    "active_location": "Ultimate Sandbox",
                    "player_y": 8.6,
                    "player_z": 7.2,
                },
                plan_completed=True,
                plan_cycle_count=1,
            )

            self.assertEqual("success", status)
            payload = msgpack.unpackb(verdict_path.read_bytes(), raw=False)
            self.assertEqual("success", payload["status"])
            self.assertEqual("success_if", payload["reason"])
            self.assertIn("interact", payload["context"]["executed_actions"])
            self.assertIn("sandbox_story_book_approach", payload["context"]["teleport_targets"])

    def test_tracker_persists_failure_when_fail_rule_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            verdict_path = Path(tmp) / "video_bot_verdict.msgpack"
            tracker = VideoBotVerdictTracker(
                verdict_path=verdict_path,
                plan_name="ultimate_sandbox_probe",
                success_if={"executed_action_contains": "interact"},
                fail_if={"player_z_min_lte": -1.0},
            )

            tracker.note_event({"type": "tap", "action": "interact"})
            tracker.note_context({"active_location": "Ultimate Sandbox", "player_z": -2.4})

            status = tracker.update(
                {
                    "movement_requested": False,
                    "stuck_for_sec": 0.0,
                    "is_flying": False,
                    "in_water": False,
                    "enemy_distance": 4.0,
                    "npc_distance": 2.0,
                    "active_location": "Ultimate Sandbox",
                    "player_y": 8.6,
                    "player_z": -2.4,
                },
                plan_completed=False,
                plan_cycle_count=0,
            )

            self.assertEqual("failure", status)
            payload = msgpack.unpackb(verdict_path.read_bytes(), raw=False)
            self.assertEqual("failure", payload["status"])
            self.assertEqual("fail_if", payload["reason"])
            self.assertLessEqual(payload["context"]["player_z_min"], -2.4)


if __name__ == "__main__":
    unittest.main()
