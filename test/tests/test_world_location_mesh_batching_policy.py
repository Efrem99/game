import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sharuan_world import (
    resolve_location_mesh_hlod_profile,
    resolve_location_mesh_cull_profile,
    should_batch_location_meshes,
    should_hide_location_mesh_by_distance,
    should_use_location_mesh_hlod,
)


class WorldLocationMeshBatchingPolicyTests(unittest.TestCase):
    def test_batching_disabled_by_flag(self):
        self.assertFalse(should_batch_location_meshes(12, enabled=False, min_count=4))

    def test_batching_requires_minimum_count(self):
        self.assertFalse(should_batch_location_meshes(2, enabled=True, min_count=3))
        self.assertTrue(should_batch_location_meshes(3, enabled=True, min_count=3))

    def test_batching_clamps_invalid_threshold(self):
        self.assertTrue(should_batch_location_meshes(1, enabled=True, min_count=0))

    def test_distance_visibility_hysteresis(self):
        # Visible mesh should hide only past far threshold.
        self.assertFalse(
            should_hide_location_mesh_by_distance(
                distance=150.0,
                currently_hidden=False,
                cull_distance=160.0,
                hysteresis=20.0,
            )
        )
        self.assertTrue(
            should_hide_location_mesh_by_distance(
                distance=171.0,
                currently_hidden=False,
                cull_distance=160.0,
                hysteresis=20.0,
            )
        )
        # Hidden mesh should stay hidden until we pass the near threshold.
        self.assertTrue(
            should_hide_location_mesh_by_distance(
                distance=159.0,
                currently_hidden=True,
                cull_distance=160.0,
                hysteresis=20.0,
            )
        )
        self.assertFalse(
            should_hide_location_mesh_by_distance(
                distance=149.0,
                currently_hidden=True,
                cull_distance=160.0,
                hysteresis=20.0,
            )
        )

    def test_resolve_location_mesh_cull_profile_returns_defaults_for_unknown_location(self):
        profile = resolve_location_mesh_cull_profile(
            active_location="Unknown",
            base_distance=170.0,
            base_hysteresis=18.0,
            base_interval=0.25,
            profiles={"castle_sharuan": {"distance": 120.0}},
        )
        self.assertEqual(170.0, profile["distance"])
        self.assertEqual(18.0, profile["hysteresis"])
        self.assertEqual(0.25, profile["interval"])

    def test_resolve_location_mesh_cull_profile_applies_location_override(self):
        profile = resolve_location_mesh_cull_profile(
            active_location="Castle Sharuan",
            base_distance=170.0,
            base_hysteresis=18.0,
            base_interval=0.25,
            profiles={"castle_sharuan": {"distance": 115.0, "hysteresis": 12.0, "interval": 0.12}},
        )
        self.assertEqual(115.0, profile["distance"])
        self.assertEqual(12.0, profile["hysteresis"])
        self.assertEqual(0.12, profile["interval"])

    def test_resolve_location_mesh_cull_profile_clamps_invalid_values(self):
        profile = resolve_location_mesh_cull_profile(
            active_location="Castle Sharuan",
            base_distance=170.0,
            base_hysteresis=18.0,
            base_interval=0.25,
            profiles={"castle_sharuan": {"distance": -1.0, "hysteresis": -4.0, "interval": 0.0}},
        )
        self.assertEqual(20.0, profile["distance"])
        self.assertEqual(0.0, profile["hysteresis"])
        self.assertEqual(0.05, profile["interval"])

    def test_hlod_hysteresis_enters_after_far_threshold(self):
        self.assertFalse(
            should_use_location_mesh_hlod(
                distance=88.0,
                currently_using_hlod=False,
                hlod_distance=90.0,
                hysteresis=20.0,
            )
        )
        self.assertTrue(
            should_use_location_mesh_hlod(
                distance=101.0,
                currently_using_hlod=False,
                hlod_distance=90.0,
                hysteresis=20.0,
            )
        )

    def test_hlod_hysteresis_exits_only_after_near_threshold(self):
        self.assertTrue(
            should_use_location_mesh_hlod(
                distance=89.0,
                currently_using_hlod=True,
                hlod_distance=90.0,
                hysteresis=20.0,
            )
        )
        self.assertFalse(
            should_use_location_mesh_hlod(
                distance=79.0,
                currently_using_hlod=True,
                hlod_distance=90.0,
                hysteresis=20.0,
            )
        )

    def test_resolve_location_mesh_hlod_profile_returns_defaults_for_unknown_location(self):
        profile = resolve_location_mesh_hlod_profile(
            active_location="Unknown",
            enabled=True,
            base_distance=110.0,
            base_hysteresis=24.0,
            profiles={"castle_sharuan": {"distance": 90.0}},
        )
        self.assertTrue(profile["enabled"])
        self.assertEqual(110.0, profile["distance"])
        self.assertEqual(24.0, profile["hysteresis"])

    def test_resolve_location_mesh_hlod_profile_applies_override_and_clamps_values(self):
        profile = resolve_location_mesh_hlod_profile(
            active_location="Castle Sharuan",
            enabled=True,
            base_distance=110.0,
            base_hysteresis=24.0,
            profiles={"castle_sharuan": {"enabled": True, "distance": -5.0, "hysteresis": -1.0}},
        )
        self.assertTrue(profile["enabled"])
        self.assertEqual(15.0, profile["distance"])
        self.assertEqual(0.0, profile["hysteresis"])


if __name__ == "__main__":
    unittest.main()
