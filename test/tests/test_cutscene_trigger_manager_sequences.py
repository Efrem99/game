import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.cutscene_trigger_manager import CutsceneTriggerManager


class _CutsceneTriggerAppStub:
    def __init__(self):
        self.data_mgr = SimpleNamespace(
            cutscene_triggers={
                "event_triggers": [
                    {
                        "id": "portal_intro",
                        "event": "portal_jump",
                        "sequence": {
                            "name": "portal_arrival",
                            "priority": 74,
                            "owner": "cutscene:portal_intro",
                        },
                    }
                ]
            }
        )
        self.player = SimpleNamespace(actor=object())
        self.sequence_calls = []

    def play_camera_sequence(self, name, priority=None, owner="runtime"):
        self.sequence_calls.append(
            {
                "name": str(name),
                "priority": int(priority),
                "owner": str(owner),
            }
        )
        return True


class CutsceneTriggerManagerSequenceTests(unittest.TestCase):
    def test_event_trigger_can_play_camera_sequence(self):
        app = _CutsceneTriggerAppStub()
        mgr = CutsceneTriggerManager(app)

        mgr.emit("portal_jump", {"location": "Training Grounds"})

        self.assertEqual(
            [
                {
                    "name": "portal_arrival",
                    "priority": 74,
                    "owner": "cutscene:portal_intro",
                }
            ],
            app.sequence_calls,
        )


if __name__ == "__main__":
    unittest.main()
