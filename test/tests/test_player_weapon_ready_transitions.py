import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _ActorStub:
    def __init__(self, available=None):
        self.available = {str(name) for name in (available or set())}
        self.calls = []
        self.frame_calls = []

    def setPlayRate(self, _rate, _clip):
        return None

    def getAnimControl(self, clip):
        token = str(clip)
        return token if token in self.available else None

    def loop(self, clip, restart=1, partName=None, fromFrame=None, toFrame=None):
        self.calls.append(("loop", str(clip)))
        self.frame_calls.append(("loop", str(clip), restart, partName, fromFrame, toFrame))

    def play(self, clip, partName=None, fromFrame=None, toFrame=None):
        self.calls.append(("play", str(clip)))
        self.frame_calls.append(("play", str(clip), partName, fromFrame, toFrame))


class _WeaponTransitionDummy:
    _normalize_anim_key = Player._normalize_anim_key
    _uses_xbot_runtime_model = Player._uses_xbot_runtime_model
    _xbot_runtime_state_candidates = Player._xbot_runtime_state_candidates
    _xbot_runtime_blocked_state_tokens = Player._xbot_runtime_blocked_state_tokens
    _resolve_anim_clip = Player._resolve_anim_clip
    _weapon_transition_state_name = Player._weapon_transition_state_name
    _classify_anim_resolution = Player._classify_anim_resolution
    _record_anim_resolution = Player._record_anim_resolution
    _remember_safe_anim = Player._remember_safe_anim
    _clip_start_frame_hint = Player._clip_start_frame_hint
    _arm_active_anim_control_effect = Player._arm_active_anim_control_effect
    _begin_anim_blend_transition = Player._begin_anim_blend_transition
    _anim_play_rate = Player._anim_play_rate
    _play_actor_anim = Player._play_actor_anim
    _trigger_weapon_ready_transition = Player._trigger_weapon_ready_transition
    _set_weapon_drawn = Player._set_weapon_drawn

    def __init__(self, available=None):
        self.actor = _ActorStub(available=available)
        self._available_anims = set(available or set())
        self._state_anim_hints = {}
        self._state_anim_overrides = {}
        self._state_anim_tokens = {}
        self._anim_failed_once = set()
        self._anim_missing_state_once = set()
        self._anim_degraded_once = set()
        self._anim_emergency_once = set()
        self._weapon_transition_missing_once = set()
        self._anim_blend_enabled = False
        self._anim_blend_transition = None
        self._anim_blend_duration = 0.18
        self._anim_state = "idle"
        self._anim_clip = "idle"
        self._anim_resolution_mode = "uninitialized"
        self._anim_resolution_source = ""
        self._anim_resolution_requested_state = ""
        self._anim_resolution_clip = ""
        self._last_safe_anim_state = "idle"
        self._last_safe_anim_clip = "idle"
        self._state_lock_until = 0.0
        self.walk_speed = 5.0
        self.run_speed = 9.0
        self.flight_speed = 15.0
        self.cs = SimpleNamespace(velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0))
        self._weapon_drawn = False
        self._drawn_hold_timer = 0.0
        self._has_weapon_visual = True
        self._has_offhand_visual = False
        self._weapon_visual_style = "blade"
        self._offhand_visual_style = "ward"
        self._sword_node = _NodeStub("sword")
        self._shield_node = _NodeStub("shield")
        self._sword_hand_anchor = _NodeStub("right_hand")
        self._shield_hand_anchor = _NodeStub("left_hand")
        self._sword_sheath_anchor = _NodeStub("left_hip")
        self._spine_upper = _NodeStub("spine")
        self._state_defs = {
            "weapon_unsheathe": {"duration": 0.42, "blend_time": 0.05},
            "weapon_sheathe": {"duration": 0.40, "blend_time": 0.05},
        }
        self._played_sfx = []

    def _equipment_pose_profile(self, slot_name, _style, drawn):
        if slot_name == "weapon_main":
            return ("right_hand", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) if drawn else ("left_hip", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        return ("spine", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def _resolve_attach_point(self, anchor_name):
        token = str(anchor_name or "")
        if token == "right_hand":
            return self._sword_hand_anchor
        if token == "left_hand":
            return self._shield_hand_anchor
        if token in {"left_hip", "hip_l", "sheathe"}:
            return self._sword_sheath_anchor
        return self._spine_upper

    def _play_sfx(self, key, volume=1.0):
        self._played_sfx.append((str(key), float(volume)))


class _NodeStub:
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.visible = False
        self.pos = None
        self.hpr = None

    def wrtReparentTo(self, parent):
        self.parent = parent

    def setPos(self, *args):
        self.pos = args

    def setHpr(self, *args):
        self.hpr = args

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class PlayerWeaponReadyTransitionTests(unittest.TestCase):
    def test_trigger_weapon_ready_transition_plays_strict_unsheathe_clip_when_available(self):
        dummy = _WeaponTransitionDummy({"weapon_unsheathe", "weapon_sheathe"})

        ok = dummy._trigger_weapon_ready_transition(True)

        self.assertTrue(ok)
        self.assertEqual("weapon_unsheathe", dummy._anim_state)
        self.assertEqual("weapon_unsheathe", dummy._anim_clip)
        self.assertEqual("ok", dummy._anim_resolution_mode)
        self.assertIn(("play", "weapon_unsheathe"), dummy.actor.calls)
        self.assertGreater(dummy._state_lock_until, 0.0)

    def test_trigger_weapon_ready_transition_refuses_to_fake_missing_clip(self):
        dummy = _WeaponTransitionDummy({"idle"})

        ok = dummy._trigger_weapon_ready_transition(True)

        self.assertFalse(ok)
        self.assertEqual("idle", dummy._anim_state)
        self.assertEqual("idle", dummy._anim_clip)
        self.assertEqual([], dummy.actor.calls)

    def test_set_weapon_drawn_routes_visual_and_requests_weapon_ready_transition(self):
        dummy = _WeaponTransitionDummy({"weapon_unsheathe", "weapon_sheathe"})

        dummy._set_weapon_drawn(True)
        dummy._set_weapon_drawn(False)

        self.assertEqual(("play", "weapon_unsheathe"), dummy.actor.calls[0])
        self.assertEqual(("play", "weapon_sheathe"), dummy.actor.calls[1])
        self.assertEqual(self._extract_names(dummy._played_sfx), ["weapon_unsheathe"])
        self.assertIs(dummy._sword_node.parent, dummy._sword_sheath_anchor)

    def _extract_names(self, rows):
        return [str(name) for name, _volume in rows]


if __name__ == "__main__":
    unittest.main()
