import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import sample_polyline_points


class WorldPathSamplingTests(unittest.TestCase):
    def test_sample_polyline_points_returns_dense_points(self):
        points = [(0.0, 0.0), (0.0, 10.0)]
        sampled = sample_polyline_points(points, spacing=2.0)
        self.assertGreaterEqual(len(sampled), 6)
        self.assertEqual((0.0, 0.0), sampled[0])
        self.assertEqual((0.0, 10.0), sampled[-1])

    def test_sample_polyline_points_handles_corner(self):
        points = [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0)]
        sampled = sample_polyline_points(points, spacing=3.0)
        self.assertIn((6.0, 0.0), sampled)
        self.assertIn((6.0, 6.0), sampled)
        self.assertTrue(any(abs(x - 3.0) < 0.01 and abs(y) < 0.01 for x, y in sampled))


if __name__ == "__main__":
    unittest.main()
