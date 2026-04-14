import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import app as app_module
from app import XBotApp
from entities.companion_unit import CompanionUnit


class _DummyActor:
    def __init__(self, pos):
        self._pos = pos

    def getPos(self, render=None):
        del render
        return self._pos


class _FakeRuntimeUnit:
    def __init__(self, app, member_id, data):
        self.app = app
        self.member_id = str(member_id)
        self.data = dict(data or {})
        self.spawned_at = None
        self.despawned = False

    def spawn(self, pos):
        self.spawned_at = pos

    def despawn(self):
        self.despawned = True


class _DummyCompanionManager:
    def __init__(self):
        self.active_companion_id = "adrian"
        self.active_pet_id = "emberfox"
        self._rows = {
            "adrian": {"id": "adrian", "name": "Adrian", "kind": "companion"},
            "emberfox": {"id": "emberfox", "name": "Emberfox", "kind": "pet"},
        }

    def get_active_companion_id(self):
        return self.active_companion_id

    def get_active_pet_id(self):
        return self.active_pet_id

    def get_runtime_member_data(self, member_id):
        return dict(self._rows.get(str(member_id), {}))


class _RuntimeSyncDummy:
    _sync_party_runtime = XBotApp._sync_party_runtime

    def __init__(self):
        self.render = object()
        self.player = SimpleNamespace(actor=_DummyActor(app_module.Vec3(12.0, 4.0, 1.0)))
        self.companion_mgr = _DummyCompanionManager()
        self._active_party = {}


class CompanionRuntimeSyncTests(unittest.TestCase):
    def test_sync_party_runtime_uses_manager_runtime_data_and_spawns_missing_units(self):
        app = _RuntimeSyncDummy()

        with patch.object(app_module, "CompanionUnit", _FakeRuntimeUnit):
            app._sync_party_runtime()

        self.assertEqual({"adrian", "emberfox"}, set(app._active_party.keys()))
        self.assertEqual("Adrian", app._active_party["adrian"].data["name"])
        self.assertEqual("Emberfox", app._active_party["emberfox"].data["name"])

    def test_sync_party_runtime_despawns_units_removed_from_active_slots(self):
        app = _RuntimeSyncDummy()
        stale = _FakeRuntimeUnit(app, "adrian", {"id": "adrian"})
        app._active_party["adrian"] = stale
        app.companion_mgr.active_companion_id = ""
        app.companion_mgr.active_pet_id = "emberfox"

        with patch.object(app_module, "CompanionUnit", _FakeRuntimeUnit):
            app._sync_party_runtime()

        self.assertTrue(stale.despawned)
        self.assertNotIn("adrian", app._active_party)
        self.assertIn("emberfox", app._active_party)


class _EnemyRoot:
    def __init__(self, pos):
        self._pos = pos

    def getPos(self, render=None):
        del render
        return self._pos

    def lookAt(self, pos):
        self.look_target = pos

    def setP(self, value):
        self.pitch = value


class _EnemyStub:
    def __init__(self, enemy_id, pos, is_alive=True):
        self.id = str(enemy_id)
        self.root = _EnemyRoot(pos)
        self.actor = None
        self.is_alive = bool(is_alive)
        self.damage_log = []

    def take_damage(self, amount, damage_type, source_id):
        self.damage_log.append(
            {
                "amount": float(amount),
                "damage_type": str(damage_type),
                "source_id": str(source_id),
            }
        )


class _MagicVfxStub:
    def __init__(self):
        self.telegraph_calls = []
        self.phase_calls = []

    def spawn_spell_telegraph_vfx(self, pos, radius=0.0, color=None, duration=0.0):
        self.telegraph_calls.append(
            {
                "pos": pos,
                "radius": float(radius),
                "color": tuple(color) if isinstance(color, (list, tuple)) else color,
                "duration": float(duration),
            }
        )

    def spawn_spell_phase_vfx(self, pos, phase="", color=None, radius=0.0, duration=0.0):
        self.phase_calls.append(
            {
                "pos": pos,
                "phase": str(phase),
                "color": tuple(color) if isinstance(color, (list, tuple)) else color,
                "radius": float(radius),
                "duration": float(duration),
            }
        )


class _AudioStub:
    def __init__(self):
        self.calls = []

    def play_sfx(self, key, volume=1.0, rate=1.0):
        self.calls.append((str(key), float(volume), float(rate)))
        return True


class CompanionUnitTargetingTests(unittest.TestCase):
    def test_find_best_target_falls_back_to_boss_manager_units_when_helper_missing(self):
        unit = CompanionUnit.__new__(CompanionUnit)
        unit.render = object()
        unit.root = _EnemyRoot(app_module.Vec3(0.0, 0.0, 0.0))
        unit.app = SimpleNamespace(
            player=None,
            boss_manager=SimpleNamespace(
                units=[
                    _EnemyStub("far", app_module.Vec3(8.0, 0.0, 0.0)),
                    _EnemyStub("near", app_module.Vec3(3.0, 0.0, 0.0)),
                ]
            ),
        )

        target = unit._find_best_target()

        self.assertIsNotNone(target)
        self.assertEqual("near", target.id)


class CompanionUnitCombatProfileTests(unittest.TestCase):
    def test_resolve_assist_profile_is_contextual_to_combat_style(self):
        unit = CompanionUnit.__new__(CompanionUnit)

        archery = unit._resolve_assist_profile({"combat_assist": "arcane_archery"})
        blade = unit._resolve_assist_profile({"combat_assist": "training_blade_support"})
        shield = unit._resolve_assist_profile({"combat_assist": "shield_wall"})

        self.assertGreater(archery["range"], blade["range"])
        self.assertGreater(archery["damage"], shield["damage"])
        self.assertGreater(shield["cooldown"], blade["cooldown"])
        self.assertEqual("arcane", archery["damage_type"])

    def test_handle_assist_uses_profile_damage_cooldown_and_feedback(self):
        target = _EnemyStub("raider", app_module.Vec3(6.0, 0.0, 0.0))
        vfx = _MagicVfxStub()
        audio = _AudioStub()
        unit = CompanionUnit.__new__(CompanionUnit)
        unit.app = SimpleNamespace(
            magic_vfx=vfx,
            audio_director=audio,
            audio=audio,
            player=None,
        )
        unit.render = object()
        unit.root = _EnemyRoot(app_module.Vec3(0.0, 0.0, 0.0))
        unit.id = "eldrin_elf"
        unit.name = "Eldrin"
        unit.data = {"assist": {"combat_assist": "arcane_archery"}}
        unit._combat_target = target
        unit._attack_cooldown = 0.0

        unit._handle_assist(0.1, unit.data["assist"])

        self.assertEqual(1, len(target.damage_log))
        self.assertEqual("eldrin_elf", target.damage_log[0]["source_id"])
        self.assertGreater(unit._attack_cooldown, 1.0)
        self.assertTrue(vfx.phase_calls)
        self.assertTrue(audio.calls)


if __name__ == "__main__":
    unittest.main()
