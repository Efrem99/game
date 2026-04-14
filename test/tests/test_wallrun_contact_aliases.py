import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player
from entities.player_state_machine_mixin import PlayerStateMachineMixin


class _WallrunAliasDummy:
    _sync_wall_contact_state = PlayerStateMachineMixin._sync_wall_contact_state
    _parkour_action_name = PlayerStateMachineMixin._parkour_action_name
    _parkour_action_token = Player._parkour_action_token

    def __init__(self):
        self.ps = type("ParkourState", (), {"action": ""})()
        self._was_wallrun = False
        self._queued_state_triggers = []

    def _queue_state_trigger(self, trigger):
        self._queued_state_triggers.append(str(trigger or "").strip().lower())


class WallrunContactAliasTests(unittest.TestCase):
    def test_camel_case_wallrun_variant_queues_wall_contact(self):
        actor = _WallrunAliasDummy()
        actor.ps.action = "wallRunRight"

        actor._sync_wall_contact_state()

        self.assertIn("wall_contact", actor._queued_state_triggers)
        self.assertTrue(actor._was_wallrun)

    def test_camel_case_wallrun_variant_queues_exit_on_release(self):
        actor = _WallrunAliasDummy()
        actor._was_wallrun = True
        actor.ps.action = ""

        actor._sync_wall_contact_state()

        self.assertIn("exit_wallrun", actor._queued_state_triggers)
        self.assertFalse(actor._was_wallrun)


if __name__ == "__main__":
    unittest.main()
