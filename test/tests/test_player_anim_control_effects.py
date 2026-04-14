import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player
from entities.player_animation_config import (
    ANIM_TOKEN_ALIASES,
    CLIP_START_FRAME_HINTS,
    STATE_ANIM_FALLBACK,
)


class _ActorStub:
    class _AnimControlStub:
        def __init__(self, clip):
            self.clip = str(clip)
            self.playing = False

        def isPlaying(self):
            return self.playing

    def __init__(self, available, controllable=None):
        self.available = {str(name) for name in (available or set())}
        if controllable is None:
            controllable = set(self.available)
        self.controllable = {str(name) for name in (controllable or set())}
        self.calls = []
        self.frame_calls = []
        self.effects = []
        self.effect_map = {}
        self.anim_control_queries = []
        self.blend_enabled = False
        self.current_anim = ""
        self.controls = {
            token: self._AnimControlStub(token) for token in self.controllable
        }

    def setPlayRate(self, _rate, _clip):
        return None

    def getAnimNames(self):
        return list(self.available)

    def enableBlend(self):
        self.blend_enabled = True

    def setControlEffect(self, clip, value):
        token = (str(clip), float(value))
        self.effects.append(token)
        self.effect_map[str(clip)] = float(value)

    def getAnimControl(self, clip):
        token = str(clip)
        self.anim_control_queries.append(token)
        return self.controls.get(token)

    def getCurrentAnim(self):
        return self.current_anim

    def loop(self, clip, restart=1, partName=None, fromFrame=None, toFrame=None):
        token = str(clip)
        self.calls.append(("loop", token))
        self.frame_calls.append(("loop", token, restart, partName, fromFrame, toFrame))
        for control in self.controls.values():
            control.playing = False
        if token in self.controls:
            self.controls[token].playing = True
        self.current_anim = token

    def play(self, clip, partName=None, fromFrame=None, toFrame=None):
        token = str(clip)
        self.calls.append(("play", token))
        self.frame_calls.append(("play", token, partName, fromFrame, toFrame))
        for control in self.controls.values():
            control.playing = False
        if token in self.controls:
            self.controls[token].playing = True
        self.current_anim = token


class _AnimDummy:
    _normalize_anim_key = Player._normalize_anim_key
    _uses_xbot_runtime_model = Player._uses_xbot_runtime_model
    _xbot_runtime_state_candidates = Player._xbot_runtime_state_candidates
    _xbot_runtime_blocked_state_tokens = Player._xbot_runtime_blocked_state_tokens
    _clip_start_frame_hint = Player._clip_start_frame_hint
    _state_loop_hint = Player._state_loop_hint
    _resolve_anim_clip = Player._resolve_anim_clip
    _classify_anim_resolution = Player._classify_anim_resolution
    _record_anim_resolution = Player._record_anim_resolution
    _record_anim_emergency_recovery = Player._record_anim_emergency_recovery
    _remember_safe_anim = Player._remember_safe_anim
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

    def __init__(self, available, controllable=None):
        self.actor = _ActorStub(available, controllable=controllable)
        self.data_mgr = SimpleNamespace(controls={})
        self._available_anims = set(available)
        self._state_anim_tokens = {}
        self._state_anim_overrides = {}
        self._state_anim_hints = {}
        self._manifest_anim_loop_hints = {}
        self._state_anim_fallback = {
            key: list(value) for key, value in STATE_ANIM_FALLBACK.items()
        }
        self._anim_token_aliases = {
            key: list(value) for key, value in ANIM_TOKEN_ALIASES.items()
        }
        self._anim_failed_once = set()
        self._anim_missing_state_once = set()
        self._anim_blend_skipped_once = set()
        self._anim_state = "idle"
        self._anim_clip = ""
        self._last_safe_anim_state = "idle"
        self._last_safe_anim_clip = ""
        self._anim_blend_enabled = False
        self._anim_blend_transition = None
        self._anim_blend_duration = 0.18
        self._anim_resolution_mode = "uninitialized"
        self._anim_resolution_source = ""
        self._anim_resolution_requested_state = ""
        self._anim_resolution_clip = ""
        self._anim_degraded_once = set()
        self._anim_emergency_once = set()
        self.walk_speed = 5.0
        self.run_speed = 9.0
        self.flight_speed = 15.0
        self._weapon_drawn = False
        self._loaded_player_model_path = "assets/models/hero/sherward/sherward_rework.glb"
        self.cs = SimpleNamespace(velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0))
        self._load_player_state_animation_tokens = lambda: {}
        self._load_actor_animation_overrides = lambda: {}
        self._load_manifest_loop_hints = lambda: {}
        self._write_animation_coverage_report = lambda: None
        self._noncore_animation_playback_block_reason = lambda: None


class _LoopHintDummy:
    _load_manifest_loop_hints = Player._load_manifest_loop_hints
    _normalize_anim_key = Player._normalize_anim_key
    _alias_animation_key = Player._alias_animation_key
    _state_loop_hint = Player._state_loop_hint

    def __init__(self):
        self.data_mgr = SimpleNamespace(get_player_animation_manifest=lambda: {})
        self.app = SimpleNamespace()
        self._state_anim_tokens = {"running": "run_blade", "walking": "walk"}
        self._manifest_anim_loop_hints = self._load_manifest_loop_hints()


class PlayerAnimControlEffectsTests(unittest.TestCase):
    def test_manifest_loop_hints_do_not_poison_base_run_from_wallrun_transition_aliases(self):
        dummy = _LoopHintDummy()

        self.assertIsNone(dummy._manifest_anim_loop_hints.get("run"))
        self.assertTrue(dummy._state_loop_hint("running", "run"))

    def test_init_animation_system_filters_out_names_without_live_anim_control(self):
        dummy = _AnimDummy({"idle", "walk", "jumping"}, controllable={"idle", "walk"})

        dummy._init_animation_system()

        self.assertIn("idle", dummy._available_anims)
        self.assertIn("walk", dummy._available_anims)
        self.assertNotIn("jumping", dummy._available_anims)

    def test_init_animation_system_enables_real_blend_path(self):
        dummy = _AnimDummy({"idle", "walk"})

        dummy._init_animation_system()

        self.assertTrue(dummy.actor.blend_enabled)
        self.assertTrue(dummy._anim_blend_enabled)
        self.assertIn(("loop", "idle"), dummy.actor.calls)
        self.assertEqual(1.0, dummy.actor.effect_map.get("idle"))

    def test_init_animation_system_defers_full_anim_control_audit_for_large_clip_sets(self):
        large_available = {"idle", "walk", "run"} | {
            f"attack_variant_{idx}" for idx in range(96)
        }
        dummy = _AnimDummy(large_available, controllable={"idle", "walk", "run"})
        dummy._load_player_state_animation_tokens = lambda: {
            "idle": "idle",
            "walking": "walk",
            "running": "run",
        }

        dummy._init_animation_system()

        self.assertLessEqual(len(dummy.actor.anim_control_queries), 16)
        self.assertIn("idle", dummy._available_anims)
        self.assertIn("walk", dummy._available_anims)
        self.assertIn("run", dummy._available_anims)

    def test_init_animation_system_keeps_deferred_audit_on_small_safety_probe_set(self):
        large_available = {
            "idle",
            "walk",
            "run",
            "jumping",
            "falling",
            "landing",
            "weapon_unsheathe",
            "weapon_sheathe",
        } | {f"attack_variant_{idx}" for idx in range(96)}
        dummy = _AnimDummy(large_available, controllable={"idle", "walk", "run"})
        dummy._load_player_state_animation_tokens = lambda: {
            "idle": "idle",
            "walking": "walk",
            "running": "run",
            "jumping": "jumping",
            "falling": "falling",
            "landing": "landing",
        }
        dummy._load_actor_animation_overrides = lambda: {
            "jumping": ["jumping"],
            "falling": ["falling"],
            "landing": ["landing"],
            "weapon_unsheathe": ["weapon_unsheathe"],
            "weapon_sheathe": ["weapon_sheathe"],
        }

        dummy._init_animation_system()

        self.assertLessEqual(len(dummy.actor.anim_control_queries), 6)

    def test_set_anim_starts_blend_transition_between_current_and_target_clip(self):
        dummy = _AnimDummy({"idle", "walk"})
        dummy.actor.enableBlend()
        dummy._anim_blend_enabled = True
        dummy._state_anim_tokens = {"walking": "walk"}
        dummy._anim_state = "idle"
        dummy._anim_clip = "idle"
        dummy.actor.loop("idle")
        dummy._arm_active_anim_control_effect("idle")

        ok = dummy._set_anim("walking", loop=True, blend_time=0.3, force=True)

        self.assertTrue(ok)
        self.assertEqual("walking", dummy._anim_state)
        self.assertEqual("walk", dummy._anim_clip)
        self.assertIn(("loop", "walk"), dummy.actor.calls)
        self.assertIsInstance(dummy._anim_blend_transition, dict)
        self.assertEqual("idle", dummy._anim_blend_transition.get("from_clip"))
        self.assertEqual("walk", dummy._anim_blend_transition.get("to_clip"))
        self.assertAlmostEqual(0.3, dummy._anim_blend_transition.get("duration"), places=3)
        self.assertEqual(1.0, dummy.actor.effect_map.get("idle"))
        self.assertEqual(0.0, dummy.actor.effect_map.get("walk"))
        self.assertEqual("ok", dummy._anim_resolution_mode)
        self.assertEqual("walking", dummy._anim_resolution_requested_state)
        self.assertEqual("walk", dummy._anim_resolution_clip)

    def test_tick_anim_blend_crossfades_until_target_owns_full_weight(self):
        dummy = _AnimDummy({"idle", "walk"})
        dummy.actor.enableBlend()
        dummy._anim_blend_enabled = True
        dummy._state_anim_tokens = {"walking": "walk"}
        dummy._anim_state = "idle"
        dummy._anim_clip = "idle"
        dummy.actor.loop("idle")
        dummy._arm_active_anim_control_effect("idle")

        ok = dummy._set_anim("walking", loop=True, blend_time=0.3, force=True)

        self.assertTrue(ok)
        dummy._tick_anim_blend(0.15)
        self.assertIsNotNone(dummy._anim_blend_transition)
        self.assertAlmostEqual(0.5, dummy.actor.effect_map.get("idle", -1.0), places=2)
        self.assertAlmostEqual(0.5, dummy.actor.effect_map.get("walk", -1.0), places=2)

        dummy._tick_anim_blend(0.15)
        self.assertIsNone(dummy._anim_blend_transition)
        self.assertAlmostEqual(0.0, dummy.actor.effect_map.get("idle", -1.0), places=2)
        self.assertAlmostEqual(1.0, dummy.actor.effect_map.get("walk", -1.0), places=2)

    def test_set_anim_marks_degraded_single_clip_when_state_uses_substitute_clip(self):
        dummy = _AnimDummy({"idle", "run"})
        dummy.actor.enableBlend()
        dummy._anim_blend_enabled = True

        ok = dummy._set_anim("jumping", loop=True, force=True)

        self.assertTrue(ok)
        self.assertEqual("jumping", dummy._anim_state)
        self.assertEqual("run", dummy._anim_clip)
        self.assertEqual("degraded_single_clip", dummy._anim_resolution_mode)
        self.assertEqual("state_fallback", dummy._anim_resolution_source)
        self.assertEqual("jumping", dummy._anim_resolution_requested_state)
        self.assertEqual("run", dummy._anim_resolution_clip)

    def test_set_anim_uses_direct_play_when_previous_clip_is_not_actively_playing(self):
        dummy = _AnimDummy({"idle", "walk"})
        dummy.actor.enableBlend()
        dummy._anim_blend_enabled = True
        dummy._state_anim_tokens = {"walking": "walk"}
        dummy._anim_state = "idle"
        dummy._anim_clip = "idle"

        ok = dummy._set_anim("walking", loop=True, blend_time=0.3, force=True)

        self.assertTrue(ok)
        self.assertIsNone(dummy._anim_blend_transition)
        self.assertEqual(("loop", "walk"), dummy.actor.calls[-1])
        self.assertEqual(1.0, dummy.actor.effect_map.get("walk"))
        self.assertEqual(0.0, dummy.actor.effect_map.get("idle", 0.0))

    def test_arm_active_anim_control_effect_limits_effect_writes_when_audit_is_deferred(self):
        dummy = _AnimDummy({"idle", "walk", "run"} | {f"clip_{idx}" for idx in range(48)})
        dummy._anim_blend_enabled = True
        dummy._anim_control_audit_deferred = True
        dummy._anim_effect_clips = {"walk"}

        dummy._arm_active_anim_control_effect("idle")

        self.assertLessEqual(len(dummy.actor.effects), 2)
        self.assertEqual(1.0, dummy.actor.effect_map.get("idle"))

    def test_xbot_runtime_running_prefers_direct_run_when_weapon_is_sheathed(self):
        dummy = _AnimDummy({"run", "run_blade"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"
        dummy._state_anim_tokens = {"running": "run_blade"}
        dummy._state_anim_overrides = {"running": ["run_blade", "run"]}

        clip, source, requested = dummy._resolve_anim_clip("running", with_meta=True)

        self.assertEqual("run", clip)
        self.assertEqual("xbot_runtime", source)
        self.assertEqual("run", requested)

    def test_xbot_runtime_running_prefers_blade_run_when_weapon_is_drawn(self):
        dummy = _AnimDummy({"run", "run_blade"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"
        dummy._weapon_drawn = True
        dummy._state_anim_tokens = {"running": "run_blade"}
        dummy._state_anim_overrides = {"running": ["run_blade", "run"]}

        clip, source, requested = dummy._resolve_anim_clip("running", with_meta=True)

        self.assertEqual("run_blade", clip)
        self.assertEqual("xbot_runtime", source)
        self.assertEqual("run_blade", requested)

    def test_play_actor_anim_starts_xbot_idle_from_safe_frame_to_skip_bind_pose_lead_in(self):
        dummy = _AnimDummy({"idle"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"

        ok = dummy._play_actor_anim("idle", loop=True, state_name="idle")

        self.assertTrue(ok)
        self.assertEqual(
            ("loop", "idle", 1, None, CLIP_START_FRAME_HINTS["idle"], None),
            dummy.actor.frame_calls[-1],
        )

    def test_play_actor_anim_keeps_weapon_transition_clips_untrimmed(self):
        dummy = _AnimDummy({"weapon_unsheathe"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"

        ok = dummy._play_actor_anim("weapon_unsheathe", loop=False, state_name="weapon_unsheathe")

        self.assertTrue(ok)
        self.assertEqual(
            ("play", "weapon_unsheathe", None, None, None),
            dummy.actor.frame_calls[-1],
        )

    def test_play_actor_anim_uses_explicit_landing_hint_even_on_sherward_non_loop_clip(self):
        dummy = _AnimDummy({"landing"})
        dummy._loaded_player_model_path = "assets/models/hero/sherward/sherward_rework_full_corrective.glb"

        ok = dummy._play_actor_anim("landing", loop=False, state_name="landing")

        self.assertTrue(ok)
        self.assertEqual(
            ("play", "landing", None, CLIP_START_FRAME_HINTS["landing"], None),
            dummy.actor.frame_calls[-1],
        )

    def test_xbot_runtime_can_reach_project_clip_that_manifest_was_not_prioritizing(self):
        dummy = _AnimDummy({"blocking", "block_guard"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"
        dummy._state_anim_tokens = {"blocking": "blocking"}
        dummy._state_anim_overrides = {"blocking": ["blocking"]}

        clip, source, requested = dummy._resolve_anim_clip("blocking", with_meta=True)

        self.assertEqual("block_guard", clip)
        self.assertEqual("xbot_runtime", source)
        self.assertEqual("block_guard", requested)

    def test_xbot_runtime_prefers_dedicated_falling_hard_clip_when_available(self):
        dummy = _AnimDummy({"falling", "falling_hard"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"
        dummy._state_anim_overrides = {"falling_hard": ["falling_hard"]}

        clip, source, requested = dummy._resolve_anim_clip("falling_hard", with_meta=True)

        self.assertEqual("falling_hard", clip)
        self.assertEqual("xbot_runtime", source)
        self.assertEqual("falling_hard", requested)

    def test_xbot_runtime_wallrun_accepts_curated_state_clip_when_it_is_the_live_pack_entry(self):
        dummy = _AnimDummy({"wallrun", "run", "walk"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"

        clip, source, requested = dummy._resolve_anim_clip("wallrun", with_meta=True)

        self.assertEqual("wallrun", clip)
        self.assertIn(source, {"player_states", "state_name"})
        self.assertEqual("wallrun", requested)

    def test_xbot_runtime_climbing_prefers_alternative_clip_when_it_exists(self):
        dummy = _AnimDummy({"climbing", "climb_fast", "run", "walk"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"

        clip, source, requested = dummy._resolve_anim_clip("climbing", with_meta=True)

        self.assertEqual("climb_fast", clip)
        self.assertEqual("xbot_runtime", source)
        self.assertEqual("climb_fast", requested)

    def test_xbot_runtime_vaulting_accepts_curated_state_clip_when_aliases_are_not_present(self):
        dummy = _AnimDummy({"vaulting", "run", "walk"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"

        clip, source, requested = dummy._resolve_anim_clip("vaulting", with_meta=True)

        self.assertEqual("vaulting", clip)
        self.assertIn(source, {"player_states", "state_name"})
        self.assertEqual("vaulting", requested)

    def test_xbot_runtime_climbing_accepts_curated_state_clip_when_aliases_are_not_present(self):
        dummy = _AnimDummy({"climbing", "run", "walk"})
        dummy._loaded_player_model_path = "assets/models/xbot/Xbot.glb"

        clip, source, requested = dummy._resolve_anim_clip("climbing", with_meta=True)

        self.assertEqual("climbing", clip)
        self.assertIn(source, {"player_states", "state_name"})
        self.assertEqual("climbing", requested)



if __name__ == "__main__":
    unittest.main()
