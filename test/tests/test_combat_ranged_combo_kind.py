import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _RangedComboOwner(PlayerCombatMixin):
    _perform_ranged_attack = PlayerCombatMixin._perform_ranged_attack

    def __init__(self):
        self.combo_steps = []
        self.queued = []
        self.forced = []
        self.events = []
        self._state_anim_hints = {}
        self.app = None

    def _is_ranged_weapon_equipped(self):
        return True

    def _ranged_weapon_profile(self):
        return {
            "label": "bow",
            "sfx": "bow_release",
            "sfx_volume": 0.7,
            "sfx_rate": 1.0,
        }

    def _play_sfx(self, name, volume=1.0, rate=1.0):
        _ = name
        _ = volume
        _ = rate

    def _resolve_weapon_attack_triggers(self, attack_kind):
        _ = attack_kind
        return ["bow_shoot", "attack_light_both"]

    def _apply_state_anim_hint_tokens(self, state_name, tokens):
        self._state_anim_hints[str(state_name)] = list(tokens)

    def _queue_state_trigger(self, trigger):
        self.queued.append(str(trigger))

    def _force_action_state(self, state_name):
        self.forced.append(str(state_name))

    def _current_aim_target(self):
        return {"distance": 12.0}

    def _compute_ranged_damage(self, profile, target_info):
        _ = profile
        _ = target_info
        return 14.0

    def _apply_ranged_damage(self, target_info, damage):
        _ = target_info
        _ = damage
        return True

    def _push_combat_event(self, damage_type, amount, source_label=None):
        self.events.append((damage_type, amount, source_label))

    def _register_combo_step(self, kind, amount=1):
        self.combo_steps.append((str(kind), int(amount)))


class CombatRangedComboKindTests(unittest.TestCase):
    def test_ranged_hits_register_ranged_combo_kind(self):
        owner = _RangedComboOwner()

        ok = owner._perform_ranged_attack("light")

        self.assertTrue(ok)
        self.assertEqual([("ranged", 1)], owner.combo_steps)
        self.assertIn("attacking", owner.forced)
        self.assertTrue(owner.events)


if __name__ == "__main__":
    unittest.main()
