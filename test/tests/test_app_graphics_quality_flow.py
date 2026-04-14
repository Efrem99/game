import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _GraphicsRenderStub:
    def __init__(self):
        self.antialias_calls = []
        self.shader_inputs = []

    def setAntialias(self, *args):
        self.antialias_calls.append(args)

    def set_shader_input(self, name, value, priority=None):
        self.shader_inputs.append((str(name), value, priority))


class _AdaptivePerfStub:
    def __init__(self):
        self.calls = []

    def on_quality_changed(self, quality, user_initiated=False):
        self.calls.append((str(quality), bool(user_initiated)))


class _DataMgrStub:
    def __init__(self):
        self.graphics_settings = {
            "pbr": {"exposure": 1.1},
            "post_processing": {"bloom": {"intensity": 0.55, "threshold": 0.7}},
        }
        self.saved = []

    def save_settings(self, path, payload):
        self.saved.append((str(path), dict(payload)))


class _GraphicsQualityDummy:
    apply_graphics_quality = XBotApp.apply_graphics_quality
    _resolve_startup_graphics_quality = XBotApp._resolve_startup_graphics_quality
    _should_enable_screenspace_pass = XBotApp._should_enable_screenspace_pass

    def __init__(self):
        self.render = _GraphicsRenderStub()
        self._advanced_rendering = False
        self._screenspace_ready = True
        self._video_bot_visibility_boost = False
        self._debug_skip_screenspace = False
        self._debug_skip_screenspace_logged = False
        self.data_mgr = _DataMgrStub()
        self.adaptive_perf_mgr = _AdaptivePerfStub()
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
        return 2


class AppGraphicsQualityFlowTests(unittest.TestCase):
    def test_startup_graphics_quality_uses_env_override_when_present(self):
        app = _GraphicsQualityDummy()

        with patch.dict("os.environ", {"XBOT_GRAPHICS_QUALITY": "ultra"}, clear=False):
            self.assertEqual("ultra", app._resolve_startup_graphics_quality("low"))

    def test_startup_graphics_quality_keeps_stored_value_without_override(self):
        app = _GraphicsQualityDummy()

        with patch.dict("os.environ", {}, clear=False):
            self.assertEqual("medium", app._resolve_startup_graphics_quality("medium"))

    def test_apply_graphics_quality_updates_lighting_sampler_and_state(self):
        app = _GraphicsQualityDummy()

        app.apply_graphics_quality("high", persist=False)

        self.assertEqual(["high"], app._lighting_tokens)
        self.assertEqual(["high"], app._sampler_tokens)
        self.assertEqual("High", app._gfx_quality)
        self.assertEqual([("High", False)], app.adaptive_perf_mgr.calls)

    def test_apply_graphics_quality_persists_selected_quality(self):
        app = _GraphicsQualityDummy()

        app.apply_graphics_quality("medium", persist=True)

        self.assertEqual([("graphics_settings.json", app.data_mgr.graphics_settings)], app.data_mgr.saved)
        self.assertEqual("Medium", app.data_mgr.graphics_settings["quality"])


if __name__ == "__main__":
    unittest.main()
