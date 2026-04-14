import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _FlagPlayerStub:
    def __init__(self):
        self._is_aiming = False
        self._aim_mode = ""
        self._stealth_crouch = False
        self._shadow_mode = False
        self.shadow_calls = []
        self.crouch_calls = []

    def set_shadow_mode(self, active=True):
        state = bool(active)
        self._shadow_mode = state
        self.shadow_calls.append(state)

    def _set_stealth_crouch(self, active):
        state = bool(active)
        self._stealth_crouch = state
        self.crouch_calls.append(state)


class _VideoBotFlagDummy:
    _video_bot_apply_flag = XBotApp._video_bot_apply_flag

    def __init__(self):
        self.player = _FlagPlayerStub()
        self.char_state = None

    def _video_bot_set_action(self, _action, _pressed):
        return None


class AppVideoBotApplyFlagTests(unittest.TestCase):
    def test_aim_mode_flag_sets_runtime_mode_and_aim_state(self):
        app = _VideoBotFlagDummy()

        app._video_bot_apply_flag("aim_mode", "bow")
        self.assertTrue(app.player._is_aiming)
        self.assertEqual("bow", app.player._aim_mode)

        app._video_bot_apply_flag("is_aiming", False)
        self.assertFalse(app.player._is_aiming)
        self.assertEqual("", app.player._aim_mode)

    def test_stealth_and_shadow_flags_use_player_helpers(self):
        app = _VideoBotFlagDummy()

        app._video_bot_apply_flag("stealth_crouch", True)
        app._video_bot_apply_flag("shadow_mode", True)

        self.assertEqual([True], app.player.crouch_calls)
        self.assertEqual([True], app.player.shadow_calls)
        self.assertTrue(app.player._stealth_crouch)
        self.assertTrue(app.player._shadow_mode)


if __name__ == "__main__":
    unittest.main()
