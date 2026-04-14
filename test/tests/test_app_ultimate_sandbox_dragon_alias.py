import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _RootStub:
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


class _ActorStub:
    def __init__(self):
        self.pos = SimpleNamespace(x=0.0, y=0.0, z=10.0)

    def getPos(self, _render=None):
        return self.pos


class _SandboxDragonAliasDummy:
    _apply_test_profile = XBotApp._apply_test_profile
    _resolve_runtime_dragon_boss_candidate = XBotApp._resolve_runtime_dragon_boss_candidate
    _is_runtime_dragon_boss = XBotApp._is_runtime_dragon_boss

    def __init__(self):
        self._test_profile = "ultimate_sandbox"
        self._test_location_raw = ""
        self._test_scenario_raw = ""
        self._video_bot_enabled = False
        self.world = SimpleNamespace(active_location="")
        self.player = SimpleNamespace(actor=_ActorStub())
        self.render = object()
        self.npc_mgr = None
        self.movement_tutorial = None
        self.dragon_boss = None
        self.boss_manager = None

    def _resolve_test_scenario(self, _raw):
        return None

    def _resolve_test_location(self, _token):
        return None

    def _resolve_test_world_location_name(self, _token):
        return ""

    def _apply_test_profile_visuals(self, _profile):
        return None

    def _teleport_player_to(self, _pos):
        return True


class AppUltimateSandboxDragonAliasTests(unittest.TestCase):
    def test_resolve_runtime_dragon_boss_candidate_ignores_primary_golem_fallback(self):
        app = _SandboxDragonAliasDummy()
        golem = SimpleNamespace(id="golem_warden", kind="golem", root=_RootStub())
        app.boss_manager = SimpleNamespace(units=[golem])

        self.assertIsNone(app._resolve_runtime_dragon_boss_candidate())

    def test_apply_test_profile_does_not_move_aliased_golem_as_dragon_in_ultimate_sandbox(self):
        app = _SandboxDragonAliasDummy()
        golem_root = _RootStub()
        golem = SimpleNamespace(id="golem_warden", kind="golem", root=golem_root)
        app.boss_manager = SimpleNamespace(get_primary=lambda kind: golem if kind == "golem" else None, units=[golem])
        app.dragon_boss = golem

        app._apply_test_profile()

        self.assertAlmostEqual(110.0, float(golem_root.pos.x), places=3)
        self.assertAlmostEqual(190.0, float(golem_root.pos.y), places=3)
        self.assertAlmostEqual(5.5, float(golem_root.pos.z), places=3)


if __name__ == "__main__":
    unittest.main()
