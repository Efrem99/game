import sys
import unittest
from unittest.mock import patch

from launchers import bootstrap


class LauncherBootstrapPauseTests(unittest.TestCase):
    def test_pause_before_close_ignores_lost_stdin(self):
        class _LostStdin:
            def isatty(self):
                raise RuntimeError("lost sys.stdin")

        with patch.object(sys, "stdin", _LostStdin()):
            with patch("builtins.input", side_effect=AssertionError("input should not be called")):
                self.assertFalse(bootstrap._pause_before_close("Press Enter to close..."))

    def test_pause_before_close_uses_input_for_interactive_console(self):
        class _ConsoleStdin:
            def isatty(self):
                return True

        with patch.object(sys, "stdin", _ConsoleStdin()):
            with patch("builtins.input", return_value="") as fake_input:
                self.assertTrue(bootstrap._pause_before_close("Press Enter to close..."))

        fake_input.assert_called_once()


if __name__ == "__main__":
    unittest.main()
