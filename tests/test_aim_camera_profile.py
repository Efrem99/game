import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.camera_director import CameraDirector


class _DummyApp:
    def __init__(self, aiming=False):
        self.data_mgr = SimpleNamespace(camera_profiles={})
        self.event_bus = None
        self.player = SimpleNamespace(_is_aiming=bool(aiming), _anim_state="idle")
        self.state_mgr = SimpleNamespace(current_state=SimpleNamespace(name="playing"))
        self.boss_manager = SimpleNamespace(any_engaged=lambda: False)
        self.dragon_boss = None
        self.vehicle_mgr = None
        self.movement_tutorial = None


class AimCameraProfileTests(unittest.TestCase):
    def test_camera_director_picks_aim_profile_while_player_aiming(self):
        app = _DummyApp(aiming=True)
        director = CameraDirector(app)
        self.assertEqual("aim", director._resolve_profile())

    def test_controls_include_explicit_aim_binding(self):
        payload = json.loads((ROOT / "data" / "controls.json").read_text(encoding="utf-8-sig"))
        bindings = payload.get("bindings", {})
        self.assertEqual("mouse3", str(bindings.get("aim", "")).strip().lower())


if __name__ == "__main__":
    unittest.main()
