import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.sky_manager import SkyManager


class SkyWeatherFxTests(unittest.TestCase):
    def test_celestial_factors_enable_moonlight_at_night(self):
        factors = SkyManager.compute_celestial_factors(time_value=0.92, cloud_coverage=0.25)
        self.assertGreater(factors["moon_light"], 0.15)
        self.assertGreater(factors["stars_alpha"], 0.25)
        self.assertLess(factors["sun_elevation"], 0.15)

    def test_celestial_factors_hide_stars_during_day(self):
        factors = SkyManager.compute_celestial_factors(time_value=0.52, cloud_coverage=0.1)
        self.assertLess(factors["moon_light"], 0.08)
        self.assertLess(factors["stars_alpha"], 0.05)
        self.assertGreater(factors["sun_elevation"], 0.6)

    def test_weather_fx_profile_storm(self):
        profile = SkyManager.weather_fx_profile("stormy", cloud_coverage=1.0)
        self.assertGreater(profile["rain_strength"], 0.8)
        self.assertGreater(profile["lightning_strength"], 0.7)
        self.assertGreater(profile["cloud_darkening"], 0.5)

    def test_weather_fx_profile_clear(self):
        profile = SkyManager.weather_fx_profile("clear", cloud_coverage=0.15)
        self.assertLess(profile["rain_strength"], 0.05)
        self.assertLess(profile["lightning_strength"], 0.05)
        self.assertLess(profile["cloud_darkening"], 0.2)


if __name__ == "__main__":
    unittest.main()
