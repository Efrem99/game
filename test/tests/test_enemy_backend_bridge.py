import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import BossManager
from entities.dragon_boss import DragonBoss


class _Backend:
    def __init__(self, files=None):
        self._files = dict(files or {})

    def load_file(self, rel_path):
        return self._files.get(str(rel_path), {})


class EnemyBackendBridgeTests(unittest.TestCase):
    def test_boss_manager_loads_roster_and_state_maps_from_backend_only_paths(self):
        backend = _Backend(
            files={
                "enemies/backend_only_roster.json": {
                    "enemies": [{"id": "golem_alpha", "kind": "golem", "name": "Golem Alpha"}]
                },
                "enemies/backend_only_state_maps.json": {
                    "defaults": {"golem": {"stats": {"max_hp": 777}}},
                    "units": {},
                },
            }
        )
        app = SimpleNamespace(
            data_mgr=SimpleNamespace(backend=backend, data_dir=ROOT / "data"),
            project_root=str(ROOT),
        )

        manager = object.__new__(BossManager)
        manager.app = app
        manager.cfg_path = "enemies/backend_only_roster.json"
        manager.state_map_path = "enemies/backend_only_state_maps.json"
        manager.units = []
        manager._core_runtime = None
        manager._logged_core_runtime_path = False

        with patch("entities.boss_manager.EnemyUnit", side_effect=lambda app, cfg: SimpleNamespace(cfg=cfg)):
            manager._load()

        self.assertEqual(1, len(manager.units))
        self.assertEqual("golem_alpha", manager.units[0].cfg["id"])
        self.assertEqual(777, manager.units[0].cfg["stats"]["max_hp"])

    def test_dragon_boss_loads_config_bundle_from_backend_only_paths(self):
        backend = _Backend(
            files={
                "enemies/backend_only_dragon.json": {"spawn_point": [10, 11, 12]},
                "actors/backend_only_dragon_animations.json": {"animations": {"idle": "dragon_idle"}},
                "states/backend_only_dragon_states.json": {"states": [{"name": "idle"}]},
            }
        )
        app = SimpleNamespace(
            data_mgr=SimpleNamespace(backend=backend, data_dir=ROOT / "data"),
            project_root=str(ROOT),
        )
        dragon = object.__new__(DragonBoss)
        dragon.app = app

        with patch.object(DragonBoss, "_dragon_enemy_rel_path", return_value="enemies/backend_only_dragon.json"), \
             patch.object(DragonBoss, "_dragon_anim_rel_path", return_value="actors/backend_only_dragon_animations.json"), \
             patch.object(DragonBoss, "_dragon_state_rel_path", return_value="states/backend_only_dragon_states.json"):
            cfg = dragon._load_dragon_config()

        self.assertEqual([10, 11, 12], cfg["enemy"]["spawn_point"])
        self.assertEqual("dragon_idle", cfg["anim"]["animations"]["idle"])
        self.assertEqual("idle", cfg["state"]["states"][0]["name"])


if __name__ == "__main__":
    unittest.main()
