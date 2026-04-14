import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.save_manager import SaveManager


class _DummyActor:
    def __init__(self):
        self._pos = SimpleNamespace(x=1.0, y=2.0, z=3.0)

    def getPos(self, render=None):
        del render
        return self._pos

    def setPos(self, x, y=None, z=None):
        if y is None and z is None:
            self._pos = x
        else:
            self._pos = SimpleNamespace(x=float(x), y=float(y), z=float(z))


class _DummyQuestMgr:
    def __init__(self):
        self.active_quests = {}
        self.completed_quests = set()


class _DummyDataMgr:
    def __init__(self):
        self._language = "en"

    def get_language(self):
        return self._language

    def set_language(self, value):
        self._language = str(value)
        return True


class _DummyPlayer:
    def __init__(self):
        self.actor = _DummyActor()
        self.imported_combat = None

    def export_combat_runtime_state(self):
        return {"combo_state": {"count": 2, "style": "sword", "kind": "melee", "remain": 0.4}}

    def export_equipment_state(self):
        return {"weapon_main": "training_sword"}

    def import_combat_runtime_state(self, payload):
        self.imported_combat = dict(payload or {})


class _DummyApp:
    def __init__(self, save_dir, backend_config=None):
        self.profile = {"xp": 12, "gold": 99}
        self.player = _DummyPlayer()
        self.quest_mgr = _DummyQuestMgr()
        self.data_mgr = _DummyDataMgr()
        self.world = SimpleNamespace(active_location="Town Center")
        self.vehicle_mgr = None
        self.inventory_ui = None
        self.movement_tutorial = None
        self.skill_tree_mgr = None
        self.char_state = SimpleNamespace(position=SimpleNamespace(x=1.0, y=2.0, z=3.0))
        self.save_mgr = SaveManager(self, save_dir=save_dir, backend_config=backend_config)


class SaveManagerBackendTests(unittest.TestCase):
    def test_sqlite_msgpack_backend_roundtrip_keeps_slot_load_working(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = _DummyApp(
                tmpdir,
                backend_config={
                    "backend": "sqlite_msgpack",
                    "sqlite_path": "save_store.sqlite3",
                    "auto_build": True,
                    "mirror_json": True,
                },
            )
            path = app.save_mgr.save_slot(1)

            self.assertEqual("sqlite_msgpack", app.save_mgr.backend_name)
            self.assertTrue(path.exists())
            self.assertTrue((Path(tmpdir) / "save_store.sqlite3").exists())

            loaded = _DummyApp(
                tmpdir,
                backend_config={
                    "backend": "sqlite_msgpack",
                    "sqlite_path": "save_store.sqlite3",
                    "auto_build": True,
                    "mirror_json": True,
                },
            )
            self.assertTrue(loaded.save_mgr.load_slot(1))
            self.assertEqual(99, loaded.profile["gold"])
            self.assertEqual("Town Center", loaded.world.active_location)
            self.assertIsInstance(loaded.player.imported_combat, dict)

    def test_sqlite_msgpack_backend_imports_existing_legacy_json_slot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            slot_path = Path(tmpdir) / "slot1.json"
            slot_path.write_text(
                json.dumps(
                    {
                        "meta": {
                            "version": 3,
                            "saved_at_utc": "2026-03-28T20:00:00+00:00",
                            "summary": {"xp": 7, "gold": 44, "location": "River Road"},
                        },
                        "player": {"position": [4, 5, 6], "state": {}, "combat": {}},
                        "progression": {"profile": {"xp": 7, "gold": 44}, "language": "ru"},
                        "world": {"active_location": "River Road"},
                        "ui": {"map_state": {"tab": "inventory", "range": 180.0}},
                    }
                ),
                encoding="utf-8",
            )

            app = _DummyApp(
                tmpdir,
                backend_config={
                    "backend": "sqlite_msgpack",
                    "sqlite_path": "save_store.sqlite3",
                    "auto_build": True,
                    "mirror_json": False,
                },
            )

            self.assertTrue(app.save_mgr.load_slot(1))
            self.assertEqual("ru", app.data_mgr.get_language())
            self.assertTrue((Path(tmpdir) / "save_store.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
