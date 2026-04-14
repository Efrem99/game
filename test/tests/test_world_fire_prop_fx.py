import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import SharuanWorld


class _FakeNode:
    def __init__(self, name="node"):
        self.name = name
        self.children = []
        self.scale = None
        self.pos = None
        self.r = None
        self.color = None
        self.tags = {}

    def attachNewNode(self, child):
        node = _FakeNode(getattr(child, "name", str(child)))
        self.children.append(node)
        return node

    def setScale(self, *value):
        self.scale = value

    def setPos(self, *value):
        self.pos = value

    def setR(self, value):
        self.r = value

    def setTransparency(self, *_args, **_kwargs):
        return None

    def setDepthWrite(self, *_args, **_kwargs):
        return None

    def setDepthTest(self, *_args, **_kwargs):
        return None

    def setTwoSided(self, *_args, **_kwargs):
        return None

    def setLightOff(self, *_args, **_kwargs):
        return None

    def setShaderOff(self, *_args, **_kwargs):
        return None

    def setBillboardPointEye(self, *_args, **_kwargs):
        return None

    def setBin(self, *_args, **_kwargs):
        return None

    def setColorScale(self, *value):
        self.color = value

    def setTag(self, key, value):
        self.tags[str(key)] = str(value)


class WorldFirePropFxTests(unittest.TestCase):
    def test_world_model_fx_profile_flags_fire_props(self):
        world = SharuanWorld.__new__(SharuanWorld)

        forge = SharuanWorld._world_model_fx_profile(world, "models/props/forge_fire.glb")
        fireplace = SharuanWorld._world_model_fx_profile(world, "models/props/fireplace_large.glb")
        stone = SharuanWorld._world_model_fx_profile(world, "assets/models/world/props/stone_1.glb")

        self.assertIsInstance(forge, dict)
        self.assertIsInstance(fireplace, dict)
        self.assertIsNone(stone)

    def test_attach_world_model_fx_registers_animated_fire_entries(self):
        world = SharuanWorld.__new__(SharuanWorld)
        world._ambient_fire_props = []
        world.loader = None
        node = _FakeNode("forge_fire")

        root = SharuanWorld._attach_world_model_fx(world, node, "models/props/forge_fire.glb")

        self.assertIsNotNone(root)
        self.assertGreaterEqual(len(world._ambient_fire_props), 2)
        self.assertEqual("fire_prop", root.tags.get("fx_role"))


if __name__ == "__main__":
    unittest.main()
