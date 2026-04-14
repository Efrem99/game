import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import SharuanWorld


class _PlacedNode:
    def __init__(self):
        self.pos = None

    def set_pos(self, x, y, z):
        self.pos = (float(x), float(y), float(z))


class _LoadedNodePath:
    def __init__(self):
        self.copy_targets = []
        self.result = _PlacedNode()

    def copy_to(self, target):
        self.copy_targets.append(target)
        return self.result


class _RenderStub:
    def __init__(self):
        self.attached = []

    def attach_new_node(self, geom):
        self.attached.append(geom)
        return _PlacedNode()


class _WorldPlacementDummy:
    _attach_scene_node = SharuanWorld._attach_scene_node
    _pl = SharuanWorld._pl

    def __init__(self):
        self.render = _RenderStub()
        self.terrain_shader = None
        self.phys = None
        self.colliders = []


class SharuanWorldNodePathPlacementTests(unittest.TestCase):
    def test_pl_copies_loaded_nodepaths_instead_of_attaching_them_as_geom(self):
        world = _WorldPlacementDummy()
        geom = _LoadedNodePath()

        placed = world._pl(geom, 1.0, 2.0, 3.0, is_platform=False)

        self.assertEqual([], world.render.attached)
        self.assertEqual([world.render], geom.copy_targets)
        self.assertIs(geom.result, placed)
        self.assertEqual((1.0, 2.0, 3.0), placed.pos)


if __name__ == "__main__":
    unittest.main()
