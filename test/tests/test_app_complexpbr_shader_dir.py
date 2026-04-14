import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _ComplexPbrShaderDirDummy:
    _complexpbr_shader_dir = XBotApp._complexpbr_shader_dir


class AppComplexPbrShaderDirTests(unittest.TestCase):
    def test_complexpbr_uses_canonical_shader_dir_by_default(self):
        app = _ComplexPbrShaderDirDummy()

        self.assertEqual("shaders/", app._complexpbr_shader_dir())


if __name__ == "__main__":
    unittest.main()
