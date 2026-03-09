import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.npc_manager import NPCManager


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


class NPCNonCoreVisualFallbackTests(unittest.TestCase):
    def test_animated_npc_keeps_skinning_path(self):
        manager = NPCManager(SimpleNamespace())
        actor = _DummyAnimatedActor()
        manager._apply_non_core_visual_fallback(actor, python_mode=True)
        self.assertEqual(0, actor.shader_off_calls)
        self.assertGreater(actor.color_scale_calls, 0)
        self.assertGreater(actor.two_sided_calls, 0)

    def test_static_npc_can_use_shader_off_fallback(self):
        manager = NPCManager(SimpleNamespace())
        node = _DummyStaticNode()
        manager._apply_non_core_visual_fallback(node, python_mode=True)
        self.assertEqual(1, node.shader_off_calls)
        self.assertGreater(node.color_scale_calls, 0)
        self.assertGreater(node.two_sided_calls, 0)


if __name__ == "__main__":
    unittest.main()
