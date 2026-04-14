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
        self.name = str(name)
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
        if self.parent is not None:
            self.parent.children = [child for child in self.parent.children if child is not self]
        self.parent = node
        if self not in node.children:
            node.children.append(self)

    def setPos(self, *value):
        self.pos = tuple(value)

    def setHpr(self, *value):
        self.hpr = tuple(value)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class _StyleBuildDummy:
    _slot_alias = Player._slot_alias

    def _make_box(self, parent, name, _sx, _sy, _sz, _color):
        return parent.attachNewNode(name)


class _FakeDataManager:
    def __init__(self):
        self._items = {
            "hunter_bow": {
                "id": "hunter_bow",
                "slot": "weapon_main",
                "attach_point": "right_hand",
                "equip_visual": {
                    "style": "bow",
                    "scale": 1.08,
                    "color": [0.58, 0.44, 0.32, 1.0],
                },
                "weapon_class": "bow",
            },
            "royal_armor": {
                "id": "royal_armor",
                "slot": "chest",
                "attach_point": "spine_upper",
                "equip_visual": {
                    "style": "heavy",
                    "scale": 1.06,
                    "color": [0.92, 0.92, 1.0, 1.0],
                },
            },
            "rune_charm": {
                "id": "rune_charm",
                "slot": "trinket",
                "attach_point": "spine_upper",
                "equip_visual": {
                    "style": "charm",
                    "scale": 0.55,
                    "color": [0.90, 0.90, 0.95, 1.0],
                },
            },
        }

    def get_item(self, item_id):
        payload = self._items.get(str(item_id or "").strip())
        return dict(payload) if isinstance(payload, dict) else None


class _EquipmentStyleDummy:
    _slot_alias = Player._slot_alias
    _safe_color4 = Player._safe_color4
    _resolve_attach_point = Player._resolve_attach_point
    _apply_equipment_visuals = Player._apply_equipment_visuals

    def __init__(self):
        self.data_mgr = _FakeDataManager()
        self._equipment_state = {
            "weapon_main": "hunter_bow",
            "offhand": "",
            "chest": "royal_armor",
            "trinket": "rune_charm",
        }
        self._weapon_visual_style = ""
        self._offhand_visual_style = ""
        self._armor_visual_style = ""
        self._trinket_visual_style = ""
        self._has_weapon_visual = False
        self._has_offhand_visual = False

        self.actor = _Node("actor")
        self._spine_upper = _Node("spine_upper")
        self._sword_hand_anchor = _Node("right_hand")
        self._shield_hand_anchor = _Node("left_hand")
        self._sword_sheath_anchor = _Node("hip_left")
        self._shield_sheath_anchor = _Node("back")

        self._sword_node = _Node("sword_visual")
        self._shield_node = _Node("shield_visual")
        self._armor_node = _Node("armor_visual")
        self._trinket_node = _Node("trinket_visual")

    def _make_box(self, parent, name, _sx, _sy, _sz, _color):
        return parent.attachNewNode(name)


class PlayerEquipmentStyleVisualTests(unittest.TestCase):
    def test_bow_builder_creates_bow_specific_parts(self):
        method = getattr(Player, "_build_weapon_visual", None)
        self.assertTrue(callable(method), "Player must define _build_weapon_visual")

        dummy = _StyleBuildDummy()
        parent = _Node("weapon_root")
        method(dummy, parent, "bow")

        names = [child.name for child in parent.getChildren()]
        self.assertIn("bow_limb_top", names)
        self.assertIn("bow_string", names)
        self.assertNotIn("sword_blade", names)

    def test_heavy_armor_builder_creates_pauldrons(self):
        method = getattr(Player, "_build_armor_visual", None)
        self.assertTrue(callable(method), "Player must define _build_armor_visual")

        dummy = _StyleBuildDummy()
        parent = _Node("armor_root")
        method(dummy, parent, "heavy")

        names = [child.name for child in parent.getChildren()]
        self.assertIn("armor_pauldron_l", names)
        self.assertIn("armor_pauldron_r", names)

    def test_apply_equipment_visuals_rebuilds_style_driven_geometry(self):
        self.assertTrue(hasattr(Player, "_apply_equipment_visuals"))
        self.assertTrue(hasattr(Player, "_build_weapon_visual"))
        self.assertTrue(hasattr(Player, "_build_armor_visual"))
        self.assertTrue(hasattr(Player, "_build_trinket_visual"))

        dummy = _EquipmentStyleDummy()
        dummy._clear_visual_children = Player._clear_visual_children.__get__(dummy, _EquipmentStyleDummy)
        dummy._coerce_equipment_visual_style = Player._coerce_equipment_visual_style.__get__(dummy, _EquipmentStyleDummy)
        dummy._build_weapon_visual = Player._build_weapon_visual.__get__(dummy, _EquipmentStyleDummy)
        dummy._build_offhand_visual = Player._build_offhand_visual.__get__(dummy, _EquipmentStyleDummy)
        dummy._build_armor_visual = Player._build_armor_visual.__get__(dummy, _EquipmentStyleDummy)
        dummy._build_trinket_visual = Player._build_trinket_visual.__get__(dummy, _EquipmentStyleDummy)
        dummy._refresh_equipment_visual_geometry = Player._refresh_equipment_visual_geometry.__get__(dummy, _EquipmentStyleDummy)

        dummy._apply_equipment_visuals()

        weapon_names = [child.name for child in dummy._sword_node.getChildren()]
        armor_names = [child.name for child in dummy._armor_node.getChildren()]
        trinket_names = [child.name for child in dummy._trinket_node.getChildren()]

        self.assertEqual("bow", dummy._weapon_visual_style)
        self.assertEqual("heavy", dummy._armor_visual_style)
        self.assertEqual("charm", dummy._trinket_visual_style)
        self.assertIn("bow_string", weapon_names)
        self.assertIn("armor_pauldron_l", armor_names)
        self.assertIn("trinket_tassel", trinket_names)

    def test_bow_pose_profile_differs_from_blade_pose(self):
        method = getattr(Player, "_equipment_pose_profile", None)
        self.assertTrue(callable(method), "Player must define _equipment_pose_profile")

        dummy = _StyleBuildDummy()
        blade_drawn = method(dummy, "weapon_main", "blade", True)
        bow_drawn = method(dummy, "weapon_main", "bow", True)
        bow_sheathed = method(dummy, "weapon_main", "bow", False)

        self.assertNotEqual(blade_drawn, bow_drawn)
        self.assertEqual("back", bow_sheathed[0])
        self.assertNotEqual(bow_drawn[2], blade_drawn[2])


if __name__ == "__main__":
    unittest.main()
