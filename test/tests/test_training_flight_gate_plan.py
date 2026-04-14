import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import build_training_flight_gate_plan


class TrainingFlightGatePlanTests(unittest.TestCase):
    def test_flight_gate_plan_builds_framed_markers_not_sphere_loops(self):
        rows = build_training_flight_gate_plan()

        self.assertIsInstance(rows, list)
        self.assertEqual(9, len(rows))

        ids = {str(row.get("id", "")).strip().lower() for row in rows}
        for gate_idx in range(3):
            self.assertIn(f"flight_gate_{gate_idx}_left_post", ids)
            self.assertIn(f"flight_gate_{gate_idx}_right_post", ids)
            self.assertIn(f"flight_gate_{gate_idx}_top_beam", ids)

        shapes = {str(row.get("shape", "")).strip().lower() for row in rows}
        self.assertFalse("sphere" in shapes)
        self.assertTrue({"box"}.issubset(shapes))


if __name__ == "__main__":
    unittest.main()
