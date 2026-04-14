import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.adaptive_performance_manager import AdaptivePerformanceManager


class _FakeSimTierManager:
    def __init__(self):
        self.calls = []

    def set_runtime_profile(self, tick_rate_hz=None, budget_scale=None):
        self.calls.append((float(tick_rate_hz or 0.0), float(budget_scale or 0.0)))


class _FakeApp:
    def __init__(self, quality="High"):
        self._gfx_quality = quality
        self._particle_upload_interval = 1.0 / 30.0
        self.sim_tier_mgr = _FakeSimTierManager()
        self.runtime_profiles = []
        self.quality_calls = []

    def apply_graphics_quality(self, level, persist=True):
        self._gfx_quality = str(level or "")
        self.quality_calls.append((str(level or ""), bool(persist)))

    def set_runtime_load_profile(self, profile, level=0):
        self.runtime_profiles.append((int(level), dict(profile)))


class AdaptivePerformanceManagerTests(unittest.TestCase):
    def test_stays_in_level_zero_at_60fps(self):
        app = _FakeApp(quality="High")
        mgr = AdaptivePerformanceManager(app)
        for _ in range(180):
            mgr.update(1.0 / 60.0, is_playing=True)
        self.assertEqual(0, mgr.current_level)
        self.assertEqual([], [c for c in app.quality_calls if c[1] is False])

    def test_escalates_under_sustained_frame_pressure(self):
        app = _FakeApp(quality="Ultra")
        mgr = AdaptivePerformanceManager(app)
        for _ in range(360):
            mgr.update(1.0 / 28.0, is_playing=True)
        self.assertGreaterEqual(mgr.current_level, 2)
        self.assertTrue(app.runtime_profiles)
        self.assertTrue(app.sim_tier_mgr.calls)
        self.assertTrue(any(call[1] is False for call in app.quality_calls))

    def test_recovers_after_pressure_is_gone(self):
        app = _FakeApp(quality="Ultra")
        mgr = AdaptivePerformanceManager(app)
        for _ in range(360):
            mgr.update(1.0 / 28.0, is_playing=True)
        self.assertGreaterEqual(mgr.current_level, 1)
        for _ in range(520):
            mgr.update(1.0 / 75.0, is_playing=True)
        self.assertEqual(0, mgr.current_level)

    def test_manual_quality_change_updates_base_target(self):
        app = _FakeApp(quality="High")
        mgr = AdaptivePerformanceManager(app)
        mgr.on_quality_changed("Ultra", user_initiated=True)
        for _ in range(260):
            mgr.update(1.0 / 32.0, is_playing=True)
        self.assertNotEqual("low", str(app._gfx_quality).strip().lower())

    def test_performance_mode_escalates_faster_than_quality_mode(self):
        app_quality = _FakeApp(quality="Ultra")
        app_perf = _FakeApp(quality="Ultra")
        mgr_quality = AdaptivePerformanceManager(app_quality, mode="quality")
        mgr_perf = AdaptivePerformanceManager(app_perf, mode="performance")
        for _ in range(240):
            mgr_quality.update(1.0 / 35.0, is_playing=True)
            mgr_perf.update(1.0 / 35.0, is_playing=True)
        self.assertGreater(mgr_perf.current_level, mgr_quality.current_level)

    def test_observed_fps_overrides_capped_dt_for_pressure_detection(self):
        app = _FakeApp(quality="Ultra")
        mgr = AdaptivePerformanceManager(app, mode="quality")
        for _ in range(220):
            mgr.update(0.05, is_playing=True, observed_fps=4.0)
        self.assertGreaterEqual(mgr.current_level, 2)


if __name__ == "__main__":
    unittest.main()
