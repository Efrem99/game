import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _LocationDummy:
    _resolve_test_location = XBotApp._resolve_test_location

    def __init__(self):
        self.world = SimpleNamespace(
            active_location="sharuan_town",
            _th=lambda x, y: 5.0,
            sample_water_height=lambda x, y: -3.0,
        )


class AppTestLocationResolutionTests(unittest.TestCase):
    def test_named_preset_token_resolves_without_coordinate_fallback(self):
        app = _LocationDummy()

        pos = app._resolve_test_location("training")

        self.assertIsNotNone(pos)
        self.assertAlmostEqual(18.0, float(pos.x), places=3)
        self.assertAlmostEqual(24.0, float(pos.y), places=3)
        self.assertAlmostEqual(7.2, float(pos.z), places=3)

    def test_unknown_non_numeric_token_returns_none_cleanly(self):
        app = _LocationDummy()

        self.assertIsNone(app._resolve_test_location("forest_canopy"))


if __name__ == "__main__":
    unittest.main()
