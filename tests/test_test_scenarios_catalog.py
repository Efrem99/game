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


if __name__ == "__main__":
    unittest.main()
