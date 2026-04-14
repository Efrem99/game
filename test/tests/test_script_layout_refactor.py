import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ScriptLayoutRefactorTests(unittest.TestCase):
    def test_animation_scripts_have_themed_homes_and_root_wrappers(self):
        themed_report = ROOT / "scripts" / "animation" / "player_anim_runtime_report.py"
        themed_manifest = ROOT / "scripts" / "animation" / "validate_player_manifest.py"
        root_report = ROOT / "scripts" / "player_anim_runtime_report.py"
        root_manifest = ROOT / "scripts" / "validate_player_manifest.py"

        self.assertTrue(themed_report.exists())
        self.assertTrue(themed_manifest.exists())
        self.assertIn(
            "from scripts.animation.player_anim_runtime_report import main",
            root_report.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "from scripts.animation.validate_player_manifest import main",
            root_manifest.read_text(encoding="utf-8"),
        )

    def test_data_backend_script_has_themed_home_and_root_wrapper(self):
        themed_builder = ROOT / "scripts" / "data" / "build_data_backend.py"
        root_builder = ROOT / "scripts" / "build_data_backend.py"

        self.assertTrue(themed_builder.exists())
        self.assertIn(
            "from scripts.data.build_data_backend import main",
            root_builder.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
