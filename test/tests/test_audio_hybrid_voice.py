import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers import audio_director as audio_module
from managers.audio_director import AudioDirector, AudioSound
from managers.dialog_cinematic_manager import DialogCinematicManager


class _FakeSound:
    def __init__(self, path, play_log):
        self.path = str(path).replace("\\", "/")
        self._play_log = play_log
        self._playing = False
        self._volume = 0.0
        self._rate = 1.0
        self._loop = False

    def setLoop(self, enabled):
        self._loop = bool(enabled)

    def setVolume(self, volume):
        self._volume = float(volume)

    def getVolume(self):
        return float(self._volume)

    def setPlayRate(self, rate):
        self._rate = float(rate)

    def play(self):
        self._playing = True
        self._play_log.append((self.path, float(self._volume), float(self._rate), bool(self._loop)))

    def stop(self):
        self._playing = False

    def status(self):
        return AudioSound.PLAYING if self._playing else 0


class _FakeLoader:
    def __init__(self, play_log):
        self._play_log = play_log

    def loadSfx(self, path):
        return _FakeSound(path, self._play_log)

    def loadMusic(self, path):
        return _FakeSound(path, self._play_log)


class _FakeTaskMgr:
    def __init__(self):
        self.calls = []

    def doMethodLater(self, delay, callback, name, extraArgs=None, appendTask=False):
        args = list(extraArgs or [])
        self.calls.append((float(delay), str(name)))
        return callback(*args)


class _FakeClock:
    def __init__(self):
        self.now = 0.0

    def getFrameTime(self):
        return float(self.now)


class _FakeDataManager:
    def __init__(self, sound_config):
        self.sound_config = dict(sound_config)


class _FakeApp:
    def __init__(self, sound_config):
        self.project_root = str(ROOT)
        self.play_log = []
        self.loader = _FakeLoader(self.play_log)
        self.data_mgr = _FakeDataManager(sound_config)
        self.taskMgr = _FakeTaskMgr()
        self.event_bus = None
        self.state_mgr = None
        self.GameState = None
        self.player = None
        self.world = None
        self.vehicle_mgr = None
        self.boss_manager = None
        self.dragon_boss = None


class _FakeAudioRoute:
    def __init__(self):
        self.calls = []

    def play_hybrid_voice_key(self, voice_key, **kwargs):
        self.calls.append((str(voice_key), dict(kwargs)))
        return True


class _FakeDialogApp:
    def __init__(self, audio_route):
        self.audio_director = audio_route
        self.audio = audio_route


class AudioHybridVoiceTests(unittest.TestCase):
    def _director(self, extra_cfg=None):
        cfg = {
            "voice_volume": 1.0,
            "voice_playback": {
                "rate_jitter": 0.0,
                "volume_jitter": 0.0,
                "playrate_min": 0.5,
                "playrate_max": 1.75,
            },
            "voice_hybrid": {
                "shadow_rate": 0.88,
                "shadow_volume": 0.55,
                "growl_volume": 0.40,
            },
            "voice_emotions": {
                "default": {"growl": 0.25, "shadow": 0.45},
                "threat": {"growl": 0.55, "shadow": 0.62},
            },
            "world_corruption": {
                "music_duck": 0.26,
                "ambient_duck": 0.18,
                "voice_shadow_boost": 0.25,
                "voice_growl_boost": 0.35,
                "lerp_speed": 3.0,
            },
        }
        if isinstance(extra_cfg, dict):
            cfg.update(extra_cfg)
        app = _FakeApp(cfg)
        director = AudioDirector(app)
        director._resolve_path = lambda path: str(path).replace("\\", "/") if path else None
        return director, app

    def test_hybrid_voice_plays_main_shadow_and_growl_layers(self):
        clock = _FakeClock()
        with patch.object(audio_module, "globalClock", clock):
            director, app = self._director()
            played = director.play_hybrid_voice_key(
                "dracolord/taunt",
                growl_key="dracolord/taunt_growl",
                emotion="threat",
            )
        self.assertTrue(played)
        self.assertEqual(3, len(app.play_log))
        main = app.play_log[0]
        shadow = app.play_log[1]
        growl = app.play_log[2]
        self.assertEqual("data/audio/voices/dracolord/taunt.ogg", main[0])
        self.assertEqual("data/audio/voices/dracolord/taunt.ogg", shadow[0])
        self.assertEqual("data/audio/voices/dracolord/taunt_growl.ogg", growl[0])
        self.assertLess(shadow[2], main[2])
        self.assertLess(main[1], 1.01)
        self.assertGreater(growl[1], 0.0)

    def test_world_corruption_ducks_mix_gains(self):
        clock = _FakeClock()
        with patch.object(audio_module, "globalClock", clock):
            director, _ = self._director()
            director.set_world_corruption(1.0, immediate=True)
            music_gain, ambient_gain = director._compute_mix_gains()
        self.assertAlmostEqual(0.74, music_gain, places=3)
        self.assertAlmostEqual(0.82, ambient_gain, places=3)

    def test_world_corruption_interpolates_toward_target(self):
        clock = _FakeClock()
        with patch.object(audio_module, "globalClock", clock):
            director, _ = self._director()
            director.set_world_corruption(1.0, immediate=False)
            director._update_world_corruption(0.25)
            value = director.get_world_corruption()
        self.assertGreater(value, 0.0)
        self.assertLess(value, 1.0)

    def test_dialog_voice_prefers_hybrid_route_when_available(self):
        route = _FakeAudioRoute()
        mgr = DialogCinematicManager.__new__(DialogCinematicManager)
        mgr.app = _FakeDialogApp(route)
        ok = mgr._play_voice(
            "dragon_boss/start",
            volume=0.9,
            rate=1.02,
            mix={
                "growl_key": "dragon_boss/start_growl",
                "emotion": "threat",
                "emotion_intensity": 0.8,
                "corruption": 0.45,
            },
        )
        self.assertTrue(ok)
        self.assertEqual(1, len(route.calls))
        key, kwargs = route.calls[0]
        self.assertEqual("dragon_boss/start", key)
        self.assertEqual("dragon_boss/start_growl", kwargs.get("growl_key"))
        self.assertEqual("threat", kwargs.get("emotion"))
        self.assertAlmostEqual(0.45, float(kwargs.get("corruption", 0.0)), places=3)


if __name__ == "__main__":
    unittest.main()
