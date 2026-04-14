import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VEHICLE_DIR = ROOT / "data" / "vehicles"


class VehicleModelAssetsTests(unittest.TestCase):
    def test_vehicle_kinds_use_real_model_paths(self):
        required = {"horse", "wolf", "stag", "carriage", "ship"}
        for kind in required:
            path = VEHICLE_DIR / f"{kind}.json"
            self.assertTrue(path.exists(), f"missing config: {path}")
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            model_path = str(payload.get("model", "") or "").strip()
            self.assertTrue(model_path, f"{kind} must define model path")
            abs_model = ROOT / model_path
            self.assertTrue(abs_model.exists(), f"{kind} model path not found: {model_path}")


if __name__ == "__main__":
    unittest.main()
