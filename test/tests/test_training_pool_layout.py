import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import world.sharuan_world as sharuan_world


class TrainingPoolLayoutTests(unittest.TestCase):
    def test_training_pool_has_canonical_center_constant(self):
        self.assertTrue(hasattr(sharuan_world, "TRAINING_POOL_CENTER"))

    def test_training_pool_is_outside_brown_training_plaza_lane(self):
        tx, ty = sharuan_world.TRAINING_GROUNDS_CENTER
        plaza_half_w, plaza_half_h = sharuan_world.TRAINING_PLAZA_HALF_EXTENTS
        pool_x, pool_y = sharuan_world.TRAINING_POOL_CENTER
        pool_half_w, pool_half_h = sharuan_world.TRAINING_POOL_HALF_EXTENTS

        plaza_north_edge = ty + plaza_half_h
        pool_south_edge = pool_y - pool_half_h
        pool_offset = math.hypot(pool_x - tx, pool_y - ty)

        self.assertGreaterEqual(
            pool_south_edge,
            plaza_north_edge + 1.0,
            "training_pool must not overlap the brown placeholder plaza lane",
        )
        self.assertLessEqual(
            pool_offset,
            sharuan_world.TRAINING_GROUNDS_RADIUS,
            "training_pool should stay inside the Training Grounds location bubble",
        )


if __name__ == "__main__":
    unittest.main()
