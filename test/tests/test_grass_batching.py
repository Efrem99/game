import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import (
    compose_grass_batch_rows,
    estimate_grass_tuft_count,
    make_grass_tuft_spec,
)


class GrassBatchingTests(unittest.TestCase):
    def test_make_grass_tuft_spec_is_deterministic_for_seeded_rng(self):
        spec_a = make_grass_tuft_spec(random.Random(12345), 1.0, 2.0, 3.0)
        spec_b = make_grass_tuft_spec(random.Random(12345), 1.0, 2.0, 3.0)
        self.assertEqual(spec_a, spec_b)

    def test_make_grass_tuft_spec_stays_in_expected_ranges(self):
        spec = make_grass_tuft_spec(random.Random(1), 0.0, 0.0, 0.0)
        self.assertGreaterEqual(spec["tint"], 0.88)
        self.assertLessEqual(spec["tint"], 1.06)
        self.assertGreaterEqual(spec["blade_h"], 1.2)
        self.assertLessEqual(spec["blade_h"], 2.3)
        self.assertGreaterEqual(spec["blade_w"], 0.48)
        self.assertLessEqual(spec["blade_w"], 0.76)
        self.assertGreaterEqual(spec["heading"], -180.0)
        self.assertLessEqual(spec["heading"], 180.0)
        self.assertGreaterEqual(spec["tip_scale"], 0.22)
        self.assertLessEqual(spec["tip_scale"], 0.52)
        self.assertGreaterEqual(spec["lean"], 0.02)
        self.assertLessEqual(spec["lean"], 0.24)
        self.assertGreaterEqual(spec["lean_heading"], -180.0)
        self.assertLessEqual(spec["lean_heading"], 180.0)

    def test_compose_grass_batch_rows_builds_two_tapered_cards_per_tuft(self):
        spec = {
            "x": 10.0,
            "y": 20.0,
            "z": 1.5,
            "tint": 1.0,
            "blade_h": 1.2,
            "blade_w": 0.6,
            "heading": 0.0,
            "tip_scale": 0.3,
            "lean": 0.2,
            "lean_heading": 90.0,
        }
        rows, triangles = compose_grass_batch_rows([spec])
        self.assertEqual(8, len(rows))
        self.assertEqual(4, len(triangles))
        self.assertEqual((9.7, 20.0, 1.5), rows[0]["vertex"])
        self.assertEqual((10.09, 20.2, 2.7), rows[2]["vertex"])
        self.assertEqual((9.91, 20.2, 2.7), rows[3]["vertex"])
        self.assertEqual((0, 1, 2), triangles[0])
        self.assertEqual((4, 6, 7), triangles[3])

    def test_estimate_grass_tuft_count_scales_with_quality_and_caps_budget(self):
        low = estimate_grass_tuft_count(18.0, 1.0, "low")
        medium = estimate_grass_tuft_count(18.0, 1.0, "medium")
        high = estimate_grass_tuft_count(18.0, 1.0, "high")
        ultra = estimate_grass_tuft_count(80.0, 2.0, "ultra")
        self.assertLess(low, medium)
        self.assertLess(medium, high)
        self.assertLessEqual(ultra, 1600)
        self.assertGreaterEqual(low, 16)


if __name__ == "__main__":
    unittest.main()
