import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _LoopHintDummy:
    _normalize_anim_key = Player._normalize_anim_key
    _state_loop_hint = getattr(Player, "_state_loop_hint", None)

    def __init__(self):
        self._manifest_anim_loop_hints = {
            "idle": True,
            "jump": False,
            "crouchidle": True,
        }
        self._state_anim_tokens = {
            "jumping": "jump",
            "crouch_idle": "crouch_idle",
        }


class PlayerStateLoopHintTests(unittest.TestCase):
    def test_player_exposes_state_loop_hint_helper(self):
        self.assertTrue(callable(getattr(Player, "_state_loop_hint", None)))

    def test_state_loop_hint_prefers_resolved_clip_then_state_aliases(self):
        dummy = _LoopHintDummy()

        self.assertTrue(dummy._state_loop_hint("idle", resolved_clip="idle"))
        self.assertFalse(dummy._state_loop_hint("jumping", resolved_clip="jump"))
        self.assertTrue(dummy._state_loop_hint("crouch_idle", resolved_clip="missing"))
        self.assertIsNone(dummy._state_loop_hint("unknown", resolved_clip="missing"))


if __name__ == "__main__":
    unittest.main()
