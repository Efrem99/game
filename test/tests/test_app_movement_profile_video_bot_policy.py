import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _DummyActor:
    def __init__(self):
        self.pos = SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def setPos(self, *args):
        if len(args) == 1:
            self.pos = args[0]
            return
        self.pos = SimpleNamespace(x=float(args[0]), y=float(args[1]), z=float(args[2]))

    def getPos(self, render=None):
        del render
        return self.pos


class _CaptureTutorial:
    def __init__(self):
        self.calls = []

    def disable(self):
        return None

    def set_mode(self, mode, reset=False):
        del mode, reset
        return None


class _DummyMovementProfileApp:
    _apply_test_profile = XBotApp._apply_test_profile
    _resolve_test_scenario = XBotApp._resolve_test_scenario
    _resolve_test_location = XBotApp._resolve_test_location
    _resolve_test_world_location_name = XBotApp._resolve_test_world_location_name
    _norm_test_mode = XBotApp._norm_test_mode

    def __init__(self, *, video_bot_enabled=False, plan_raw="", scenario_raw="movement_04"):
        self._test_profile = "movement"
        self._test_location_raw = ""
        self._test_scenario_raw = scenario_raw
        self._video_bot_enabled = bool(video_bot_enabled)
        self._video_bot_plan_raw = str(plan_raw)
        self.world = SimpleNamespace(active_location="")
        self.camera = SimpleNamespace(setPos=lambda *a, **k: None, lookAt=lambda *a, **k: None)
        self.player = SimpleNamespace(actor=_DummyActor(), _is_flying=False)
        self.char_state = SimpleNamespace(position=None, velocity=None)
        self.render = object()
        self.movement_tutorial = _CaptureTutorial()
        self.data_mgr = SimpleNamespace(
            get_test_scenarios=lambda: [
                {
                    "id": "movement_04",
                    "profile": "movement",
                    "location": "town",
                    "world_location": "Sharuan Town",
                }
            ]
        )
        self.state_mgr = SimpleNamespace(set_state=lambda *a, **k: None)
        self.GameState = SimpleNamespace(INVENTORY="INVENTORY")

    def _teleport_player_to(self, pos):
        self.player.actor.setPos(pos)
        self.char_state.position = pos
        self.char_state.velocity = (0.0, 0.0, 0.0)
        return True

    def _apply_test_profile_visuals(self, profile):
        del profile

    def _start_tutorial_flow(self, **kwargs):
        self.movement_tutorial.calls.append(dict(kwargs))

    def _activate_journal_test_data(self):
        return None


class AppMovementProfileVideoBotPolicyTests(unittest.TestCase):
    def test_movement_profile_starts_demo_without_video_bot_plan(self):
        app = _DummyMovementProfileApp(video_bot_enabled=False, plan_raw="")

        app._apply_test_profile()

        self.assertEqual(1, len(app.movement_tutorial.calls))
        self.assertEqual("demo", app.movement_tutorial.calls[0]["mode"])

    def test_movement_profile_skips_demo_when_video_bot_plan_is_active(self):
        app = _DummyMovementProfileApp(
            video_bot_enabled=True,
            plan_raw="anim_locomotion_transitions",
        )

        app._apply_test_profile()

        self.assertEqual([], app.movement_tutorial.calls)


if __name__ == "__main__":
    unittest.main()
