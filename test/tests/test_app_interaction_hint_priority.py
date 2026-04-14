import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _InteractionHintDummy:
    _resolve_runtime_interaction_hint = XBotApp._resolve_runtime_interaction_hint

    def __init__(self, vehicle_hint="", npc_hint="", story_hint=""):
        self.player = object()
        self.vehicle_mgr = SimpleNamespace(
            get_interaction_hint=lambda _player: vehicle_hint,
        )
        self.npc_interaction = SimpleNamespace(
            get_interaction_hint=lambda: npc_hint,
        )
        self.story_interaction = SimpleNamespace(
            get_interaction_hint=lambda: story_hint,
        )


class AppInteractionHintPriorityTests(unittest.TestCase):
    def test_story_hint_overrides_other_runtime_hints(self):
        app = _InteractionHintDummy(
            vehicle_hint="[E] Mount Horse",
            npc_hint="[E] Talk to Guide",
            story_hint="[E] Loot Chest",
        )
        self.assertEqual("[E] Loot Chest", app._resolve_runtime_interaction_hint())

    def test_npc_hint_fills_gap_when_story_hint_missing(self):
        app = _InteractionHintDummy(
            vehicle_hint="[E] Mount Horse",
            npc_hint="[E] Talk to Guide",
            story_hint="",
        )
        self.assertEqual("[E] Talk to Guide", app._resolve_runtime_interaction_hint())

    def test_vehicle_hint_is_used_when_no_other_interactions_exist(self):
        app = _InteractionHintDummy(
            vehicle_hint="[E] Mount Horse",
            npc_hint="",
            story_hint="",
        )
        self.assertEqual("[E] Mount Horse", app._resolve_runtime_interaction_hint())


if __name__ == "__main__":
    unittest.main()
