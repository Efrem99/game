import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.menu_inventory import InventoryUI


class _PreviewNode:
    def __init__(self):
        self.visible = True
        self.color_scale = None
        self.scale = None
        self.shader_inputs = {}

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def setColorScale(self, *value):
        self.color_scale = tuple(value)

    def setScale(self, value):
        self.scale = value

    def set_shader_input(self, key, value, priority=None):
        _ = priority
        self.shader_inputs[str(key)] = value


class _InventoryPreviewDummy:
    _apply_character_visual_profile = InventoryUI._apply_character_visual_profile

    def __init__(self):
        self._preview_actor = _PreviewNode()
        self._preview_weapon_root = _PreviewNode()
        self._preview_shield_root = _PreviewNode()
        self._preview_armor_root = _PreviewNode()
        self._preview_trinket_root = _PreviewNode()


class InventoryPreviewProfileTests(unittest.TestCase):
    def test_apply_character_visual_profile_updates_preview_visibility_and_tints(self):
        ui = _InventoryPreviewDummy()

        ui._apply_character_visual_profile(
            {
                "weapon_visible": True,
                "shield_visible": False,
                "trinket_visible": True,
                "armor_tint": (0.7, 0.72, 0.78, 1.0),
                "armor_gloss": 0.42,
                "weapon_badge_color": (0.9, 0.7, 0.3, 1.0),
                "shield_badge_color": (0.4, 0.5, 0.6, 1.0),
                "trim_alpha": 0.8,
                "armor_score": 0.55,
            }
        )

        self.assertTrue(ui._preview_weapon_root.visible)
        self.assertFalse(ui._preview_shield_root.visible)
        self.assertTrue(ui._preview_trinket_root.visible)
        self.assertEqual((0.7, 0.72, 0.78, 1.0), ui._preview_armor_root.color_scale)
        self.assertEqual((0.9, 0.7, 0.3, 1.0), ui._preview_weapon_root.color_scale)
        self.assertEqual((0.4, 0.5, 0.6, 1.0), ui._preview_shield_root.color_scale)


if __name__ == "__main__":
    unittest.main()
