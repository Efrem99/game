import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.vehicle_manager import VehicleManager


class VehicleVisualPaletteTests(unittest.TestCase):
    def test_vehicle_visual_palette_normalizes_aliases(self):
        manager = VehicleManager.__new__(VehicleManager)

        ship_palette = manager._vehicle_visual_palette("ship")
        boat_palette = manager._vehicle_visual_palette("boat")

        self.assertEqual(ship_palette, boat_palette)

    def test_vehicle_visual_palette_exposes_distinct_accent_colors(self):
        manager = VehicleManager.__new__(VehicleManager)

        horse = manager._vehicle_visual_palette("horse")
        wolf = manager._vehicle_visual_palette("wolf")
        stag = manager._vehicle_visual_palette("stag")
        carriage = manager._vehicle_visual_palette("carriage")
        ship = manager._vehicle_visual_palette("ship")

        for palette in (horse, wolf, stag, carriage, ship):
            self.assertIn("body", palette)
            self.assertIn("accent", palette)
            self.assertIn("cloth", palette)
            self.assertIn("metal", palette)

        self.assertNotEqual(horse["accent"], wolf["accent"])
        self.assertNotEqual(stag["accent"], carriage["accent"])
        self.assertNotEqual(ship["cloth"], carriage["cloth"])


if __name__ == "__main__":
    unittest.main()
