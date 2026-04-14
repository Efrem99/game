"""Context-aware camera director with polished cinematic shot support.

Improvements over previous version:
- Shots use a better easing curve: ease-in at start, ease-out at end (smooth cubic quintic)
- Cutscene exit is eased (blend back smoothly into gameplay camera)
- Shot end is detected early to pre-blend back, preventing a snap
- Camera profiles have tuned smooth values for each context
- added `cinematic` profile for letterbox/wide shots
- Dialog / boss shots have improved yaw/pitch offsets for drama
"""

import math
import os
import random

from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import LPoint3, Vec3

from utils.logger import logger


# ─────────────────────────────────────────────────────────────────────────
# Easing functions
# ─────────────────────────────────────────────────────────────────────────

def _smoothstep(t: float) -> float:
    """Classic cubic smoothstep — accelerate then decelerate."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _smootherstep(t: float) -> float:
    """Quintic smootherstep — zero first+second derivative at edges → butter-smooth."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    else:
        p = 2.0 * t - 2.0
        return 0.5 * p * p * p + 1.0


def _ease_out_quart(t: float) -> float:
    t = max(0.0, min(1.0, t))
    m = t - 1.0
    return 1.0 - (m * m * m * m)


def _lerp3(a, b, t):
    t = max(0.0, min(1.0, float(t)))
    try:
        ax, ay, az = float(a.x), float(a.y), float(a.z)
        bx, by, bz = float(b.x), float(b.y), float(b.z)
        if any(math.isnan(v) or math.isinf(v) for v in (ax, ay, az, bx, by, bz)):
            return LPoint3(0, 0, 0)
        return LPoint3(
            ax + (bx - ax) * t,
            ay + (by - ay) * t,
            az + (bz - az) * t,
        )
    except Exception:
        return LPoint3(0, 0, 0)


class CameraDirector:
    COMBAT_ANIM_STATES = {
        "attacking", "attack_light", "attack_heavy", "attack_finisher",
        "dodging", "dash_forward", "dash_back",
        "casting", "cast_prepare", "cast_channel", "cast_release",
        "blocking", "block_hold", "block_perfect",
    }

    # Fraction of shot duration to start blending back to gameplay cam.
    # e.g. 0.15 = last 15 % of the shot eases back gracefully.
    BLEND_BACK_FRACTION = 0.18

    def __init__(self, app):
        self.app = app
        self._default_profiles = {
            "exploration": {"dist": 22.0, "pitch": -20.0, "target_z": 1.8,  "side": 0.0, "smooth": 7.5},
            "combat":      {"dist": 17.5, "pitch": -15.0, "target_z": 1.9,  "side": 0.0, "smooth": 10.0},
            "aim":         {"dist": 9.8,  "pitch":  -8.5, "target_z": 1.72, "side": 1.45, "smooth": 13.5},
            "bow_aim":     {"dist": 8.9,  "pitch":  -7.0, "target_z": 1.72, "side": 1.72, "smooth": 15.0, "look_side": -0.92, "look_ahead": 2.85},
            "magic_cast":  {"dist": 11.2, "pitch":  -9.6, "target_z": 1.86, "side": -1.35, "smooth": 12.8, "look_side": 0.58, "look_ahead": 1.85},
            "shoulder_right": {"dist": 10.8, "pitch": -8.0, "target_z": 1.74, "side": 1.85, "smooth": 14.0, "look_side": -0.82, "look_ahead": 2.2},
            "shoulder_left": {"dist": 10.8, "pitch": -8.0, "target_z": 1.74, "side": -1.85, "smooth": 14.0, "look_side": 0.82, "look_ahead": 2.2},
            "stealth":     {"dist": 12.8, "pitch": -9.0, "target_z": 1.62, "side": -1.25, "smooth": 11.5, "look_side": 0.42, "look_ahead": 1.35},
            "boss":        {"dist": 29.0, "pitch": -12.0, "target_z": 2.4,  "side": 0.0, "smooth": 5.5},
            "tutorial":    {"dist": 20.0, "pitch": -18.0, "target_z": 1.9,  "side": 0.0, "smooth": 8.5},
            "swim":        {"dist": 18.5, "pitch": -10.0, "target_z": 1.4,  "side": 0.0, "smooth": 7.2},
            "flight":      {"dist": 30.0, "pitch": -26.0, "target_z": 2.6,  "side": 0.0, "smooth": 5.3},
            "mounted":     {"dist": 24.0, "pitch": -17.0, "target_z": 2.2,  "side": 0.0, "smooth": 6.8},
            "mounted_horse": {"dist": 23.0, "pitch": -16.0, "target_z": 2.1, "side": 0.0, "smooth": 7.4},
            "mounted_carriage": {"dist": 25.5, "pitch": -18.0, "target_z": 2.45, "side": 0.5, "smooth": 6.2},
            "mounted_ship": {"dist": 27.5, "pitch": -13.5, "target_z": 2.9, "side": 0.0, "smooth": 5.4},
            "dialog":      {"dist": 11.5, "pitch":  -8.0, "target_z": 1.85, "side": 2.0, "smooth": 9.0},
            # Wide cinematic profile — used during cutscene shots
            "cinematic":   {"dist": 26.0, "pitch": -14.0, "target_z": 2.0,  "side": 3.5, "smooth": 4.0},
        }
        self._profiles = {k: dict(v) for k, v in self._default_profiles.items()}

        self._default_shots = {
            "dialog":     {"duration": 1.35, "profile": "dialog",    "side": 2.3,  "yaw_bias_deg":  8.0},
            "boss_intro": {"duration": 1.80, "profile": "cinematic", "side": 5.5,  "yaw_bias_deg": 22.0},
            "location":   {"duration": 2.00, "profile": "cinematic", "side": 4.0,  "yaw_bias_deg": 12.0},
            "spell_hit":  {"duration": 0.90, "profile": "combat",    "side": 1.5,  "yaw_bias_deg":  5.0},
        }
        self._shots = {k: dict(v) for k, v in self._default_shots.items()}
        self._default_sequences = {
            "location_reveal": [
                {"name": "location_wide", "duration": 1.05, "profile": "cinematic", "side": 3.8, "yaw_bias_deg": 12.0},
                {"name": "location_settle", "duration": 0.80, "profile": "exploration", "side": 1.35, "yaw_bias_deg": -4.0},
            ],
            "portal_arrival": [
                {"name": "portal_wide", "duration": 0.95, "profile": "cinematic", "side": 4.4, "yaw_bias_deg": 16.0},
                {"name": "portal_settle", "duration": 0.78, "profile": "shoulder_right", "side": 1.65, "yaw_bias_deg": -8.0},
            ],
        }
        self._sequences = {k: [dict(row) for row in v] for k, v in self._default_sequences.items()}
        self._locations = {}
        self._zones = []

        self._auto_boss_intro = True
        self._boss_intro_cooldown_sec = 9.0
        self._active_profile = "exploration"
        self._forced_profile = None
        self._forced_until = 0.0
        self._profile_override_priority = -999
        self._profile_override_owner = ""

        # Shot state
        self._cutscene = None
        # Snapshot of gameplay camera taken when shot ENDS (for blend-back)
        self._blend_back = None
        self._active_shot_priority = -999
        self._active_shot_owner = ""
        self._shot_priority_cfg = {
            "dialog": 92,
            "dialog_auto": 91,
            "dialog_npc": 93,
            "dialog_player": 93,
            "dialog_wide": 90,
            "boss_intro": 82,
            "location": 70,
            "spell_hit": 64,
            "shot": 50,
        }
        self._profile_priority_cfg = {
            "dialog": 90,
            "cinematic": 84,
            "boss": 80,
            "bow_aim": 79,
            "magic_cast": 78,
            "aim": 72,
            "stealth": 70,
            "combat": 60,
            "exploration": 40,
        }

        self._last_state_name = ""
        self._last_location_token = ""
        self._last_logged_profile = ""
        self._zone_inside = {}
        self._boss_prev = False
        self._boss_intro_cooldown_until = 0.0
        self._last_shot_log_t = 0.0
        self._last_resolved_pos = None
        self._last_resolved_look = None
        self._sequence_state = None
        self._impulse_pitch = 0.0
        self._impulse_yaw = 0.0
        self._impulse_roll = 0.0
        self._impulse_shake = 0.0
        self._debug_disable_camera_context_rules = False
        self._screen_state = {
            "vignette_boost": 0.0,
            "fear_tint": 0.0,
            "damage_tint": 0.0,
            "combat_heat": 0.0,
        }
        self._load_config()
        if str(os.environ.get("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO", "0")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            self._auto_boss_intro = False
            logger.warning(
                "[Debug] Disabled auto boss intro via "
                "XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO=1"
            )
        if str(os.environ.get("XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES", "0")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            self._debug_disable_camera_context_rules = True
            logger.warning(
                "[Debug] Disabled camera location/zone context rules via "
                "XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES=1"
            )
        self._bind_event_bus()

    # ──────────────────────────────────────────────────────────────
    # Config helpers
    # ──────────────────────────────────────────────────────────────

    def _now(self):
        return float(globalClock.getFrameTime())

    def _coerce_float(self, value, default, min_value=None, max_value=None):
        try:
            out = float(value)
        except Exception:
            out = float(default)
        if min_value is not None:
            out = max(float(min_value), out)
        if max_value is not None:
            out = min(float(max_value), out)
        return float(out)

    def _point3_is_finite(self, value):
        try:
            return all(math.isfinite(float(axis)) for axis in (value.x, value.y, value.z))
        except Exception:
            return False

    def _point3_is_near_origin(self, value, eps=1e-4):
        if not self._point3_is_finite(value):
            return False
        try:
            return (
                abs(float(value.x)) <= float(eps)
                and abs(float(value.y)) <= float(eps)
                and abs(float(value.z)) <= float(eps)
            )
        except Exception:
            return False

    def _camera_start_pose(self, center, base_z, cfg):
        from_look = self._look_target(
            center=center,
            base_z=base_z,
            yaw_rad=math.radians(float(getattr(self.app, "_cam_yaw", 0.0) or 0.0)),
            target_z=float(cfg.get("target_z", 1.8)),
            look_side=float(cfg.get("look_side", 0.0)),
            look_ahead=float(cfg.get("look_ahead", 0.0)),
        )
        try:
            node_pos = self.app.camera.getPos(self.app.render)
        except Exception:
            node_pos = None
        if self._point3_is_finite(node_pos) and not self._point3_is_near_origin(node_pos):
            return (
                LPoint3(float(node_pos.x), float(node_pos.y), float(node_pos.z)),
                from_look,
            )
        cached_pos = self._last_resolved_pos
        cached_look = self._last_resolved_look
        if self._point3_is_finite(cached_pos) and self._point3_is_finite(cached_look):
            return (
                LPoint3(float(cached_pos.x), float(cached_pos.y), float(cached_pos.z)),
                LPoint3(float(cached_look.x), float(cached_look.y), float(cached_look.z)),
            )
        if self._point3_is_finite(node_pos):
            return (
                LPoint3(float(node_pos.x), float(node_pos.y), float(node_pos.z)),
                from_look,
            )
        return LPoint3(0.0, 0.0, 0.0), from_look

    def _coerce_int(self, value, default, min_value=None, max_value=None):
        try:
            out = int(value)
        except Exception:
            out = int(default)
        if min_value is not None:
            out = max(int(min_value), out)
        if max_value is not None:
            out = min(int(max_value), out)
        return int(out)

    def _merge_profile(self, base, payload):
        if not isinstance(payload, dict):
            return dict(base)
        out = dict(base)
        out["dist"]     = self._coerce_float(payload.get("dist",     out.get("dist",     22.0)),  out.get("dist",     22.0),  4.0, 80.0)
        out["pitch"]    = self._coerce_float(payload.get("pitch",    out.get("pitch",   -20.0)),  out.get("pitch",   -20.0), -85.0, 85.0)
        out["target_z"] = self._coerce_float(payload.get("target_z", out.get("target_z",  1.8)),  out.get("target_z",  1.8),  0.0,  8.0)
        out["side"]     = self._coerce_float(payload.get("side",     out.get("side",     0.0)),   out.get("side",     0.0), -20.0, 20.0)
        out["smooth"]   = self._coerce_float(payload.get("smooth",   out.get("smooth",   7.5)),   out.get("smooth",   7.5),  0.1, 30.0)
        out["look_side"] = self._coerce_float(payload.get("look_side", out.get("look_side", 0.0)), out.get("look_side", 0.0), -12.0, 12.0)
        out["look_ahead"] = self._coerce_float(payload.get("look_ahead", out.get("look_ahead", 0.0)), out.get("look_ahead", 0.0), -20.0, 20.0)
        return out

    def _merge_shot(self, base, payload):
        if not isinstance(payload, dict):
            return dict(base)
        out = dict(base)
        out["duration"]     = self._coerce_float(payload.get("duration",     out.get("duration",     1.0)), out.get("duration",     1.0),  0.2, 10.0)
        out["side"]         = self._coerce_float(payload.get("side",         out.get("side",         0.0)), out.get("side",         0.0), -30.0, 30.0)
        out["yaw_bias_deg"] = self._coerce_float(payload.get("yaw_bias_deg", out.get("yaw_bias_deg", 0.0)), out.get("yaw_bias_deg", 0.0), -180.0, 180.0)
        profile_name = str(payload.get("profile", out.get("profile", "exploration")) or "").strip().lower()
        if profile_name:
            out["profile"] = profile_name
        return out

    def _merge_sequence_step(self, payload, default_name="shot"):
        base = {
            "name": str(default_name or "shot"),
            "duration": 1.0,
            "profile": "exploration",
            "side": 0.0,
            "yaw_bias_deg": 0.0,
        }
        if not isinstance(payload, dict):
            return dict(base)
        out = self._merge_shot(base, payload)
        out["name"] = str(payload.get("name") or default_name or "shot")
        return out

    def _merge_location_rule(self, name, payload):
        if not isinstance(payload, dict):
            payload = {}
        return {
            "key": str(name or "").strip().lower(),
            "profile": str(payload.get("profile", "") or "").strip().lower(),
            "priority": self._coerce_int(payload.get("priority", 78), 78, -999, 999),
            "enter_shot": str(payload.get("enter_shot", "") or "").strip().lower(),
            "enter_sequence": str(payload.get("enter_sequence", "") or "").strip().lower(),
            "owner": str(payload.get("owner") or f"location:{name}"),
        }

    def _safe_vec3(self, value):
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            try:
                return (
                    float(value[0]),
                    float(value[1]),
                    float(value[2]),
                )
            except Exception:
                return None
        return None

    def _merge_zone_rule(self, payload, idx=0):
        if not isinstance(payload, dict):
            payload = {}
        center = self._safe_vec3(payload.get("center"))
        if center is None:
            return None
        token = str(payload.get("id") or f"zone_{idx}").strip().lower()
        return {
            "id": token,
            "location": str(payload.get("location", "") or "").strip().lower(),
            "center": center,
            "radius": self._coerce_float(payload.get("radius", 4.0), 4.0, 0.1, 2000.0),
            "profile": str(payload.get("profile", "") or "").strip().lower(),
            "priority": self._coerce_int(payload.get("priority", 80), 80, -999, 999),
            "enter_shot": str(payload.get("enter_shot", "") or "").strip().lower(),
            "enter_sequence": str(payload.get("enter_sequence", "") or "").strip().lower(),
            "owner": str(payload.get("owner") or f"zone:{token}"),
        }

    def _load_config(self):
        cfg = getattr(getattr(self.app, "data_mgr", None), "camera_profiles", None)
        if not isinstance(cfg, dict):
            return

        profiles_cfg = cfg.get("profiles", {})
        if isinstance(profiles_cfg, dict):
            merged = {k: dict(v) for k, v in self._default_profiles.items()}
            for key, payload in profiles_cfg.items():
                name = str(key or "").strip().lower()
                if not name:
                    continue
                base = merged.get(name, merged.get("exploration", {}))
                merged[name] = self._merge_profile(base, payload)
            self._profiles = merged

        shots_cfg = cfg.get("shots", {})
        if isinstance(shots_cfg, dict):
            merged_shots = {k: dict(v) for k, v in self._default_shots.items()}
            for key, payload in shots_cfg.items():
                name = str(key or "").strip().lower()
                if not name:
                    continue
                base = merged_shots.get(name, {"duration": 1.0, "profile": "exploration", "side": 0.0, "yaw_bias_deg": 0.0})
                merged_shots[name] = self._merge_shot(base, payload)
            self._shots = merged_shots

        sequences_cfg = cfg.get("sequences", {})
        merged_sequences = {k: [dict(step) for step in v] for k, v in self._default_sequences.items()}
        if isinstance(sequences_cfg, dict):
            for key, payload in sequences_cfg.items():
                name = str(key or "").strip().lower()
                if (not name) or (not isinstance(payload, list)):
                    continue
                steps = []
                for idx, row in enumerate(payload):
                    steps.append(self._merge_sequence_step(row, default_name=f"{name}_{idx + 1}"))
                if steps:
                    merged_sequences[name] = steps
        self._sequences = merged_sequences

        location_cfg = cfg.get("locations", {})
        merged_locations = {}
        if isinstance(location_cfg, dict):
            for key, payload in location_cfg.items():
                token = str(key or "").strip().lower()
                if not token:
                    continue
                merged_locations[token] = self._merge_location_rule(token, payload)
        elif isinstance(location_cfg, list):
            for item in location_cfg:
                if not isinstance(item, dict):
                    continue
                token = str(item.get("location") or item.get("name") or "").strip().lower()
                if not token:
                    continue
                merged_locations[token] = self._merge_location_rule(token, item)
        self._locations = merged_locations

        zone_cfg = cfg.get("zones", [])
        merged_zones = []
        if isinstance(zone_cfg, list):
            for idx, item in enumerate(zone_cfg):
                zone = self._merge_zone_rule(item, idx=idx)
                if isinstance(zone, dict):
                    merged_zones.append(zone)
        self._zones = merged_zones

        settings = cfg.get("settings", {})
        if isinstance(settings, dict):
            self._auto_boss_intro = bool(settings.get("auto_boss_intro", self._auto_boss_intro))
            self._boss_intro_cooldown_sec = self._coerce_float(
                settings.get("boss_intro_cooldown", self._boss_intro_cooldown_sec),
                self._boss_intro_cooldown_sec, 0.0, 60.0,
            )
            shot_priorities = settings.get("shot_priorities", {})
            if isinstance(shot_priorities, dict):
                for key, value in shot_priorities.items():
                    token = str(key or "").strip().lower()
                    if not token:
                        continue
                    self._shot_priority_cfg[token] = self._coerce_int(value, 50, -999, 999)
            profile_priorities = settings.get("profile_override_priorities", {})
            if isinstance(profile_priorities, dict):
                for key, value in profile_priorities.items():
                    token = str(key or "").strip().lower()
                    if not token:
                        continue
                    self._profile_priority_cfg[token] = self._coerce_int(value, 40, -999, 999)

        logger.info(
            f"[CameraDirector] Loaded {len(self._profiles)} profiles, "
            f"{len(self._shots)} shots, {len(self._sequences)} sequences, "
            f"{len(self._locations)} location rules, {len(self._zones)} zones, "
            f"auto_boss_intro={self._auto_boss_intro}"
        )

    # ──────────────────────────────────────────────────────────────
    # Context queries
    # ──────────────────────────────────────────────────────────────

    def _player(self):
        return getattr(self.app, "player", None)

    def _player_center(self):
        player = self._player()
        if not player or not getattr(player, "actor", None):
            return None, 0.0
        cs = getattr(self.app, "char_state", None)
        if cs and hasattr(cs, "position"):
            cp = cs.position
            return Vec3(float(cp.x), float(cp.y), float(cp.z)), float(cp.z)
        pos = player.actor.getPos()
        try:
            px, py, pz = float(pos.x), float(pos.y), float(pos.z)
            if any(math.isnan(v) or math.isinf(v) for v in (px, py, pz)):
                return LPoint3(0, 0, 0), 0.0
            return Vec3(px, py, pz), pz
        except Exception:
            return LPoint3(0, 0, 0), 0.0

    def _state_name(self):
        state_mgr = getattr(self.app, "state_mgr", None)
        state = getattr(state_mgr, "current_state", None)
        return str(getattr(state, "name", state) or "").strip().lower()

    def _is_boss_context(self):
        boss_mgr = getattr(self.app, "boss_manager", None)
        if boss_mgr and hasattr(boss_mgr, "any_engaged"):
            try:
                if boss_mgr.any_engaged():
                    return True
            except Exception:
                pass
        dragon = getattr(self.app, "dragon_boss", None)
        if dragon and bool(getattr(dragon, "is_engaged", False)):
            return True
        return False

    def _is_combat_context(self):
        player = self._player()
        if not player:
            return False
        if self._locked_enemy_target_info():
            return True
        getter = getattr(player, "get_hud_combat_event", None)
        if callable(getter):
            try:
                if getter():
                    return True
            except Exception:
                pass
        anim_state = str(getattr(player, "_anim_state", "") or "").strip().lower()
        return anim_state in self.COMBAT_ANIM_STATES

    def _is_aim_context(self):
        player = self._player()
        if not player:
            return False
        return bool(getattr(player, "_is_aiming", False))

    def _aim_mode(self):
        player = self._player()
        if not player:
            return ""
        return str(getattr(player, "_aim_mode", "") or "").strip().lower()

    def _is_ranged_aim_context(self):
        player = self._player()
        if not player or not bool(getattr(player, "_is_aiming", False)):
            return False
        aim_mode = self._aim_mode()
        if aim_mode == "magic":
            return False
        if aim_mode == "bow":
            return True
        checker = getattr(player, "_is_ranged_weapon_equipped", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return False

    def _is_magic_context(self):
        player = self._player()
        if not player:
            return False
        aim_mode = self._aim_mode()
        if bool(getattr(player, "_is_aiming", False)) and aim_mode == "magic":
            return True
        if getattr(player, "_pending_spell", None):
            return True
        try:
            if float(getattr(player, "_spell_cast_lock_until", 0.0) or 0.0) > self._now():
                return True
        except Exception:
            pass
        anim_state = str(getattr(player, "_anim_state", "") or "").strip().lower()
        return anim_state in {"casting", "cast_prepare", "cast_channel", "cast_release"}

    def _is_stealth_context(self):
        player = self._player()
        if not player:
            return False
        return bool(
            getattr(player, "_stealth_crouch", False)
            or getattr(player, "_shadow_mode", False)
        )

    def _is_tutorial_context(self):
        tutorial = getattr(self.app, "movement_tutorial", None)
        return bool(tutorial and getattr(tutorial, "enabled", False))

    def _is_mounted(self):
        vm = getattr(self.app, "vehicle_mgr", None)
        return bool(vm and getattr(vm, "is_mounted", False))

    def _mounted_kind(self):
        vm = getattr(self.app, "vehicle_mgr", None)
        if not vm or not getattr(vm, "is_mounted", False):
            return ""
        vehicle = vm.mounted_vehicle() if hasattr(vm, "mounted_vehicle") else None
        if not isinstance(vehicle, dict):
            return ""
        kind = str(vehicle.get("kind", "")).strip().lower()
        if kind in {"boat", "skiff", "sloop"}:
            kind = "ship"
        elif kind in {"direwolf", "dire_wolf", "warg", "wolf", "stag", "deer", "elk", "reindeer", "pony", "mare"}:
            kind = "horse"
        elif kind in {"wagon", "cart"}:
            kind = "carriage"
        return kind

    def _is_in_water(self):
        player = self._player()
        cs = getattr(player, "cs", None) if player else None
        return bool(cs and getattr(cs, "inWater", False))

    def _is_flying(self):
        player = self._player()
        return bool(player and getattr(player, "_is_flying", False))

    def _locked_enemy_target_info(self):
        info = getattr(self.app, "_aim_target_info", None)
        if not isinstance(info, dict):
            return None
        if not bool(info.get("locked", False)):
            return None
        kind = str(info.get("kind", "") or "").strip().lower()
        if kind != "enemy":
            return None
        return dict(info)

    def _target_world_pos(self, info):
        if not isinstance(info, dict):
            return None
        pos = info.get("position")
        if pos is not None and all(hasattr(pos, axis) for axis in ("x", "y", "z")):
            try:
                return Vec3(float(pos.x), float(pos.y), float(pos.z))
            except Exception:
                return None
        node = info.get("node")
        if not node:
            return None
        getter = getattr(node, "getPos", None)
        if not callable(getter):
            getter = getattr(node, "get_pos", None)
        if not callable(getter):
            return None
        try:
            render = getattr(self.app, "render", None)
            pos = getter(render) if render is not None else getter()
            return Vec3(float(pos.x), float(pos.y), float(pos.z))
        except Exception:
            return None

    def _combat_focus_state(self):
        player = self._player()
        event = None
        if player:
            getter = getattr(player, "get_hud_combat_event", None)
            if callable(getter):
                try:
                    event = getter()
                except Exception:
                    event = None

        locked = self._locked_enemy_target_info()
        locked_pos = self._target_world_pos(locked)
        center, _ = self._player_center()
        target_distance = None
        side_sign = 1.0
        if center is not None and locked_pos is not None:
            dx = float(locked_pos.x) - float(center.x)
            dy = float(locked_pos.y) - float(center.y)
            target_distance = math.sqrt((dx * dx) + (dy * dy))
            yaw_rad = math.radians(float(getattr(self.app, "_cam_yaw", 0.0) or 0.0))
            lateral = (dx * math.cos(yaw_rad)) - (dy * math.sin(yaw_rad))
            side_sign = -1.0 if lateral < 0.0 else 1.0

        anim_state = str(getattr(player, "_anim_state", "") or "").strip().lower() if player else ""
        active = bool(event) or bool(locked) or bool(self._is_boss_context()) or anim_state in self.COMBAT_ANIM_STATES
        amount = 0.0
        if isinstance(event, dict):
            try:
                amount = max(0.0, float(event.get("amount", 0.0) or 0.0))
            except Exception:
                amount = 0.0

        return {
            "active": bool(active),
            "locked": bool(locked),
            "target_distance": target_distance,
            "side_sign": side_sign,
            "amount": amount,
            "label": str(event.get("label", "") if isinstance(event, dict) else "").strip().lower(),
        }

    def _augment_combat_profile(self, profile_name, cfg, focus):
        out = dict(cfg or {})
        token = str(profile_name or "").strip().lower()
        if token not in {"combat", "aim", "bow_aim", "magic_cast", "boss"}:
            return out
        if not isinstance(focus, dict) or not bool(focus.get("active", False)):
            return out

        locked = bool(focus.get("locked", False))
        target_distance = focus.get("target_distance")
        side_sign = -1.0 if float(focus.get("side_sign", 1.0) or 1.0) < 0.0 else 1.0
        base_dist = self._coerce_float(out.get("dist", 22.0), 22.0, 5.0, 80.0)
        base_side = self._coerce_float(out.get("side", 0.0), 0.0, -20.0, 20.0)
        base_target_z = self._coerce_float(out.get("target_z", 1.8), 1.8, 0.0, 8.0)
        base_pitch = self._coerce_float(out.get("pitch", -20.0), -20.0, -85.0, 85.0)

        if token in {"aim", "bow_aim"}:
            if locked:
                out["side"] = side_sign * max(1.75, abs(base_side))
                out["dist"] = min(16.0, max(base_dist, 10.8))
                out["target_z"] = max(base_target_z, 1.86)
            return out

        dist_bonus = 0.85
        if locked:
            dist_bonus += 0.95
        if isinstance(target_distance, (int, float)):
            if float(target_distance) < 6.5:
                dist_bonus += 0.95
            elif float(target_distance) < 11.5:
                dist_bonus += 0.35
        out["dist"] = min(24.5, max(10.0, base_dist + dist_bonus))
        out["side"] = side_sign * max(0.95 if locked else 0.45, abs(base_side))
        out["target_z"] = max(base_target_z, 2.02 if locked else 1.95)
        out["pitch"] = max(-15.0, min(-12.5, base_pitch + 1.8))
        out["smooth"] = max(self._coerce_float(out.get("smooth", 8.0), 8.0, 0.1, 30.0), 11.0)
        return out

    def _resolve_profile(self):
        state_name = self._state_name()
        if state_name in {"main_menu", "loading", "paused", "inventory"}:
            return "exploration"
        if state_name == "dialog":
            return "dialog"
        if self._is_magic_context():
            if "magic_cast" in self._profiles:
                return "magic_cast"
            if "shoulder_left" in self._profiles:
                return "shoulder_left"
            return "aim" if "aim" in self._profiles else "combat"
        if self._is_ranged_aim_context():
            if "bow_aim" in self._profiles:
                return "bow_aim"
            return "aim" if "aim" in self._profiles else "combat"
        if self._is_aim_context():
            return "aim" if "aim" in self._profiles else "combat"
        if self._is_boss_context():
            return "boss"
        if self._is_combat_context():
            return "combat"
        if self._is_mounted():
            mounted_kind = self._mounted_kind()
            if mounted_kind in {"horse", "carriage", "ship"}:
                specific = f"mounted_{mounted_kind}"
                if specific in self._profiles:
                    return specific
            return "mounted"
        if self._is_flying():
            return "flight"
        if self._is_in_water():
            return "swim"
        if self._is_tutorial_context():
            return "tutorial"
        if self._is_stealth_context():
            return "stealth" if "stealth" in self._profiles else "exploration"
        return "exploration"

    # ──────────────────────────────────────────────────────────────
    # Math helpers
    # ──────────────────────────────────────────────────────────────

    def _approach(self, current, target, gain):
        if abs(target - current) < 1e-4:
            return float(target)
        return float(current + ((target - current) * gain))

    def _camera_pos(self, center, base_z, yaw_rad, pitch_rad, dist, side, target_z, min_floor=0.5):
        try:
            cx_ref, cy_ref, cz_ref = float(center.x), float(center.y), float(center.z)
            dist, side = float(dist), float(side)
            yr, pr = float(yaw_rad), float(pitch_rad)
            tz, bz = float(target_z), float(base_z)
            
            if any(math.isnan(v) or math.isinf(v) for v in (cx_ref, cy_ref, cz_ref, dist, side, yr, pr, tz, bz)):
                return LPoint3(0, 0, 0), LPoint3(0, 0, 0)

            cx = cx_ref + (dist * math.sin(yr) * math.cos(pr)) + (side * math.cos(yr))
            cy = cy_ref - (dist * math.cos(yr) * math.cos(pr)) + (side * math.sin(yr))
            cz = bz + tz + (dist * math.sin(-pr))
            if cz < bz + min_floor:
                cz = bz + min_floor
            
            if any(math.isnan(v) or math.isinf(v) for v in (cx, cy, cz)):
                return LPoint3(0, 0, 0), LPoint3(0, 0, 0)
                
            look_at = LPoint3(cx_ref, cy_ref, bz + tz)
            # Enforce minimum distance to avoid co-location lookAt crashes
            if (LPoint3(cx, cy, cz) - look_at).length_squared() < 1e-6:
                cx += 0.01
            return LPoint3(cx, cy, cz), look_at
        except Exception:
            return LPoint3(0, 0, 0), LPoint3(0, 0, 0)

    def _look_target(self, center, base_z, yaw_rad, target_z, look_side=0.0, look_ahead=0.0):
        try:
            cx_ref, cy_ref = float(center.x), float(center.y)
            bz = float(base_z)
            yr = float(yaw_rad)
            ls = float(look_side or 0.0)
            la = float(look_ahead or 0.0)
            tz = float(target_z)
            if any(math.isnan(v) or math.isinf(v) for v in (cx_ref, cy_ref, bz, yr, ls, la, tz)):
                return LPoint3(0, 0, 0)
            right_x = math.cos(yr)
            right_y = math.sin(yr)
            forward_x = math.sin(yr)
            forward_y = math.cos(yr)
            return LPoint3(
                cx_ref + (right_x * ls) + (forward_x * la),
                cy_ref + (right_y * ls) + (forward_y * la),
                bz + tz,
            )
        except Exception:
            return LPoint3(0, 0, 0)

    def _movement_heading_rad(self, profile_name=""):
        cs = getattr(self.app, "char_state", None)
        velocity = getattr(cs, "velocity", None) if cs else None
        if velocity is None:
            return None
        try:
            vx = float(getattr(velocity, "x", 0.0) or 0.0)
            vy = float(getattr(velocity, "y", 0.0) or 0.0)
        except Exception:
            return None
        speed = math.sqrt((vx * vx) + (vy * vy))
        token = str(profile_name or "").strip().lower()
        min_speed = 1.4 if token == "flight" else 2.0
        if speed < min_speed:
            return None
        return math.atan2(vx, vy)

    def _compose_dialog_pair_pose(self, *, base_z, look_target, partner_target, side):
        try:
            if not (self._point3_is_finite(look_target) and self._point3_is_finite(partner_target)):
                return None
            sx = float(look_target.x)
            sy = float(look_target.y)
            sz = float(look_target.z)
            px = float(partner_target.x)
            py = float(partner_target.y)
            pz = float(partner_target.z)
            bz = float(base_z)
            dx = sx - px
            dy = sy - py
            planar = math.hypot(dx, dy)
            if planar < 0.18:
                return None

            forward_x = dx / planar
            forward_y = dy / planar
            right_x = forward_y
            right_y = -forward_x
            side_sign = -1.0 if float(side or 0.0) < 0.0 else 1.0

            back_offset = max(1.4, min(3.6, planar * 0.45))
            shoulder_offset = max(0.45, min(1.1, abs(float(side or 0.0)) * 0.55))
            mid_x = (sx + px) * 0.5
            mid_y = (sy + py) * 0.5
            eye_z = max(bz + 1.25, (sz * 0.55) + (pz * 0.45) - 0.05)

            cam_pos = LPoint3(
                mid_x - (forward_x * back_offset) + (right_x * side_sign * shoulder_offset),
                mid_y - (forward_y * back_offset) + (right_y * side_sign * shoulder_offset),
                eye_z,
            )
            if not self._point3_is_finite(cam_pos):
                return None
            if (cam_pos - look_target).length_squared() < 0.05:
                return None
            return cam_pos
        except Exception:
            return None

    def _profile_zoom_bounds(self, profile_name, cfg):
        token = str(profile_name or "").strip().lower()
        defaults = {
            "exploration": (12.0, 34.0),
            "combat": (13.5, 26.0),
            "aim": (7.8, 13.5),
            "bow_aim": (7.2, 12.4),
            "magic_cast": (8.8, 15.6),
            "shoulder_right": (8.0, 14.5),
            "shoulder_left": (8.0, 14.5),
            "stealth": (9.0, 16.0),
            "boss": (18.0, 34.0),
            "tutorial": (14.0, 28.0),
            "swim": (12.0, 24.0),
            "flight": (14.5, 24.5),
            "mounted": (16.0, 34.0),
            "mounted_horse": (16.0, 32.0),
            "mounted_carriage": (18.0, 36.0),
            "mounted_ship": (19.0, 40.0),
            "dialog": (8.5, 16.0),
            "cinematic": (18.0, 40.0),
        }
        min_default, max_default = defaults.get(token, defaults["exploration"])
        min_dist = self._coerce_float(cfg.get("min_dist", min_default), min_default, 4.0, 80.0)
        max_dist = self._coerce_float(cfg.get("max_dist", max_default), max_default, min_dist, 90.0)
        return min_dist, max_dist

    def _movement_speed_ratio(self, profile_name):
        cs = getattr(self.app, "char_state", None)
        velocity = getattr(cs, "velocity", None) if cs else None
        if velocity is None:
            return 0.0
        try:
            vx = float(getattr(velocity, "x", 0.0) or 0.0)
            vy = float(getattr(velocity, "y", 0.0) or 0.0)
        except Exception:
            return 0.0
        speed = math.sqrt((vx * vx) + (vy * vy))
        player = self._player()
        walk_speed = self._coerce_float(getattr(player, "walk_speed", 5.0), 5.0, 0.1, 40.0)
        run_speed = self._coerce_float(getattr(player, "run_speed", 9.0), 9.0, 0.1, 50.0)
        flight_speed = self._coerce_float(getattr(player, "flight_speed", 15.0), 15.0, 0.1, 80.0)
        token = str(profile_name or "").strip().lower()
        if token in {"aim", "bow_aim"}:
            ref = max(4.0, walk_speed * 0.9)
        elif token in {"combat", "boss", "magic_cast"}:
            ref = max(5.5, run_speed * 0.92)
        elif token.startswith("mounted"):
            ref = max(8.5, run_speed * 1.35)
        elif token == "flight":
            ref = max(10.0, flight_speed * 0.8)
        elif token == "swim":
            ref = max(3.5, walk_speed * 0.85)
        else:
            ref = max(6.0, run_speed)
        return max(0.0, min(1.25, speed / max(0.1, ref)))

    def _movement_trailing_adjustments(self, profile_name, cfg):
        token = str(profile_name or "").strip().lower()
        ratio = self._movement_speed_ratio(token)
        if ratio <= 0.001:
            return {"dist_delta": 0.0, "pitch_delta": 0.0, "target_z_delta": 0.0}
        tuning = {
            "exploration": (2.1, -1.25, 0.10),
            "combat": (1.25, -0.90, 0.08),
            "aim": (0.35, -0.25, 0.02),
            "bow_aim": (0.20, -0.15, 0.02),
            "magic_cast": (0.55, -0.38, 0.03),
            "boss": (1.65, -0.75, 0.10),
            "tutorial": (1.25, -0.85, 0.08),
            "swim": (0.95, -0.55, 0.05),
            "flight": (1.35, -0.85, 0.14),
            "mounted": (2.80, -1.15, 0.16),
            "mounted_horse": (2.50, -1.00, 0.14),
            "mounted_carriage": (3.00, -1.05, 0.18),
            "mounted_ship": (3.40, -0.80, 0.20),
            "dialog": (0.0, 0.0, 0.0),
            "cinematic": (0.0, 0.0, 0.0),
        }
        dist_scale, pitch_scale, z_scale = tuning.get(token, tuning["exploration"])
        return {
            "dist_delta": dist_scale * ratio,
            "pitch_delta": pitch_scale * ratio,
            "target_z_delta": z_scale * ratio,
        }

    # ──────────────────────────────────────────────────────────────
    # Profile override
    # ──────────────────────────────────────────────────────────────

    def _resolve_shot_priority(self, shot_name, explicit=None):
        if explicit is not None:
            return self._coerce_int(explicit, 50, -999, 999)
        token = str(shot_name or "shot").strip().lower()
        return int(self._shot_priority_cfg.get(token, self._shot_priority_cfg.get("shot", 50)))

    def _can_take_shot(self, priority, owner):
        now = self._now()
        if not isinstance(self._cutscene, dict) or now >= float(self._cutscene.get("end_t", 0.0)):
            return True
        if str(owner or "").strip().lower() == str(self._active_shot_owner or "").strip().lower():
            return True
        return int(priority) >= int(self._active_shot_priority)

    def _resolve_profile_priority(self, profile_name, explicit=None):
        if explicit is not None:
            return self._coerce_int(explicit, 40, -999, 999)
        token = str(profile_name or "").strip().lower()
        return int(self._profile_priority_cfg.get(token, self._profile_priority_cfg.get("exploration", 40)))

    def _can_set_profile(self, priority, owner):
        now = self._now()
        if not self._forced_profile or now >= float(self._forced_until):
            return True
        if str(owner or "").strip().lower() == str(self._profile_override_owner or "").strip().lower():
            return True
        return int(priority) >= int(self._profile_override_priority)

    def _bind_event_bus(self):
        bus = getattr(self.app, "event_bus", None)
        if not bus or not hasattr(bus, "subscribe"):
            return
        try:
            bus.subscribe("camera.shot.request", self._on_event_camera_shot, priority=70)
            bus.subscribe("camera.sequence.request", self._on_event_camera_sequence, priority=72)
            bus.subscribe("camera.profile.request", self._on_event_camera_profile, priority=65)
            bus.subscribe("camera.impact", self._on_event_camera_impact, priority=75)
        except Exception as exc:
            logger.debug(f"[CameraDirector] Event bus bind failed: {exc}")

    def _on_event_camera_shot(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.play_camera_shot(
            name=payload.get("name", "shot"),
            duration=payload.get("duration", 1.2),
            profile=payload.get("profile", "exploration"),
            side=payload.get("side", 0.0),
            yaw_bias_deg=payload.get("yaw_bias_deg", 0.0),
            priority=payload.get("priority"),
            owner=payload.get("owner", "event_bus"),
        )

    def _on_event_camera_sequence(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.play_camera_sequence(
            name=payload.get("name", "location_reveal"),
            shots=payload.get("shots"),
            priority=payload.get("priority"),
            owner=payload.get("owner", "event_bus"),
        )

    def _on_event_camera_profile(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.set_profile(
            profile_name=payload.get("profile", "exploration"),
            hold_seconds=payload.get("hold_seconds", 0.0),
            priority=payload.get("priority"),
            owner=payload.get("owner", "event_bus"),
        )

    def _on_event_camera_impact(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.emit_impact(
            kind=payload.get("kind", "hit"),
            intensity=payload.get("intensity", 1.0),
            direction_deg=payload.get("direction_deg", 0.0),
        )

    def set_profile(self, profile_name, hold_seconds=0.0, priority=None, owner="runtime"):
        token = str(profile_name or "").strip().lower()
        if token not in self._profiles:
            return False
        prio = self._resolve_profile_priority(token, explicit=priority)
        if not self._can_set_profile(prio, owner):
            return False
        self._forced_profile = token
        self._forced_until = self._now() + max(0.0, float(hold_seconds))
        self._profile_override_priority = int(prio)
        self._profile_override_owner = str(owner or "runtime")
        return True

    def clear_profile_override(self):
        self._forced_profile = None
        self._forced_until = 0.0
        self._profile_override_priority = -999
        self._profile_override_owner = ""

    def _current_location_token(self):
        world = getattr(self.app, "world", None)
        token = str(getattr(world, "active_location", "") or "").strip().lower()
        if token:
            return token
        return str(getattr(self.app, "_test_location_raw", "") or "").strip().lower()

    def _match_location_rule(self, location_token):
        token = str(location_token or "").strip().lower()
        if not token:
            return None
        direct = self._locations.get(token)
        if isinstance(direct, dict):
            return dict(direct)
        for key, rule in self._locations.items():
            if key and key in token:
                return dict(rule)
        return None

    def _update_location_rule(self):
        location_token = self._current_location_token()
        if self._debug_disable_camera_context_rules:
            self._last_location_token = location_token
            return None
        rule = self._match_location_rule(location_token)
        location_changed = location_token != self._last_location_token
        self._last_location_token = location_token
        if location_changed and isinstance(rule, dict):
            owner = str(rule.get("owner") or f"location:{location_token}" or "location")
            priority = self._coerce_int(rule.get("priority", 78), 78, -999, 999)
            enter_sequence = str(rule.get("enter_sequence", "") or "").strip().lower()
            enter_shot = str(rule.get("enter_shot", "") or "").strip().lower()
            if enter_sequence:
                self.play_camera_sequence(
                    name=enter_sequence,
                    priority=priority,
                    owner=owner,
                )
            elif enter_shot:
                shot_cfg = self._shots.get(enter_shot)
                if isinstance(shot_cfg, dict):
                    self.play_camera_shot(
                        name=enter_shot,
                        duration=shot_cfg.get("duration", 1.1),
                        profile=shot_cfg.get("profile", "cinematic"),
                        side=shot_cfg.get("side", 0.0),
                        yaw_bias_deg=shot_cfg.get("yaw_bias_deg", 0.0),
                        priority=priority,
                        owner=owner,
                    )
        return rule

    def _match_zone_rule(self, zone, location_token, center):
        if not isinstance(zone, dict):
            return False
        expected_location = str(zone.get("location", "") or "").strip().lower()
        if expected_location and expected_location != str(location_token or "").strip().lower():
            return False
        if center is None:
            return False
        zone_center = zone.get("center")
        if not isinstance(zone_center, tuple):
            return False
        radius = max(0.1, float(zone.get("radius", 4.0) or 4.0))
        dx = float(center.x) - float(zone_center[0])
        dy = float(center.y) - float(zone_center[1])
        dz = float(center.z) - float(zone_center[2])
        return ((dx * dx) + (dy * dy) + (dz * dz)) <= (radius * radius)

    def _update_zone_rule(self):
        location_token = self._current_location_token()
        if self._debug_disable_camera_context_rules:
            self._zone_inside = {}
            return None
        center, _base_z = self._player_center()
        active = []
        for zone in self._zones:
            zone_id = str(zone.get("id", "") or "").strip().lower()
            inside = self._match_zone_rule(zone, location_token, center)
            prev_inside = bool(self._zone_inside.get(zone_id, False))
            self._zone_inside[zone_id] = bool(inside)
            if inside:
                active.append(zone)
                if not prev_inside:
                    owner = str(zone.get("owner") or f"zone:{zone_id}")
                    priority = self._coerce_int(zone.get("priority", 80), 80, -999, 999)
                    enter_sequence = str(zone.get("enter_sequence", "") or "").strip().lower()
                    enter_shot = str(zone.get("enter_shot", "") or "").strip().lower()
                    if enter_sequence:
                        self.play_camera_sequence(
                            name=enter_sequence,
                            priority=priority,
                            owner=owner,
                        )
                    elif enter_shot:
                        shot_cfg = self._shots.get(enter_shot)
                        if isinstance(shot_cfg, dict):
                            self.play_camera_shot(
                                name=enter_shot,
                                duration=shot_cfg.get("duration", 1.1),
                                profile=shot_cfg.get("profile", "cinematic"),
                                side=shot_cfg.get("side", 0.0),
                                yaw_bias_deg=shot_cfg.get("yaw_bias_deg", 0.0),
                                priority=priority,
                                owner=owner,
                            )
                    logger.info(
                        f"[CameraDirector] Zone enter '{zone_id}' -> profile='{zone.get('profile', '')}' "
                        f"location='{location_token or '-'}'"
                    )
        if not active:
            return None
        active.sort(key=lambda row: int(row.get("priority", 0)), reverse=True)
        return dict(active[0])

    def get_screen_effect_state(self):
        return dict(self._screen_state)

    def emit_impact(self, kind="hit", intensity=1.0, direction_deg=0.0):
        tag = str(kind or "hit").strip().lower()
        i = max(0.0, min(2.0, float(intensity or 0.0)))
        d = math.radians(float(direction_deg or 0.0))
        sign = 1.0 if math.sin(d) >= 0.0 else -1.0

        if tag in {"parry", "block"}:
            self._impulse_pitch += 0.45 * i
            self._impulse_yaw += 0.35 * i * sign
            self._impulse_roll += 0.18 * i * sign
            self._impulse_shake += 0.06 * i
        elif tag in {"critical", "heavy", "hard_fall"}:
            self._impulse_pitch += 2.20 * i
            self._impulse_yaw += 1.55 * i * sign
            self._impulse_roll += 0.95 * i * sign
            self._impulse_shake += 0.26 * i
        elif tag in {"near_miss"}:
            self._impulse_pitch += 0.28 * i
            self._impulse_yaw += 0.95 * i * sign
            self._impulse_roll += 0.55 * i * sign
            self._impulse_shake += 0.08 * i
        else:
            self._impulse_pitch += 1.05 * i
            self._impulse_yaw += 0.72 * i * sign
            self._impulse_roll += 0.42 * i * sign
            self._impulse_shake += 0.12 * i

    # ──────────────────────────────────────────────────────────────
    # Shot playback
    # ──────────────────────────────────────────────────────────────

    def is_cutscene_active(self):
        if not isinstance(self._cutscene, dict):
            return False
        return self._now() < float(self._cutscene.get("end_t", 0.0))

    def _activate_camera_shot_for_anchor(
        self,
        *,
        center,
        base_z,
        yaw_deg,
        name,
        duration,
        profile,
        side,
        yaw_bias_deg,
        priority,
        owner,
        look_target=None,
        partner_target=None,
        framing=None,
    ):
        if center is None:
            return False
        try:
            center = Vec3(float(center.x), float(center.y), float(center.z))
            base_z = float(base_z)
        except Exception:
            return False

        profile_name = str(profile or "boss").strip().lower()
        cfg = dict(self._profiles.get(profile_name, self._profiles.get("boss", self._profiles["exploration"])))
        duration = max(0.3, min(8.0, float(duration)))

        from_pos, from_look = self._camera_start_pose(center, base_z, cfg)
        if self.is_cutscene_active():
            try:
                active_pose = self._cutscene_transform(from_pos, from_look)
            except Exception:
                active_pose = None
            if isinstance(active_pose, tuple) and len(active_pose) >= 2:
                active_pos, active_look = active_pose[0], active_pose[1]
                if self._point3_is_finite(active_pos) and self._point3_is_finite(active_look):
                    from_pos = LPoint3(float(active_pos.x), float(active_pos.y), float(active_pos.z))
                    from_look = LPoint3(float(active_look.x), float(active_look.y), float(active_look.z))

        yaw_rad = math.radians(float(yaw_deg or 0.0) + float(yaw_bias_deg))
        pitch_rad = math.radians(float(cfg.get("pitch", -12.0)))
        to_pos, _to_look = self._camera_pos(
            center=center,
            base_z=base_z,
            yaw_rad=yaw_rad,
            pitch_rad=pitch_rad,
            dist=float(cfg.get("dist", 22.0)),
            side=float(side if side is not None else cfg.get("side", 0.0)),
            target_z=float(cfg.get("target_z", 1.8)),
        )
        if self._point3_is_finite(look_target):
            to_look = LPoint3(float(look_target.x), float(look_target.y), float(look_target.z))
        else:
            to_look = self._look_target(
                center=center,
                base_z=base_z,
                yaw_rad=yaw_rad,
                target_z=float(cfg.get("target_z", 1.8)),
                look_side=float(cfg.get("look_side", 0.0)),
                look_ahead=float(cfg.get("look_ahead", 0.0)),
            )
        if str(framing or "").strip().lower() == "dialog_pair":
            preferred_side = float(side if side is not None else cfg.get("side", 0.0))
            pair_pos = self._compose_dialog_pair_pose(
                base_z=base_z,
                look_target=to_look,
                partner_target=partner_target,
                side=preferred_side,
            )
            alt_pair_pos = None
            if abs(preferred_side) > 0.01:
                alt_pair_pos = self._compose_dialog_pair_pose(
                    base_z=base_z,
                    look_target=to_look,
                    partner_target=partner_target,
                    side=-preferred_side,
                )

            chosen_pair_pos = pair_pos
            if self._point3_is_finite(from_pos) and self._point3_is_finite(pair_pos) and self._point3_is_finite(alt_pair_pos):
                requested_dist_sq = (pair_pos - from_pos).length_squared()
                alt_dist_sq = (alt_pair_pos - from_pos).length_squared()
                if alt_dist_sq + 1e-4 < requested_dist_sq:
                    chosen_pair_pos = alt_pair_pos
            elif not self._point3_is_finite(pair_pos) and self._point3_is_finite(alt_pair_pos):
                chosen_pair_pos = alt_pair_pos

            if self._point3_is_finite(chosen_pair_pos):
                staged_z = float(chosen_pair_pos.z)
                if self._point3_is_finite(from_pos):
                    staged_z = max(
                        staged_z,
                        min(float(from_pos.z) - 0.35, float(chosen_pair_pos.z) + 2.0),
                    )
                to_pos = LPoint3(
                    float(chosen_pair_pos.x),
                    float(chosen_pair_pos.y),
                    staged_z,
                )

        now = self._now()
        self._cutscene = {
            "name": str(name or "shot"),
            "start_t": now,
            "end_t": now + duration,
            "from_pos": from_pos,
            "to_pos": to_pos,
            "from_look": LPoint3(from_look.x, from_look.y, from_look.z),
            "to_look": LPoint3(to_look.x, to_look.y, to_look.z),
            "priority": int(priority),
            "owner": str(owner or "runtime"),
        }
        self._active_shot_priority = int(priority)
        self._active_shot_owner = str(owner or "runtime")
        self._blend_back = None
        logger.info(
            f"[CameraDirector] Shot '{name}' -> {duration:.2f}s "
            f"params=[from={from_pos}, to={to_pos}, look={to_look}]"
        )
        return True

    def _activate_camera_shot(
        self,
        *,
        name,
        duration,
        profile,
        side,
        yaw_bias_deg,
        priority,
        owner,
    ):
        center, base_z = self._player_center()
        return self._activate_camera_shot_for_anchor(
            center=center,
            base_z=base_z,
            yaw_deg=float(getattr(self.app, "_cam_yaw", 0.0) or 0.0),
            name=name,
            duration=duration,
            profile=profile,
            side=side,
            yaw_bias_deg=yaw_bias_deg,
            priority=priority,
            owner=owner,
        )

    def _legacy_play_camera_shot(
        self,
        name="shot",
        duration=1.35,
        profile="boss",
        side=0.0,
        yaw_bias_deg=0.0,
        priority=None,
        owner="runtime",
    ):
        center, base_z = self._player_center()
        if center is None:
            return False

        shot_name = str(name or "shot").strip().lower()
        prio = self._resolve_shot_priority(shot_name, explicit=priority)
        if not self._can_take_shot(prio, owner):
            return False

        profile_name = str(profile or "boss").strip().lower()
        cfg = dict(self._profiles.get(profile_name, self._profiles.get("boss", self._profiles["exploration"])))
        duration = max(0.3, min(8.0, float(duration)))

        from_pos  = self.app.camera.getPos(self.app.render)
        from_look = center + Vec3(0.0, 0.0, float(cfg.get("target_z", 1.8)))

        yaw_rad   = math.radians(float(getattr(self.app, "_cam_yaw", 0.0) or 0.0) + float(yaw_bias_deg))
        pitch_rad = math.radians(float(cfg.get("pitch", -12.0)))
        to_pos, to_look = self._camera_pos(
            center=center,
            base_z=base_z,
            yaw_rad=yaw_rad,
            pitch_rad=pitch_rad,
            dist=float(cfg.get("dist", 22.0)),
            side=float(side if side is not None else cfg.get("side", 0.0)),
            target_z=float(cfg.get("target_z", 1.8)),
        )

        now = self._now()
        self._cutscene = {
            "name":      str(name or "shot"),
            "start_t":   now,
            "end_t":     now + duration,
            "from_pos":  from_pos,
            "to_pos":    to_pos,
            "from_look": LPoint3(from_look.x, from_look.y, from_look.z),
            "to_look":   LPoint3(to_look.x,   to_look.y,  to_look.z),
            "priority":  int(prio),
            "owner":     str(owner or "runtime"),
        }
        self._active_shot_priority = int(prio)
        self._active_shot_owner = str(owner or "runtime")
        self._blend_back = None  # reset blend-back snapshot
        logger.info(f"[CameraDirector] Shot '{name}' → {duration:.2f}s params=[from={from_pos}, to={to_pos}, look={to_look}]")
        return True

    def play_dialog_shot(self, duration=None):
        cfg = self._shots.get("dialog", self._default_shots["dialog"])
        return self.play_camera_shot(
            name="dialog",
            duration=duration if duration is not None else cfg.get("duration", 1.35),
            profile=cfg.get("profile", "dialog"),
            side=cfg.get("side", 2.3),
            yaw_bias_deg=cfg.get("yaw_bias_deg", 8.0),
            priority=self._resolve_shot_priority("dialog", None),
            owner="dialog",
        )

    def play_boss_intro_shot(self, duration=None):
        cfg = self._shots.get("boss_intro", self._default_shots["boss_intro"])
        return self.play_camera_shot(
            name="boss_intro",
            duration=duration if duration is not None else cfg.get("duration", 1.80),
            profile=cfg.get("profile", "cinematic"),
            side=cfg.get("side", 5.5),
            yaw_bias_deg=cfg.get("yaw_bias_deg", 22.0),
            priority=self._resolve_shot_priority("boss_intro", None),
            owner="boss_intro",
        )

    def play_camera_shot(
        self,
        name="shot",
        duration=1.35,
        profile="boss",
        side=0.0,
        yaw_bias_deg=0.0,
        priority=None,
        owner="runtime",
    ):
        shot_name = str(name or "shot").strip().lower()
        prio = self._resolve_shot_priority(shot_name, explicit=priority)
        if not self._can_take_shot(prio, owner):
            return False
        if self._sequence_state and str(self._sequence_state.get("owner", "")).strip().lower() != str(owner or "").strip().lower():
            self._sequence_state = None
        return self._activate_camera_shot(
            name=name,
            duration=duration,
            profile=profile,
            side=side,
            yaw_bias_deg=yaw_bias_deg,
            priority=prio,
            owner=owner,
        )

    def play_anchor_camera_shot(
        self,
        *,
        center,
        base_z,
        yaw_deg,
        look_target=None,
        partner_target=None,
        framing=None,
        name="shot",
        duration=1.35,
        profile="boss",
        side=0.0,
        yaw_bias_deg=0.0,
        priority=None,
        owner="runtime",
    ):
        shot_name = str(name or "shot").strip().lower()
        prio = self._resolve_shot_priority(shot_name, explicit=priority)
        if not self._can_take_shot(prio, owner):
            return False
        if self._sequence_state and str(self._sequence_state.get("owner", "")).strip().lower() != str(owner or "").strip().lower():
            self._sequence_state = None
        return self._activate_camera_shot_for_anchor(
            center=center,
            base_z=base_z,
            yaw_deg=yaw_deg,
            look_target=look_target,
            partner_target=partner_target,
            framing=framing,
            name=name,
            duration=duration,
            profile=profile,
            side=side,
            yaw_bias_deg=yaw_bias_deg,
            priority=prio,
            owner=owner,
        )

    def _start_sequence_step(self):
        sequence = self._sequence_state
        if not isinstance(sequence, dict):
            return False
        shots = sequence.get("shots")
        if not isinstance(shots, list):
            self._sequence_state = None
            return False
        next_index = int(sequence.get("index", -1)) + 1
        if next_index >= len(shots):
            self._sequence_state = None
            return False
        sequence["index"] = next_index
        step = dict(shots[next_index] or {})
        return self._activate_camera_shot(
            name=step.get("name", f"{sequence.get('name', 'sequence')}_{next_index + 1}"),
            duration=step.get("duration", 1.0),
            profile=step.get("profile", "exploration"),
            side=step.get("side", 0.0),
            yaw_bias_deg=step.get("yaw_bias_deg", 0.0),
            priority=step.get("priority", sequence.get("priority", 50)),
            owner=step.get("owner", sequence.get("owner", "runtime")),
        )

    def play_camera_sequence(self, name="location_reveal", shots=None, priority=None, owner="runtime"):
        seq_name = str(name or "sequence").strip().lower()
        steps = []
        if isinstance(shots, list):
            for idx, row in enumerate(shots):
                steps.append(self._merge_sequence_step(row, default_name=f"{seq_name}_{idx + 1}"))
        else:
            raw = self._sequences.get(seq_name)
            if isinstance(raw, list):
                steps = [dict(row) for row in raw]
        if not steps:
            return False
        prio = self._resolve_shot_priority(seq_name, explicit=priority)
        if not self._can_take_shot(prio, owner):
            return False
        self._sequence_state = {
            "name": seq_name,
            "shots": steps,
            "index": -1,
            "priority": int(prio),
            "owner": str(owner or "runtime"),
        }
        return bool(self._start_sequence_step())

    # ──────────────────────────────────────────────────────────────
    # Cutscene transform with easing + blend-back
    # ──────────────────────────────────────────────────────────────

    def _legacy_cutscene_transform(self, gameplay_pos, gameplay_look):
        """Return (pos, look) for the current cutscene frame, or None if shot over."""
        shot = self._cutscene
        if not isinstance(shot, dict):
            return None

        now     = self._now()
        start_t = float(shot.get("start_t", now))
        end_t   = float(shot.get("end_t",   now))
        span    = max(1e-4, end_t - start_t)

        if now >= end_t:
            self._cutscene = None
            self._blend_back = None
            self._active_shot_priority = -999
            self._active_shot_owner = ""
            return None

        raw_t = max(0.0, min(1.0, (now - start_t) / span))

        # Determine blend-back window
        blend_start = 1.0 - self.BLEND_BACK_FRACTION
        if raw_t >= blend_start:
            # Blend-back phase: ease out from cinematic → gameplay camera
            if self._blend_back is None:
                # Snapshot the cinematic pos at the blend-back pivot
                pivot_t = _smootherstep(blend_start)
                fp = shot["from_pos"]; tp = shot["to_pos"]
                fl = shot["from_look"]; tl = shot["to_look"]
                self._blend_back = (
                    _lerp3(fp, tp, pivot_t),
                    _lerp3(fl, tl, pivot_t),
                )
            blend_from_pos,  blend_from_look  = self._blend_back
            blend_raw = (raw_t - blend_start) / max(1e-4, 1.0 - blend_start)
            blend_t = _ease_out_quart(blend_raw)
            pos  = _lerp3(blend_from_pos,  gameplay_pos,  blend_t)
            look = _lerp3(blend_from_look, gameplay_look, blend_t)
        else:
            # Main shot phase: ease in-out
            t = _smootherstep(raw_t)
            fp = shot["from_pos"]; tp = shot["to_pos"]
            fl = shot["from_look"]; tl = shot["to_look"]
            pos  = _lerp3(fp, tp, t)
            look = _lerp3(fl, tl, t)

        # Diagnostic Heartbeat (every 0.5s)
        if now - self._last_shot_log_t >= 0.5:
            self._last_shot_log_t = now
            name = str(shot.get("name", "unknown"))
            logger.info(f"[CameraHeartbeat] Shot='{name}' Progress={raw_t*100:.1f}% Pos={pos}")

        return pos, look

    # ──────────────────────────────────────────────────────────────
    # Main update (called every frame from app)
    # ──────────────────────────────────────────────────────────────

    def _cutscene_transform(self, gameplay_pos, gameplay_look):
        """Return (pos, look) for the current cutscene frame, or None if shot over."""
        while True:
            shot = self._cutscene
            if not isinstance(shot, dict):
                return None

            now = self._now()
            start_t = float(shot.get("start_t", now))
            end_t = float(shot.get("end_t", now))
            span = max(1e-4, end_t - start_t)

            if now >= end_t:
                self._cutscene = None
                self._blend_back = None
                if self._start_sequence_step():
                    continue
                self._active_shot_priority = -999
                self._active_shot_owner = ""
                return None
            break

        raw_t = max(0.0, min(1.0, (now - start_t) / span))
        blend_start = 1.0 - self.BLEND_BACK_FRACTION
        if raw_t >= blend_start:
            if self._blend_back is None:
                pivot_t = _smootherstep(blend_start)
                fp = shot["from_pos"]
                tp = shot["to_pos"]
                fl = shot["from_look"]
                tl = shot["to_look"]
                self._blend_back = (
                    _lerp3(fp, tp, pivot_t),
                    _lerp3(fl, tl, pivot_t),
                )
            blend_from_pos, blend_from_look = self._blend_back
            blend_raw = (raw_t - blend_start) / max(1e-4, 1.0 - blend_start)
            blend_t = _ease_out_quart(blend_raw)
            pos = _lerp3(blend_from_pos, gameplay_pos, blend_t)
            look = _lerp3(blend_from_look, gameplay_look, blend_t)
        else:
            t = _smootherstep(raw_t)
            fp = shot["from_pos"]
            tp = shot["to_pos"]
            fl = shot["from_look"]
            tl = shot["to_look"]
            pos = _lerp3(fp, tp, t)
            look = _lerp3(fl, tl, t)

        if now - self._last_shot_log_t >= 0.5:
            self._last_shot_log_t = now
            name = str(shot.get("name", "unknown"))
            logger.info(f"[CameraHeartbeat] Shot='{name}' Progress={raw_t*100:.1f}% Pos={pos}")

        return pos, look

    def update(self, dt, manual_look=False):
        dt = max(0.0, float(dt or 0.0))
        now = self._now()

        state_name = self._state_name()
        if state_name != self._last_state_name:
            if state_name == "dialog":
                self.play_dialog_shot(duration=None)
            self._last_state_name = state_name

        boss_now = self._is_boss_context()
        if (self._auto_boss_intro and boss_now and (not self._boss_prev)
                and now >= self._boss_intro_cooldown_until):
            if self.play_boss_intro_shot(duration=None):
                self._boss_intro_cooldown_until = now + self._boss_intro_cooldown_sec
        self._boss_prev = boss_now

        if self._forced_profile and now > self._forced_until:
            self.clear_profile_override()

        location_rule = self._update_location_rule()
        zone_rule = self._update_zone_rule()
        location_profile = ""
        zone_profile = ""
        if isinstance(location_rule, dict):
            location_profile = str(location_rule.get("profile", "") or "").strip().lower()
        if isinstance(zone_rule, dict):
            zone_profile = str(zone_rule.get("profile", "") or "").strip().lower()
        target_profile = self._forced_profile or zone_profile or location_profile or self._resolve_profile()
        if target_profile not in self._profiles:
            target_profile = "exploration"
        if target_profile != self._last_logged_profile:
            profile_source = "runtime"
            if self._forced_profile:
                profile_source = f"override:{self._profile_override_owner or 'runtime'}"
            elif zone_profile:
                profile_source = f"zone:{str(zone_rule.get('id', '') or '').strip()}" if isinstance(zone_rule, dict) else "zone"
            elif location_profile:
                profile_source = f"location:{self._last_location_token or 'unknown'}"
            logger.info(
                f"[CameraDirector] Profile -> '{target_profile}' source='{profile_source}'"
            )
            self._last_logged_profile = target_profile
        self._active_profile = target_profile

        combat_focus = self._combat_focus_state()
        cfg = self._augment_combat_profile(target_profile, self._profiles[target_profile], combat_focus)
        motion = self._movement_trailing_adjustments(target_profile, cfg)
        if any(abs(float(motion.get(key, 0.0) or 0.0)) > 1e-6 for key in ("dist_delta", "pitch_delta", "target_z_delta")):
            cfg = dict(cfg)
            cfg["dist"] = self._coerce_float(
                float(cfg.get("dist", 22.0)) + float(motion.get("dist_delta", 0.0) or 0.0),
                22.0,
                4.0,
                80.0,
            )
            cfg["pitch"] = self._coerce_float(
                float(cfg.get("pitch", -20.0)) + float(motion.get("pitch_delta", 0.0) or 0.0),
                -20.0,
                -85.0,
                85.0,
            )
            cfg["target_z"] = self._coerce_float(
                float(cfg.get("target_z", 1.8)) + float(motion.get("target_z_delta", 0.0) or 0.0),
                1.8,
                0.0,
                8.0,
            )
        gain = max(0.0, min(1.0, float(cfg.get("smooth", 8.0)) * dt))
        zoom_offset = self._coerce_float(
            getattr(self.app, "_cam_zoom_offset", 0.0),
            0.0,
            -18.0,
            28.0,
        )
        min_dist, max_dist = self._profile_zoom_bounds(target_profile, cfg)
        target_dist = self._coerce_float(float(cfg.get("dist", 22.0)) + zoom_offset, 22.0, min_dist, max_dist)
        self.app._cam_dist = self._approach(
            float(getattr(self.app, "_cam_dist", 22.0) or 22.0),
            target_dist,
            gain,
        )
        if not bool(manual_look):
            self.app._cam_pitch = self._approach(
                float(getattr(self.app, "_cam_pitch", -20.0) or -20.0),
                float(cfg.get("pitch", -20.0)),
                gain,
            )
        decay = max(0.0, min(1.0, dt * 6.8))
        self._impulse_pitch = self._approach(self._impulse_pitch, 0.0, decay)
        self._impulse_yaw = self._approach(self._impulse_yaw, 0.0, decay)
        self._impulse_roll = self._approach(self._impulse_roll, 0.0, decay)
        self._impulse_shake = self._approach(self._impulse_shake, 0.0, max(0.0, min(1.0, dt * 8.2)))

        player = self._player()
        fear = 0.0
        hp_ratio = 1.0
        if player and hasattr(player, "brain"):
            try:
                fear = float(getattr(player.brain, "mental", {}).get("fear", 0.0) or 0.0)
            except Exception:
                fear = 0.0
        cs = getattr(player, "cs", None) if player else None
        if cs and hasattr(cs, "health") and hasattr(cs, "maxHealth"):
            try:
                hp_ratio = float(cs.health) / max(1.0, float(cs.maxHealth))
            except Exception:
                hp_ratio = 1.0
        self._screen_state["fear_tint"] = max(0.0, min(1.0, fear))
        self._screen_state["damage_tint"] = max(0.0, min(1.0, 1.0 - hp_ratio))
        combat_heat = 0.0
        if isinstance(combat_focus, dict) and bool(combat_focus.get("active", False)):
            if target_profile == "combat":
                combat_heat += 0.06
            elif target_profile == "aim":
                combat_heat += 0.04
            elif target_profile == "boss":
                combat_heat += 0.08
            if bool(combat_focus.get("locked", False)):
                combat_heat += 0.05
            combat_heat += min(0.12, max(0.0, float(combat_focus.get("amount", 0.0) or 0.0)) / 180.0)
        self._screen_state["combat_heat"] = max(0.0, min(1.0, combat_heat))
        self._screen_state["vignette_boost"] = max(
            0.0,
            min(1.0, (fear * 0.55) + ((1.0 - hp_ratio) * 0.65) + self._impulse_shake + combat_heat),
        )
        return dict(cfg)

    # ──────────────────────────────────────────────────────────────
    # Final transform resolver (used by app camera update)
    # ──────────────────────────────────────────────────────────────

    def resolve_transform(self, center, base_z, yaw_rad, pitch_rad, profile_cfg):
        cfg = profile_cfg if isinstance(profile_cfg, dict) else self._profiles.get(self._active_profile, {})
        active_profile = str(getattr(self, "_active_profile", "") or "").strip().lower()
        dist     = float(getattr(self.app, "_cam_dist", cfg.get("dist",     22.0)))
        target_z = float(cfg.get("target_z", 1.8))
        side     = float(cfg.get("side",     0.0))
        look_side = float(cfg.get("look_side", 0.0) or 0.0)
        look_ahead = float(cfg.get("look_ahead", 0.0) or 0.0)
        motion_yaw = self._movement_heading_rad(active_profile)
        if active_profile == "flight" and motion_yaw is not None:
            yaw_rad = float(motion_yaw)
        else:
            yaw_rad = float(yaw_rad)
        yaw_rad = yaw_rad + math.radians(self._impulse_yaw)
        pitch_rad = float(pitch_rad) + math.radians(self._impulse_pitch)
        side = side + (self._impulse_roll * 0.12)
        if self._impulse_shake > 1e-4:
            target_z += random.uniform(-1.0, 1.0) * self._impulse_shake * 0.12

        # Compute the "gameplay" position first (used for blend-back target)
        gameplay_pos, _gameplay_focus = self._camera_pos(
            center, base_z, yaw_rad, pitch_rad, dist, side, target_z
        )
        gameplay_look = self._look_target(
            center=center,
            base_z=base_z,
            yaw_rad=yaw_rad,
            target_z=target_z,
            look_side=look_side,
            look_ahead=look_ahead,
        )

        # Check if a cinematic shot is active
        shot = self._cutscene_transform(gameplay_pos, gameplay_look)
        if shot:
            final_pos, final_look = shot[0], shot[1]
        else:
            final_pos, final_look = gameplay_pos, gameplay_look

        # Final safety check before returning to app
        try:
            if any(math.isnan(float(v)) or math.isinf(float(v)) for v in [final_pos.x, final_pos.y, final_pos.z, final_look.x, final_look.y, final_look.z]):
                return LPoint3(0,0,0), LPoint3(0,0,1)
            if (final_pos - final_look).length_squared() < 1e-6:
                final_pos = final_pos + Vec3(0, 0.01, 0)
        except Exception:
            return LPoint3(0,0,0), LPoint3(0,0,1)
        self._last_resolved_pos = LPoint3(float(final_pos.x), float(final_pos.y), float(final_pos.z))
        self._last_resolved_look = LPoint3(float(final_look.x), float(final_look.y), float(final_look.z))
        return final_pos, final_look
