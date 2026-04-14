import sys
import tempfile
import unittest
from pathlib import Path

import msgpack


ROOT = Path(__file__).resolve().parents[2]
VIDEO_SCENARIO_DIR = ROOT / "test" / "tests" / "video_scenarios"
if str(VIDEO_SCENARIO_DIR) not in sys.path:
    sys.path.insert(0, str(VIDEO_SCENARIO_DIR))

from check_video_bot_verdict import validate_video_bot_verdict


class CheckVideoBotVerdictRuntimeTests(unittest.TestCase):
    def test_validate_video_bot_verdict_reads_msgpack_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            verdict_path = project_root / "logs" / "video_bot_verdict.msgpack"
            verdict_path.parent.mkdir(parents=True, exist_ok=True)
            verdict_path.write_bytes(
                msgpack.packb(
                    {
                        "status": "success",
                        "reason": "success_if",
                        "plan_name": "ultimate_sandbox_probe",
                        "context": {
                            "plan_completed": True,
                            "executed_actions": ["interact"],
                            "teleport_targets": ["sandbox_story_book_approach"],
                        },
                    },
                    use_bin_type=True,
                )
            )

            ok, message = validate_video_bot_verdict(
                scenario_name="ultimate-sandbox-collider-probe",
                scenario_cfg={
                    "game_env": {
                        "XBOT_VIDEO_BOT_SUCCESS_IF": "{\"all_of\":[{\"plan_completed\":true}]}",
                    }
                },
                project_root=project_root,
            )

            self.assertTrue(ok)
            self.assertIn("verdict ok", message)


if __name__ == "__main__":
    unittest.main()
