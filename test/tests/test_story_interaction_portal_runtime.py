import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.story_interaction_manager import StoryInteractionManager


class _VecStub:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _NodeStub:
    def __init__(self, pos=None):
        self.pos = pos or _VecStub()

    def getPos(self, _render=None):
        return self.pos


class _ActorStub:
    def __init__(self, pos=None):
        self.pos = pos or _VecStub()

    def getPos(self, _render=None):
        return self.pos


class _PortalAppStub:
    def __init__(self):
        self.render = object()
        self.profile = {}
        self.player = SimpleNamespace(actor=_ActorStub(_VecStub(0.0, 0.0, 0.0)))
        self.cutscene_events = []
        self.portal_jumps = []

    def _emit_cutscene_event(self, event_name, payload=None):
        self.cutscene_events.append((str(event_name), dict(payload or {})))

    def _apply_portal_jump_event(self, payload):
        self.portal_jumps.append(dict(payload or {}))
        return True


class StoryInteractionPortalRuntimeTests(unittest.TestCase):
    def test_portal_interaction_emits_event_and_applies_runtime_jump(self):
        app = _PortalAppStub()
        mgr = StoryInteractionManager(app)
        node = _NodeStub(_VecStub(0.0, 0.0, 0.0))

        ok = mgr.register_anchor(
            "portal_c",
            node,
            name="Void Portal (Center)",
            hint="Teleport to Origin",
            single_use=False,
            event_name="portal_jump",
            event_payload={"target": "ultimate_sandbox", "kind": "void"},
        )

        self.assertTrue(ok)
        self.assertTrue(mgr.try_interact(app.player.actor.getPos(app.render)))
        self.assertEqual([("portal_jump", {"target": "ultimate_sandbox", "kind": "void"})], app.cutscene_events)
        self.assertEqual([{"target": "ultimate_sandbox", "kind": "void"}], app.portal_jumps)
        self.assertFalse(bool(mgr.get_anchor("portal_c").get("consumed", False)))


if __name__ == "__main__":
    unittest.main()
