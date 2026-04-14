import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from panda3d.core import NodePath, Vec3

ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from render.magic_vfx import MagicVFXSystem


class MagicVfxSwordTrailRuntimeTests(unittest.TestCase):
    def _system(self):
        return MagicVFXSystem(SimpleNamespace(render=NodePath("render")))

    def test_spawn_sword_trail_initializes_last_pos_base(self):
        system = self._system()

        trail_data = system.spawn_sword_trail()

        self.assertIn("last_pos_base", trail_data)
        self.assertIsNone(trail_data["last_pos_base"])

    def test_update_sword_trail_accepts_legacy_payload_without_last_pos_base(self):
        system = self._system()
        trail_data = {
            "root": NodePath("trail_root"),
            "segments": [],
            "max_segments": 8,
            "color": (1, 1, 1, 1),
            "last_pos": None,
        }

        system.update_sword_trail(
            trail_data,
            Vec3(1.0, 2.0, 4.1),
            Vec3(1.0, 2.0, 3.0),
            0.25,
        )

        self.assertIn("last_pos_base", trail_data)
        self.assertEqual((1.0, 2.0, 3.0), tuple(float(v) for v in trail_data["last_pos_base"]))

    def test_update_sword_trail_builds_segment_on_second_sample(self):
        system = self._system()
        trail_data = system.spawn_sword_trail()

        system.update_sword_trail(
            trail_data,
            Vec3(1.0, 2.0, 4.1),
            Vec3(1.0, 2.0, 3.0),
            0.10,
        )
        system.update_sword_trail(
            trail_data,
            Vec3(1.3, 2.0, 4.2),
            Vec3(1.3, 2.0, 3.1),
            0.10,
        )

        self.assertEqual(1, len(trail_data["segments"]))
        self.assertFalse(trail_data["segments"][0].isEmpty())


if __name__ == "__main__":
    unittest.main()
