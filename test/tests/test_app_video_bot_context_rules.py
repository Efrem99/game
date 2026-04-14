import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _VideoBotRuleDummy:
    _video_bot_register_context_rule = XBotApp._video_bot_register_context_rule
    _video_bot_apply_context_rules = XBotApp._video_bot_apply_context_rules

    def __init__(self):
        self._video_bot_context_rules = []
        self._video_bot_context_rule_state = {}
        self._fired = []

    def _video_bot_run_event(self, event_row, now_sec):
        self._fired.append((float(now_sec), dict(event_row)))


class AppVideoBotContextRuleTests(unittest.TestCase):
    def test_register_context_rule_stores_rule_row(self):
        app = _VideoBotRuleDummy()

        app._video_bot_register_context_rule(
            {
                "type": "context_rule",
                "id": "unstick_jump",
                "when": {"movement_requested": True, "stuck_for_sec_gte": 0.8},
                "then": {"type": "tap", "action": "jump"},
                "cooldown_sec": 1.0,
            }
        )

        self.assertEqual(1, len(app._video_bot_context_rules))
        self.assertEqual("unstick_jump", app._video_bot_context_rules[0]["id"])

    def test_apply_context_rules_fires_then_event_once_per_cooldown(self):
        app = _VideoBotRuleDummy()
        app._video_bot_register_context_rule(
            {
                "type": "context_rule",
                "id": "unstick_jump",
                "when": {"movement_requested": True, "stuck_for_sec_gte": 0.8},
                "then": {"type": "tap", "action": "jump"},
                "cooldown_sec": 1.0,
            }
        )
        context = {
            "movement_requested": True,
            "stuck_for_sec": 1.2,
            "is_flying": False,
            "in_water": False,
            "enemy_distance": 999.0,
            "active_location": "Ultimate Sandbox",
        }

        app._video_bot_apply_context_rules(now_sec=2.0, context=context)
        app._video_bot_apply_context_rules(now_sec=2.4, context=context)
        app._video_bot_apply_context_rules(now_sec=3.2, context=context)

        self.assertEqual(2, len(app._fired))
        self.assertEqual("jump", app._fired[0][1]["action"])
        self.assertEqual("jump", app._fired[1][1]["action"])


if __name__ == "__main__":
    unittest.main()
