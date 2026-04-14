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
                "cast_time": 0.22,
                "anim_trigger": "cast_fire",
                "projectile": {"radius": 0.8},
                "effect": {"type": "explosion", "radius": 2.5},
            },
            "meteor": {
                "id": "meteor",
                "name": "Meteor",
                "damage": 50,
                "cast_time": 0.35,
                "anim_trigger": "cast_fire",
                "projectile": {"radius": 1.2},
                "effect": {"type": "explosion", "radius": 4.0},
                "runtime": {
                    "telegraph": {
                        "enabled": True,
                        "anchor": "impact",
                        "radius": 4.0,
                    }
                },
            },
        }

    def get_spell(self, key):
        payload = self.spells.get(str(key or "").strip())
        return dict(payload) if isinstance(payload, dict) else {}

    def get_item(self, _item_id):
        return {}


class _ActorStub:
    def getPos(self, _render=None):
        return SimpleNamespace(x=10.0, y=20.0, z=3.0)

    def getH(self):
        return 90.0


class _Owner(PlayerCombatMixin):
    def __init__(self, spell_key="fireball", stamina=100.0):
        self.data_mgr = _DataMgr()
        self._spell_cache = [spell_key]
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
        self.app = SimpleNamespace()
        self.cs = SimpleNamespace(stamina=float(stamina), maxStamina=100.0)
        self.magic = None
        self.particles = None
        self.enemies = []
        self._anim_state = "idle"

    def _refresh_spell_cache(self):
        return None

    def _play_sfx(self, *_args, **_kwargs):
        return None

    def _set_weapon_drawn(self, *_args, **_kwargs):
        return None

    def _queue_state_trigger(self, trigger):
        self._queued_state_triggers.append(str(trigger or ""))

    def _enter_state(self, name):
        self._anim_state = str(name or "")
        return True


class SpellProjectileScatterTests(unittest.TestCase):
    def _cast_runtime(self, owner, idx=0):
        self.assertTrue(owner._cast_spell_by_index(idx))
        runtime = dict(owner._pending_spell["runtime"])
        owner._pending_spell = None
        owner._pending_spell_release_time = 0.0
        owner._spell_cast_lock_until = 0.0
        owner._spell_cooldowns.clear()
        return runtime

    def test_fast_projectiles_gain_more_scatter_when_spammed_while_fatigued(self):
        owner = _Owner("fireball", stamina=100.0)
        runtime_first = self._cast_runtime(owner)
        first = owner._build_python_spell_effect("fireball", runtime_first)
        base_y = 20.0
        first_dev = abs(float(first.destination.y) - base_y)

        owner.cs.stamina = 20.0
        for _ in range(4):
            runtime_last = self._cast_runtime(owner)
        last = owner._build_python_spell_effect("fireball", runtime_last)
        last_dev = abs(float(last.destination.y) - base_y)

        self.assertTrue(runtime_first["scatter"]["enabled"])
        self.assertGreater(last_dev, first_dev + 0.15)

    def test_slow_projectiles_keep_scatter_disabled(self):
        owner = _Owner("meteor", stamina=15.0)
        runtime = self._cast_runtime(owner)
        effect = owner._build_python_spell_effect("meteor", runtime)

        self.assertFalse(runtime["scatter"]["enabled"])
        self.assertAlmostEqual(20.0, float(effect.destination.y), places=3)


if __name__ == "__main__":
    unittest.main()
