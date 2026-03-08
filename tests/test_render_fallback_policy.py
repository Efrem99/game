import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import should_enable_world_shader


class RenderFallbackPolicyTests(unittest.TestCase):
    def test_world_shader_disabled_without_core_by_default(self):
        self.assertFalse(should_enable_world_shader(False, env={}))

    def test_world_shader_can_be_forced_without_core(self):
        self.assertTrue(should_enable_world_shader(False, env={"XBOT_FORCE_WORLD_SHADER": "1"}))

    def test_world_shader_can_be_explicitly_disabled_with_core(self):
        self.assertFalse(should_enable_world_shader(True, env={"XBOT_DISABLE_WORLD_SHADER": "1"}))


if __name__ == "__main__":
    unittest.main()
