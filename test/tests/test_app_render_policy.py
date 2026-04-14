import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _RenderPolicyDummy:
    _should_disable_ultimate_sandbox_postfx = XBotApp._should_disable_ultimate_sandbox_postfx
    _should_force_ultimate_sandbox_pbr = XBotApp._should_force_ultimate_sandbox_pbr

    def __init__(self, profile=""):
        self._test_profile = str(profile)


class _GraphicsRenderStub:
    def __init__(self):
        self.antialias_calls = []
        self.shader_inputs = []

    def setAntialias(self, *args):
        self.antialias_calls.append(args)

    def set_shader_input(self, name, value, priority=None):
        self.shader_inputs.append((str(name), value, priority))


class _GraphicsQualityDummy:
    apply_graphics_quality = XBotApp.apply_graphics_quality
    _should_enable_screenspace_pass = XBotApp._should_enable_screenspace_pass

    def __init__(self):
        self.render = _GraphicsRenderStub()
        self._advanced_rendering = False
        self._screenspace_ready = True
        self._video_bot_visibility_boost = False
        self._video_bot_enabled = False
        self._test_profile = ""
        self._test_location_raw = ""
        self._test_scenario_raw = ""
        self._debug_skip_screenspace = False
        self.data_mgr = SimpleNamespace(
            graphics_settings={
                "pbr": {"exposure": 1.1},
                "post_processing": {"bloom": {"intensity": 0.55, "threshold": 0.7}},
            }
        )
        self.adaptive_perf_mgr = None
        self._lighting_tokens = []
        self._sampler_tokens = []
        self._gfx_quality = ""

    def _safe_screenspace_init(self):
        raise AssertionError("should not initialize screenspace in this test")

    def _remove_screenspace_nodes(self):
        self._screenspace_ready = False

    def _apply_lighting_from_settings(self, token):
        self._lighting_tokens.append(str(token))

    def _apply_texture_sampler_defaults(self, token):
        self._sampler_tokens.append(str(token))
        return 0


class AppRenderPolicyTests(unittest.TestCase):
    def test_python_only_ultimate_sandbox_disables_postfx(self):
        app = _RenderPolicyDummy(profile="ultimate_sandbox")

        with patch("app.HAS_CORE", False):
            with patch.dict(os.environ, {"XBOT_DISABLE_POSTFX": "0"}, clear=False):
                self.assertTrue(app._should_disable_ultimate_sandbox_postfx())
                self.assertFalse(app._should_force_ultimate_sandbox_pbr())

    def test_disable_postfx_env_overrides_sandbox_force(self):
        app = _RenderPolicyDummy(profile="ultimate_sandbox")

        with patch("app.HAS_CORE", True):
            with patch.dict(os.environ, {"XBOT_DISABLE_POSTFX": "1"}, clear=False):
                self.assertFalse(app._should_force_ultimate_sandbox_pbr())

    def test_core_runtime_can_keep_ultimate_sandbox_pbr(self):
        app = _RenderPolicyDummy(profile="ultimate_sandbox")

        with patch("app.HAS_CORE", True):
            with patch.dict(os.environ, {"XBOT_DISABLE_POSTFX": "0"}, clear=False):
                self.assertTrue(app._should_force_ultimate_sandbox_pbr())

    def test_apply_graphics_quality_updates_lighting_and_gfx_state(self):
        app = _GraphicsQualityDummy()

        app.apply_graphics_quality("high", persist=False)

        self.assertEqual(["high"], app._lighting_tokens)
        self.assertEqual(["high"], app._sampler_tokens)
        self.assertEqual("High", app._gfx_quality)


if __name__ == "__main__":
    unittest.main()
