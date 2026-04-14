import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.movement_tutorial_manager import MovementTutorialManager


class _TutorialAppDummy:
    def __init__(self, pos=(18.0, 24.0, 0.0)):
        self.player = SimpleNamespace(
            actor=SimpleNamespace(
                getPos=lambda render=None: SimpleNamespace(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]))
            ),
            cs=SimpleNamespace(velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0), grounded=True, inWater=False),
            _anim_state="idle",
            _is_flying=False,
            _get_action=lambda _k: False,
            get_hud_combat_event=lambda: {},
        )
        self.render = object()
        self.project_root = str(ROOT)
        self.world = SimpleNamespace(active_location="training_grounds")
        self.data_mgr = SimpleNamespace(
            t=lambda _key, default="": default,
            get_binding=lambda action: {
                "forward": "w",
                "left": "a",
                "backward": "s",
                "right": "d",
                "jump": "space",
            }.get(str(action), str(action)),
        )
        self.event_bus = None


class MovementTutorialCheckpointPopupTests(unittest.TestCase):
    def test_active_checkpoint_near_player_uses_card_popup(self):
        app = _TutorialAppDummy(pos=(18.0, 24.0, 0.0))
        manager = MovementTutorialManager(app)
        manager.enable(reset=True, mode="main")

        payload = manager.get_hud_payload()

        self.assertTrue(payload["visible"])
        self.assertEqual("card", payload["display_mode"])
        self.assertEqual("move", payload["step_id"])
        self.assertGreaterEqual(len(payload["keys"]), 1)

    def test_distant_checkpoint_stays_banner(self):
        app = _TutorialAppDummy(pos=(99.0, 99.0, 0.0))
        manager = MovementTutorialManager(app)
        manager.enable(reset=True, mode="main")

        payload = manager.get_hud_payload()

        self.assertTrue(payload["visible"])
        self.assertEqual("banner", payload["display_mode"])


if __name__ == "__main__":
    unittest.main()
