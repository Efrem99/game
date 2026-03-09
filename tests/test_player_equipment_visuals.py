import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _Node:
    def __init__(self, name):
        self.name = name
        self.visible = True
        self.scale = None
        self.color = None
        self.parent = None
        self.pos = None
        self.hpr = None

    def setScale(self, *value):
        self.scale = value[0] if len(value) == 1 else tuple(value)

    def setColorScale(self, *value):
        self.color = tuple(value)

    def wrtReparentTo(self, node):
        self.parent = node

    def setPos(self, *value):
        self.pos = tuple(value)

    def setHpr(self, *value):
        self.hpr = tuple(value)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class _FakeDataManager:
    def __init__(self):
        self._items = {
            "iron_sword": {
                "id": "iron_sword",
                "slot": "weapon_main",
                "equip_visual": {
                    "style": "blade",
                    "scale": 1.0,
                    "color": [0.82, 0.84, 0.9, 1.0],
                },
            },
            "leather_armor": {
                "id": "leather_armor",
                "slot": "chest",
                "attach_point": "spine_upper",
                "equip_visual": {
                    "style": "light",
                    "scale": 1.0,
                    "color": [0.95, 0.88, 0.78, 1.0],
                },
            },
        }

    def get_item(self, item_id):
        payload = self._items.get(str(item_id or "").strip())
        return dict(payload) if isinstance(payload, dict) else None


class _EquipmentDummy:
    _slot_alias = Player._slot_alias
    _safe_color4 = Player._safe_color4
    _resolve_attach_point = Player._resolve_attach_point
    _apply_equipment_visuals = Player._apply_equipment_visuals
    equip_item = Player.equip_item
    unequip_slot = Player.unequip_slot

    def __init__(self):
        self.data_mgr = _FakeDataManager()
        self._equipment_state = {
            "weapon_main": "",
            "offhand": "",
            "chest": "",
            "trinket": "",
        }
        self._weapon_drawn = False
        self._has_weapon_visual = False
        self._has_offhand_visual = False

        self.actor = _Node("actor")
        self._spine_upper = _Node("spine_upper")
        self._sword_hand_anchor = _Node("right_hand")
        self._shield_hand_anchor = _Node("left_hand")
        self._sword_sheath_anchor = _Node("hip_left")

        self._sword_node = _Node("sword_visual")
        self._shield_node = _Node("shield_visual")
        self._armor_node = _Node("armor_visual")
        self._trinket_node = _Node("trinket_visual")

    def _set_weapon_drawn(self, drawn, reset_timer=False):
        self._weapon_drawn = bool(drawn)


class _StartingEquipmentDummy:
    def __init__(self):
        self.calls = []

    def _player_model_config(self):
        return {
            "starting_items": [
                "iron_sword",
                "leather_armor",
                "",
                None,
                "invalid_item",
            ]
        }

    def equip_item(self, item_id, item_data=None):
        token = str(item_id or "").strip()
        self.calls.append(token)
        if token == "invalid_item":
            return False, "missing_item_data"
        return True, "ok"


class PlayerEquipmentVisualTests(unittest.TestCase):
    def test_chest_armor_becomes_visible_when_equipped(self):
        actor = _EquipmentDummy()
        ok, slot = actor.equip_item("leather_armor")
        self.assertTrue(ok)
        self.assertEqual("chest", slot)
        self.assertTrue(actor._armor_node.visible)
        self.assertEqual((0.95, 0.88, 0.78, 1.0), actor._armor_node.color)

    def test_chest_armor_hides_when_unequipped(self):
        actor = _EquipmentDummy()
        actor.equip_item("leather_armor")
        self.assertTrue(actor.unequip_slot("chest"))
        self.assertFalse(actor._armor_node.visible)

    def test_player_has_starting_equipment_bootstrap(self):
        self.assertTrue(
            hasattr(Player, "_apply_starting_equipment"),
            "Player must define _apply_starting_equipment for automatic starter gear",
        )
        method = getattr(Player, "_apply_starting_equipment")
        dummy = _StartingEquipmentDummy()
        equipped = method(dummy)
        self.assertEqual(["iron_sword", "leather_armor"], equipped)
        self.assertEqual(["iron_sword", "leather_armor", "invalid_item"], dummy.calls)


if __name__ == "__main__":
    unittest.main()
