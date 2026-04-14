import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import build_castle_interior_prop_plan


class CastleInteriorPropPlanTests(unittest.TestCase):
    def _prop_ids(self, room_id):
        rows = build_castle_interior_prop_plan(room_id)
        self.assertIsInstance(rows, list)
        out = set()
        for row in rows:
            self.assertIsInstance(row, dict)
            out.add(str(row.get("id", "")).strip().lower())
        return out

    def test_prince_chamber_contains_furniture_set(self):
        prop_ids = self._prop_ids("prince_chamber")
        for required in {"bed_frame", "wardrobe", "writing_desk", "room_rug"}:
            self.assertIn(required, prop_ids)

    def test_world_map_gallery_contains_map_showcase(self):
        prop_ids = self._prop_ids("world_map_gallery")
        for required in {"map_table", "map_wall_frame_l", "map_wall_frame_r"}:
            self.assertIn(required, prop_ids)

    def test_throne_hall_contains_grand_dressing(self):
        prop_ids = self._prop_ids("throne_hall")
        for required in {"carpet_run", "chandelier_ring", "guest_bench_l", "guest_bench_r"}:
            self.assertIn(required, prop_ids)


if __name__ == "__main__":
    unittest.main()
