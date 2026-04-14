import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.adaptive_performance_manager import AdaptivePerformanceManager


class _FakeSimTierManager:
    def set_runtime_profile(self, tick_rate_hz=None, budget_scale=None):
        return {
            "tick_rate_hz": float(tick_rate_hz or 0.0),
            "budget_scale": float(budget_scale or 0.0),
        }


class _FakeApp:
    def __init__(self):
        self._gfx_quality = "High"
        self.sim_tier_mgr = _FakeSimTierManager()

    def set_runtime_load_profile(self, profile, level=0):
        self.last_profile = (int(level), dict(profile))

    def apply_graphics_quality(self, level, persist=True):
        self._gfx_quality = str(level or "High")


class RuntimeProfileLoadSheddingTests(unittest.TestCase):
    def test_profiles_include_npc_and_enemy_logic_intervals(self):
        mgr = AdaptivePerformanceManager(_FakeApp())
        p0 = mgr._profile_for_mode_level(0)
        p3 = mgr._profile_for_mode_level(3)

        self.assertIn("npc_logic_update_interval", p0)
        self.assertIn("enemy_update_interval", p0)
        self.assertGreaterEqual(float(p3["npc_logic_update_interval"]), float(p0["npc_logic_update_interval"]))
        self.assertGreaterEqual(float(p3["enemy_update_interval"]), float(p0["enemy_update_interval"]))

    def test_profiles_include_enemy_fire_particle_budget(self):
        mgr = AdaptivePerformanceManager(_FakeApp())
        p0 = mgr._profile_for_mode_level(0)
        p3 = mgr._profile_for_mode_level(3)

        self.assertIn("enemy_fire_particle_budget", p0)
        self.assertIn("enemy_fire_particle_budget", p3)
        self.assertLessEqual(int(p3["enemy_fire_particle_budget"]), int(p0["enemy_fire_particle_budget"]))

    def test_profiles_include_world_mesh_distance_scalars(self):
        mgr = AdaptivePerformanceManager(_FakeApp())
        p0 = mgr._profile_for_mode_level(0)
        p3 = mgr._profile_for_mode_level(3)

        self.assertIn("world_mesh_cull_distance_scale", p0)
        self.assertIn("world_mesh_hlod_distance_scale", p0)
        self.assertIn("world_mesh_visibility_update_scale", p0)
        self.assertLessEqual(
            float(p3["world_mesh_cull_distance_scale"]),
            float(p0["world_mesh_cull_distance_scale"]),
        )
        self.assertLessEqual(
            float(p3["world_mesh_hlod_distance_scale"]),
            float(p0["world_mesh_hlod_distance_scale"]),
        )
        self.assertGreaterEqual(
            float(p3["world_mesh_visibility_update_scale"]),
            float(p0["world_mesh_visibility_update_scale"]),
        )


if __name__ == "__main__":
    unittest.main()
