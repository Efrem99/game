import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.dialog_cinematic_manager import DialogCinematicManager
from managers.companion_manager import CompanionManager


class _FakeQuestManager:
    def __init__(self, active=None, complete=None):
        self._active = set(active or [])
        self._complete = set(complete or [])

    def is_active(self, quest_id):
        return str(quest_id) in self._active

    def is_complete(self, quest_id):
        return str(quest_id) in self._complete


class _FakeCompanionApp:
    def __init__(self, definitions=None, gold=0):
        self.profile = {"gold": int(gold)}
        self.data_mgr = type("DataManager", (), {"companions": definitions or {}})()
        self.quest_mgr = _FakeQuestManager(active={"q_first_blood"}, complete={"q_opening_done"})


class _FakeDialogApp:
    def __init__(self, companion_mgr=None, quest_mgr=None, profile=None):
        self.companion_mgr = companion_mgr
        self.quest_mgr = quest_mgr or _FakeQuestManager()
        self.profile = profile if isinstance(profile, dict) else {}
        self.player = type("Player", (), {"level": 4, "inventory": None})()
        self.shop_manager = None


class CompanionManagerTests(unittest.TestCase):
    def _definitions(self):
        return {
            "emberfox": {
                "name": "Emberfox",
                "kind": "pet",
                "recruitment": {
                    "method": "tame",
                    "encounter": "roadside",
                },
                "support": {
                    "healing_pulse": 0.15,
                    "combat_assist": "ember_bolt",
                },
            },
            "mira_wayfarer": {
                "name": "Mira Wayfarer",
                "kind": "companion",
                "recruitment": {
                    "method": "hire",
                    "cost": 120,
                    "dialogue_required": True,
                },
                "assist": {
                    "combat_assist": "crossbow_cover_fire",
                },
            },
            "adrian": {
                "name": "Adrian",
                "kind": "companion",
                "recruitment": {
                    "method": "rescue",
                },
                "assist": {
                    "combat_assist": "training_blade_support",
                },
            },
            "torvin": {
                "name": "Torvin",
                "kind": "companion",
                "recruitment": {
                    "method": "story",
                },
                "assist": {
                    "combat_assist": "shield_wall",
                },
            },
        }

    def test_hiring_companion_spends_gold_and_sets_active_companion(self):
        app = _FakeCompanionApp(definitions=self._definitions(), gold=180)
        manager = CompanionManager(app)

        acquired = manager.acquire_member("mira_wayfarer", source="hire")

        self.assertTrue(acquired)
        self.assertEqual(60, app.profile["gold"])
        self.assertTrue(manager.has_companion("mira_wayfarer"))
        self.assertEqual("mira_wayfarer", manager.get_active_companion_id())
        snapshot = manager.get_party_snapshot()
        self.assertEqual("mira_wayfarer", snapshot["active_companion"]["id"])
        self.assertEqual("companion", snapshot["active_companion"]["kind"])

    def test_taming_pet_sets_active_pet_and_preserves_companion_slot(self):
        app = _FakeCompanionApp(definitions=self._definitions(), gold=40)
        manager = CompanionManager(app)

        acquired = manager.acquire_member("emberfox", source="tame")

        self.assertTrue(acquired)
        self.assertEqual(40, app.profile["gold"])
        self.assertTrue(manager.has_pet("emberfox"))
        self.assertEqual("emberfox", manager.get_active_pet_id())
        snapshot = manager.get_party_snapshot()
        self.assertEqual("emberfox", snapshot["active_pet"]["id"])
        self.assertEqual("ember_bolt", snapshot["active_pet"]["support"]["combat_assist"])

    def test_wrong_recruitment_source_is_rejected(self):
        app = _FakeCompanionApp(definitions=self._definitions(), gold=200)
        manager = CompanionManager(app)

        acquired = manager.acquire_member("mira_wayfarer", source="rescue")

        self.assertFalse(acquired)
        self.assertFalse(manager.has_companion("mira_wayfarer"))
        self.assertEqual(200, app.profile["gold"])

    def test_can_recruit_hire_companion_requires_enough_gold(self):
        app = _FakeCompanionApp(definitions=self._definitions(), gold=40)
        manager = CompanionManager(app)

        self.assertFalse(manager.can_recruit("mira_wayfarer", source="hire"))
        self.assertTrue(manager.can_recruit("emberfox", source="tame"))

    def test_story_and_rescue_sources_are_persisted_in_profile(self):
        app = _FakeCompanionApp(definitions=self._definitions(), gold=90)
        manager = CompanionManager(app)

        self.assertTrue(manager.acquire_member("adrian", source="rescue"))
        self.assertTrue(manager.acquire_member("torvin", source="story"))

        party = app.profile.get("party", {})
        companions = party.get("companions", {})
        self.assertEqual("rescue", companions["owned"]["adrian"]["source"])
        self.assertEqual("story", companions["owned"]["torvin"]["source"])

    def test_behavior_defaults_to_follow_and_persists_on_owned_members(self):
        app = _FakeCompanionApp(definitions=self._definitions(), gold=180)
        manager = CompanionManager(app)

        self.assertTrue(manager.acquire_member("mira_wayfarer", source="hire"))
        self.assertEqual("follow", manager.get_behavior_state("mira_wayfarer"))
        self.assertTrue(manager.set_behavior_state("mira_wayfarer", "stay"))
        self.assertEqual("stay", manager.get_behavior_state("mira_wayfarer"))

        snapshot = manager.get_party_snapshot()
        self.assertEqual("stay", snapshot["active_companion"]["behavior"])


class DialogCompanionIntegrationTests(unittest.TestCase):
    def _dialog_manager(self, app):
        mgr = DialogCinematicManager.__new__(DialogCinematicManager)
        mgr.app = app
        mgr._npc_id = "mira_wayfarer"
        return mgr

    def test_dialog_condition_uses_quest_mgr_alias(self):
        app = _FakeDialogApp(quest_mgr=_FakeQuestManager(active={"q_first_blood"}))
        mgr = self._dialog_manager(app)

        self.assertTrue(mgr._check_condition("quest_active:q_first_blood"))
        self.assertFalse(mgr._check_condition("quest_active:q_missing"))

    def test_dialog_condition_can_check_companion_recruitment(self):
        companion_app = _FakeCompanionApp(
            definitions=CompanionManagerTests()._definitions(),
            gold=150,
        )
        companion_mgr = CompanionManager(companion_app)
        app = _FakeDialogApp(companion_mgr=companion_mgr)
        mgr = self._dialog_manager(app)

        self.assertTrue(mgr._check_condition("can_recruit:mira_wayfarer"))
        self.assertFalse(mgr._check_condition("has_companion:mira_wayfarer"))

    def test_dialog_actions_delegate_to_companion_manager(self):
        companion_app = _FakeCompanionApp(
            definitions=CompanionManagerTests()._definitions(),
            gold=160,
        )
        companion_mgr = CompanionManager(companion_app)
        app = _FakeDialogApp(companion_mgr=companion_mgr)
        mgr = self._dialog_manager(app)

        mgr._execute_action("hire_companion:mira_wayfarer")
        mgr._execute_action("tame_pet:emberfox")
        mgr._execute_action("rescue_companion:adrian")

        self.assertTrue(companion_mgr.has_companion("mira_wayfarer"))
        self.assertTrue(companion_mgr.has_pet("emberfox"))
        self.assertTrue(companion_mgr.has_companion("adrian"))
        self.assertEqual("adrian", companion_mgr.get_active_companion_id())
        self.assertEqual("emberfox", companion_mgr.get_active_pet_id())

    def test_dialog_give_gold_updates_profile_for_followup_hire(self):
        companion_app = _FakeCompanionApp(
            definitions=CompanionManagerTests()._definitions(),
            gold=0,
        )
        companion_mgr = CompanionManager(companion_app)
        shared_profile = companion_app.profile
        app = _FakeDialogApp(companion_mgr=companion_mgr, profile=shared_profile)
        mgr = self._dialog_manager(app)

        mgr._execute_action("give_gold:120")

        self.assertEqual(120, shared_profile["gold"])
        self.assertTrue(mgr._check_condition("can_recruit:mira_wayfarer"))


if __name__ == "__main__":
    unittest.main()
