import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import entities.player_combat_mixin as combat_module
from entities.player_combat_mixin import PlayerCombatMixin


class _DataMgr:
    def __init__(self):
        self.spells = {
            "fireball": {
                "id": "fireball",
                "name": "Fireball",
                "damage": 24,
                "runtime": {
                    "cast_time": 0.0,
                    "cooldown": 1.2,
                },
                "sfx": {
                    "cast": "spell_cast",
                    "impact": "spell_fire",
                },
            }
        }

    def get_spell(self, key):
        payload = self.spells.get(str(key or "").strip())
        return dict(payload) if isinstance(payload, dict) else {}

    def get_item(self, _item_id):
        return {}


class _InfluenceMgr:
    def __init__(self):
        self.rows = []

    def add_influence(self, fx_type, pos, radius, strength, duration):
        self.rows.append(
            {
                "fx_type": fx_type,
                "pos": pos,
                "radius": radius,
                "strength": strength,
                "duration": duration,
            }
        )


class _ActorStub:
    def getPos(self, _render=None):
        return SimpleNamespace(x=10.0, y=20.0, z=3.0)

    def getH(self):
        return 90.0


class _Owner(PlayerCombatMixin):
    def __init__(self):
        self.data_mgr = _DataMgr()
        self._spell_cache = ["fireball"]
        self._spell_cooldowns = {}
        self._spell_cast_lock_until = 0.0
        self._next_cast_hand = "right"
        self._next_weapon_hand = "right"
        self._equipment_state = {"weapon_main": "", "offhand": ""}
        self._state_anim_hints = {}
        self._queued_state_triggers = []
        self._pending_spell = None
        self._pending_spell_release_time = 0.0
        self._active_spell_idx = 0
        self._last_combat_event = None
        self._combo_chain = 0
        self._combo_deadline = 0.0
        self._combo_style = "unarmed"
        self._combo_kind = "melee"
        self._spell_type_alias = {}
        self.actor = _ActorStub()
        self.render = object()
        self.app = SimpleNamespace(influence_mgr=_InfluenceMgr())
        self.cs = None
        self.magic = None
        self.particles = None
        self.enemies = []
        self._anim_state = "idle"
        self._entered_states = []

    def _refresh_spell_cache(self):
        return None

    def _play_sfx(self, *_args, **_kwargs):
        return None

    def _set_weapon_drawn(self, *_args, **_kwargs):
        return None

    def _queue_state_trigger(self, trigger):
        self._queued_state_triggers.append(str(trigger or ""))

    def _enter_state(self, name):
        self._entered_states.append(str(name or ""))
        self._anim_state = str(name or "")
        return True

    def _register_combo_step(self, kind, amount=1):
        self._combo_kind = str(kind or "")
        self._combo_chain += int(max(1, amount))


class MagicNonCoreFallbackTests(unittest.TestCase):
    def test_cast_spell_works_without_core_magic_system(self):
        owner = _Owner()
        original = combat_module.HAS_CORE
        combat_module.HAS_CORE = False
        try:
            casted = owner._cast_spell_by_index(0)
            self.assertTrue(casted)
            self.assertIsNotNone(owner._pending_spell)
            self.assertIn("cast_spell", owner._queued_state_triggers)
            self.assertIn("casting", [s.lower() for s in owner._entered_states])

            owner._release_pending_spell()
            self.assertEqual("fire", owner._last_combat_event.get("type"))
            self.assertEqual(24, owner._last_combat_event.get("amount"))
            self.assertEqual("magic", owner._combo_kind)
            self.assertGreaterEqual(owner._combo_chain, 1)
            self.assertEqual(1, len(owner.app.influence_mgr.rows))
        finally:
            combat_module.HAS_CORE = original


if __name__ == "__main__":
    unittest.main()
