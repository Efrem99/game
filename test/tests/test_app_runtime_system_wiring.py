import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _MagicVfxStub:
    def __init__(self):
        self.update_calls = []

    def update(self, dt):
        self.update_calls.append(float(dt))


class AppRuntimeSystemWiringTests(unittest.TestCase):
    def test_update_magic_vfx_runtime_calls_magic_vfx_system(self):
        app = types.SimpleNamespace(magic_vfx=_MagicVfxStub())

        self.assertTrue(hasattr(XBotApp, "_update_magic_vfx_runtime"))
        XBotApp._update_magic_vfx_runtime(app, 0.25)

        self.assertEqual([0.25], app.magic_vfx.update_calls)

    def test_runtime_trace_stage_logs_only_when_budget_and_video_bot_are_active(self):
        app = types.SimpleNamespace(
            _video_bot_enabled=True,
            _runtime_trace_frames_left=3,
            _runtime_trace_frame_index=2,
        )

        with patch("app.logger.info") as log_info:
            traced = XBotApp._trace_runtime_update_stage(app, "post_player")

        self.assertTrue(traced)
        log_info.assert_called_once()
        self.assertIn("frame=2", log_info.call_args[0][0])
        self.assertIn("stage=post_player", log_info.call_args[0][0])

    def test_runtime_trace_stage_skips_when_disabled(self):
        app = types.SimpleNamespace(
            _video_bot_enabled=False,
            _runtime_trace_frames_left=3,
            _runtime_trace_frame_index=1,
        )

        with patch("app.logger.info") as log_info:
            traced = XBotApp._trace_runtime_update_stage(app, "post_player")

        self.assertFalse(traced)
        log_info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
