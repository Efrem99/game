import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _VideoBotSetupDummy:
    _setup_video_bot = XBotApp._setup_video_bot

    def __init__(self, plan_raw="ground", plan_json_raw=""):
        self._video_bot_enabled = True
        self._video_bot_plan_raw = plan_raw
        self._video_bot_plan_json_raw = plan_json_raw
        self._video_bot_plan_name = "ground"
        self._video_bot_plan = []
        self._video_bot_elapsed = 0.0
        self._video_bot_event_idx = 0
        self._video_bot_hold_actions = {}
        self._video_bot_forced_flags = {}
        self._video_bot_warned_actions = set()
        self._video_bot_done = False
        self._video_bot_bindings = {}
        self._video_bot_cursor_pos = (0.0, 0.0)
        self._video_bot_cursor_target = (0.0, 0.0)
        self._video_bot_cursor_visible = False
        self._video_bot_visibility_refresh_at = 0.0
        self._video_bot_cursor_visible_until = 0.0
        self._video_bot_cursor_click_until = 0.0
        self._video_bot_started = False
        self._video_bot_start_ready_at = 0.0
        self._video_bot_last_real_time = 0.0
        self._video_bot_cycle_count = 0
        self.player = None


class AppVideoBotSetupTests(unittest.TestCase):
    def test_setup_video_bot_prefers_custom_plan_json(self):
        app = _VideoBotSetupDummy(
            plan_raw="ground",
            plan_json_raw="""
            [
              {"at": 0.0, "type": "teleport", "target": "sandbox_stairs_approach"},
              {"at": 0.2, "type": "tap", "action": "jump"}
            ]
            """,
        )

        app._setup_video_bot()

        self.assertEqual("custom", app._video_bot_plan_name)
        self.assertEqual(2, len(app._video_bot_plan))
        self.assertEqual("sandbox_stairs_approach", app._video_bot_plan[0]["target"])


if __name__ == "__main__":
    unittest.main()
