import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _TaskMgrStub:
    def __init__(self):
        self.removed = []

    def remove(self, name):
        self.removed.append(name)


class _CubeBufferStub:
    def __init__(self):
        self.active = []

    def set_active(self, value):
        self.active.append(value)


class _PbrCubemapDummy:
    _should_disable_live_pbr_cubemap = XBotApp._should_disable_live_pbr_cubemap
    _maybe_disable_live_pbr_cubemap = XBotApp._maybe_disable_live_pbr_cubemap

    def __init__(self, disable_cubemap=False, enable_override=False, video_bot=False, test_profile=""):
        self._debug_disable_pbr_cubemap = bool(disable_cubemap)
        self._enable_live_pbr_cubemap_override = bool(enable_override)
        self._video_bot_enabled = bool(video_bot)
        self._test_profile = str(test_profile)
        self.taskMgr = _TaskMgrStub()
        self.cube_buffer = _CubeBufferStub()


class AppPbrCubemapPolicyTests(unittest.TestCase):
    def test_live_cubemap_can_be_disabled_explicitly(self):
        app = _PbrCubemapDummy(disable_cubemap=True)

        self.assertTrue(app._maybe_disable_live_pbr_cubemap())
        self.assertEqual([0], app.cube_buffer.active)
        self.assertEqual(["rotate_cubemap"], app.taskMgr.removed)

    def test_windows_runtime_tests_disable_live_cubemap_by_default(self):
        app = _PbrCubemapDummy(video_bot=True, test_profile="ultimate_sandbox")

        self.assertTrue(app._should_disable_live_pbr_cubemap())
        self.assertTrue(app._maybe_disable_live_pbr_cubemap())
        self.assertEqual([0], app.cube_buffer.active)
        self.assertEqual(["rotate_cubemap"], app.taskMgr.removed)

    def test_live_cubemap_override_restores_opt_in_path(self):
        app = _PbrCubemapDummy(enable_override=True, video_bot=True, test_profile="ultimate_sandbox")

        self.assertFalse(app._should_disable_live_pbr_cubemap())
        self.assertFalse(app._maybe_disable_live_pbr_cubemap())
        self.assertEqual([], app.cube_buffer.active)
        self.assertEqual([], app.taskMgr.removed)


if __name__ == "__main__":
    unittest.main()
