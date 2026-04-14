import sys
import types
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if "utils.core_runtime" not in sys.modules:
    core_runtime_mod = types.ModuleType("utils.core_runtime")
    core_runtime_mod.gc = None
    core_runtime_mod.HAS_CORE = False
    sys.modules["utils.core_runtime"] = core_runtime_mod

from entities.player import Player
from entities.player_movement_mixin import PlayerMovementMixin


class _Node:
    def __init__(self, name):
        self.name = name
        self.visible = True
        self.scale = None
        self.color = None
        self.parent = None
        self.children = []
        self.pos = None
        self.hpr = None

    def attachNewNode(self, name):
        node = _Node(name)
        node.parent = self
        self.children.append(node)
        return node

    def getChildren(self):
        return list(self.children)

    def removeNode(self):
        if self.parent is not None:
            self.parent.children = [child for child in self.parent.children if child is not self]
            self.parent = None

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


class _BuildVisualDummy:
    _build_sword = Player._build_sword

    def __init__(self):
        self.created = []

    def _make_box(self, _parent, name, _sx, _sy, _sz, _color):
        node = _Node(name)
        node.transparency_calls = 0
        node.light_off_calls = 0

        def _set_transparency(*_args, **_kwargs):
            node.transparency_calls += 1

        def _set_light_off(*_args, **_kwargs):
            node.light_off_calls += 1

        node.setTransparency = _set_transparency
        node.setLightOff = _set_light_off
        self.created.append(node)
        return node


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
    _build_sword = Player._build_sword
    _build_shield = Player._build_shield
    _build_armor = Player._build_armor
    _build_trinket = Player._build_trinket
    _build_equipment_visuals = Player._build_equipment_visuals
    _apply_runtime_clothing_visuals = lambda self: None
    _set_weapon_drawn = Player._set_weapon_drawn
    _update_weapon_sheath = PlayerMovementMixin._update_weapon_sheath
    _slot_alias = Player._slot_alias
    _safe_color4 = Player._safe_color4
    _resolve_attach_point = Player._resolve_attach_point
    _clear_visual_children = Player._clear_visual_children
    _coerce_equipment_visual_style = Player._coerce_equipment_visual_style
    _equipment_pose_profile = Player._equipment_pose_profile
    _build_weapon_visual = Player._build_weapon_visual
    _build_offhand_visual = Player._build_offhand_visual
    _build_armor_visual = Player._build_armor_visual
    _build_trinket_visual = Player._build_trinket_visual
    _refresh_equipment_visual_geometry = Player._refresh_equipment_visual_geometry
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
        self._drawn_hold_timer = 0.0
        self._has_weapon_visual = False
        self._has_offhand_visual = False
        self._is_flying = False

        self.actor = _Node("actor")
        self._spine_upper = _Node("spine_upper")
        self._hips = _Node("hips")
        self._sword_hand_anchor = _Node("right_hand")
        self._shield_hand_anchor = _Node("left_hand")
        self._sword_sheath_anchor = _Node("hip_left")

        self._sword_node = _Node("sword_visual")
        self._shield_node = _Node("shield_visual")
        self._armor_node = _Node("armor_visual")
        self._trinket_node = _Node("trinket_visual")
        self._weapon_visual_style = "blade"
        self._offhand_visual_style = "ward"
        self._armor_visual_style = "light"
        self._trinket_visual_style = "charm"

    def _make_box(self, parent, name, _sx, _sy, _sz, _color):
        return parent.attachNewNode(name)

    def _play_sfx(self, *_args, **_kwargs):
        return None

    def _trigger_weapon_ready_transition(self, *_args, **_kwargs):
        return None


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
    def test_build_equipment_visuals_attaches_sheath_anchor_to_hips(self):
        actor = _EquipmentDummy()
        actor._sword_sheath_anchor = None

        actor._build_equipment_visuals()

        self.assertIs(actor._sword_sheath_anchor.parent, actor._hips)

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

    def test_sword_builder_skips_emissive_glow_mesh(self):
        dummy = _BuildVisualDummy()
        parent = _Node("sword_parent")
        dummy._build_sword(parent)
        names = [node.name for node in dummy.created]
        self.assertNotIn("sword_glow", names)
        self.assertIn("sword_blade", names)

    def test_starter_leather_armor_uses_neutral_steel_palette(self):
        path = ROOT / "data" / "items" / "armor" / "leather_armor.json"
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        visual = payload.get("equip_visual", {})
        color = visual.get("color", [])
        self.assertEqual([0.78, 0.80, 0.86, 1.0], color)

    def test_drawn_weapon_stays_in_hand_during_flight_instead_of_auto_sheathing(self):
        actor = _EquipmentDummy()
        actor._has_weapon_visual = True
        actor._set_weapon_drawn(True, reset_timer=True)
        actor._drawn_hold_timer = 0.0
        actor._is_flying = True

        actor._update_weapon_sheath(0.25)

        self.assertTrue(actor._weapon_drawn)
        self.assertIs(actor._sword_node.parent, actor._sword_hand_anchor)


if __name__ == "__main__":
    unittest.main()
