import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.data_backend import SQLiteMsgpackDataBackend


class SQLiteMsgpackDataBackendTests(unittest.TestCase):
    def test_backend_imports_json_tree_and_loads_single_and_recursive_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            (data_dir / "items").mkdir(parents=True, exist_ok=True)
            (data_dir / "world").mkdir(parents=True, exist_ok=True)
            (data_dir / "items" / "sword.json").write_text(
                json.dumps({"id": "iron_sword", "name": "Iron Sword"}),
                encoding="utf-8",
            )
            (data_dir / "controls.json").write_text(
                json.dumps({"bindings": {"attack_light": "mouse1"}}),
                encoding="utf-8",
            )
            (data_dir / "world" / "layout.json").write_text(
                json.dumps({"locations": [{"id": "town"}]}),
                encoding="utf-8",
            )
            db_path = root / "cache" / "data_store.sqlite3"

            backend = SQLiteMsgpackDataBackend(data_dir=data_dir, db_path=db_path, auto_build=True)

            controls = backend.load_file("controls.json")
            items = backend.load_recursive("items")
            layout = backend.load_file("world/layout.json")

            self.assertEqual("mouse1", controls["bindings"]["attack_light"])
            self.assertIn("iron_sword", items)
            self.assertEqual("Iron Sword", items["iron_sword"]["name"])
            self.assertEqual("town", layout["locations"][0]["id"])
            self.assertTrue(db_path.exists())

    def test_save_file_updates_json_source_and_sqlite_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "controls.json").write_text(
                json.dumps({"bindings": {"attack_thrust": "none"}}),
                encoding="utf-8",
            )
            db_path = root / "cache" / "data_store.sqlite3"
            backend = SQLiteMsgpackDataBackend(data_dir=data_dir, db_path=db_path, auto_build=True)

            backend.save_file("controls.json", {"bindings": {"attack_thrust": "mouse3"}})

            saved_json = json.loads((data_dir / "controls.json").read_text(encoding="utf-8"))
            loaded = backend.load_file("controls.json")
            with closing(sqlite3.connect(str(db_path))) as conn:
                row_count = conn.execute("SELECT COUNT(*) FROM entries WHERE path = 'controls.json'").fetchone()[0]

            self.assertEqual("mouse3", saved_json["bindings"]["attack_thrust"])
            self.assertEqual("mouse3", loaded["bindings"]["attack_thrust"])
            self.assertEqual(1, row_count)


if __name__ == "__main__":
    unittest.main()
