import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import SharuanWorld


class _ShaderTargetStub:
    def __init__(self, name, empty=False):
        self._name = name
        self._empty = bool(empty)
        self.shader_inputs = []

    def isEmpty(self):
        return self._empty

    def set_shader_input(self, name, value):
        self.shader_inputs.append((str(name), float(value)))


class _WorldShaderInputDummy:
    _register_terrain_shader_target = SharuanWorld._register_terrain_shader_target
    _iter_terrain_shader_targets = SharuanWorld._iter_terrain_shader_targets
    sync_environment_shader_inputs = SharuanWorld.sync_environment_shader_inputs

    def __init__(self):
        self.terrain_shader = object()
        self._terrain_shader_targets = []
        self._terrain_shader_cursed_blend = 0.0


class SharuanWorldShaderInputTests(unittest.TestCase):
    def test_sync_environment_shader_inputs_updates_only_live_registered_targets(self):
        world = _WorldShaderInputDummy()
        live = _ShaderTargetStub("live")
        empty = _ShaderTargetStub("empty", empty=True)

        world._register_terrain_shader_target(live)
        world._register_terrain_shader_target(empty)
        world.sync_environment_shader_inputs(cursed_blend=0.65)

        self.assertEqual([("cursed_blend", 0.0), ("cursed_blend", 0.65)], live.shader_inputs)
        self.assertEqual([], empty.shader_inputs)
        self.assertEqual([live], list(world._iter_terrain_shader_targets()))
        self.assertAlmostEqual(0.65, world._terrain_shader_cursed_blend, places=6)


if __name__ == "__main__":
    unittest.main()
