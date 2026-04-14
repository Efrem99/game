import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "data" / "world" / "test_scenarios.json"


class TestScenariosCatalogTests(unittest.TestCase):
    def test_catalog_contains_dozens_of_entries(self):
        payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", [])
        self.assertIsInstance(scenarios, list)
        self.assertGreaterEqual(len(scenarios), 30)

    def test_catalog_entries_have_unique_ids_and_required_fields(self):
        payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", [])
        ids = []
        for row in scenarios:
            self.assertIsInstance(row, dict)
            sid = str(row.get("id", "")).strip()
            profile = str(row.get("profile", "")).strip()
            location = str(row.get("location", "")).strip()
            self.assertTrue(sid)
            self.assertTrue(profile)
            self.assertTrue(location)
            ids.append(sid.lower())
        self.assertEqual(len(ids), len(set(ids)))

    def test_catalog_contains_mechanics_profile_scenario(self):
        payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", [])
        rows = [row for row in scenarios if isinstance(row, dict) and str(row.get("profile", "")).strip().lower() == "mechanics"]
        self.assertGreaterEqual(len(rows), 1)
        locations = {str(row.get("location", "")).strip().lower() for row in rows}
        self.assertIn("training", locations)

    def test_catalog_contains_stealth_climb_profile_scenario(self):
        payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", [])
        rows = [
            row
            for row in scenarios
            if isinstance(row, dict) and str(row.get("profile", "")).strip().lower() == "stealth_climb"
        ]
        self.assertGreaterEqual(len(rows), 1)
        locations = {str(row.get("location", "")).strip().lower() for row in rows}
        self.assertIn("stealth_climb", locations)

    def test_catalog_contains_ultimate_sandbox_profile_scenario(self):
        payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", [])
        rows = [
            row
            for row in scenarios
            if isinstance(row, dict) and str(row.get("profile", "")).strip().lower() == "ultimate_sandbox"
        ]
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("ultimate_sandbox_01", str(row.get("id", "")).strip().lower())
        self.assertEqual("ultimate_sandbox", str(row.get("location", "")).strip().lower())

    def test_catalog_contains_minimalist_parkour_variant(self):
        payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", [])
        match = [
            row
            for row in scenarios
            if isinstance(row, dict)
            and str(row.get("id", "")).strip().lower() == "parkour_07"
            and str(row.get("note", "")).strip().lower() == "parkour_minimalist_lane"
        ]
        self.assertEqual(1, len(match))


if __name__ == "__main__":
    unittest.main()
