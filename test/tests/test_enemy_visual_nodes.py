import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import should_apply_enemy_visual_defaults


class EnemyVisualNodeTests(unittest.TestCase):
    def test_telegraph_node_skips_visual_defaults(self):
        self.assertFalse(should_apply_enemy_visual_defaults("telegraph"))

    def test_regular_nodes_keep_visual_defaults(self):
        self.assertTrue(should_apply_enemy_visual_defaults("model"))
        self.assertTrue(should_apply_enemy_visual_defaults("core"))


if __name__ == "__main__":
    unittest.main()
