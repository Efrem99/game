import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.npc_manager import NPCManager


class _VisualNode:
    def __init__(self, name):
        self.name = str(name)
        self.children = []
        self.parent = None
        self.pos = None
        self.hpr = None
        self.p = None
        self.h = None
        self.color = None
        self.two_sided = False

    def attachNewNode(self, child):
        if hasattr(child, "getName") and callable(child.getName):
            name = child.getName()
        else:
            name = getattr(child, "name", child)
        node = _VisualNode(name)
        node.parent = self
        self.children.append(node)
        return node

    def getName(self):
        return self.name

    def isEmpty(self):
        return False

    def setPos(self, *value):
        self.pos = tuple(value)

    def setHpr(self, *value):
        self.hpr = tuple(value)

    def setP(self, value):
        self.p = value

    def setH(self, value):
        self.h = value

    def setColorScale(self, *value):
        self.color = tuple(value)

    def setTwoSided(self, flag):
        self.two_sided = bool(flag)


class _DummyActor(_VisualNode):
    def __init__(self):
        super().__init__("actor")
        self._joints = {}
        for name in ("Spine2", "Head", "Hips"):
            self._joints[name] = self.attachNewNode(name)

    def exposeJoint(self, *_args):
        bone = _args[-1]
        return self._joints.get(str(bone), None)


def _fake_build_mannequin(parent, name, _sx, _sy, _sz, px, py, pz, r, g, b):
    node = parent.attachNewNode(name)
    node.setPos(px, py, pz)
    node.setColorScale(r, g, b, 1.0)
    return node


def _collect_names(node):
    names = [node.getName()]
    for child in getattr(node, "children", []):
        names.extend(_collect_names(child))
    return names


class NPCDracolidVisualProfileTests(unittest.TestCase):
    def test_detects_dracolid_profile_by_species(self):
        manager = NPCManager(SimpleNamespace())
        appearance = {"species": "dracolite", "armor_type": "plate"}
        payload = {"name": "Veyr", "role": "Sentinel"}
        self.assertTrue(manager._is_dracolid_profile("dracolite_guard", payload, appearance))

    def test_detects_dracolid_profile_by_argonian_alias(self):
        manager = NPCManager(SimpleNamespace())
        appearance = {"race": "Argonian", "armor_type": "none"}
        payload = {"name": "Ssa-Riin", "role": "Scout"}
        self.assertTrue(manager._is_dracolid_profile("scout_01", payload, appearance))

    def test_build_dracolid_spec_for_armored_variant(self):
        manager = NPCManager(SimpleNamespace())
        appearance = {
            "species": "dragonkin",
            "armor_type": "plate",
            "skin_color": [0.48, 0.63, 0.44],
        }
        payload = {"name": "Kraxx", "role": "Guard Captain"}
        spec = manager._build_dracolid_visual_spec("draco_captain", payload, appearance)

        self.assertTrue(spec["enabled"])
        self.assertTrue(spec["armored"])
        self.assertEqual("humanoid", spec["body_style"])
        self.assertTrue(spec["has_wings"])
        self.assertTrue(spec["has_tail"])
        self.assertTrue(spec["has_dragon_head"])
        self.assertTrue(spec["armor_shell"])
        self.assertEqual("dragon_humanoid", spec["head_style"])
        self.assertGreaterEqual(spec["crest_spines"], 3)
        self.assertEqual(3, spec["wing_segments"])

    def test_build_dracolid_spec_for_unarmored_variant(self):
        manager = NPCManager(SimpleNamespace())
        appearance = {"race": "dracolite", "armor_type": "none"}
        payload = {"name": "Rhaz", "role": "Wanderer"}
        spec = manager._build_dracolid_visual_spec("draco_wanderer", payload, appearance)

        self.assertTrue(spec["enabled"])
        self.assertFalse(spec["armored"])
        self.assertEqual("humanoid", spec["body_style"])
        self.assertTrue(spec["has_wings"])
        self.assertTrue(spec["has_tail"])
        self.assertTrue(spec["has_dragon_head"])
        self.assertFalse(spec["armor_shell"])
        self.assertEqual("dragon_humanoid", spec["head_style"])
        self.assertGreaterEqual(spec["crest_spines"], 2)
        self.assertEqual(3, spec["wing_segments"])

    def test_non_dracolid_profile_returns_disabled_spec(self):
        manager = NPCManager(SimpleNamespace())
        appearance = {"species": "human", "armor_type": "worker"}
        payload = {"name": "Old Tom", "role": "Head Miner"}
        spec = manager._build_dracolid_visual_spec("miner0", payload, appearance)
        self.assertEqual({"enabled": False}, spec)

    def test_attach_dracolid_visual_builds_dragon_head_and_segmented_wings(self):
        manager = NPCManager(SimpleNamespace())
        actor = _DummyActor()
        appearance = {
            "species": "dracolite",
            "armor_type": "plate",
            "scale": 1.12,
            "skin_color": [0.40, 0.62, 0.48],
        }
        payload = {"name": "Kael-Ra", "role": "Sentinel"}

        with patch("managers.npc_manager.build_mannequin", side_effect=_fake_build_mannequin), patch(
            "managers.npc_manager.ensure_model_visual_defaults",
            return_value=0,
        ):
            visual = manager._attach_dracolid_visual(actor, "dracolite_sentinel", payload, appearance)

        self.assertIsNotNone(visual)
        self.assertIn("wing_l_mid", visual)
        self.assertIn("wing_r_mid", visual)
        self.assertIn("wing_l_tip", visual)
        self.assertIn("wing_r_tip", visual)
        self.assertGreaterEqual(len(visual.get("tail_joints", [])), 4)

        names = _collect_names(actor)
        self.assertTrue(any(name.startswith("dracolid_jaw_") for name in names))
        self.assertTrue(any(name.startswith("dracolid_head_crest_") for name in names))
        self.assertTrue(any(name.startswith("dracolid_wing_claw_") for name in names))
        self.assertTrue(any(name.startswith("dracolid_shoulder_spine_") for name in names))


if __name__ == "__main__":
    unittest.main()
