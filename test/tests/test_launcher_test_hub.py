import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher_test_hub as hub


ROOT = Path(__file__).resolve().parents[2]


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
                    auto_start = os.environ.get("XBOT_AUTO_START")

        self.assertEqual(0, exit_code)
        self.assertEqual("prototype_v1", applied_profile)
        self.assertEqual("parkour", applied_location)
        self.assertIsNone(auto_start)
        run_app.assert_called_once()

    def test_script_profiles_include_asset_viewer(self):
        self.assertIn("asset_viewer", hub.SCRIPT_TESTS)
        script_args = hub.SCRIPT_TESTS["asset_viewer"]
        self.assertEqual("scripts/asset_animation_viewer.py", script_args[0])

    def test_runtime_profiles_include_mechanics(self):
        self.assertIn("mechanics", hub.RUNTIME_TESTS)
        row = hub.RUNTIME_TESTS["mechanics"]
        self.assertEqual("mechanics", row["profile"])
        self.assertEqual("training", row["location"])

    def test_main_runs_ultimate_sandbox_profile(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "argv", ["launcher_test_hub.py", "--test", "ultimate_sandbox"]):
                with patch("launcher_test_hub.run_app", return_value=0) as run_app:
                    exit_code = hub.main()
                    applied_profile = os.environ.get("XBOT_TEST_PROFILE")
                    applied_location = os.environ.get("XBOT_TEST_LOCATION")
                    auto_start = os.environ.get("XBOT_AUTO_START")

        self.assertEqual(0, exit_code)
        self.assertEqual("ultimate_sandbox", applied_profile)
        self.assertEqual("ultimate_sandbox", applied_location)
        self.assertIsNone(auto_start)
        run_app.assert_called_once()

    def test_main_can_enable_auto_start_toggle(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                sys,
                "argv",
                ["launcher_test_hub.py", "--test", "ultimate_sandbox", "--auto-start"],
            ):
                with patch("launcher_test_hub.run_app", return_value=0):
                    exit_code = hub.main()
                    auto_start = os.environ.get("XBOT_AUTO_START")
                    video_bot = os.environ.get("XBOT_VIDEO_BOT")

        self.assertEqual(0, exit_code)
        self.assertEqual("1", auto_start)
        self.assertIsNone(video_bot)

    def test_main_can_enable_video_bot_toggle(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                sys,
                "argv",
                ["launcher_test_hub.py", "--test", "ultimate_sandbox", "--video-bot"],
            ):
                with patch("launcher_test_hub.run_app", return_value=0):
                    exit_code = hub.main()
                    auto_start = os.environ.get("XBOT_AUTO_START")
                    video_bot = os.environ.get("XBOT_VIDEO_BOT")

        self.assertEqual(0, exit_code)
        self.assertIsNone(auto_start)
        self.assertEqual("1", video_bot)

    def test_main_preserves_explicit_video_bot_plan_env_when_video_bot_enabled(self):
        with patch.dict(
            os.environ,
            {
                "XBOT_VIDEO_BOT_PLAN": "anim_weapon_modes",
                "XBOT_TEST_SCENARIO": "movement_04",
                "XBOT_FORCE_AGGRO_MOBS": "1",
            },
            clear=True,
        ):
            with patch.object(
                sys,
                "argv",
                ["launcher_test_hub.py", "--test", "ultimate_sandbox", "--video-bot"],
            ):
                with patch("launcher_test_hub.run_app", return_value=0):
                    exit_code = hub.main()
                    remaining = {
                        "XBOT_VIDEO_BOT": os.environ.get("XBOT_VIDEO_BOT"),
                        "XBOT_VIDEO_BOT_PLAN": os.environ.get("XBOT_VIDEO_BOT_PLAN"),
                        "XBOT_TEST_SCENARIO": os.environ.get("XBOT_TEST_SCENARIO"),
                        "XBOT_FORCE_AGGRO_MOBS": os.environ.get("XBOT_FORCE_AGGRO_MOBS"),
                    }

        self.assertEqual(0, exit_code)
        self.assertEqual(
            {
                "XBOT_VIDEO_BOT": "1",
                "XBOT_VIDEO_BOT_PLAN": "anim_weapon_modes",
                "XBOT_TEST_SCENARIO": "movement_04",
                "XBOT_FORCE_AGGRO_MOBS": "1",
            },
            remaining,
        )

    def test_main_clears_stale_runtime_automation_env(self):
        with patch.dict(
            os.environ,
            {
                "XBOT_AUTO_START": "1",
                "XBOT_VIDEO_BOT": "1",
                "XBOT_VIDEO_BOT_PLAN": "ultimate_sandbox_probe",
                "XBOT_TEST_SCENARIO": "ultimate_sandbox_01",
                "XBOT_FORCE_AGGRO_MOBS": "1",
            },
            clear=True,
        ):
            with patch.object(sys, "argv", ["launcher_test_hub.py", "--test", "ultimate_sandbox"]):
                with patch("launcher_test_hub.run_app", return_value=0):
                    exit_code = hub.main()

                    remaining = {
                        "XBOT_AUTO_START": os.environ.get("XBOT_AUTO_START"),
                        "XBOT_VIDEO_BOT": os.environ.get("XBOT_VIDEO_BOT"),
                        "XBOT_VIDEO_BOT_PLAN": os.environ.get("XBOT_VIDEO_BOT_PLAN"),
                        "XBOT_TEST_SCENARIO": os.environ.get("XBOT_TEST_SCENARIO"),
                        "XBOT_FORCE_AGGRO_MOBS": os.environ.get("XBOT_FORCE_AGGRO_MOBS"),
                    }

        self.assertEqual(0, exit_code)
        self.assertEqual(
            {
                "XBOT_AUTO_START": None,
                "XBOT_VIDEO_BOT": None,
                "XBOT_VIDEO_BOT_PLAN": None,
                "XBOT_TEST_SCENARIO": None,
                "XBOT_FORCE_AGGRO_MOBS": None,
            },
            remaining,
        )

    def test_runtime_profiles_include_stealth_climb(self):
        self.assertIn("stealth_climb", hub.RUNTIME_TESTS)
        row = hub.RUNTIME_TESTS["stealth_climb"]
        self.assertEqual("stealth_climb", row["profile"])
        self.assertEqual("stealth_climb", row["location"])

    def test_main_handles_lost_stdin_by_falling_back_to_gui_menu(self):
        class _LostStdin:
            def isatty(self):
                raise RuntimeError("lost sys.stdin")

        with patch.object(sys, "argv", ["launcher_test_hub.py"]):
            with patch.object(sys, "stdin", _LostStdin()):
                with patch("launcher_test_hub._menu_choice_gui", return_value=""):
                    with patch("launcher_test_hub._menu_choice", side_effect=AssertionError("TTY menu should not be used")):
                        exit_code = hub.main()

        self.assertEqual(0, exit_code)

    def test_main_uses_gui_toggle_selection_when_no_cli_key_is_given(self):
        class _LostStdin:
            def isatty(self):
                raise RuntimeError("lost sys.stdin")

        selection = {
            "key": "ultimate_sandbox",
            "auto_start": True,
            "video_bot": True,
        }
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "argv", ["launcher_test_hub.py"]):
                with patch.object(sys, "stdin", _LostStdin()):
                    with patch("launcher_test_hub._menu_choice_gui", return_value=selection):
                        with patch("launcher_test_hub.run_app", return_value=0):
                            exit_code = hub.main()
                            auto_start = os.environ.get("XBOT_AUTO_START")
                            video_bot = os.environ.get("XBOT_VIDEO_BOT")
                            profile = os.environ.get("XBOT_TEST_PROFILE")

        self.assertEqual(0, exit_code)
        self.assertEqual("1", auto_start)
        self.assertEqual("1", video_bot)
        self.assertEqual("ultimate_sandbox", profile)


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

    def test_asset_viewer_pyw_points_to_asset_viewer_launcher(self):
        launcher = ROOT / "launcher_asset_viewer.pyw"
        self.assertTrue(launcher.exists())
        content = launcher.read_text(encoding="utf-8")
        self.assertIn("run_launcher_script", content)
        self.assertIn("launchers/tests/launcher_test_asset_viewer.py", content)


if __name__ == "__main__":
    unittest.main()
