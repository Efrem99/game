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


class _SpellDataMgr:
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
            "nova": {
                "id": "nova",
                "name": "Arcane Nova",
                "damage": 15,
                "cast_time": 0.25,
                "anim_trigger": "cast_arcane",
                "effect": {"type": "nova", "radius": 6.0},
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
                        "duration": 0.22,
                    }
                },
            },
        }

    def get_spell(self, key):
        payload = self.spells.get(str(key or "").strip())
        return dict(payload) if isinstance(payload, dict) else {}

    def get_item(self, _item_id):
        return {}


class _MagicVfxStub:
    def __init__(self):
        self.telegraphs = []
        self.phase_rows = []

    def spawn_spell_telegraph_vfx(self, pos, radius=0.0, color=None, duration=0.0):
        self.telegraphs.append(
            {
                "x": float(getattr(pos, "x", 0.0)),
                "y": float(getattr(pos, "y", 0.0)),
                "z": float(getattr(pos, "z", 0.0)),
                "radius": float(radius),
                "color": tuple(color) if isinstance(color, (list, tuple)) else color,
                "duration": float(duration),
            }
        )
        return object()

    def spawn_spell_phase_vfx(self, pos, phase="", color=None, radius=0.0, duration=0.0):
        self.phase_rows.append(
            {
                "phase": str(phase or ""),
                "x": float(getattr(pos, "x", 0.0)),
                "y": float(getattr(pos, "y", 0.0)),
                "z": float(getattr(pos, "z", 0.0)),
                "radius": float(radius),
                "color": tuple(color) if isinstance(color, (list, tuple)) else color,
                "duration": float(duration),
            }
        )
        return object()


class _ActorStub:
    def getPos(self, _render=None):
        return SimpleNamespace(x=3.0, y=4.0, z=1.5)

    def getH(self):
        return 0.0


class _Owner(PlayerCombatMixin):
    def __init__(self, spell_key):
        self.data_mgr = _SpellDataMgr()
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
        self.app = SimpleNamespace(magic_vfx=_MagicVfxStub())
        self.cs = None
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


class SpellTelegraphHookTests(unittest.TestCase):
    def test_projectile_spell_does_not_emit_cast_telegraph(self):
        owner = _Owner("fireball")
        original = combat_module.HAS_CORE
        combat_module.HAS_CORE = False
        try:
            self.assertTrue(owner._cast_spell_by_index(0))
            self.assertEqual([], owner.app.magic_vfx.telegraphs)
        finally:
            combat_module.HAS_CORE = original

    def test_aoe_spell_emits_cast_telegraph_on_start(self):
        owner = _Owner("nova")
        original = combat_module.HAS_CORE
        combat_module.HAS_CORE = False
        try:
            self.assertTrue(owner._cast_spell_by_index(0))
            self.assertEqual(1, len(owner.app.magic_vfx.telegraphs))
            row = owner.app.magic_vfx.telegraphs[0]
            self.assertGreater(row["radius"], 0.0)
            self.assertGreater(row["duration"], 0.0)
            self.assertAlmostEqual(3.0, row["x"], places=3)
            self.assertAlmostEqual(4.0, row["y"], places=3)
        finally:
            combat_module.HAS_CORE = original

    def test_targeted_projectile_spell_emits_impact_telegraph_in_front_of_caster(self):
        owner = _Owner("meteor")
        original = combat_module.HAS_CORE
        combat_module.HAS_CORE = False
        try:
            self.assertTrue(owner._cast_spell_by_index(0))
            self.assertEqual(1, len(owner.app.magic_vfx.telegraphs))
            row = owner.app.magic_vfx.telegraphs[0]
            self.assertAlmostEqual(3.0, row["x"], places=3)
            self.assertAlmostEqual(11.0, row["y"], places=3)
            self.assertGreater(row["radius"], 3.5)
        finally:
            combat_module.HAS_CORE = original

    def test_spell_phase_vfx_windows_emit_prepare_release_and_impact(self):
        owner = _Owner("meteor")
        original = combat_module.HAS_CORE
        combat_module.HAS_CORE = False
        try:
            self.assertTrue(owner._cast_spell_by_index(0))
            phases = [row["phase"] for row in owner.app.magic_vfx.phase_rows]
            self.assertIn("prepare", phases)

            owner._release_pending_spell()
            phases = [row["phase"] for row in owner.app.magic_vfx.phase_rows]
            self.assertIn("release", phases)
            self.assertIn("impact", phases)
        finally:
            combat_module.HAS_CORE = original


if __name__ == "__main__":
    unittest.main()
