import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import app as app_module
from app import XBotApp
from managers.companion_manager import CompanionManager
from managers.save_manager import SaveManager


class _DummyActor:
    def __init__(self, pos=None):
        self._pos = pos or SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def getPos(self, render=None):
        del render
        return self._pos

    def setPos(self, x, y=None, z=None):
        if y is None and z is None:
            self._pos = x
            return
        self._pos = SimpleNamespace(x=float(x), y=float(y), z=float(z))


class _DummyQuestManager:
    def __init__(self):
        self.active_quests = {}
        self.completed_quests = set()


class _DummyTutorialManager:
    def export_state(self):
        return {}

    def import_state(self, payload):
        self.payload = dict(payload or {})


class _DummySkillTreeManager:
    def __init__(self):
        self.state = {"points": 0, "unlocked": {}}

    def export_state(self):
        return {
            "points": int(self.state.get("points", 0)),
            "unlocked": dict(self.state.get("unlocked", {})),
        }

    def import_state(self, payload):
        self.state = {
            "points": int(payload.get("points", 0)),
            "unlocked": dict(payload.get("unlocked", {})),
        }
        return True


class _DummyInventoryUi:
    def __init__(self):
        self.imported_map_state = None
        self.visible = False
        self.last_tab = None

    def export_map_state(self):
        return {"tab": "party", "range": 180.0}

    def import_map_state(self, payload):
        self.imported_map_state = dict(payload or {})

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def _switch_tab(self, tab):
        self.last_tab = str(tab)


class _DummyPauseMenu:
    def __init__(self):
        self.visible = False
        self.loading = None

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def set_loading(self, flag):
        self.loading = bool(flag)


class _DummyAspect2D:
    def __init__(self):
        self.visible = True

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class _DummyHud:
    def __init__(self):
        self.visible = False

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class _ModalStateMgr:
    def __init__(self, state):
        self.current_state = state

    def set_state(self, state):
        self.current_state = state


class _SaveLoadApp:
    def __init__(self, definitions, save_dir):
        self.profile = {"gold": 200}
        self.player = SimpleNamespace(actor=_DummyActor(), gold=0)
        self.quest_mgr = _DummyQuestManager()
        self.data_mgr = SimpleNamespace(get_language=lambda: "en", companions=dict(definitions))
        self.world = SimpleNamespace(active_location="River Road")
        self.vehicle_mgr = None
        self.inventory_ui = _DummyInventoryUi()
        self.movement_tutorial = _DummyTutorialManager()
        self.skill_tree_mgr = _DummySkillTreeManager()
        self.char_state = SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0, z=0.0))
        self.save_mgr = SaveManager(self, save_dir=save_dir)
        self.companion_mgr = CompanionManager(self, definitions=definitions)


class PartySavePersistenceTests(unittest.TestCase):
    def _definitions(self):
        return {
            "emberfox": {
                "name": "Emberfox",
                "kind": "pet",
                "recruitment": {"method": "tame"},
                "support": {"combat_assist": "ember_bolt"},
            },
            "eldrin_elf": {
                "name": "Eldrin",
                "kind": "companion",
                "recruitment": {"method": "hire", "cost": 150},
                "assist": {"combat_assist": "arcane_archery"},
            },
        }

    def test_save_load_roundtrip_preserves_party_roster_and_behavior(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = _SaveLoadApp(self._definitions(), tmpdir)
            self.assertTrue(app.companion_mgr.acquire_member("eldrin_elf", source="hire"))
            self.assertTrue(app.companion_mgr.acquire_member("emberfox", source="tame"))
            self.assertTrue(app.companion_mgr.set_behavior_state("eldrin_elf", "stay"))
            self.assertTrue(app.companion_mgr.set_behavior_state("emberfox", "follow"))

            app.save_mgr.save_slot(1)

            loaded = _SaveLoadApp(self._definitions(), tmpdir)
            loaded.profile = {"gold": 0}
            ok = loaded.save_mgr.load_slot(1)

            self.assertTrue(ok)
            self.assertTrue(loaded.companion_mgr.has_companion("eldrin_elf"))
            self.assertTrue(loaded.companion_mgr.has_pet("emberfox"))
            self.assertEqual("stay", loaded.companion_mgr.get_behavior_state("eldrin_elf"))
            self.assertEqual("follow", loaded.companion_mgr.get_behavior_state("emberfox"))

    def test_save_load_roundtrip_preserves_skill_tree_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = _SaveLoadApp(self._definitions(), tmpdir)
            app.skill_tree_mgr.state = {
                "points": 3,
                "unlocked": {
                    "nova_mastery": True,
                    "ward_shell": True,
                },
            }

            app.save_mgr.save_slot(1)

            loaded = _SaveLoadApp(self._definitions(), tmpdir)
            loaded.skill_tree_mgr.state = {"points": 0, "unlocked": {}}
            ok = loaded.save_mgr.load_slot(1)

            self.assertTrue(ok)
            self.assertEqual(3, loaded.skill_tree_mgr.state["points"])
            self.assertTrue(loaded.skill_tree_mgr.state["unlocked"].get("nova_mastery"))
            self.assertTrue(loaded.skill_tree_mgr.state["unlocked"].get("ward_shell"))


class _ModalDummy:
    GameState = app_module.GameState
    _set_modal_hud_visible = XBotApp._set_modal_hud_visible
    _hide_inventory_ui = XBotApp._hide_inventory_ui

    def __init__(self, state):
        self.state_mgr = _ModalStateMgr(state)
        self.pause_menu = _DummyPauseMenu()
        self.inventory_ui = _DummyInventoryUi()
        self.main_menu = _DummyPauseMenu()
        self.aspect2d = _DummyAspect2D()
        self.hud = _DummyHud()


class ModalUiExclusivityTests(unittest.TestCase):
    def test_inventory_open_hides_pause_and_switches_tab(self):
        self.assertTrue(hasattr(XBotApp, "_show_inventory_ui"))
        dummy = _ModalDummy(app_module.GameState.PAUSED)
        dummy.pause_menu.visible = True

        XBotApp._show_inventory_ui(dummy, tab="party")

        self.assertEqual(app_module.GameState.INVENTORY, dummy.state_mgr.current_state)
        self.assertFalse(dummy.pause_menu.visible)
        self.assertTrue(dummy.inventory_ui.visible)
        self.assertEqual("party", dummy.inventory_ui.last_tab)

    def test_inventory_open_hides_main_menu_too(self):
        dummy = _ModalDummy(app_module.GameState.PAUSED)
        dummy.main_menu.visible = True

        XBotApp._show_inventory_ui(dummy, tab="inventory")

        self.assertFalse(dummy.main_menu.visible)

    def test_pause_open_hides_inventory(self):
        self.assertTrue(hasattr(XBotApp, "_show_pause_menu"))
        dummy = _ModalDummy(app_module.GameState.INVENTORY)
        dummy.inventory_ui.visible = True

        XBotApp._show_pause_menu(dummy)

        self.assertEqual(app_module.GameState.PAUSED, dummy.state_mgr.current_state)
        self.assertFalse(dummy.inventory_ui.visible)
        self.assertTrue(dummy.pause_menu.visible)

    def test_pause_open_hides_main_menu_too(self):
        dummy = _ModalDummy(app_module.GameState.INVENTORY)
        dummy.main_menu.visible = True

        XBotApp._show_pause_menu(dummy)

        self.assertFalse(dummy.main_menu.visible)

    def test_hide_all_menus_closes_inventory_too(self):
        dummy = _ModalDummy(app_module.GameState.INVENTORY)
        dummy.main_menu.visible = True
        dummy.pause_menu.visible = True
        dummy.inventory_ui.visible = True

        XBotApp._hide_all_menus(dummy)

        self.assertFalse(dummy.main_menu.visible)
        self.assertFalse(dummy.pause_menu.visible)
        self.assertFalse(dummy.inventory_ui.visible)

    def test_show_inventory_hides_hud_and_selects_requested_tab(self):
        dummy = _ModalDummy(app_module.GameState.PLAYING)
        dummy.hud.visible = True

        ok = XBotApp._show_inventory_ui(dummy, tab="journal")

        self.assertTrue(ok)
        self.assertEqual(app_module.GameState.INVENTORY, dummy.state_mgr.current_state)
        self.assertFalse(dummy.hud.visible)
        self.assertTrue(dummy.inventory_ui.visible)
        self.assertEqual("journal", dummy.inventory_ui.last_tab)

    def test_hide_inventory_restores_hud_when_returning_to_gameplay(self):
        dummy = _ModalDummy(app_module.GameState.INVENTORY)
        dummy.inventory_ui.visible = True

        ok = XBotApp._hide_inventory_ui(dummy)

        self.assertTrue(ok)
        self.assertEqual(app_module.GameState.PLAYING, dummy.state_mgr.current_state)
        self.assertTrue(dummy.hud.visible)
        self.assertFalse(dummy.aspect2d.visible)

    def test_hide_pause_restores_hud_when_returning_to_gameplay(self):
        dummy = _ModalDummy(app_module.GameState.PAUSED)
        dummy.pause_menu.visible = True

        ok = XBotApp._hide_pause_menu(dummy)

        self.assertTrue(ok)
        self.assertEqual(app_module.GameState.PLAYING, dummy.state_mgr.current_state)
        self.assertTrue(dummy.hud.visible)
        self.assertFalse(dummy.aspect2d.visible)


class VideoBotModalTimelineTests(unittest.TestCase):
    class _VideoBotDummy:
        GameState = app_module.GameState

        def __init__(self, state, plan, event_idx=0):
            self.player = object()
            self.state_mgr = _ModalStateMgr(state)
            self._video_bot_plan = list(plan)
            self._video_bot_event_idx = int(event_idx)
            self.loading_screen = SimpleNamespace(frame=SimpleNamespace(isHidden=lambda: True))

    def test_video_bot_can_continue_inventory_ui_sequence_while_inventory_is_open(self):
        dummy = self._VideoBotDummy(
            app_module.GameState.INVENTORY,
            [{"type": "ui_action", "action": "inventory_tab", "tab": "map"}],
        )

        self.assertTrue(XBotApp._video_bot_can_drive_gameplay(dummy))

    def test_video_bot_can_continue_pause_ui_sequence_while_pause_is_open(self):
        dummy = self._VideoBotDummy(
            app_module.GameState.PAUSED,
            [{"type": "ui_action", "action": "pause_open_settings"}],
        )

        self.assertTrue(XBotApp._video_bot_can_drive_gameplay(dummy))

    def test_video_bot_still_blocks_gameplay_actions_while_inventory_is_open(self):
        dummy = self._VideoBotDummy(
            app_module.GameState.INVENTORY,
            [{"type": "tap", "action": "jump"}],
        )

        self.assertFalse(XBotApp._video_bot_can_drive_gameplay(dummy))


if __name__ == "__main__":
    unittest.main()
