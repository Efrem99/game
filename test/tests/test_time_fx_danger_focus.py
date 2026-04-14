import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.time_fx_manager import TimeFxManager


class _DummyApp:
    pass


class TimeFxDangerFocusTests(unittest.TestCase):
    def test_danger_focus_is_milder_than_hard_combat_slowmo(self):
        manager = TimeFxManager(_DummyApp())
        manager.trigger("danger_focus", duration=None)
        manager.update(0.016)

        scales = manager.get_scales()
        self.assertGreater(scales.get("world", 1.0), 0.60)
        self.assertLess(scales.get("world", 1.0), 0.90)


if __name__ == "__main__":
    unittest.main()
