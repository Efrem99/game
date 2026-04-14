import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_import(module_name: str) -> subprocess.CompletedProcess[str]:
    script = (
        "import sys\n"
        "sys.path.insert(0, 'src')\n"
        f"import {module_name}\n"
        "print('ok')\n"
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


class CoreRuntimeImportOrderTests(unittest.TestCase):
    def test_npc_manager_imports_cleanly_with_compiled_core_present(self):
        result = _run_import("managers.npc_manager")
        self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)
        self.assertIn("ok", result.stdout)

    def test_entities_player_imports_cleanly_with_compiled_core_present(self):
        result = _run_import("entities.player")
        self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)
        self.assertIn("ok", result.stdout)

    def test_entities_boss_manager_imports_cleanly_with_compiled_core_present(self):
        result = _run_import("entities.boss_manager")
        self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)
        self.assertIn("ok", result.stdout)

    def test_vehicle_manager_imports_cleanly_with_compiled_core_present(self):
        result = _run_import("managers.vehicle_manager")
        self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)
        self.assertIn("ok", result.stdout)

    def test_sharuan_world_imports_cleanly_with_compiled_core_present(self):
        result = _run_import("world.sharuan_world")
        self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)
        self.assertIn("ok", result.stdout)

    def test_app_imports_cleanly_with_compiled_core_present(self):
        result = _run_import("app")
        self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)
        self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
