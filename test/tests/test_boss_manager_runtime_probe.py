import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import BossManager


class _ProbeApp:
    def __init__(self):
        self.render = object()
        self.probes = []

    def _debug_probe_runtime_node(self, label, node, reference=None):
        self.probes.append((label, node, reference))
        return True


class _EnemyUnitStub:
    def __init__(self, app, cfg):
        self.app = app
        self.cfg = dict(cfg)
        self.root = f"root:{self.cfg.get('id', 'enemy')}"


class BossManagerRuntimeProbeTests(unittest.TestCase):
    def test_load_probes_each_spawned_enemy_root(self):
        app = _ProbeApp()
        payload = {"enemies": [{"id": "fire_elemental_1", "kind": "fire_elemental"}]}
        state_maps = {"defaults": {}, "units": {}}

        with patch("entities.boss_manager._safe_read_json", side_effect=[payload, state_maps]), patch(
            "entities.boss_manager.EnemyUnit", _EnemyUnitStub
        ):
            manager = BossManager(app, cfg_path="ignored.json", state_map_path="ignored_states.json")

        self.assertEqual(1, len(manager.units))
        self.assertEqual(
            [("enemy_spawn:fire_elemental_1", "root:fire_elemental_1", app.render)],
            app.probes,
        )


if __name__ == "__main__":
    unittest.main()
