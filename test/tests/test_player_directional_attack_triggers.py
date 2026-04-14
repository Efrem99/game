import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _DirectionalAttackDummy(PlayerCombatMixin):
    _resolve_weapon_attack_triggers = PlayerCombatMixin._resolve_weapon_attack_triggers
    _dedupe_tokens = PlayerCombatMixin._dedupe_tokens

    def __init__(self, axes):
        self._axes = axes

    def _resolve_weapon_attack_mode(self, attack_kind):
        _ = attack_kind
        return "right"

    def _weapon_combo_style(self):
        return "sword"

    def _is_ranged_weapon_style(self, style):
        _ = style
        return False

    def _get_move_axes(self):
        return self._axes


class DirectionalAttackTriggerTests(unittest.TestCase):
    def test_rightward_light_attack_prefers_right_variant_tokens(self):
        actor = _DirectionalAttackDummy((0.9, 0.1))
        triggers = actor._resolve_weapon_attack_triggers("light")
        self.assertIn("attack_light_right", triggers)
        self.assertIn("attack_right", triggers)

    def test_leftward_heavy_attack_prefers_left_variant_tokens(self):
        actor = _DirectionalAttackDummy((-0.9, 0.1))
        triggers = actor._resolve_weapon_attack_triggers("heavy")
        self.assertIn("attack_heavy_left", triggers)
        self.assertIn("attack_left", triggers)

    def test_forward_thrust_prefers_forward_variant_tokens(self):
        actor = _DirectionalAttackDummy((0.0, 1.0))
        triggers = actor._resolve_weapon_attack_triggers("thrust")
        self.assertIn("attack_thrust_forward", triggers)
        self.assertIn("attack_forward", triggers)


if __name__ == "__main__":
    unittest.main()
