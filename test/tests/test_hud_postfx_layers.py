import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.hud_overlay import HUDOverlay


class _Widget:
    def __init__(self):
        self.props = {}

    def __setitem__(self, key, value):
        self.props[key] = value

    def __getitem__(self, key):
        return self.props[key]


class _HudPostFxDummy:
    _damage_color = HUDOverlay._damage_color
    _resolve_screen_postfx_layers = HUDOverlay._resolve_screen_postfx_layers
    _apply_screen_postfx = HUDOverlay._apply_screen_postfx

    def __init__(self):
        self.app = SimpleNamespace()
        self.postfx_flash = _Widget()
        self.postfx_pulse = _Widget()


class HudPostFxLayerTests(unittest.TestCase):
    def test_damage_flash_prefers_damage_color_and_visible_alpha(self):
        hud = _HudPostFxDummy()

        layers = hud._resolve_screen_postfx_layers(
            boost=0.12,
            fear=0.0,
            damage=0.22,
            combat_heat=0.0,
            damage_type="fire",
            damage_intensity=0.8,
        )

        self.assertGreater(layers["flash"][3], 0.18)
        self.assertGreater(layers["flash"][0], layers["flash"][2])

    def test_combat_heat_adds_warm_pulse_even_without_damage(self):
        hud = _HudPostFxDummy()

        layers = hud._resolve_screen_postfx_layers(
            boost=0.08,
            fear=0.0,
            damage=0.0,
            combat_heat=0.42,
            damage_type="",
            damage_intensity=0.0,
        )

        self.assertGreater(layers["pulse"][3], 0.04)
        self.assertGreater(layers["pulse"][0], layers["pulse"][2])

    def test_apply_screen_postfx_writes_overlay_frame_colors(self):
        hud = _HudPostFxDummy()

        hud._apply_screen_postfx(
            boost=0.08,
            fear=0.12,
            damage=0.16,
            combat_heat=0.28,
            damage_type="ice",
            damage_intensity=0.5,
        )

        self.assertIn("frameColor", hud.postfx_flash.props)
        self.assertIn("frameColor", hud.postfx_pulse.props)


if __name__ == "__main__":
    unittest.main()
