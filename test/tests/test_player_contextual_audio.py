import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import types

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_global_clock = types.SimpleNamespace(getFrameTime=lambda: 1.0)
_showbase_global = types.ModuleType("direct.showbase.ShowBaseGlobal")
_showbase_global.globalClock = _global_clock
_showbase = types.ModuleType("direct.showbase")
_showbase.ShowBaseGlobal = _showbase_global
_direct = types.ModuleType("direct")
_direct.showbase = _showbase
sys.modules.setdefault("direct", _direct)
sys.modules.setdefault("direct.showbase", _showbase)
sys.modules.setdefault("direct.showbase.ShowBaseGlobal", _showbase_global)

from entities.player_audio_mixin import PlayerAudioMixin


class _PlayerAudioDummy(PlayerAudioMixin):
    _update_contextual_state_sfx = PlayerAudioMixin._update_contextual_state_sfx

    def __init__(self):
        self._anim_state = "idle"
        self._last_contextual_sfx_state = ""
        self._last_contextual_sfx_flags = {}
        self._played = []
        self.cs = SimpleNamespace(inWater=False)
        self._is_flying = False

    def _play_sfx(self, sfx_key, volume=1.0, rate=1.0):
        self._played.append((str(sfx_key), float(volume), float(rate)))
        return True


class PlayerContextualAudioTests(unittest.TestCase):
    def test_entering_water_plays_swim_enter_once(self):
        actor = _PlayerAudioDummy()

        actor._update_contextual_state_sfx()
        actor.cs.inWater = True
        actor._update_contextual_state_sfx()

        self.assertEqual("swim_enter", actor._played[-1][0])

    def test_exiting_water_plays_swim_exit_once(self):
        actor = _PlayerAudioDummy()
        actor.cs.inWater = True
        actor._update_contextual_state_sfx()
        actor._played.clear()

        actor.cs.inWater = False
        actor._update_contextual_state_sfx()

        self.assertEqual("swim_exit", actor._played[0][0])

    def test_vaulting_state_plays_parkour_vault_sound(self):
        actor = _PlayerAudioDummy()
        actor._anim_state = "vaulting"

        actor._update_contextual_state_sfx()

        self.assertEqual("parkour_vault", actor._played[-1][0])

    def test_flight_takeoff_state_plays_takeoff_sound(self):
        actor = _PlayerAudioDummy()
        actor._anim_state = "flight_takeoff"

        actor._update_contextual_state_sfx()

        self.assertEqual("flight_takeoff", actor._played[-1][0])


if __name__ == "__main__":
    unittest.main()
