import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _CandidateDummy:
    _resolve_player_model_candidates = Player._resolve_player_model_candidates
    _resolve_base_anims = Player._resolve_base_anims

    def __init__(self):
        self._cfg = {
            "model": "assets/models/hero/sherward/sherward.glb",
            "model_candidates": [
                "assets/models/hero/sherward/sherward.glb",
                "assets/models/xbot/Xbot.glb",
            ],
            "fallback_model": "assets/models/xbot/Xbot.glb",
            "prefer_animation_compatible": True,
            "base_anims": {
                "idle": "assets/models/xbot/idle.glb",
                "walk": "assets/models/xbot/walk.glb",
                "run": "assets/models/xbot/run.glb",
            },
        }

    def _player_model_config(self):
        return dict(self._cfg)


class PlayerModelCandidatePriorityTests(unittest.TestCase):
    def test_xbot_is_prioritized_when_base_anims_are_xbot_only(self):
        dummy = _CandidateDummy()
        candidates = dummy._resolve_player_model_candidates()
        self.assertTrue(candidates)
        self.assertIn("xbot", candidates[0].lower())


if __name__ == "__main__":
    unittest.main()
