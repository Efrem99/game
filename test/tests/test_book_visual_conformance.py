import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.book_visual_conformance import (
    evaluate_location_conformance,
    infer_canonical_locations_for_run,
    load_world_snapshot,
    map_runtime_location_to_canonical,
)


class BookVisualConformanceTests(unittest.TestCase):
    def test_runtime_location_mapping_collapses_cave_tokens(self):
        self.assertEqual("town_center", map_runtime_location_to_canonical("town"))
        self.assertEqual("town_center", map_runtime_location_to_canonical("town_center"))
        self.assertEqual("dwarven_caves", map_runtime_location_to_canonical("dwarven_caves_gate"))
        self.assertEqual("dwarven_caves", map_runtime_location_to_canonical("dwarven_caves_halls"))
        self.assertEqual("dwarven_caves", map_runtime_location_to_canonical("dwarven_caves_throne"))
        self.assertEqual("krimora_forest", map_runtime_location_to_canonical("krimora_forest_cage"))
        self.assertEqual("krimora_forest", map_runtime_location_to_canonical("kremor_forest_cage"))
        self.assertIsNone(map_runtime_location_to_canonical("dragon_arena"))

    def test_location_dialogue_probe_infers_expected_book_locations(self):
        locations = infer_canonical_locations_for_run("location_dialogue_probe", "castle_interior")
        expected = {"castle_interior", "port_market", "krimora_forest", "dwarven_caves"}
        self.assertTrue(expected.issubset(set(locations)))

    def test_all_locations_grand_tour_infers_town_and_world_clusters(self):
        locations = infer_canonical_locations_for_run("all_locations_grand_tour", "town")
        expected = {"town_center", "port_market", "castle_interior", "krimora_forest", "dwarven_caves", "old_forest"}
        self.assertTrue(expected.issubset(set(locations)))

    def test_dwarven_caves_pass_with_book_cues_and_world_state(self):
        snapshot = load_world_snapshot(ROOT)
        book_text = (
            "The dwarven caves greeted us with a stone gate. "
            "Inside, torchlight washed across the vaults, the forge thundered nearby, "
            "and a vast throne hall rose at the center."
        )
        row = evaluate_location_conformance("dwarven_caves", book_text, snapshot)
        self.assertEqual("pass", row.get("status"))
        self.assertTrue(bool(row.get("world_ok", False)))

    def test_krimora_fails_when_book_has_no_location_evidence(self):
        snapshot = load_world_snapshot(ROOT)
        book_text = "Abstract notes with no concrete places, visuals, or story landmarks."
        row = evaluate_location_conformance("krimora_forest", book_text, snapshot)
        self.assertEqual("fail", row.get("status"))
        self.assertEqual("book_not_confirmed", row.get("reason"))


if __name__ == "__main__":
    unittest.main()
