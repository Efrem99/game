import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp
from world.sharuan_world import TRAINING_POOL_CENTER


class _ActorStub:
    def __init__(self):
        self.pos = None

    def setPos(self, x, y, z):
        self.pos = (float(x), float(y), float(z))


class _CameraStub:
    def __init__(self):
        self.pos = None
        self.look_target = None

    def setPos(self, x, y, z):
        self.pos = (float(x), float(y), float(z))

    def lookAt(self, target):
        self.look_target = target


class _WorldStub:
    def __init__(self):
        self.active_location = None

    def _th(self, x, y):
        return 2.5


class _TeleportTrainingPoolDummy:
    _video_bot_teleport_training_pool = XBotApp._video_bot_teleport_training_pool

    def __init__(self):
        self.player = SimpleNamespace(actor=_ActorStub(), _py_in_water=False)
        self.world = _WorldStub()
        self.camera = _CameraStub()
        self.char_state = None


class AppTrainingPoolTeleportTests(unittest.TestCase):
    def test_video_bot_training_pool_teleport_uses_canonical_world_center(self):
        app = _TeleportTrainingPoolDummy()

        app._video_bot_teleport_training_pool()

        self.assertIsNotNone(app.player.actor.pos)
        self.assertAlmostEqual(TRAINING_POOL_CENTER[0], app.player.actor.pos[0], places=3)
        self.assertAlmostEqual(TRAINING_POOL_CENTER[1], app.player.actor.pos[1], places=3)
        self.assertEqual("Training Grounds", app.world.active_location)
        self.assertTrue(app.player._py_in_water)


if __name__ == "__main__":
    unittest.main()
