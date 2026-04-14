import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_game_core.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_game_core_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BuildGameCoreTests(unittest.TestCase):
    def test_project_root_from_script_preserves_invoked_ascii_path(self):
        module = _load_module()

        root = module.project_root_from_script(
            Path(r"C:\xampp\htdocs\king-wizard\scripts\build_game_core.py")
        )

        self.assertEqual(Path(r"C:\xampp\htdocs\king-wizard"), root)

    def test_visual_studio_generators_include_vs2026_when_vs18_is_installed(self):
        module = _load_module()
        instances = [
            {
                "installationVersion": "18.2.11415.280",
                "installationPath": r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools",
                "displayName": "Visual Studio Build Tools 2026",
            }
        ]

        generators = module.visual_studio_generators(instances)

        self.assertTrue(generators)
        self.assertEqual("Visual Studio 18 2026", generators[0][1][1])

    def test_prefers_newer_release_module_over_stale_root_copy(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale_root = root / "game_core.pyd"
            release_dir = root / "Release"
            release_dir.mkdir()
            fresh_release = release_dir / "game_core.pyd"
            stale_root.write_bytes(b"old")
            fresh_release.write_bytes(b"new")

            stale_time = 1_700_000_000
            fresh_time = stale_time + 60
            import os

            os.utime(stale_root, (stale_time, stale_time))
            os.utime(fresh_release, (fresh_time, fresh_time))

            chosen = module.built_module_source(root=root, configured_build_dir=None)

            self.assertEqual(fresh_release, chosen)


if __name__ == "__main__":
    unittest.main()
