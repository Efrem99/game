import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.debug_video_overlay import build_debug_overlay_lines, build_collider_wireframe_segments


class DebugVideoOverlayTests(unittest.TestCase):
    def test_build_debug_overlay_lines_include_video_bot_and_collider_counts(self):
        lines = build_debug_overlay_lines(
            debug_overlay_enabled=True,
            debug_colliders_enabled=True,
            video_bot_enabled=True,
            plan_name="parkour",
            collider_count=7,
        )

        self.assertEqual("DEBUG VIDEO OVERLAY", lines[0])
        self.assertIn("VideoBot plan: parkour", lines)
        self.assertIn("Collider overlay: ON", lines)
        self.assertIn("Visible collider boxes: 7", lines)

    def test_build_collider_wireframe_segments_builds_aabb_edges(self):
        segments = build_collider_wireframe_segments(
            [
                {
                    "min_x": 1.0,
                    "min_y": 2.0,
                    "min_z": 3.0,
                    "max_x": 4.0,
                    "max_y": 5.0,
                    "max_z": 6.0,
                }
            ]
        )

        self.assertEqual(12, len(segments))
        self.assertIn(((1.0, 2.0, 3.0), (4.0, 2.0, 3.0)), segments)
        self.assertIn(((1.0, 2.0, 6.0), (1.0, 5.0, 6.0)), segments)


if __name__ == "__main__":
    unittest.main()
