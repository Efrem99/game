import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import entities.boss_manager as boss_module
from entities.boss_manager import EnemyUnit


class _DummyAnimatedActor:
    def __init__(self):
        self.shader_off_calls = 0
        self.color_scale_calls = 0
        self.two_sided_calls = 0

    def getAnimNames(self):
        return ["idle"]

    def loop(self, _clip):
        return None

    def play(self, _clip):
        return None

    def setShaderOff(self, *_args, **_kwargs):
        self.shader_off_calls += 1

    def setColorScale(self, *_args, **_kwargs):
        self.color_scale_calls += 1

    def setTwoSided(self, *_args, **_kwargs):
        self.two_sided_calls += 1


class _DummyStaticNode:
    def __init__(self):
        self.shader_off_calls = 0
        self.color_scale_calls = 0
        self.two_sided_calls = 0

    def setShaderOff(self, *_args, **_kwargs):
        self.shader_off_calls += 1

    def setColorScale(self, *_args, **_kwargs):
        self.color_scale_calls += 1

    def setTwoSided(self, *_args, **_kwargs):
        self.two_sided_calls += 1


class EnemyNonCoreVisualFallbackTests(unittest.TestCase):
    def test_animated_enemy_keeps_skinning_path(self):
        original = boss_module.HAS_CORE
        boss_module.HAS_CORE = False
        try:
            unit = EnemyUnit.__new__(EnemyUnit)
            actor = _DummyAnimatedActor()
            EnemyUnit._apply_python_only_visual_fallback(unit, actor, debug_label="test_actor")
            self.assertEqual(0, actor.shader_off_calls)
            self.assertGreater(actor.color_scale_calls, 0)
            self.assertGreater(actor.two_sided_calls, 0)
        finally:
            boss_module.HAS_CORE = original

    def test_static_enemy_node_uses_shader_off_fallback(self):
        original = boss_module.HAS_CORE
        boss_module.HAS_CORE = False
        try:
            unit = EnemyUnit.__new__(EnemyUnit)
            node = _DummyStaticNode()
            EnemyUnit._apply_python_only_visual_fallback(unit, node, debug_label="test_node")
            self.assertEqual(1, node.shader_off_calls)
            self.assertGreater(node.color_scale_calls, 0)
            self.assertGreater(node.two_sided_calls, 0)
        finally:
            boss_module.HAS_CORE = original


if __name__ == "__main__":
    unittest.main()
