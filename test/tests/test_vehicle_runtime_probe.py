import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.vehicle_manager import VehicleManager


class _ProbeApp:
    def __init__(self):
        self.render = object()
        self.probes = []

    def _debug_probe_runtime_node(self, label, node, reference=None):
        self.probes.append((label, node, reference))
        return True


class VehicleRuntimeProbeTests(unittest.TestCase):
    def test_spawn_default_vehicles_probes_each_spawned_vehicle_node(self):
        app = _ProbeApp()
        manager = VehicleManager(app)
        manager._load_navigation_zones = lambda: None
        manager._spawn_entries_from_config = lambda: [{"id": "horse_1", "kind": "horse"}]
        manager._spawn_vehicle_from_entry = lambda entry, fallback_index=0: {
            "id": str(entry["id"]),
            "node": f"node:{entry['id']}",
        }

        manager.spawn_default_vehicles()

        self.assertEqual(
            [("vehicle_spawn:horse_1", "node:horse_1", app.render)],
            app.probes,
        )


if __name__ == "__main__":
    unittest.main()
