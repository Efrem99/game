import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _CreditsRecorder:
    def __init__(self):
        self.calls = []

    def update(self, dt):
        self.calls.append(float(dt))


class _CreditsDummy:
    _update_credits_overlay = XBotApp._update_credits_overlay

    def __init__(self):
        self.credits = _CreditsRecorder()


class AppCreditsRuntimeTests(unittest.TestCase):
    def test_update_credits_overlay_uses_runtime_dt(self):
        app = _CreditsDummy()

        app._update_credits_overlay(0.125)

        self.assertEqual([0.125], app.credits.calls)


if __name__ == "__main__":
    unittest.main()
