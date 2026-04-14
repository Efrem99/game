import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import entities.player as player_module
from entities.player import Player


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

    def setShaderOff(self, *_args, **_kwargs):
        self.shader_off_calls += 1


class _DummyPlayer:
    def __init__(self, actor):
        self.actor = actor


class PlayerNonCoreVisualFallbackTests(unittest.TestCase):
    def test_non_core_fallback_keeps_shader_enabled_for_animated_actor(self):
        original = player_module.HAS_CORE
        player_module.HAS_CORE = False
        try:
            actor = _DummyAnimatedActor()
            dummy = _DummyPlayer(actor)
            Player._apply_non_core_actor_visual_fallback(dummy)
            self.assertEqual(0, actor.shader_off_calls)
            self.assertEqual(0, actor.color_scale_calls)
            self.assertGreater(actor.two_sided_calls, 0)
        finally:
            player_module.HAS_CORE = original

    def test_non_core_fallback_can_disable_shader_for_static_nodes(self):
        original = player_module.HAS_CORE
        player_module.HAS_CORE = False
        try:
            node = _DummyStaticNode()
            dummy = _DummyPlayer(node)
            Player._apply_non_core_actor_visual_fallback(dummy)
            self.assertEqual(1, node.shader_off_calls)
        finally:
            player_module.HAS_CORE = original


if __name__ == "__main__":
    unittest.main()
