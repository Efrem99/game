import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import compose_grass_batch_rows, make_grass_tuft_spec


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

    def test_compose_grass_batch_rows_builds_two_crossed_quads_per_tuft(self):
        spec = {
            "x": 10.0,
            "y": 20.0,
            "z": 1.5,
            "tint": 1.0,
            "blade_h": 1.2,
            "blade_w": 0.6,
            "heading": 0.0,
        }
        rows, triangles = compose_grass_batch_rows([spec])
        self.assertEqual(8, len(rows))
        self.assertEqual(4, len(triangles))
        self.assertEqual((9.7, 20.0, 1.5), rows[0]["vertex"])
        self.assertEqual((10.3, 20.0, 2.7), rows[2]["vertex"])
        self.assertEqual((0, 1, 2), triangles[0])
        self.assertEqual((4, 6, 7), triangles[3])


if __name__ == "__main__":
    unittest.main()
