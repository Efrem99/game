import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _ProbeDummy:
    _should_run_runtime_node_probe = XBotApp._should_run_runtime_node_probe
    _debug_probe_runtime_node = XBotApp._debug_probe_runtime_node

    def __init__(self, video_bot=False, test_profile="", test_location="", should_fail=False):
        self._video_bot_enabled = bool(video_bot)
        self._test_profile = str(test_profile)
        self._test_location_raw = str(test_location)
        self.render = object()
        self.should_fail = bool(should_fail)
        self.calls = []

    def _scene_node_debug_name(self, node):
        return str(node)

    def _probe_scene_node_transform(self, node, reference=None):
        self.calls.append((node, reference))
        if self.should_fail:
            raise ValueError("bad transform")
        return True


class AppRuntimeSceneProbeTests(unittest.TestCase):
    def test_probe_is_disabled_without_runtime_debug_context(self):
        app = _ProbeDummy(video_bot=False, test_profile="", test_location="")

        ok = app._debug_probe_runtime_node("enemy_spawn:test", "enemy-node")

        self.assertTrue(ok)
        self.assertEqual([], app.calls)

    def test_probe_uses_render_reference_when_enabled(self):
        app = _ProbeDummy(video_bot=True)

        ok = app._debug_probe_runtime_node("enemy_spawn:test", "enemy-node")

        self.assertTrue(ok)
        self.assertEqual([("enemy-node", app.render)], app.calls)

    def test_probe_reports_invalid_transform_without_masking_it(self):
        app = _ProbeDummy(video_bot=True, should_fail=True)

        ok = app._debug_probe_runtime_node("vehicle_spawn:test", "vehicle-node")

        self.assertFalse(ok)
        self.assertEqual([("vehicle-node", app.render)], app.calls)


if __name__ == "__main__":
    unittest.main()
