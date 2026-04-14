import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
APP_PATH = ROOT / "src" / "app.py"
APP_SOURCE = APP_PATH.read_text(encoding="utf-8")


def _function_block(name: str) -> str:
    marker = f"    def {name}("
    start = APP_SOURCE.find(marker)
    if start < 0:
        raise AssertionError(f"Function {name} not found in {APP_PATH}")
    next_start = APP_SOURCE.find("\n    def ", start + len(marker))
    if next_start < 0:
        return APP_SOURCE[start:]
    return APP_SOURCE[start:next_start]


class AppVideoBotRunEventSourceTests(unittest.TestCase):
    def test_close_dialogue_ui_action_is_wired_to_escape_finish(self):
        block = _function_block("_video_bot_apply_ui_action")
        self.assertIn('"close_dialogue"', block)
        self.assertIn('state == self.GameState.DIALOG', block)
        self.assertIn('_on_escape_pressed(from_video_bot=True)', block)

    def test_video_bot_can_drive_ui_actions_while_dialog_is_open(self):
        block = _function_block("_video_bot_can_drive_gameplay")
        self.assertIn('getattr(self.GameState, "DIALOG", None)', block)
        self.assertIn('== "ui_action"', block)


if __name__ == "__main__":
    unittest.main()
