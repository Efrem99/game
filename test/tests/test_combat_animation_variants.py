import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _VariantDataManager:
    def __init__(self):
        self.spells = {}
        self._items = {
            "iron_sword": {
                "id": "iron_sword",
                "weapon_class": "sword",
                "equip_visual": {"style": "blade"},
            },
            "battle_staff": {
                "id": "battle_staff",
                "weapon_class": "staff",
                "equip_visual": {"style": "staff"},
            },
            "arcane_focus": {
                "id": "arcane_focus",
                "weapon_class": "focus",
                "equip_visual": {"style": "magic"},
            },
            "offhand_dagger": {
                "id": "offhand_dagger",
                "weapon_class": "dagger",
                "equip_visual": {"style": "dagger"},
            },
            "offhand_shield": {
                "id": "offhand_shield",
                "slot": "offhand",
                "equip_visual": {"style": "shield"},
            },
        }

    def get_item(self, item_id):
        payload = self._items.get(str(item_id or "").strip())
        return dict(payload) if isinstance(payload, dict) else None


class _VariantOwner(PlayerCombatMixin):
    def __init__(self):
        self.data_mgr = _VariantDataManager()
        self._equipment_state = {
            "weapon_main": "iron_sword",
            "offhand": "",
            "chest": "",
            "trinket": "",
        }
        self._next_cast_hand = "right"
        self._next_weapon_hand = "right"


class CombatAnimationVariantTests(unittest.TestCase):
    def test_projectile_spell_variants_keep_fast_cast_and_cycle_between_hands(self):
        owner = _VariantOwner()
        resolver = getattr(owner, "_resolve_spell_anim_triggers", None)
        self.assertTrue(callable(resolver), "PlayerCombatMixin must expose _resolve_spell_anim_triggers")

        first = resolver(
            "fireball",
            {"id": "fireball"},
            {"anim_trigger": "cast_spell"},
        )
        second = resolver(
            "fireball",
            {"id": "fireball"},
            {"anim_trigger": "cast_spell"},
        )

        self.assertIsInstance(first, list)
        self.assertIsInstance(second, list)
        self.assertTrue(first and second)
        self.assertEqual("cast_fast", first[0])
        self.assertEqual("cast_fast", second[0])
        self.assertIn("cast_fast", first)
        self.assertIn("cast_fast", second)
        self.assertIn("cast_fire", first)
        self.assertIn("cast_fire", second)
        self.assertIn("cast_right", first)
        self.assertIn("cast_left", second)
        self.assertIn("cast_spell", first)
        self.assertIn("cast_spell", second)

    def test_support_spell_variants_surface_telegraph_before_both_mode(self):
        owner = _VariantOwner()
        resolver = getattr(owner, "_resolve_spell_anim_triggers", None)
        self.assertTrue(callable(resolver), "PlayerCombatMixin must expose _resolve_spell_anim_triggers")

        variants = resolver(
            "ward",
            {
                "id": "ward",
                "runtime": {"cast_mode": "both"},
            },
            {"anim_trigger": "cast_spell"},
        )
        self.assertTrue(variants)
        self.assertEqual("cast_telegraph", variants[0])
        self.assertIn("cast_ward", variants)
        self.assertIn("cast_both", variants)
        self.assertIn("cast_spell", variants)

    def test_weapon_variants_exist_and_cycle_for_single_hand(self):
        owner = _VariantOwner()
        resolver = getattr(owner, "_resolve_weapon_attack_triggers", None)
        self.assertTrue(callable(resolver), "PlayerCombatMixin must expose _resolve_weapon_attack_triggers")

        first = resolver("light")
        second = resolver("light")
        self.assertTrue(first and second)
        self.assertEqual("attack_light_right", first[0])
        self.assertEqual("attack_light_left", second[0])
        self.assertEqual("attack", first[-1])

    def test_weapon_variants_choose_both_for_staff_heavy(self):
        owner = _VariantOwner()
        owner._equipment_state["weapon_main"] = "battle_staff"

        resolver = getattr(owner, "_resolve_weapon_attack_triggers", None)
        self.assertTrue(callable(resolver), "PlayerCombatMixin must expose _resolve_weapon_attack_triggers")
        variants = resolver("heavy")
        self.assertTrue(variants)
        self.assertEqual("attack_heavy_both", variants[0])

    def test_weapon_variants_choose_both_for_magic_focus(self):
        owner = _VariantOwner()
        owner._equipment_state["weapon_main"] = "arcane_focus"

        resolver = getattr(owner, "_resolve_weapon_attack_triggers", None)
        self.assertTrue(callable(resolver), "PlayerCombatMixin must expose _resolve_weapon_attack_triggers")
        variants = resolver("heavy")
        self.assertTrue(variants)
        self.assertEqual("attack_heavy_both", variants[0])

    def test_magic_focus_light_attack_stays_in_both_hand_flow(self):
        owner = _VariantOwner()
        owner._equipment_state["weapon_main"] = "arcane_focus"

        resolver = getattr(owner, "_resolve_weapon_attack_triggers", None)
        self.assertTrue(callable(resolver), "PlayerCombatMixin must expose _resolve_weapon_attack_triggers")
        variants = resolver("light")
        self.assertTrue(variants)
        self.assertEqual("attack_light_both", variants[0])

    def test_weapon_variants_choose_dual_when_offhand_is_dual_capable(self):
        owner = _VariantOwner()
        owner._equipment_state["offhand"] = "offhand_dagger"

        resolver = getattr(owner, "_resolve_weapon_attack_triggers", None)
        self.assertTrue(callable(resolver), "PlayerCombatMixin must expose _resolve_weapon_attack_triggers")
        variants = resolver("light")
        self.assertTrue(variants)
        self.assertEqual("attack_light_dual", variants[0])


if __name__ == "__main__":
    unittest.main()
