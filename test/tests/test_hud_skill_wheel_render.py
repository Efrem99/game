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
        self.visible = True
        self.text = ""
        self.fg = None
        self.color_scale = None
        self.image = None
        self.props = {}

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def setText(self, value):
        self.text = str(value)

    def setFg(self, value):
        self.fg = value

    def setColorScale(self, *value):
        self.color_scale = tuple(value)

    def setImage(self, value):
        self.image = value

    def __setitem__(self, key, value):
        self.props[key] = value

    def __getitem__(self, key):
        return self.props[key]


class _HudDummy:
    set_skill_wheel = HUDOverlay.set_skill_wheel
    _fmt_key_hint = HUDOverlay._fmt_key_hint
    _refresh_control_hint_tokens = HUDOverlay._refresh_control_hint_tokens

    def __init__(self):
        bindings = {
            "skill_wheel": "tab",
            "attack_light": "mouse1",
            "target_lock": "t",
            "interact": "f",
        }
        self.app = SimpleNamespace(
            data_mgr=SimpleNamespace(get_binding=lambda action: bindings.get(action)),
        )
        self._skill_wheel_visible = True
        self._skill_hover_idx = None
        self._skill_preview_idx = 0
        self._active_skill_idx = 0
        self._ultimate_skill_idx = 1
        self._skill_wheel_hint_key = "TAB"
        self._attack_hint_key = "LMB"
        self._cast_hint_key = "wheel slot"
        self._target_lock_hint_key = "T"
        self._interact_hint_key = "F"
        self._skill_icon_cache = {}
        self.skill_wheel_backdrop = _Widget()
        self.skill_wheel_center_ring = _Widget()
        self.skill_center_text = _Widget()
        self.skill_controls_text = _Widget()
        self.skill_slot_meta = [{"x": 0.0, "y": 0.0, "r": 0.1}, {"x": 0.1, "y": 0.0, "r": 0.1}]
        self.skill_slots = []
        for _ in range(2):
            self.skill_slots.append(
                {
                    "ring": _Widget(),
                    "plate": _Widget(),
                    "glow": _Widget(),
                    "flare": _Widget(),
                    "icon_image": _Widget(),
                    "icon_text": _Widget(),
                    "label": _Widget(),
                    "icon_path": None,
                }
            )

    def _skill_style_for_spell(self, label):
        token = str(label or "").strip().lower()
        if "fire" in token:
            return "F", (1.0, 0.4, 0.2, 1.0)
        return "S", (0.8, 0.84, 0.92, 1.0)

    def _resolve_spell_icon_path(self, label):
        _ = label
        return None


class HudSkillWheelRenderTests(unittest.TestCase):
    def test_set_skill_wheel_renders_active_and_ultimate_slots_without_crashing(self):
        hud = _HudDummy()

        hud.set_skill_wheel(["fireball", "sword"], active_idx=0, ultimate_idx=1)

        self.assertIn("Selected", hud.skill_center_text.text)
        self.assertTrue(hud.skill_slots[0]["ring"].visible)
        self.assertTrue(hud.skill_slots[1]["ring"].visible)
        self.assertIn("frameColor", hud.skill_slots[0]["ring"].props)
        self.assertIn("frameColor", hud.skill_slots[1]["ring"].props)


if __name__ == "__main__":
    unittest.main()
