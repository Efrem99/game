import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_json(rel_path):
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8-sig"))


class PartyWorldEncounterDataTests(unittest.TestCase):
    def test_party_encounters_reference_real_members_npcs_and_dialogues(self):
        companions = _load_json("data/companions.json")
        npcs = _load_json("data/npcs.json")
        layout = _load_json("data/world/layout.json")
        encounter_rows = layout.get("party_encounters", [])

        self.assertIsInstance(encounter_rows, list)
        self.assertGreaterEqual(len(encounter_rows), 5)

        dialogue_dir = ROOT / "data" / "dialogues"
        for row in encounter_rows:
            self.assertIsInstance(row, dict)
            member_id = str(row.get("member_id", "") or "").strip().lower()
            npc_id = str(row.get("npc_id", member_id) or "").strip().lower()
            zone_id = str(row.get("zone_id", "") or "").strip().lower()
            self.assertIn(member_id, companions)
            self.assertIn(npc_id, npcs)
            self.assertTrue(zone_id)

            dialogue_id = str(npcs[npc_id].get("dialogue", "") or "").strip()
            self.assertTrue(dialogue_id)
            self.assertTrue((dialogue_dir / f"{dialogue_id}.json").exists(), dialogue_id)

    def test_party_encounters_fit_declared_zone_radius(self):
        npcs = _load_json("data/npcs.json")
        layout = _load_json("data/world/layout.json")
        zones = {
            str(row.get("id", "") or "").strip().lower(): row
            for row in layout.get("zones", [])
            if isinstance(row, dict)
        }

        for row in layout.get("party_encounters", []):
            if not isinstance(row, dict):
                continue
            zone = zones.get(str(row.get("zone_id", "") or "").strip().lower())
            self.assertIsNotNone(zone)
            npc_id = str(row.get("npc_id", row.get("member_id", "")) or "").strip().lower()
            self.assertIn(npc_id, npcs)
            pos = npcs[npc_id].get("pos", [])
            center = zone.get("center", [])
            self.assertGreaterEqual(len(pos), 3)
            self.assertGreaterEqual(len(center), 2)
            radius = float(zone.get("radius", 0.0) or 0.0)
            dx = float(pos[0]) - float(center[0])
            dy = float(pos[1]) - float(center[1])
            self.assertLessEqual((dx * dx) + (dy * dy), (radius * radius))

    def test_companion_recruitment_locations_cover_world_encounter_zones(self):
        companions = _load_json("data/companions.json")
        layout = _load_json("data/world/layout.json")

        for row in layout.get("party_encounters", []):
            if not isinstance(row, dict):
                continue
            member_id = str(row.get("member_id", "") or "").strip().lower()
            zone_id = str(row.get("zone_id", "") or "").strip().lower()
            self.assertIn(member_id, companions)
            recruitment = companions[member_id].get("recruitment", {})
            locations = {
                str(token or "").strip().lower()
                for token in recruitment.get("locations", [])
            }
            self.assertIn(zone_id, locations)


if __name__ == "__main__":
    unittest.main()
