import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.menu_inventory import InventoryUI


class InventoryLayoutProfileTests(unittest.TestCase):
    def test_layout_profile_exists_and_scales_with_aspect(self):
        self.assertTrue(
            hasattr(InventoryUI, "_layout_profile_for_aspect"),
            "InventoryUI must expose _layout_profile_for_aspect",
        )
        fn = getattr(InventoryUI, "_layout_profile_for_aspect")
        baseline = fn(16.0 / 9.0)
        wide = fn(21.0 / 9.0)
        narrow = fn(4.0 / 3.0)

        self.assertIsInstance(baseline, dict)
        self.assertIsInstance(wide, dict)
        self.assertIsInstance(narrow, dict)
        self.assertLess(wide["panel_scale"], baseline["panel_scale"])
        self.assertLess(narrow["panel_scale"], baseline["panel_scale"])


if __name__ == "__main__":
    unittest.main()
