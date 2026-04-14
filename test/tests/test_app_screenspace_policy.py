import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _ScreenspacePolicyDummy:
    _should_enable_screenspace_pass = XBotApp._should_enable_screenspace_pass

    def __init__(
        self,
        advanced_rendering=True,
        skip_screenspace=False,
        video_bot=False,
        test_profile="",
        test_location="",
        test_scenario="",
    ):
        self._advanced_rendering = bool(advanced_rendering)
        self._debug_skip_screenspace = bool(skip_screenspace)
        self._video_bot_enabled = bool(video_bot)
        self._test_profile = str(test_profile)
        self._test_location_raw = str(test_location)
        self._test_scenario_raw = str(test_scenario)


class AppScreenspacePolicyTests(unittest.TestCase):
    def test_high_quality_enables_screenspace_when_rendering_is_advanced(self):
        app = _ScreenspacePolicyDummy(advanced_rendering=True, skip_screenspace=False)

        self.assertTrue(app._should_enable_screenspace_pass("high"))

    def test_explicit_debug_flag_can_disable_screenspace_pass(self):
        app = _ScreenspacePolicyDummy(advanced_rendering=True, skip_screenspace=True)

        self.assertFalse(app._should_enable_screenspace_pass("high"))

    def test_runtime_test_boot_disables_screenspace_even_on_high_quality(self):
        app = _ScreenspacePolicyDummy(advanced_rendering=True, test_scenario="ultimate_sandbox_01")

        self.assertFalse(app._should_enable_screenspace_pass("high"))


if __name__ == "__main__":
    unittest.main()
