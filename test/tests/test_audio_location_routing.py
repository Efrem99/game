import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.audio_director import AudioDirector


class _FakeLoader:
    def loadSfx(self, path):
        del path
        return None

    def loadMusic(self, path):
        del path
        return None


class _FakeDataManager:
    def __init__(self, sound_config):
        self.sound_config = dict(sound_config)


class _FakeApp:
    def __init__(self, sound_config, active_location):
        self.project_root = str(ROOT)
        self.loader = _FakeLoader()
        self.data_mgr = _FakeDataManager(sound_config)
        self.taskMgr = None
        self.event_bus = None
        self.state_mgr = None
        self.GameState = None
        self.player = None
        self.vehicle_mgr = None
        self.boss_manager = None
        self.dragon_boss = None
        self.world = types.SimpleNamespace(active_location=str(active_location))


def _load_sound_config():
    path = ROOT / "data" / "audio" / "sound_config.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class AudioLocationRoutingTests(unittest.TestCase):
    def test_castle_interior_prefers_interior_ambient(self):
        app = _FakeApp(_load_sound_config(), "Castle Interior")
        director = AudioDirector(app)
        location_key = director._location_key()
        ambient = director._pick_gameplay_ambient(
            director._infer_biome_key(location_key),
            location_key,
        )
        self.assertEqual("castle_interior", ambient)

    def test_dwarven_halls_prefers_caves_ambient(self):
        app = _FakeApp(_load_sound_config(), "Dwarven Forge Halls")
        director = AudioDirector(app)
        location_key = director._location_key()
        ambient = director._pick_gameplay_ambient(
            director._infer_biome_key(location_key),
            location_key,
        )
        self.assertEqual("caves", ambient)


if __name__ == "__main__":
    unittest.main()
