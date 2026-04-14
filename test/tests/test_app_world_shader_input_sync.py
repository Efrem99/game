import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _RenderStub:
    def __init__(self):
        self.calls = []

    def set_shader_input(self, name, value, priority=None):
        self.calls.append((name, value, priority))


class _WorldStub:
    def __init__(self):
        self.calls = []

    def sync_environment_shader_inputs(self, cursed_blend=0.0):
        self.calls.append(float(cursed_blend))


class _AppWorldShaderInputDummy:
    _sync_world_environment_shader_inputs = XBotApp._sync_world_environment_shader_inputs

    def __init__(self, cursed_blend):
        self.render = _RenderStub()
        self.world = _WorldStub()
        self.weather_mgr = type("WeatherStub", (), {"cursed_blend": cursed_blend})()
        self._cursed_blend = -1.0


class AppWorldShaderInputSyncTests(unittest.TestCase):
    def test_sync_world_environment_shader_inputs_routes_cursed_blend_to_world_helper(self):
        app = _AppWorldShaderInputDummy(0.4)

        synced = app._sync_world_environment_shader_inputs()

        self.assertTrue(synced)
        self.assertEqual([0.4], app.world.calls)
        self.assertEqual([], app.render.calls)
        self.assertAlmostEqual(0.4, app._cursed_blend, places=6)

    def test_sync_world_environment_shader_inputs_sanitizes_invalid_values(self):
        app = _AppWorldShaderInputDummy(float("nan"))

        synced = app._sync_world_environment_shader_inputs()

        self.assertTrue(synced)
        self.assertEqual([0.0], app.world.calls)
        self.assertEqual([], app.render.calls)
        self.assertFalse(math.isnan(app._cursed_blend))
        self.assertAlmostEqual(0.0, app._cursed_blend, places=6)


if __name__ == "__main__":
    unittest.main()
