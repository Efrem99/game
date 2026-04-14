import sys
import unittest
from pathlib import Path

from panda3d.core import TexGenAttrib

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import render.model_visuals as model_visuals


class _FakeNode:
    def __init__(self, name, children=None):
        self._name = str(name)
        self._children = list(children or [])
        self.shader_off_priority = None
        self.tex_gen = None

    def getName(self):
        return self._name

    def get_name(self):
        return self._name

    def getChildren(self):
        return list(self._children)

    def isEmpty(self):
        return False

    def is_empty(self):
        return False

    def setShaderOff(self, priority):
        self.shader_off_priority = priority

    def set_tex_gen(self, stage, mode):
        self.tex_gen = (stage, mode)


class ModelVisualEnvExemptionTests(unittest.TestCase):
    def test_exempts_background_weather_and_dash_nodes_from_env_mapping(self):
        safe = _FakeNode("sandbox_void_base")
        sky = _FakeNode("sky_sun")
        rain = _FakeNode("rain_streak_12")
        dash = _FakeNode("dash_fx_root")
        root = _FakeNode("render_root", children=[safe, sky, rain, dash])

        patched = model_visuals.exempt_problematic_scene_nodes_from_env_texgen(root)

        self.assertEqual(3, patched)
        self.assertIsNone(safe.tex_gen)
        self.assertEqual(TexGenAttrib.MOff, sky.tex_gen[1])
        self.assertEqual(TexGenAttrib.MOff, rain.tex_gen[1])
        self.assertEqual(TexGenAttrib.MOff, dash.tex_gen[1])
        self.assertEqual(1003, sky.shader_off_priority)
        self.assertEqual(1003, rain.shader_off_priority)
        self.assertEqual(1003, dash.shader_off_priority)


if __name__ == "__main__":
    unittest.main()
