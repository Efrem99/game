import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.location_meshes import normalize_location_mesh_entries


class LocationMeshesConfigTests(unittest.TestCase):
    def test_normalize_location_mesh_entry_with_scalar_scale(self):
        layout = {
            "location_meshes": [
                {
                    "id": "sherward_room",
                    "model": "assets\\models\\locations\\sherward_room.glb",
                    "position": [6, 74, 24],
                    "hpr": [180, 0, 0],
                    "scale": 1.25,
                }
            ]
        }
        rows = normalize_location_mesh_entries(layout)
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("sherward_room", row["id"])
        self.assertEqual("assets/models/locations/sherward_room.glb", row["model"])
        self.assertEqual((6.0, 74.0, 24.0), row["pos"])
        self.assertEqual((180.0, 0.0, 0.0), row["hpr"])
        self.assertEqual((1.25, 1.25, 1.25), row["scale"])
        self.assertTrue(row["is_platform"])

    def test_skip_rows_without_model(self):
        layout = {
            "location_meshes": [
                {"id": "bad"},
                {"id": "ok", "model": "assets/models/locations/castle_keep.fbx"},
            ]
        }
        rows = normalize_location_mesh_entries(layout)
        self.assertEqual(1, len(rows))
        self.assertEqual("ok", rows[0]["id"])

    def test_accept_pos_alias_and_non_platform(self):
        layout = {
            "location_meshes": [
                {
                    "id": "castle_block",
                    "model": "assets/models/locations/castle_block.fbx",
                    "pos": [0, 78, 23],
                    "rotation": [0, 0, 0],
                    "scale": [1.0, 1.2, 1.0],
                    "is_platform": False,
                    "label": "Castle Blockout",
                }
            ]
        }
        rows = normalize_location_mesh_entries(layout)
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual((0.0, 78.0, 23.0), row["pos"])
        self.assertEqual((0.0, 0.0, 0.0), row["hpr"])
        self.assertEqual((1.0, 1.2, 1.0), row["scale"])
        self.assertFalse(row["is_platform"])
        self.assertEqual("Castle Blockout", row["label"])

    def test_disabled_rows_are_ignored(self):
        layout = {
            "location_meshes": [
                {"id": "off", "enabled": False, "model": "assets/models/locations/off.glb"},
                {"id": "on", "enabled": True, "model": "assets/models/locations/on.glb"},
            ]
        }
        rows = normalize_location_mesh_entries(layout)
        self.assertEqual(1, len(rows))
        self.assertEqual("on", rows[0]["id"])


if __name__ == "__main__":
    unittest.main()
