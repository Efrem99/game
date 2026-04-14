import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import (
    normalize_location_door_entries,
    resolve_location_door_transition,
)


class WorldLocationDoorTriggerTests(unittest.TestCase):
    def test_normalize_location_door_entries_filters_invalid_rows(self):
        rows = normalize_location_door_entries(
            [
                {"id": "a", "from": "Castle Courtyard", "to": "Castle Interior", "center": [1, 2, 3], "radius": 2.4},
                {"id": "broken_missing_to", "from": "Castle Courtyard", "center": [0, 0, 0]},
                {"id": "broken_missing_center", "to": "Castle Interior"},
                {"id": "b", "to": "Throne Hall", "center": [5, 6, 7], "radius": 0.1},
            ]
        )
        self.assertEqual(2, len(rows))
        self.assertEqual("a", rows[0]["id"])
        self.assertEqual("castle_courtyard", rows[0]["from_token"])
        self.assertEqual("castle_interior", rows[0]["to_token"])
        self.assertEqual(0.6, rows[1]["radius"])

    def test_resolve_location_door_transition_returns_nearest_matching_door(self):
        doors = normalize_location_door_entries(
            [
                {"id": "door_far", "from": "Castle Courtyard", "to": "Castle Interior", "center": [0.0, 0.0, 0.0], "radius": 4.0},
                {"id": "door_near", "from": "Castle Courtyard", "to": "Throne Hall", "center": [1.0, 0.0, 0.0], "radius": 4.0},
            ]
        )
        hit = resolve_location_door_transition((1.1, 0.0, 0.0), "Castle Courtyard", doors)
        self.assertIsNotNone(hit)
        self.assertEqual("door_near", hit["id"])
        self.assertEqual("Throne Hall", hit["to"])

    def test_resolve_location_door_transition_respects_from_location(self):
        doors = normalize_location_door_entries(
            [
                {"id": "door_interior", "from": "Castle Interior", "to": "Castle Courtyard", "center": [0.0, 0.0, 0.0], "radius": 3.0},
                {"id": "door_open", "to": "Port Market", "center": [0.0, 2.0, 0.0], "radius": 3.0},
            ]
        )
        # The first door is ignored because we're not in Castle Interior.
        hit = resolve_location_door_transition((0.0, 0.2, 0.0), "Castle Courtyard", doors)
        self.assertIsNotNone(hit)
        self.assertEqual("door_open", hit["id"])

    def test_resolve_location_door_transition_returns_none_when_outside_radius(self):
        doors = normalize_location_door_entries(
            [{"id": "door", "to": "Castle Interior", "center": [10.0, 10.0, 0.0], "radius": 1.5}]
        )
        hit = resolve_location_door_transition((0.0, 0.0, 0.0), "", doors)
        self.assertIsNone(hit)


if __name__ == "__main__":
    unittest.main()
