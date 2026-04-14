import os
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


class _EnemyUnitStub:
    def __init__(self, app, cfg):
        self.app = app
        self.cfg = dict(cfg)
        self.id = self.cfg.get("id", "enemy")
        self.root = f"root:{self.id}"


class BossManagerDebugRosterFilterTests(unittest.TestCase):
    def test_debug_enemy_roster_filter_keeps_only_matching_entries(self):
        payload = {
            "enemies": [
                {"id": "golem_warden", "kind": "golem"},
                {"id": "shadow_stalker_1", "kind": "shadow"},
                {"id": "goblin_raider_1", "kind": "goblin"},
            ]
        }
        state_maps = {"defaults": {}, "units": {}}
        app = SimpleNamespace(render=object())

        with patch.dict(os.environ, {"XBOT_DEBUG_ENEMY_ROSTER_IDS": "shadow_stalker_1, goblin"}, clear=False):
            with patch("entities.boss_manager._safe_read_json", side_effect=[payload, state_maps]), patch(
                "entities.boss_manager.EnemyUnit", _EnemyUnitStub
            ):
                manager = BossManager(app, cfg_path="ignored.json", state_map_path="ignored_states.json")

        self.assertEqual(["shadow_stalker_1", "goblin_raider_1"], [unit.id for unit in manager.units])


if __name__ == "__main__":
    unittest.main()
