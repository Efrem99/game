import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _NonCoreCombatDummy:
    _update_combat = Player._update_combat

    def __init__(self):
        self._skill_wheel_open = False
        self.combat = None
        self.magic = None
        self.cs = None
        self.enemies = []
        self._spell_cache = ["sword"]
        self._active_spell_idx = 0
        self._once = {"attack_light": True}
        self._is_aiming = False
        self._aim_mode = ""
        self._weapon_drawn = False
        self.queued_triggers = []
        self.pushed_events = []
        self.combo_steps = []
        self.requested_attack_kinds = []

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
        return False

    def _perform_ranged_attack(self, attack_kind="light"):
        _ = attack_kind
        return False

    def _should_contextual_thrust(self):
        return False

    def _play_sfx(self, name, volume=1.0, rate=1.0):
        _ = name
        _ = volume
        _ = rate

    def _on_hit(self, result):
        _ = result

    def _resolve_weapon_attack_triggers(self, attack_kind):
        token = str(attack_kind or "").strip().lower() or "light"
        self.requested_attack_kinds.append(token)
        return [f"attack_{token}", "attack"]

    def _apply_state_anim_hint_tokens(self, state_name, tokens):
        _ = state_name
        _ = tokens

    def _queue_state_trigger(self, trigger):
        self.queued_triggers.append(str(trigger))

    def _set_weapon_drawn(self, drawn):
        self._weapon_drawn = bool(drawn)

    def _push_combat_event(self, damage_type, amount, source_label=None):
        self.pushed_events.append((str(damage_type), int(amount), str(source_label or "")))

    def _register_combo_step(self, kind, amount=1):
        self.combo_steps.append((str(kind), int(amount)))

    def _on_spell_effect(self, fx):
        _ = fx

    def _update_spell_casting(self):
        return None


class CombatNonCoreFallbackTests(unittest.TestCase):
    def test_light_attack_without_core_queues_attack_state_and_does_not_crash(self):
        actor = _NonCoreCombatDummy()
        actor._update_combat(0.016)
        self.assertIn("attack", actor.queued_triggers)
        self.assertIn("attack_light", actor.queued_triggers)
        self.assertEqual(["light"], actor.requested_attack_kinds)
        self.assertTrue(actor._weapon_drawn)
        self.assertTrue(actor.pushed_events)

    def test_thrust_attack_without_light_still_queues_attack_state(self):
        actor = _NonCoreCombatDummy()
        actor._once = {"attack_thrust": True}
        actor._update_combat(0.016)
        self.assertIn("attack", actor.queued_triggers)
        self.assertIn("attack_thrust", actor.queued_triggers)
        self.assertEqual(["thrust"], actor.requested_attack_kinds)
        self.assertTrue(actor._weapon_drawn)
        self.assertTrue(actor.pushed_events)

    def test_non_core_melee_fallback_does_not_fake_combo_hits_without_confirmation(self):
        actor = _NonCoreCombatDummy()
        actor._update_combat(0.016)

        self.assertEqual([], actor.combo_steps)


if __name__ == "__main__":
    unittest.main()
