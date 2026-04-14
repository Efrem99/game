import json
import sys
import tempfile
import unittest
from pathlib import Path

import msgpack

ROOT = Path(__file__).resolve().parents[1]
VIDEO_SCENARIO_DIR = ROOT / "test" / "tests" / "video_scenarios"
if str(VIDEO_SCENARIO_DIR) not in sys.path:
    sys.path.insert(0, str(VIDEO_SCENARIO_DIR))

from check_video_bot_verdict import validate_video_bot_verdict


class VideoBotVerdictCheckerTests(unittest.TestCase):
    def test_checker_is_noop_when_scenario_has_no_verdict_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ok, message = validate_video_bot_verdict(
                scenario_name="plain",
                scenario_cfg={"game_env": {}},
                project_root=root,
            )
            self.assertTrue(ok)
            self.assertIn("no verdict rules", message.lower())

    def test_checker_requires_success_when_success_rule_is_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            (logs / "video_bot_verdict.msgpack").write_bytes(
                msgpack.packb({"status": "pending", "reason": "", "context": {}}, use_bin_type=True),
            )

            ok, message = validate_video_bot_verdict(
                scenario_name="sandbox",
                scenario_cfg={
                    "game_env": {
                        "XBOT_VIDEO_BOT_SUCCESS_IF": json.dumps({"plan_completed": True}),
                    }
                },
                project_root=root,
            )
            self.assertFalse(ok)
            self.assertIn("expected success", message.lower())

    def test_checker_fails_when_runtime_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            (logs / "video_bot_verdict.msgpack").write_bytes(
                msgpack.packb({"status": "failure", "reason": "fail_if", "context": {}}, use_bin_type=True),
            )

            ok, message = validate_video_bot_verdict(
                scenario_name="sandbox",
                scenario_cfg={
                    "game_env": {
                        "XBOT_VIDEO_BOT_FAIL_IF": json.dumps({"player_z_min_lte": -1.0}),
                    }
                },
                project_root=root,
            )
            self.assertFalse(ok)
            self.assertIn("reported failure", message.lower())
