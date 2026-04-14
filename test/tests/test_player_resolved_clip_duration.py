import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _DurationControl:
    def __init__(self, frames, rate):
        self._frames = frames
        self._rate = rate

    def getFrameRate(self):
        return self._rate

    def getNumFrames(self):
        return self._frames


class _DurationActor:
    def __init__(self, duration=0.0, control=None):
        self._duration = duration
        self._control = control

    def getDuration(self, _clip):
        return self._duration

    def getAnimControl(self, _clip):
        return self._control


class _DurationDummy:
    _resolved_clip_duration = Player._resolved_clip_duration

    def __init__(self, actor):
        self.actor = actor


class PlayerResolvedClipDurationTests(unittest.TestCase):
    def test_prefers_actor_duration_when_available(self):
        dummy = _DurationDummy(_DurationActor(duration=0.58))
        self.assertAlmostEqual(0.58, dummy._resolved_clip_duration("flight_takeoff"), places=2)

    def test_falls_back_to_anim_control_frames_and_rate(self):
        control = _DurationControl(frames=24, rate=48)
        dummy = _DurationDummy(_DurationActor(duration=0.0, control=control))
        self.assertAlmostEqual(0.5, dummy._resolved_clip_duration("flight_takeoff"), places=2)


if __name__ == "__main__":
    unittest.main()
