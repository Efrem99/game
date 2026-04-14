import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _Node:
    def __init__(self, name):
        self.name = str(name)
        self.visible = True
        self.parent = None
        self.children = []
        self.pos = None
        self.color = None
        self.light_off_calls = 0
        self.tex_gen_calls = []

    def attachNewNode(self, name):
        node = _Node(name)
        node.parent = self
        self.children.append(node)
        return node

    def getChildren(self):
        return list(self.children)

    def removeNode(self):
        if self.parent is not None:
            self.parent.children = [child for child in self.parent.children if child is not self]
            self.parent = None

    def setPos(self, *value):
        self.pos = tuple(value)

    def setColorScale(self, *value):
        self.color = tuple(value)

    def setLightOff(self, *_args, **_kwargs):
        self.light_off_calls += 1

    def wrtReparentTo(self, node):
        if self.parent is not None:
            self.parent.children = [child for child in self.parent.children if child is not self]
        self.parent = node
        if self not in node.children:
            node.children.append(self)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class _RuntimeClothingDummy:
    _clear_visual_children = Player._clear_visual_children
    _build_runtime_bodywear_visual = Player._build_runtime_bodywear_visual
    _build_runtime_legwear_visual = Player._build_runtime_legwear_visual
    _apply_runtime_clothing_visuals = Player._apply_runtime_clothing_visuals

    def __init__(self, model_path):
        self.actor = _Node("actor")
        self._spine_upper = _Node("spine_upper")
        self._hips = _Node("hips")
        self._bodywear_node = _Node("bodywear_visual")
        self._legwear_node = _Node("legwear_visual")
        self._sword_node = _Node("sword_visual")
        self._shield_node = _Node("shield_visual")
        self._armor_node = _Node("armor_visual")
        self._trinket_node = _Node("trinket_visual")
        self._loaded_player_model_path = str(model_path)

    def _make_box(self, parent, name, _sx, _sy, _sz, _color):
        return parent.attachNewNode(name)


class PlayerRuntimeClothingVisualTests(unittest.TestCase):
    def test_xbot_runtime_receives_default_bodywear_and_legwear(self):
        dummy = _RuntimeClothingDummy("assets/models/xbot/Xbot.glb")

        Player._apply_runtime_clothing_visuals(dummy)

        body_names = [child.name for child in dummy._bodywear_node.getChildren()]
        leg_names = [child.name for child in dummy._legwear_node.getChildren()]
        self.assertTrue(dummy._bodywear_node.visible)
        self.assertTrue(dummy._legwear_node.visible)
        self.assertIn("bodywear_tunic", body_names)
        self.assertIn("legwear_trousers", leg_names)
        self.assertGreater(dummy._bodywear_node.light_off_calls, 0)
        self.assertGreater(dummy._legwear_node.light_off_calls, 0)

    def test_hero_runtime_hides_default_xbot_clothing_overlay(self):
        dummy = _RuntimeClothingDummy("assets/models/hero/sherward/sherward_rework.glb")

        Player._apply_runtime_clothing_visuals(dummy)

        self.assertFalse(dummy._bodywear_node.visible)
        self.assertFalse(dummy._legwear_node.visible)
        self.assertEqual([], dummy._bodywear_node.getChildren())
        self.assertEqual([], dummy._legwear_node.getChildren())


if __name__ == "__main__":
    unittest.main()
