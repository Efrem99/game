import sys
import unittest
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import render.model_visuals as model_visuals


class _FakeComplexPbr:
    def __init__(self):
        self.calls = 0

    def skin(self, node):
        self.calls += 1
        node.skinned = True


class _FakeNode:
    def __init__(self):
        self.skinned = False


class ModelVisualSkinGuardTests(unittest.TestCase):
    def test_apply_hardware_skinning_skips_when_skin_attrib_missing(self):
        fake = _FakeComplexPbr()
        node = _FakeNode()

        with patch.object(model_visuals, "complexpbr", fake), patch.object(
            model_visuals, "base", SimpleNamespace(), create=True
        ):
            self.assertFalse(model_visuals._apply_hardware_skinning(node, "test"))
            self.assertEqual(0, fake.calls)
            self.assertFalse(node.skinned)

    def test_apply_hardware_skinning_runs_when_skin_attrib_exists(self):
        fake = _FakeComplexPbr()
        node = _FakeNode()

        with patch.object(model_visuals, "complexpbr", fake), patch.object(
            model_visuals,
            "base",
            SimpleNamespace(complexpbr_skin_attrib=object()),
            create=True,
        ):
            self.assertTrue(model_visuals._apply_hardware_skinning(node, "test"))
            self.assertEqual(1, fake.calls)
            self.assertTrue(node.skinned)

    def test_apply_hardware_skinning_skips_when_debug_flag_is_enabled(self):
        fake = _FakeComplexPbr()
        node = _FakeNode()

        with patch.dict(os.environ, {"XBOT_DEBUG_SKIP_PBR_SKIN": "1"}, clear=False), patch.object(
            model_visuals, "complexpbr", fake
        ), patch.object(
            model_visuals,
            "base",
            SimpleNamespace(complexpbr_skin_attrib=object()),
            create=True,
        ):
            self.assertFalse(model_visuals._apply_hardware_skinning(node, "test"))
            self.assertEqual(0, fake.calls)
            self.assertFalse(node.skinned)


if __name__ == "__main__":
    unittest.main()
