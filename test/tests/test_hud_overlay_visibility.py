import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.hud_overlay import HUDOverlay


class _Widget:
    def __init__(self):
        self.hidden = False
        self.text = None

    def hide(self):
        self.hidden = True

    def setText(self, text):
        self.text = text


class _HUDHideDummy:
    hide = HUDOverlay.hide

    def __init__(self):
        self.root = _Widget()
        self._checkpoint_marker_root = _Widget()
        self.minimap_pin = _Widget()
        self.minimap_hint = _Widget()
        self.target_label = _Widget()
        self.target_hint = _Widget()
        self._breadcrumbs_hidden = False
        self._tutorial_cleared = False
        self._boss_updates = []

    def _hide_breadcrumbs(self):
        self._breadcrumbs_hidden = True

    def _update_boss_health_bar(self, payload):
        self._boss_updates.append(payload)

    def _clear_tutorial_hint(self):
        self._tutorial_cleared = True


class HUDOverlayVisibilityTests(unittest.TestCase):
    def test_hide_tolerates_missing_npc_scene_debug_text(self):
        hud = _HUDHideDummy()

        hud.hide()

        self.assertTrue(hud.root.hidden)
        self.assertTrue(hud._checkpoint_marker_root.hidden)
        self.assertTrue(hud.minimap_pin.hidden)
        self.assertTrue(hud._breadcrumbs_hidden)
        self.assertTrue(hud._tutorial_cleared)
        self.assertEqual([None], hud._boss_updates)
        self.assertEqual("", hud.minimap_hint.text)
        self.assertEqual("", hud.target_label.text)
        self.assertEqual("", hud.target_hint.text)


if __name__ == "__main__":
    unittest.main()
