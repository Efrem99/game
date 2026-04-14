import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _RuntimePolicyDummy:
    _build_ultimate_sandbox_enemy_overrides = XBotApp._build_ultimate_sandbox_enemy_overrides
    _apply_test_profile = XBotApp._apply_test_profile
    _build_ultimate_sandbox_runtime_npcs = XBotApp._build_ultimate_sandbox_runtime_npcs
    _runtime_npc_spawn_data = XBotApp._runtime_npc_spawn_data
    _spawn_npcs = XBotApp._spawn_npcs
    _resolve_test_location = XBotApp._resolve_test_location
    _resolve_test_scenario = XBotApp._resolve_test_scenario
    _resolve_test_world_location_name = XBotApp._resolve_test_world_location_name
    _norm_test_mode = XBotApp._norm_test_mode
    _is_lightweight_test_runtime = XBotApp._is_lightweight_test_runtime
    _should_skip_runtime_npc_spawns = XBotApp._should_skip_runtime_npc_spawns
    _should_skip_runtime_roster_spawns = XBotApp._should_skip_runtime_roster_spawns
    _should_spawn_default_runtime_vehicles = XBotApp._should_spawn_default_runtime_vehicles
    _should_spawn_sandbox_runtime_npcs = XBotApp._should_spawn_sandbox_runtime_npcs

    def __init__(
        self,
        profile="",
        video_bot=False,
        force_aggro=False,
        location_raw="",
        skip_roster=False,
        skip_vehicles=False,
    ):
        self._test_profile = str(profile)
        self._video_bot_enabled = bool(video_bot)
        self._video_bot_force_aggro_mobs = bool(force_aggro)
        self._debug_skip_runtime_roster_spawns = bool(skip_roster)
        self._debug_skip_runtime_vehicles = bool(skip_vehicles)
        self._test_location_raw = str(location_raw)
        self._test_scenario_raw = ""
        self.world = SimpleNamespace(active_location="")
        self.camera = SimpleNamespace(
            setPos=lambda *args, **kwargs: None,
            lookAt=lambda *args, **kwargs: None,
        )
        self.player = SimpleNamespace(actor=_DummyActor())
        self.char_state = SimpleNamespace(position=None, velocity=None)
        self.render = object()
        self.movement_tutorial = None
        self.npc_mgr = None
        self.data_mgr = SimpleNamespace(
            get_test_scenarios=lambda: [],
            npcs={
                "town_guard": {
                    "name": "Town Guard",
                    "role": "guard",
                    "pos": [14.0, 22.0, 0.0],
                    "appearance": {"model": "assets/models/xbot/Xbot.glb", "scale": 1.0},
                }
            },
        )

    def _load_test_scenario(self, profile):
        del profile
        return None

    def _teleport_player_to(self, pos):
        self.player.actor.setPos(pos)
        self.char_state.position = pos
        self.char_state.velocity = (0.0, 0.0, 0.0)
        return True

    def _apply_test_profile_visuals(self, profile):
        del profile

    def _setup_cursor(self):
        return None


class _DummyActor:
    def __init__(self):
        self.pos = None

    def setPos(self, *args):
        if len(args) == 1:
            self.pos = args[0]
            return
        self.pos = SimpleNamespace(
            x=float(args[0]),
            y=float(args[1]),
            z=float(args[2]),
        )

    def getPos(self, render=None):
        del render
        return self.pos


class _CaptureNpcManager:
    def __init__(self):
        self.spawn_rows = None

    def spawn_from_data(self, rows):
        self.spawn_rows = dict(rows or {})


class AppUltimateSandboxRuntimePolicyTests(unittest.TestCase):
    def test_ultimate_sandbox_keeps_full_runtime_even_without_core(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")

        with patch("app.HAS_CORE", False):
            self.assertFalse(app._is_lightweight_test_runtime())
            self.assertTrue(app._should_spawn_sandbox_runtime_npcs())

    def test_lightweight_ultimate_sandbox_keeps_default_vehicles(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")

        with patch("app.HAS_CORE", False):
            self.assertTrue(app._should_spawn_default_runtime_vehicles())

    def test_other_runtime_profiles_keep_default_vehicles(self):
        app = _RuntimePolicyDummy(profile="movement")

        with patch("app.HAS_CORE", False):
            self.assertTrue(app._is_lightweight_test_runtime())
            self.assertTrue(app._should_spawn_default_runtime_vehicles())

    def test_force_aggro_restores_full_ultimate_sandbox_spawns(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox", video_bot=True, force_aggro=True)

        with patch("app.HAS_CORE", False):
            self.assertFalse(app._is_lightweight_test_runtime())
            self.assertTrue(app._should_spawn_default_runtime_vehicles())
            self.assertTrue(app._should_spawn_sandbox_runtime_npcs())

    def test_explicit_debug_flag_can_skip_runtime_roster_spawns(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox", skip_roster=True)

        self.assertTrue(app._should_skip_runtime_roster_spawns())

    def test_explicit_debug_flag_can_skip_runtime_vehicles(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox", skip_vehicles=True)

        self.assertFalse(app._should_spawn_default_runtime_vehicles())

    def test_apply_test_profile_keeps_explicit_ultimate_sandbox_coordinates(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox", location_raw="25,5,6.2")

        app._apply_test_profile()

        self.assertEqual("ultimate_sandbox", app.world.active_location)
        self.assertAlmostEqual(25.0, float(app.player.actor.pos.x), places=3)
        self.assertAlmostEqual(5.0, float(app.player.actor.pos.y), places=3)
        self.assertAlmostEqual(6.2, float(app.player.actor.pos.z), places=3)

    def test_apply_test_profile_keeps_default_ultimate_sandbox_center_spawn(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")

        app._apply_test_profile()

        self.assertEqual("ultimate_sandbox", app.world.active_location)
        self.assertAlmostEqual(0.0, float(app.player.actor.pos.x), places=3)
        self.assertAlmostEqual(0.0, float(app.player.actor.pos.y), places=3)
        self.assertAlmostEqual(10.0, float(app.player.actor.pos.z), places=3)

    def test_apply_test_profile_does_not_double_move_primary_golem_via_dragon_alias(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")
        golem_root = _DummyActor()
        golem = SimpleNamespace(root=golem_root)
        app.boss_manager = SimpleNamespace(get_primary=lambda kind: golem if kind == "golem" else None)
        app.dragon_boss = golem

        with patch("app.HAS_CORE", True):
            app._apply_test_profile()

        self.assertAlmostEqual(110.0, float(golem_root.pos.x), places=3)
        self.assertAlmostEqual(190.0, float(golem_root.pos.y), places=3)
        self.assertAlmostEqual(5.5, float(golem_root.pos.z), places=3)

    def test_apply_test_profile_skips_ultimate_sandbox_boss_relocation_without_core(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")
        golem_root = _DummyActor()
        golem_root.setPos(34.0, -6.0, 7.0)
        golem = SimpleNamespace(root=golem_root)
        app.boss_manager = SimpleNamespace(get_primary=lambda kind: golem if kind == "golem" else None)
        app.dragon_boss = golem

        with patch("app.HAS_CORE", False):
            app._apply_test_profile()

        self.assertAlmostEqual(34.0, float(golem_root.pos.x), places=3)
        self.assertAlmostEqual(-6.0, float(golem_root.pos.y), places=3)
        self.assertAlmostEqual(7.0, float(golem_root.pos.z), places=3)

    def test_resolve_test_location_supports_safe_ultimate_sandbox_probe_anchors(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")
        app.world = SimpleNamespace(
            active_location="ultimate_sandbox",
            _th=lambda x, y: 5.0,
            sample_water_height=lambda x, y: -3.0,
        )

        expected = {
            "sandbox_stairs_approach": (25.0, -36.0, 7.2),
            "sandbox_traversal_approach": (18.0, -4.0, 7.2),
            "sandbox_wallrun_approach": (-28.5, -16.0, 7.2),
            "sandbox_tower_approach": (-12.0, -60.0, 7.2),
            "sandbox_pool_edge": (0.0, 32.0, 7.2),
            "sandbox_story_chest_approach": (12.0, 8.6, 7.2),
            "sandbox_story_book_approach": (-12.0, 8.6, 7.2),
        }

        for token, (exp_x, exp_y, exp_z) in expected.items():
            pos = app._resolve_test_location(token)
            self.assertIsNotNone(pos, token)
            self.assertAlmostEqual(exp_x, float(pos.x), places=3, msg=token)
            self.assertAlmostEqual(exp_y, float(pos.y), places=3, msg=token)
            self.assertAlmostEqual(exp_z, float(pos.z), places=3, msg=token)

    def test_ultimate_sandbox_runtime_npcs_do_not_reintroduce_extra_sandbox_guide(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")

        rows = app._build_ultimate_sandbox_runtime_npcs()

        self.assertIsInstance(rows, dict)
        self.assertEqual({}, rows)
        self.assertNotIn("sandbox_wolf_1", rows)
        self.assertNotIn("sandbox_golem", rows)

    def test_ultimate_sandbox_enemy_overrides_preserve_authored_golem_and_wolves(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")

        rows = app._build_ultimate_sandbox_enemy_overrides()
        ids = {str(row.get("id", "")).strip() for row in rows if isinstance(row, dict)}

        self.assertIn("sandbox_golem", ids)
        self.assertIn("sandbox_wolf_1", ids)
        self.assertIn("sandbox_wolf_2", ids)

    def test_ultimate_sandbox_runtime_uses_curated_npc_payload_instead_of_world_roster(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")

        rows = app._runtime_npc_spawn_data()

        self.assertIsInstance(rows, dict)
        self.assertEqual({}, rows)
        self.assertNotIn("town_guard", rows)

    def test_non_sandbox_runtime_keeps_world_npc_roster(self):
        app = _RuntimePolicyDummy(profile="movement")

        rows = app._runtime_npc_spawn_data()

        self.assertIn("town_guard", rows)

    def test_spawn_npcs_uses_curated_runtime_roster_for_ultimate_sandbox(self):
        app = _RuntimePolicyDummy(profile="ultimate_sandbox")
        app.npc_mgr = _CaptureNpcManager()

        app._spawn_npcs()

        self.assertIsNotNone(app.npc_mgr.spawn_rows)
        self.assertEqual({}, app.npc_mgr.spawn_rows)
        self.assertNotIn("town_guard", app.npc_mgr.spawn_rows)


if __name__ == "__main__":
    unittest.main()
