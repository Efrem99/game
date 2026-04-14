import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.data_manager import DataManager


class DataManagerBackendConfigTests(unittest.TestCase):
    def test_data_manager_loads_through_sqlite_msgpack_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            (data_dir / "items").mkdir(parents=True, exist_ok=True)
            (data_dir / "actors").mkdir(parents=True, exist_ok=True)
            (data_dir / "locales").mkdir(parents=True, exist_ok=True)
            (data_dir / "world").mkdir(parents=True, exist_ok=True)
            (data_dir / "logic").mkdir(parents=True, exist_ok=True)
            (data_dir / "combat").mkdir(parents=True, exist_ok=True)
            (data_dir / "audio").mkdir(parents=True, exist_ok=True)

            (data_dir / "data_backend.json").write_text(
                json.dumps(
                    {
                        "backend": "sqlite_msgpack",
                        "sqlite_path": "cache/test_data_store.sqlite3",
                        "auto_build": True,
                    }
                ),
                encoding="utf-8",
            )
            (data_dir / "items" / "potion.json").write_text(
                json.dumps({"id": "health_potion", "name": "Health Potion"}),
                encoding="utf-8",
            )
            (data_dir / "controls.json").write_text(
                json.dumps({"bindings": {"attack_light": "mouse1"}, "movement": {"run_speed": 9.0}}),
                encoding="utf-8",
            )
            (data_dir / "graphics_settings.json").write_text(
                json.dumps({"language": "ru"}),
                encoding="utf-8",
            )
            (data_dir / "ui_strings.json").write_text(json.dumps({"hud": {"combo": "COMBO"}}), encoding="utf-8")
            (data_dir / "actors" / "player.json").write_text(
                json.dumps({"player": {"model": "assets/models/xbot/Xbot.glb"}}),
                encoding="utf-8",
            )
            (data_dir / "locales" / "en.json").write_text(json.dumps({"hud": {"combo": "COMBO"}}), encoding="utf-8")
            (data_dir / "locales" / "ru.json").write_text(json.dumps({"hud": {"combo": "КОМБО"}}), encoding="utf-8")
            (data_dir / "world" / "layout.json").write_text(json.dumps({"locations": []}), encoding="utf-8")
            (data_dir / "world" / "test_scenarios.json").write_text(json.dumps({"scenarios": []}), encoding="utf-8")
            (data_dir / "logic" / "character_brain.json").write_text(json.dumps({}), encoding="utf-8")
            (data_dir / "combat" / "styles.json").write_text(json.dumps({"styles": {}}), encoding="utf-8")
            (data_dir / "audio" / "sound_config.json").write_text(json.dumps({}), encoding="utf-8")

            dm = DataManager(data_dir=data_dir)

            self.assertEqual("sqlite_msgpack", dm.backend_name)
            self.assertEqual("mouse1", dm.get_binding("attack_light"))
            self.assertEqual(9.0, dm.get_move_param("run_speed"))
            self.assertEqual("Health Potion", dm.get_item("health_potion")["name"])
            self.assertEqual("КОМБО", dm.t("hud.combo", "combo"))
            self.assertEqual("assets/models/xbot/Xbot.glb", dm.get_player_config()["model"])


if __name__ == "__main__":
    unittest.main()
