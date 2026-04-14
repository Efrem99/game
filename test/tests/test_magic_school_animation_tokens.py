import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _SchoolDataMgr:
    def get_item(self, _item_id):
        return {}


class _SchoolOwner(PlayerCombatMixin):
    def __init__(self):
        self.data_mgr = _SchoolDataMgr()
        self._equipment_state = {"weapon_main": "", "offhand": ""}
        self._next_cast_hand = "right"
        self._next_weapon_hand = "right"


class MagicSchoolAnimationTokenTests(unittest.TestCase):
    def test_projectile_fireball_prefers_generic_projectile_cast_tokens(self):
        owner = _SchoolOwner()

        tokens = owner._resolve_spell_anim_triggers(
            "fireball",
            {"id": "fireball", "damage_type": "fire", "cast_time": 0.22},
            {"anim_trigger": "cast_spell", "cast_time": 0.22},
        )

        self.assertTrue(tokens)
        self.assertEqual("cast_fast", tokens[0])
        self.assertIn("cast_fire", tokens)
        self.assertIn("cast_fast", tokens)
        self.assertIn("cast_spell", tokens)

    def test_support_spells_get_telegraph_and_distinct_school_tokens(self):
        owner = _SchoolOwner()

        ward_tokens = owner._resolve_spell_anim_triggers(
            "ward",
            {"id": "ward", "damage_type": "holy", "runtime": {"cast_mode": "both"}},
            {"anim_trigger": "cast_spell", "cast_time": 0.3},
        )
        heal_tokens = owner._resolve_spell_anim_triggers(
            "HealingAura",
            {"id": "HealingAura", "heal_value": 50, "cast_time": 0.6},
            {"anim_trigger": "cast_spell", "cast_time": 0.6},
        )

        self.assertTrue(ward_tokens)
        self.assertTrue(heal_tokens)
        self.assertEqual("cast_telegraph", ward_tokens[0])
        self.assertIn("cast_ward", ward_tokens)
        self.assertIn("cast_both", ward_tokens)
        self.assertEqual("cast_telegraph", heal_tokens[0])
        self.assertIn("cast_heal", heal_tokens)
        self.assertIn("cast_channel", heal_tokens)

    def test_runtime_profile_infers_school_specific_anim_trigger_for_legacy_spells(self):
        owner = _SchoolOwner()

        lightning = owner._spell_runtime_profile(
            "LightningBolt",
            {"id": "LightningBolt", "damage": 40, "particle_tag": "lightning_arc"},
        )
        ice = owner._spell_runtime_profile(
            "IceShards",
            {"id": "IceShards", "damage": 10, "particle_tag": "ice_spike"},
        )
        force = owner._spell_runtime_profile(
            "ForceWave",
            {"id": "ForceWave", "damage": 5, "particle_tag": "force_push"},
        )

        self.assertEqual("cast_lightning", lightning["anim_trigger"])
        self.assertEqual("cast_ice", ice["anim_trigger"])
        self.assertEqual("cast_arcane", force["anim_trigger"])

    def test_runtime_profile_marks_projectile_and_aoe_telegraph_roles(self):
        owner = _SchoolOwner()

        fireball = owner._spell_runtime_profile(
            "fireball",
            {
                "id": "fireball",
                "damage_type": "fire",
                "cast_time": 0.22,
                "projectile": {"radius": 0.8},
                "effect": {"type": "explosion", "radius": 2.5},
            },
        )
        nova = owner._spell_runtime_profile(
            "nova",
            {
                "id": "nova",
                "damage_type": "arcane",
                "cast_time": 0.25,
                "effect": {"type": "nova", "radius": 6.0},
            },
        )
        heal = owner._spell_runtime_profile(
            "HealingAura",
            {
                "id": "HealingAura",
                "heal_value": 50,
                "cast_time": 0.6,
            },
        )

        self.assertEqual("projectile", fireball["cast_family"])
        self.assertFalse(fireball["telegraph"]["enabled"])
        self.assertEqual("aoe", nova["cast_family"])
        self.assertTrue(nova["telegraph"]["enabled"])
        self.assertEqual("telegraph_aoe", nova["telegraph"]["token"])
        self.assertEqual("support", heal["cast_family"])
        self.assertTrue(heal["telegraph"]["enabled"])
        self.assertEqual("telegraph_support", heal["telegraph"]["token"])

    def test_runtime_profile_marks_meteor_as_projectile_with_impact_telegraph(self):
        owner = _SchoolOwner()

        meteor = owner._spell_runtime_profile(
            "meteor",
            {
                "id": "meteor",
                "damage_type": "fire",
                "cast_time": 0.35,
                "projectile": {"radius": 1.2},
                "effect": {"type": "explosion", "radius": 4.0},
                "runtime": {
                    "telegraph": {
                        "enabled": True,
                        "anchor": "impact",
                        "radius": 4.0,
                    }
                },
            },
        )

        self.assertEqual("projectile", meteor["cast_family"])
        self.assertTrue(meteor["telegraph"]["enabled"])
        self.assertEqual("impact", meteor["telegraph"]["anchor"])
        self.assertEqual(4.0, meteor["telegraph"]["radius"])
        self.assertIn("prepare", meteor["vfx_windows"])
        self.assertIn("release", meteor["vfx_windows"])
        self.assertIn("impact", meteor["vfx_windows"])


if __name__ == "__main__":
    unittest.main()
