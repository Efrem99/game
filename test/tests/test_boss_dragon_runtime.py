import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp
from entities.dragon_boss import DragonBoss
from entities.player_combat_mixin import PlayerCombatMixin
from ui.hud_overlay import HUDOverlay


class _DummyVec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _DummyActor:
    def __init__(self, pos=None):
        self._pos = pos or _DummyVec()

    def getPos(self, render=None):
        del render
        return self._pos


class _DragonBossStub:
    def __init__(self, app):
        self.app = app
        self.id = "dragon_boss"
        self.name = "Ashen Dragon"
        self.is_boss = True
        self.is_engaged = False
        self.hp = 900.0
        self.max_hp = 1200.0
        self.root = object()
        self.update_calls = []

    @property
    def is_alive(self):
        return bool(self.hp > 0.0)

    def update(self, dt, player_pos, stealth_state=None):
        self.update_calls.append((float(dt), player_pos, stealth_state))


class _BossManagerStub:
    def __init__(self, units=None):
        self.units = list(units or [])
        self.update_calls = []
        self.primary_calls = []

    def update(self, dt, player_pos, stealth_state=None):
        self.update_calls.append((float(dt), player_pos, stealth_state))

    def get_primary(self, kind="golem"):
        self.primary_calls.append(str(kind))
        return None


class _RuntimeDragonDummy:
    _enemy_target_meta = XBotApp._enemy_target_meta

    def __init__(self, profile="", location="", dragon_boss=None, boss_manager=None):
        self._test_profile = str(profile)
        self.world = types.SimpleNamespace(active_location=str(location))
        self.render = object()
        self.player = types.SimpleNamespace(actor=_DummyActor())
        self.dragon_boss = dragon_boss
        self.boss_manager = boss_manager
        self._aim_target_info = None
        self._boss_update_fail_count = 0
        self._boss_update_last_log_time = 0.0


class _CombatOwner(PlayerCombatMixin):
    _resolve_enemy_unit_for_target = PlayerCombatMixin._resolve_enemy_unit_for_target
    _apply_ranged_damage = PlayerCombatMixin._apply_ranged_damage

    def __init__(self, app):
        self.app = app

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)


class _FakeFrame:
    def __init__(self):
        self.hidden = True
        self.props = {}

    def hide(self):
        self.hidden = True

    def show(self):
        self.hidden = False

    def isHidden(self):
        return bool(self.hidden)

    def __setitem__(self, key, value):
        self.props[key] = value

    def __getitem__(self, key):
        return self.props[key]


class _FakeText:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = str(value)


class _HudBossDummy:
    _update_boss_health_bar = HUDOverlay._update_boss_health_bar

    def __init__(self, app):
        self.app = app
        self.boss_hp_root = _FakeFrame()
        self.boss_hp_fill = _FakeFrame()
        self.boss_hp_name = _FakeText()
        self.boss_hp_value = _FakeText()


class AppDragonRuntimeTests(unittest.TestCase):
    def test_ensure_dragon_boss_runtime_spawns_real_dragon_for_dragon_profile(self):
        boss_manager = _BossManagerStub()
        app = _RuntimeDragonDummy(profile="dragon", location="Dragon Arena", boss_manager=boss_manager)
        self.assertTrue(hasattr(XBotApp, "_ensure_dragon_boss_runtime"))

        with patch("app.DragonBoss", _DragonBossStub):
            XBotApp._ensure_dragon_boss_runtime(app)

        self.assertIsInstance(app.dragon_boss, _DragonBossStub)
        self.assertEqual([], boss_manager.primary_calls)

    def test_update_enemy_boss_runtime_updates_dragon_and_enemy_roster(self):
        boss_manager = _BossManagerStub()
        dragon = _DragonBossStub(None)
        app = _RuntimeDragonDummy(
            profile="dragon",
            location="Dragon Arena",
            dragon_boss=dragon,
            boss_manager=boss_manager,
        )
        self.assertTrue(hasattr(XBotApp, "_update_enemy_boss_runtime"))

        XBotApp._update_enemy_boss_runtime(app, 0.125, _DummyVec(2.0, 3.0, 4.0))

        self.assertEqual(1, len(boss_manager.update_calls))
        self.assertEqual(1, len(dragon.update_calls))

    def test_active_boss_target_info_falls_back_to_engaged_dragon(self):
        dragon = _DragonBossStub(None)
        dragon.is_engaged = True
        dragon.hp = 640.0
        dragon.max_hp = 800.0
        app = _RuntimeDragonDummy(profile="dragon", location="Dragon Arena", dragon_boss=dragon)
        self.assertTrue(hasattr(XBotApp, "get_active_boss_target_info"))

        info = XBotApp.get_active_boss_target_info(app)

        self.assertIsInstance(info, dict)
        self.assertEqual("dragon_boss", info.get("id"))
        self.assertTrue(bool(info.get("is_boss", False)))
        self.assertAlmostEqual(0.8, float(info.get("hp_ratio", 0.0)), places=3)


class DragonCombatTargetingTests(unittest.TestCase):
    def test_resolve_enemy_unit_for_target_returns_dragon_boss(self):
        dragon = _DragonBossStub(None)
        app = types.SimpleNamespace(
            boss_manager=types.SimpleNamespace(units=[]),
            dragon_boss=dragon,
        )
        owner = _CombatOwner(app)

        unit = owner._resolve_enemy_unit_for_target({"id": "dragon_boss"})

        self.assertIs(unit, dragon)

    def test_apply_ranged_damage_prefers_take_damage_hook(self):
        dragon = _DragonBossStub(None)
        dragon.damage_calls = []

        def _take_damage(amount, damage_type="physical", source=None):
            dragon.damage_calls.append((float(amount), str(damage_type), source))
            dragon.hp = max(0.0, float(dragon.hp) - float(amount))
            return True

        dragon.take_damage = _take_damage
        app = types.SimpleNamespace(
            boss_manager=types.SimpleNamespace(units=[]),
            dragon_boss=dragon,
        )
        owner = _CombatOwner(app)

        hit = owner._apply_ranged_damage({"id": "dragon_boss"}, 140)

        self.assertTrue(hit)
        self.assertEqual(1, len(dragon.damage_calls))
        self.assertAlmostEqual(760.0, float(dragon.hp), places=3)


class BossHudFallbackTests(unittest.TestCase):
    def test_boss_bar_uses_active_boss_info_without_direct_target(self):
        app = types.SimpleNamespace(
            data_mgr=types.SimpleNamespace(t=lambda key, default: default),
            get_active_boss_target_info=lambda: {
                "kind": "enemy",
                "id": "dragon_boss",
                "name": "Ashen Dragon",
                "is_boss": True,
                "hp": 300.0,
                "max_hp": 500.0,
                "hp_ratio": 0.6,
            },
        )
        hud = _HudBossDummy(app)

        hud._update_boss_health_bar(None)

        self.assertFalse(hud.boss_hp_root.isHidden())
        self.assertEqual("BOSS HP: Ashen Dragon", hud.boss_hp_name.text)
        self.assertEqual("300/500", hud.boss_hp_value.text)


class DragonBossDamageTests(unittest.TestCase):
    def test_take_damage_can_kill_dragon_boss(self):
        dragon = DragonBoss.__new__(DragonBoss)
        dragon.cfg = {"enemy": {"stats": {"armor": 14.0, "max_hp": 1500.0}}}
        dragon.hp = 30.0
        dragon.max_hp = 1500.0
        dragon._state = "fire_breath"
        dragon._state_lock = 1.5
        dragon._is_engaged = True
        dragon.awareness = "alert"
        dragon._fire_emit_accum = 0.5
        dragon._fire_tick_accum = 0.5

        hit = dragon.take_damage(999.0, "physical", source="hero")

        self.assertTrue(hit)
        self.assertLessEqual(float(dragon.hp), 0.0)
        self.assertFalse(bool(dragon.is_alive))
        self.assertEqual("death", dragon._state)
        self.assertFalse(bool(dragon._is_engaged))


if __name__ == "__main__":
    unittest.main()
