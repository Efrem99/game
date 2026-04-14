import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.core_runtime import HAS_CORE  # noqa: F401
from ui.menu_inventory import InventoryUI


class _VisibleNode:
    def __init__(self):
        self.visible = False
        self.props = {}

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def __setitem__(self, key, value):
        self.props[str(key)] = value


class _InventorySwitchDummy:
    _switch_tab = InventoryUI._switch_tab

    def __init__(self):
        self._current_tab = "inventory"
        self.btn_inv = _VisibleNode()
        self.btn_party = _VisibleNode()
        self.btn_map = _VisibleNode()
        self.btn_skills = _VisibleNode()
        self.btn_journal = _VisibleNode()
        self.inventory_showcase = _VisibleNode()
        self.inventory_showcase_title = _VisibleNode()
        self.item_list = _VisibleNode()
        self.map_panel = _VisibleNode()
        self.map_title = _VisibleNode()
        self.map_pin_text = _VisibleNode()
        self.map_text = _VisibleNode()
        self.journal_text = _VisibleNode()
        self.journal_panel = _VisibleNode()
        self.inventory_status_text = _VisibleNode()
        self.clear_map_labels_called = 0
        self.refresh_calls = []

    def _apply_item_list_layout(self, mode):
        self.item_list.props["layout_mode"] = mode

    def _clear_map_labels(self):
        self.clear_map_labels_called += 1

    def _refresh_inventory(self):
        self.refresh_calls.append("inventory")

    def _refresh_party(self):
        self.refresh_calls.append("party")

    def _refresh_map(self):
        self.refresh_calls.append("map")

    def _refresh_skills(self):
        self.refresh_calls.append("skills")

    def _refresh_journal(self):
        self.refresh_calls.append("journal")


class InventoryTabVisibilityTests(unittest.TestCase):
    def test_map_tab_hides_inventory_and_journal_panels(self):
        dummy = _InventorySwitchDummy()

        dummy._switch_tab("map")

        self.assertTrue(dummy.map_panel.visible)
        self.assertTrue(dummy.map_title.visible)
        self.assertTrue(dummy.map_pin_text.visible)
        self.assertTrue(dummy.map_text.visible)
        self.assertFalse(dummy.item_list.visible)
        self.assertFalse(dummy.inventory_showcase.visible)
        self.assertFalse(dummy.journal_panel.visible)
        self.assertFalse(dummy.inventory_status_text.visible)
        self.assertIn("map", dummy.refresh_calls)

    def test_skills_tab_hides_map_and_journal_panels(self):
        dummy = _InventorySwitchDummy()

        dummy._switch_tab("skills")

        self.assertTrue(dummy.item_list.visible)
        self.assertFalse(dummy.map_panel.visible)
        self.assertFalse(dummy.map_title.visible)
        self.assertFalse(dummy.map_pin_text.visible)
        self.assertFalse(dummy.map_text.visible)
        self.assertFalse(dummy.journal_panel.visible)
        self.assertTrue(dummy.inventory_status_text.visible)
        self.assertIn("skills", dummy.refresh_calls)

    def test_journal_tab_hides_inventory_and_map_panels(self):
        dummy = _InventorySwitchDummy()

        dummy._switch_tab("journal")

        self.assertTrue(dummy.journal_panel.visible)
        self.assertFalse(dummy.item_list.visible)
        self.assertFalse(dummy.inventory_showcase.visible)
        self.assertFalse(dummy.map_panel.visible)
        self.assertFalse(dummy.map_title.visible)
        self.assertFalse(dummy.map_pin_text.visible)
        self.assertFalse(dummy.map_text.visible)
        self.assertFalse(dummy.inventory_status_text.visible)
        self.assertIn("journal", dummy.refresh_calls)


if __name__ == "__main__":
    unittest.main()
