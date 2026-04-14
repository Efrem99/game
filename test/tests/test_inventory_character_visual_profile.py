import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.menu_inventory import derive_inventory_character_visual_profile


class InventoryCharacterVisualProfileTests(unittest.TestCase):
    def test_profile_defaults_without_equipment(self):
        profile = derive_inventory_character_visual_profile({})
        self.assertIsInstance(profile, dict)
        self.assertFalse(bool(profile.get("shield_visible", False)))
        self.assertGreater(float(profile.get("trim_alpha", 0.0) or 0.0), 0.5)
        armor_tint = profile.get("armor_tint")
        self.assertIsInstance(armor_tint, tuple)
        self.assertEqual(4, len(armor_tint))
        self.assertIn("weapon_badge_color", profile)
        self.assertIn("shield_badge_color", profile)

    def test_profile_boosts_when_armor_shield_and_trinket_equipped(self):
        base = derive_inventory_character_visual_profile({})
        geared = derive_inventory_character_visual_profile(
            {
                "chest": "royal_armor",
                "offhand": "training_shield",
                "trinket": "rune_charm",
            }
        )
        self.assertTrue(bool(geared.get("shield_visible", False)))
        self.assertTrue(bool(geared.get("trinket_visible", False)))
        self.assertGreater(float(geared.get("trim_alpha", 0.0) or 0.0), float(base.get("trim_alpha", 0.0) or 0.0))
        self.assertNotEqual(base.get("armor_tint"), geared.get("armor_tint"))
        self.assertGreater(float(geared.get("armor_gloss", 0.0) or 0.0), 0.0)
        self.assertNotEqual(base.get("shield_badge_color"), geared.get("shield_badge_color"))

    def test_profile_infers_style_tokens_for_preview_geometry(self):
        profile = derive_inventory_character_visual_profile(
            {
                "weapon_main": "hunter_bow",
                "chest": "royal_armor",
                "offhand": "tower_shield",
                "trinket": "rune_charm",
            }
        )

        self.assertEqual("bow", profile.get("weapon_style"))
        self.assertEqual("heavy", profile.get("armor_style"))
        self.assertEqual("tower", profile.get("offhand_style"))
        self.assertEqual("charm", profile.get("trinket_style"))


if __name__ == "__main__":
    unittest.main()
