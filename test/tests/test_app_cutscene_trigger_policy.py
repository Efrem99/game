import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _CutscenePolicyDummy:
    _should_enable_cutscene_triggers_for_runtime = XBotApp._should_enable_cutscene_triggers_for_runtime

    def __init__(self, disable_cutscene_triggers=False):
        self._debug_disable_cutscene_triggers = bool(disable_cutscene_triggers)


class _TriggerManagerStub:
    def __init__(self):
        self.emitted = []

    def emit(self, event_name, payload):
        self.emitted.append((str(event_name), dict(payload or {})))


class _CutsceneEmitDummy:
    _emit_cutscene_event = XBotApp._emit_cutscene_event

    def __init__(self, enabled):
        self._cutscene_triggers_enabled = bool(enabled)
        self.cutscene_triggers = _TriggerManagerStub()
        self.event_bus = None


class AppCutsceneTriggerPolicyTests(unittest.TestCase):
    def test_cutscene_triggers_stay_disabled_when_debug_flag_is_set(self):
        app = _CutscenePolicyDummy(disable_cutscene_triggers=True)

        self.assertFalse(app._should_enable_cutscene_triggers_for_runtime())

    def test_cutscene_triggers_remain_enabled_by_default(self):
        app = _CutscenePolicyDummy(disable_cutscene_triggers=False)

        self.assertTrue(app._should_enable_cutscene_triggers_for_runtime())

    def test_emit_cutscene_event_skips_trigger_manager_when_runtime_cutscenes_are_disabled(self):
        app = _CutsceneEmitDummy(enabled=False)

        app._emit_cutscene_event("location_enter", {"location": "Training Grounds"})

        self.assertEqual([], app.cutscene_triggers.emitted)

    def test_emit_cutscene_event_reaches_trigger_manager_when_runtime_cutscenes_are_enabled(self):
        app = _CutsceneEmitDummy(enabled=True)

        app._emit_cutscene_event("location_enter", {"location": "Training Grounds"})

        self.assertEqual([("location_enter", {"location": "Training Grounds"})], app.cutscene_triggers.emitted)


if __name__ == "__main__":
    unittest.main()
