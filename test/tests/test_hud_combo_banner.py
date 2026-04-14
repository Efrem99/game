import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.hud_overlay import HUDOverlay


class _Widget:
    def __init__(self):
        self.visible = True
        self.text = ""
        self.fg = None
        self.scale = None

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def setText(self, value):
        self.text = str(value)

    def setFg(self, value):
        self.fg = value

    def setScale(self, value):
        self.scale = value


class _HudComboDummy:
    _combo_banner_text = HUDOverlay._combo_banner_text
    _combo_banner_color = HUDOverlay._combo_banner_color
    _update_combo_banner = HUDOverlay._update_combo_banner

    def __init__(self):
        self.app = SimpleNamespace(data_mgr=SimpleNamespace(t=lambda _key, default=None: str(default or "")))
        self.combo_text = _Widget()
        self._combo_banner_t = 0.0


class HudComboBannerTests(unittest.TestCase):
    def test_update_combo_banner_shows_count_for_live_combo(self):
        hud = _HudComboDummy()

        hud._update_combo_banner(
            0.016,
            {"count": 3, "style": "sword", "kind": "melee", "remain": 0.64},
        )

        self.assertTrue(hud.combo_text.visible)
        self.assertIn("3x", hud.combo_text.text)
        self.assertIn("COMBO", hud.combo_text.text)
        self.assertIsNotNone(hud.combo_text.fg)
        self.assertIsNotNone(hud.combo_text.scale)

    def test_update_combo_banner_hides_when_no_active_combo_exists(self):
        hud = _HudComboDummy()
        hud.combo_text.show()
        hud.combo_text.setText("old")

        hud._update_combo_banner(0.016, None)

        self.assertFalse(hud.combo_text.visible)
        self.assertEqual("", hud.combo_text.text)


if __name__ == "__main__":
    unittest.main()
