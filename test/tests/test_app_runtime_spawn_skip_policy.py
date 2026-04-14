import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _CaptureNpcManager:
    def __init__(self):
        self.calls = 0
        self.rows = None

    def spawn_from_data(self, rows):
        self.calls += 1
        self.rows = dict(rows or {})


class _SpawnPolicyDummy:
    _norm_test_mode = XBotApp._norm_test_mode
    _should_skip_runtime_npc_spawns = XBotApp._should_skip_runtime_npc_spawns
    _should_skip_runtime_roster_spawns = XBotApp._should_skip_runtime_roster_spawns
    _should_spawn_default_runtime_vehicles = XBotApp._should_spawn_default_runtime_vehicles
    _should_skip_intro_for_auto_start_test = XBotApp._should_skip_intro_for_auto_start_test
    _should_skip_startup_preload_for_auto_start_test = XBotApp._should_skip_startup_preload_for_auto_start_test
    _spawn_npcs = XBotApp._spawn_npcs

    def __init__(self, *, profile="", skip_roster=False, skip_vehicles=False, auto_start=False, location="", scenario=""):
        self._test_profile = str(profile)
        self._debug_skip_runtime_roster_spawns = bool(skip_roster)
        self._debug_skip_runtime_vehicles = bool(skip_vehicles)
        self._auto_start_requested = bool(auto_start)
        self._test_location_raw = str(location)
        self._test_scenario_raw = str(scenario)
        self.npc_mgr = _CaptureNpcManager()
        self.data_mgr = SimpleNamespace(
            npcs={
                "town_guard": {
                    "name": "Town Guard",
                    "pos": [1.0, 2.0, 0.0],
                    "appearance": {"scale": 1.0},
                }
            }
        )
        self.loader = SimpleNamespace(loadModel=lambda *_args, **_kwargs: None)
        self.render = object()
        self.hidden = object()


class AppRuntimeSpawnSkipPolicyTests(unittest.TestCase):
    def test_auto_start_runtime_test_skips_intro(self):
        app = _SpawnPolicyDummy(auto_start=True, profile="ultimate_sandbox", location="ultimate_sandbox")

        self.assertTrue(app._should_skip_intro_for_auto_start_test())

    def test_auto_start_runtime_test_skips_nonessential_startup_preload(self):
        app = _SpawnPolicyDummy(auto_start=True, profile="ultimate_sandbox", scenario="ultimate_sandbox_01")

        self.assertTrue(app._should_skip_startup_preload_for_auto_start_test())

    def test_explicit_debug_flag_skips_runtime_roster_spawns(self):
        app = _SpawnPolicyDummy(skip_roster=True)

        self.assertTrue(app._should_skip_runtime_roster_spawns())

    def test_non_mount_runtime_profiles_skip_default_runtime_vehicles(self):
        app = _SpawnPolicyDummy(profile="movement")

        self.assertFalse(app._should_spawn_default_runtime_vehicles())

    def test_mount_profile_keeps_default_runtime_vehicles_when_not_explicitly_disabled(self):
        app = _SpawnPolicyDummy(profile="mounts")

        self.assertTrue(app._should_spawn_default_runtime_vehicles())

    def test_spawn_npcs_respects_skip_runtime_roster_flag(self):
        app = _SpawnPolicyDummy(skip_roster=True)

        app._spawn_npcs()

        self.assertEqual(0, app.npc_mgr.calls)


if __name__ == "__main__":
    unittest.main()
