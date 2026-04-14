import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from direct.showbase.ShowBaseGlobal import globalClock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _ComboHudDummy(PlayerCombatMixin):
    _safe_float = PlayerCombatMixin._safe_float
    _resolve_combo_style = PlayerCombatMixin._resolve_combo_style
    _decay_combo_chain = PlayerCombatMixin._decay_combo_chain
    _register_combo_step = PlayerCombatMixin._register_combo_step
    get_hud_combo_state = PlayerCombatMixin.get_hud_combo_state

    def __init__(self):
        self.cs = SimpleNamespace(comboCount=0, comboTimer=0.0, grounded=True)
        self._combo_chain = 0
        self._combo_deadline = 0.0
        self._combo_style = "unarmed"
        self._combo_kind = "melee"
        self.app = None

    def _weapon_combo_style(self):
        return "sword"

    def _combat_style_config(self, style_name):
        _ = style_name
        return {"combo_window": 0.72, "max_chain": 7}


class PlayerComboHudStateTests(unittest.TestCase):
    def test_get_hud_combo_state_exposes_live_confirmed_combo_state(self):
        actor = _ComboHudDummy()

        actor._register_combo_step("melee", amount=1)

        state = actor.get_hud_combo_state()

        self.assertIsInstance(state, dict)
        self.assertEqual(1, state["count"])
        self.assertEqual("melee", state["kind"])
        self.assertEqual("sword", state["style"])
        self.assertGreater(state["remain"], 0.0)
        self.assertEqual(1, actor.cs.comboCount)
        self.assertGreater(actor.cs.comboTimer, 0.0)

    def test_get_hud_combo_state_decays_and_clears_expired_chain(self):
        actor = _ComboHudDummy()
        actor._register_combo_step("melee", amount=2)
        actor._combo_deadline = float(globalClock.getFrameTime()) - 0.05

        state = actor.get_hud_combo_state()

        self.assertIsNone(state)
        self.assertEqual(0, actor._combo_chain)
        self.assertEqual("unarmed", actor._combo_style)
        self.assertEqual("melee", actor._combo_kind)
        self.assertEqual(0, actor.cs.comboCount)
        self.assertEqual(0.0, actor.cs.comboTimer)


if __name__ == "__main__":
    unittest.main()
