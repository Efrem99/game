import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _DataManager:
    def __init__(self):
        self._items = {
            "hunter_bow": {
                "id": "hunter_bow",
                "weapon_class": "bow",
                "equip_visual": {"style": "bow"},
            },
            "iron_sword": {
                "id": "iron_sword",
                "weapon_class": "sword",
                "equip_visual": {"style": "blade"},
            },
        }

    def get_item(self, item_id):
        payload = self._items.get(str(item_id or "").strip())
        return dict(payload) if isinstance(payload, dict) else None


class _Owner(PlayerCombatMixin):
    def __init__(self):
        self.data_mgr = _DataManager()
        self._equipment_state = {
            "weapon_main": "hunter_bow",
            "offhand": "",
            "chest": "",
            "trinket": "",
        }


class BowAimPolicyTests(unittest.TestCase):
    def test_ranged_weapon_detection_works_for_bow(self):
        owner = _Owner()
        self.assertTrue(
            hasattr(owner, "_is_ranged_weapon_equipped"),
            "PlayerCombatMixin must expose _is_ranged_weapon_equipped",
        )
        self.assertTrue(owner._is_ranged_weapon_equipped())

    def test_aim_mode_prefers_magic_when_spell_slot_selected(self):
        owner = _Owner()
        self.assertTrue(
            hasattr(owner, "_resolve_aim_mode"),
            "PlayerCombatMixin must expose _resolve_aim_mode",
        )
        mode = owner._resolve_aim_mode(selected_label="fireball", aim_pressed=True)
        self.assertEqual("magic", mode)

    def test_aim_mode_uses_bow_for_melee_slot_when_bow_equipped(self):
        owner = _Owner()
        self.assertTrue(
            hasattr(owner, "_resolve_aim_mode"),
            "PlayerCombatMixin must expose _resolve_aim_mode",
        )
        mode = owner._resolve_aim_mode(selected_label="sword", aim_pressed=True)
        self.assertEqual("bow", mode)


if __name__ == "__main__":
    unittest.main()
