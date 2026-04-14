import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _DataManager:
    def __init__(self):
        self._items = {
            "hunter_bow": {
                "id": "hunter_bow",
                "weapon_class": "bow",
                "equip_visual": {"style": "bow"},
            },
            "iron_sword": {
                "id": "iron_sword",
                "weapon_class": "sword",
                "equip_visual": {"style": "blade"},
            },
            "arcane_focus": {
                "id": "arcane_focus",
                "weapon_class": "focus",
                "equip_visual": {"style": "magic"},
            },
        }

    def get_item(self, item_id):
        payload = self._items.get(str(item_id or "").strip())
        return dict(payload) if isinstance(payload, dict) else None


class _Owner(PlayerCombatMixin):
    def __init__(self):
        self.data_mgr = _DataManager()
        self._equipment_state = {
            "weapon_main": "hunter_bow",
            "offhand": "",
            "chest": "",
            "trinket": "",
        }
        self._next_cast_hand = "right"
        self._next_weapon_hand = "right"
        self._queued = []
        self._forced = []
        self._state_anim_hints = {}
        self._is_aiming = False
        self._aim_mode = ""

    def _queue_state_trigger(self, token):
        self._queued.append(str(token or ""))

    def _force_action_state(self, state_name):
        self._forced.append(str(state_name or ""))

    def _set_state_anim_hints(self, state_name, tokens):
        key = str(state_name or "").strip().lower()
        if not key:
            return
        rows = [str(t or "").strip().lower() for t in (tokens or []) if str(t or "").strip()]
        if rows:
            self._state_anim_hints[key] = rows
        else:
            self._state_anim_hints.pop(key, None)


class BowMagicAnimationTokenTests(unittest.TestCase):
    def test_fireball_prefers_projectile_cast_fast_before_school_token(self):
        owner = _Owner()
        resolver = getattr(owner, "_resolve_spell_anim_triggers", None)
        self.assertTrue(callable(resolver))

        tokens = resolver(
            "fireball",
            {"id": "fireball", "cast_time": 0.22},
            {"anim_trigger": "cast_spell", "cast_time": 0.22},
        )
        self.assertTrue(tokens)
        self.assertEqual("cast_fast", tokens[0])
        self.assertIn("cast_fire", tokens)
        self.assertIn("cast_fast", tokens)
        self.assertIn("cast_spell", tokens)

    def test_bow_attack_prefers_bow_shoot_token(self):
        owner = _Owner()
        resolver = getattr(owner, "_resolve_weapon_attack_triggers", None)
        self.assertTrue(callable(resolver))

        tokens = resolver("light")
        self.assertTrue(tokens)
        self.assertEqual("bow_shoot", tokens[0])
        self.assertIn("attack_light_both", tokens)

    def test_magic_focus_heavy_attack_uses_both_hand_flow(self):
        owner = _Owner()
        owner._equipment_state["weapon_main"] = "arcane_focus"
        resolver = getattr(owner, "_resolve_weapon_attack_triggers", None)
        self.assertTrue(callable(resolver))

        tokens = resolver("heavy")
        self.assertTrue(tokens)
        self.assertEqual("attack_heavy_both", tokens[0])

    def test_magic_focus_cast_includes_both_hand_token(self):
        owner = _Owner()
        owner._equipment_state["weapon_main"] = "arcane_focus"
        resolver = getattr(owner, "_resolve_spell_anim_triggers", None)
        self.assertTrue(callable(resolver))

        tokens = resolver(
            "arcane_burst",
            {"id": "arcane_burst", "cast_time": 0.28},
            {"anim_trigger": "cast_spell", "cast_time": 0.28},
        )
        self.assertTrue(tokens)
        self.assertIn("cast_both", tokens)

    def test_sync_aim_mode_emits_block_start_and_end_for_bow_aim(self):
        owner = _Owner()
        mode = owner._sync_aim_mode(selected_label="sword", aim_pressed=True)
        self.assertEqual("bow", mode)
        self.assertTrue(owner._is_aiming)
        self.assertIn("block_start", owner._queued)
        self.assertIn("blocking", owner._forced)
        self.assertIn("blocking", owner._state_anim_hints)
        self.assertEqual("bow_aim", owner._state_anim_hints["blocking"][0])

        owner._sync_aim_mode(selected_label="sword", aim_pressed=False)
        self.assertIn("block_end", owner._queued)
        self.assertNotIn("blocking", owner._state_anim_hints)


if __name__ == "__main__":
    unittest.main()
