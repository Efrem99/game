import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player
from entities.player_animation_config import ANIM_TOKEN_ALIASES, STATE_ANIM_FALLBACK


class _ActorStub:
    def __init__(self, *, available=None, fail=None):
        self.available = {str(name) for name in (available or set())}
        self.fail = {str(name) for name in (fail or set())}
        self.calls = []
        self.frame_calls = []
        self.effects = []
        self.effect_map = {}
        self.blend_enabled = False
        self.current_anim = ""

    def setPlayRate(self, _rate, _clip):
        return None

    def getAnimNames(self):
        return list(self.available)

    def enableBlend(self):
        self.blend_enabled = True
        return None

    def loop(self, clip, restart=1, partName=None, fromFrame=None, toFrame=None):
        token = f"loop:{clip}"
        self.calls.append(token)
        self.frame_calls.append(("loop", str(clip), restart, partName, fromFrame, toFrame))
        if token in self.fail:
            raise RuntimeError(f"blocked {token}")
        self.current_anim = str(clip)

    def play(self, clip, partName=None, fromFrame=None, toFrame=None):
        token = f"play:{clip}"
        self.calls.append(token)
        self.frame_calls.append(("play", str(clip), partName, fromFrame, toFrame))
        if token in self.fail:
            raise RuntimeError(f"blocked {token}")
        self.current_anim = str(clip)

    def setControlEffect(self, clip, value):
        token = (str(clip), float(value))
        self.effects.append(token)
        self.effect_map[str(clip)] = float(value)

    def getAnimControl(self, clip):
        token = str(clip)
        return token if token in self.available else None

    def getCurrentAnim(self):
        return self.current_anim


class _AnimDummy:
    _normalize_anim_key = Player._normalize_anim_key
    _uses_xbot_runtime_model = Player._uses_xbot_runtime_model
    _xbot_runtime_state_candidates = Player._xbot_runtime_state_candidates
    _xbot_runtime_blocked_state_tokens = Player._xbot_runtime_blocked_state_tokens
    _state_loop_hint = Player._state_loop_hint
    _resolve_anim_clip = Player._resolve_anim_clip
    _classify_anim_resolution = Player._classify_anim_resolution
    _record_anim_resolution = Player._record_anim_resolution
    _record_anim_emergency_recovery = Player._record_anim_emergency_recovery
    _remember_safe_anim = Player._remember_safe_anim
    _clip_start_frame_hint = Player._clip_start_frame_hint
    _is_anim_clip_actively_playing = Player._is_anim_clip_actively_playing
    _arm_active_anim_control_effect = Player._arm_active_anim_control_effect
    _begin_anim_blend_transition = Player._begin_anim_blend_transition
    _play_actor_anim = Player._play_actor_anim
    _force_safe_idle_anim = Player._force_safe_idle_anim
    _set_anim = Player._set_anim
    _init_animation_system = Player._init_animation_system
    _should_defer_full_anim_control_audit = Player._should_defer_full_anim_control_audit
    _startup_anim_control_audit_targets = Player._startup_anim_control_audit_targets
    _tick_anim_blend = Player._tick_anim_blend


class PlayerAntiTPoseGuardTests(unittest.TestCase):
    def _make_dummy(self, *, available_anims, fail=None):
        dummy = _AnimDummy()
        dummy.actor = _ActorStub(available=available_anims, fail=fail)
        dummy.cs = SimpleNamespace(velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0))
        dummy.walk_speed = 5.0
        dummy.run_speed = 9.0
        dummy.flight_speed = 15.0
        dummy._anim_blend_enabled = False
        dummy._anim_blend_transition = None
        dummy._anim_blend_duration = 0.18
        dummy._anim_blend_skipped_once = set()
        dummy._anim_resolution_mode = "uninitialized"
        dummy._anim_resolution_source = ""
        dummy._anim_resolution_requested_state = ""
        dummy._anim_resolution_clip = ""
        dummy._anim_degraded_once = set()
        dummy._anim_emergency_once = set()
        dummy._anim_failed_once = set()
        dummy._anim_missing_state_once = set()
        dummy._state_anim_hints = {}
        dummy._state_anim_tokens = {}
        dummy._state_anim_overrides = {}
        dummy._manifest_anim_loop_hints = {}
        dummy._state_anim_fallback = {
            key: list(value) for key, value in STATE_ANIM_FALLBACK.items()
        }
        dummy._anim_token_aliases = {
            key: list(value) for key, value in ANIM_TOKEN_ALIASES.items()
        }
        dummy._available_anims = set(available_anims)
        dummy._anim_state = "idle"
        dummy._anim_clip = ""
        dummy._last_safe_anim_state = "idle"
        dummy._last_safe_anim_clip = ""
        dummy.data_mgr = SimpleNamespace(controls={})
        dummy._load_player_state_animation_tokens = lambda: {}
        dummy._load_actor_animation_overrides = lambda: {}
        dummy._load_manifest_loop_hints = lambda: {}
        dummy._write_animation_coverage_report = lambda: None
        dummy._noncore_animation_playback_block_reason = lambda: None
        return dummy

    def test_force_safe_idle_anim_restores_last_safe_clip_when_idle_chain_is_unusable(self):
        dummy = self._make_dummy(
            available_anims={"crouch_idle", "run"},
            fail={"loop:run"},
        )
        dummy._last_safe_anim_state = "crouch_idle"
        dummy._last_safe_anim_clip = "crouch_idle"

        ok = dummy._force_safe_idle_anim(requested_state="jumping")

        self.assertTrue(ok)
        self.assertEqual("crouch_idle", dummy._anim_state)
        self.assertEqual("crouch_idle", dummy._anim_clip)
        self.assertIn("loop:run", dummy.actor.calls)
        self.assertIn("loop:crouch_idle", dummy.actor.calls)
        self.assertEqual("emergency_safe_clip", dummy._anim_resolution_mode)
        self.assertEqual("jumping", dummy._anim_resolution_requested_state)
        self.assertEqual("crouch_idle", dummy._anim_resolution_clip)

    def test_force_safe_idle_anim_can_recover_with_single_play_when_loop_is_blocked(self):
        dummy = self._make_dummy(
            available_anims={"run"},
            fail={"loop:run"},
        )
        dummy._last_safe_anim_state = "running"
        dummy._last_safe_anim_clip = "run"

        ok = dummy._force_safe_idle_anim(requested_state="falling")

        self.assertTrue(ok)
        self.assertEqual("running", dummy._anim_state)
        self.assertEqual("run", dummy._anim_clip)
        self.assertIn("loop:run", dummy.actor.calls)
        self.assertIn("play:run", dummy.actor.calls)
        self.assertEqual("emergency_safe_clip", dummy._anim_resolution_mode)
        self.assertEqual("falling", dummy._anim_resolution_requested_state)
        self.assertEqual("single_play", dummy._anim_resolution_source)

    def test_set_anim_starts_runtime_blend_for_locomotion_transition(self):
        dummy = self._make_dummy(
            available_anims={"idle", "walk"},
        )
        dummy._init_animation_system()

        ok = dummy._set_anim("walking", loop=True, blend_time=0.25, force=True)

        self.assertTrue(ok)
        self.assertTrue(dummy.actor.blend_enabled)
        self.assertTrue(dummy._anim_blend_enabled)
        self.assertEqual("walking", dummy._anim_state)
        self.assertEqual("walk", dummy._anim_clip)
        self.assertIsInstance(dummy._anim_blend_transition, dict)
        self.assertEqual("idle", dummy._anim_blend_transition.get("from_clip"))
        self.assertEqual("walk", dummy._anim_blend_transition.get("to_clip"))

    def test_tick_anim_blend_finishes_and_keeps_target_clip_fully_weighted(self):
        dummy = self._make_dummy(
            available_anims={"idle", "walk"},
        )
        dummy._init_animation_system()
        ok = dummy._set_anim("walking", loop=True, blend_time=0.25, force=True)

        self.assertTrue(ok)
        dummy._tick_anim_blend(0.125)
        self.assertAlmostEqual(0.5, dummy.actor.effect_map.get("idle", -1.0), places=2)
        self.assertAlmostEqual(0.5, dummy.actor.effect_map.get("walk", -1.0), places=2)

        dummy._tick_anim_blend(0.125)
        self.assertIsNone(dummy._anim_blend_transition)
        self.assertAlmostEqual(0.0, dummy.actor.effect_map.get("idle", -1.0), places=2)
        self.assertAlmostEqual(1.0, dummy.actor.effect_map.get("walk", -1.0), places=2)


if __name__ == "__main__":
    unittest.main()
