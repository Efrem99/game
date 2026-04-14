import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _PostFinalizeVisualsDummy:
    _stabilize_post_finalize_scene_visuals = XBotApp._stabilize_post_finalize_scene_visuals

    def __init__(self, advanced_rendering=True):
        self.render = object()
        self._advanced_rendering = bool(advanced_rendering)


class AppPostFinalizeVisualsTests(unittest.TestCase):
    def test_advanced_rendering_repairs_scene_before_audit(self):
        app = _PostFinalizeVisualsDummy(advanced_rendering=True)
        calls = []

        def _capture_ensure(*args, **kwargs):
            calls.append(("ensure", args, kwargs))
            return 9

        def _capture_exempt(*args, **kwargs):
            calls.append(("exempt", args, kwargs))
            return 6

        def _capture_audit(*args, **kwargs):
            calls.append(("audit", args, kwargs))
            return {"issues": {"missing_material": 0}}

        with patch("app.ensure_model_visual_defaults", side_effect=_capture_ensure), patch(
            "app.exempt_problematic_scene_nodes_from_env_texgen", side_effect=_capture_exempt
        ), patch(
            "app.audit_node_visual_health", side_effect=_capture_audit
        ):
            app._stabilize_post_finalize_scene_visuals()

        self.assertEqual(["ensure", "exempt", "audit"], [name for name, _, _ in calls])
        self.assertIs(app.render, calls[0][1][0])
        self.assertEqual("post_finalize_scene", calls[0][2]["debug_label"])
        self.assertIs(app.render, calls[1][1][0])
        self.assertEqual("post_finalize", calls[2][2]["debug_label"])

    def test_non_advanced_rendering_skips_scene_repair_but_keeps_audit(self):
        app = _PostFinalizeVisualsDummy(advanced_rendering=False)
        calls = []

        def _capture_audit(*args, **kwargs):
            calls.append(("audit", args, kwargs))
            return {"issues": {"missing_material": 0}}

        with patch("app.ensure_model_visual_defaults") as ensure_mock, patch(
            "app.exempt_problematic_scene_nodes_from_env_texgen"
        ) as exempt_mock, patch(
            "app.audit_node_visual_health", side_effect=_capture_audit
        ):
            app._stabilize_post_finalize_scene_visuals()

        ensure_mock.assert_not_called()
        exempt_mock.assert_not_called()
        self.assertEqual(["audit"], [name for name, _, _ in calls])


if __name__ == "__main__":
    unittest.main()
