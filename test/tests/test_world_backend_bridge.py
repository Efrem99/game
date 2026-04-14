import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import world.sharuan_world as sharuan_world


class _WorldBackendDummy:
    _load_location_meshes_cfg = sharuan_world.SharuanWorld._load_location_meshes_cfg

    def __init__(self):
        self.layout = {}
        self.app = SimpleNamespace(
            data_mgr=SimpleNamespace(
                get_location_meshes_config=lambda: {
                    "location_meshes": [
                        {
                            "id": "backend_gate",
                            "model": "assets/models/world/props/sign_post_1.glb",
                            "location": "training_grounds",
                            "pos": [1, 2, 3],
                        }
                    ]
                }
            )
        )


class WorldBackendBridgeTests(unittest.TestCase):
    def test_location_meshes_cfg_reads_from_data_manager_before_disk(self):
        dummy = _WorldBackendDummy()

        rows = dummy._load_location_meshes_cfg()

        self.assertEqual(1, len(rows))
        self.assertEqual("backend_gate", rows[0]["id"])
        self.assertEqual((1.0, 2.0, 3.0), rows[0]["pos"])


if __name__ == "__main__":
    unittest.main()
