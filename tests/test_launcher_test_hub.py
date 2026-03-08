import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher_test_hub as hub


ROOT = Path(__file__).resolve().parents[1]


class LauncherTestHubTests(unittest.TestCase):
    def test_runtime_profiles_include_prototype_v1(self):
        self.assertIn("prototype_v1", hub.RUNTIME_TESTS)
        profile = hub.RUNTIME_TESTS["prototype_v1"]
        self.assertEqual("prototype_v1", profile["profile"])
        self.assertEqual("parkour", profile["location"])

    def test_main_runs_prototype_v1_profile(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "argv", ["launcher_test_hub.py", "--test", "prototype_v1"]):
                with patch("launcher_test_hub.run_app", return_value=0) as run_app:
                    exit_code = hub.main()
                    applied_profile = os.environ.get("XBOT_TEST_PROFILE")
                    applied_location = os.environ.get("XBOT_TEST_LOCATION")

        self.assertEqual(0, exit_code)
        self.assertEqual("prototype_v1", applied_profile)
        self.assertEqual("parkour", applied_location)
        run_app.assert_called_once()


class LauncherSinglePywEntryTests(unittest.TestCase):
    def test_launcher_tests_pyw_points_to_test_hub(self):
        launcher = ROOT / "launcher_tests.pyw"
        self.assertTrue(launcher.exists())
        content = launcher.read_text(encoding="utf-8")
        self.assertIn("run_launcher_script", content)
        self.assertIn("launcher_test_hub.py", content)

    def test_no_legacy_test_pyw_launchers_remain(self):
        legacy_root = sorted(ROOT.glob("launcher_test_*.pyw"))
        legacy_nested = sorted((ROOT / "launchers" / "tests").glob("launcher_test_*.pyw"))
        self.assertEqual([], [p.name for p in legacy_root])
        self.assertEqual([], [p.name for p in legacy_nested])


if __name__ == "__main__":
    unittest.main()
