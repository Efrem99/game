import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _CombatStub:
    def __init__(self):
        self.start_calls = []
        self.update_calls = 0

    def startAttack(self, cs, attack_type, enemies):
        _ = cs
        _ = enemies
        self.start_calls.append(attack_type)
        return None

    def update(self, dt, cs, enemies):
        _ = dt
        _ = cs
        _ = enemies
        self.update_calls += 1

    def isAttacking(self):
        return False


class _MagicStub:
    def update(self, dt, enemies, cb):
        _ = dt
        _ = enemies
        _ = cb


class _BowRoutingDummy:
    _update_combat = Player._update_combat

    def __init__(self):
        self._skill_wheel_open = False
        self.combat = _CombatStub()
        self.magic = _MagicStub()
        self.cs = object()
        self.enemies = []
        self._spell_cache = ["sword"]
        self._active_spell_idx = 0
        self._once = {"attack_light": True}
        self._is_aiming = False
        self._aim_mode = ""
        self._weapon_drawn = False
        self.ranged_calls = 0

    def _refresh_spell_cache(self):
        return None

    def _once_action(self, action):
        if self._once.get(action, False):
            self._once[action] = False
            return True
        return False

    def _get_action(self, action):
        _ = action
        return False

    def _sync_aim_mode(self, selected_label, aim_pressed=False):
        _ = selected_label
        _ = aim_pressed
        self._is_aiming = False
        self._aim_mode = ""
        return ""

    def _cast_spell_by_index(self, idx):
        _ = idx
        return False

    def _is_ranged_weapon_equipped(self):
        return True

    def _perform_ranged_attack(self, attack_kind="light"):
        _ = attack_kind
        self.ranged_calls += 1
        return True

    def _should_contextual_thrust(self):
        return False

    def _play_sfx(self, name, volume=1.0, rate=1.0):
        _ = name
        _ = volume
        _ = rate

    def _on_hit(self, result):
        _ = result

    def _resolve_weapon_attack_triggers(self, attack_kind):
        _ = attack_kind
        return ["attack_light"]

    def _apply_state_anim_hint_tokens(self, state_name, tokens):
        _ = state_name
        _ = tokens

    def _queue_state_trigger(self, trigger):
        _ = trigger

    def _on_spell_effect(self, fx):
        _ = fx

    def _set_weapon_drawn(self, drawn):
        self._weapon_drawn = bool(drawn)


class CombatBowRoutingTests(unittest.TestCase):
    def test_light_attack_uses_ranged_path_when_bow_is_equipped(self):
        actor = _BowRoutingDummy()
        actor._update_combat(0.016)
        self.assertEqual(1, actor.ranged_calls)
        self.assertEqual([], actor.combat.start_calls)
        self.assertTrue(actor._weapon_drawn)


if __name__ == "__main__":
    unittest.main()
