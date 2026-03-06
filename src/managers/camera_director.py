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
    return LPoint3(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t,
    )


class CameraDirector:
    # Fraction of shot duration to start blending back to gameplay cam.
    # e.g. 0.15 = last 15 % of the shot eases back gracefully.
    BLEND_BACK_FRACTION = 0.18

    def __init__(self, app):
        self.app = app
        self._default_profiles = {
            "exploration": {"dist": 22.0, "pitch": -20.0, "target_z": 1.8,  "side": 0.0, "smooth": 7.5},
            "combat":      {"dist": 17.5, "pitch": -15.0, "target_z": 1.9,  "side": 0.0, "smooth": 10.0},
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
            "combat": 60,
            "exploration": 40,
        }

        self._last_state_name = ""
        self._boss_prev = False
        self._boss_intro_cooldown_until = 0.0
        self._impulse_pitch = 0.0
        self._impulse_yaw = 0.0
        self._impulse_roll = 0.0
        self._impulse_shake = 0.0
        self._screen_state = {
            "vignette_boost": 0.0,
            "fear_tint": 0.0,
            "damage_tint": 0.0,
        }
        self._load_config()
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
            f"{len(self._shots)} shots, auto_boss_intro={self._auto_boss_intro}"
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
        return Vec3(float(pos.x), float(pos.y), float(pos.z)), float(pos.z)

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
        getter = getattr(player, "get_hud_combat_event", None)
        if callable(getter):
            try:
                if getter():
                    return True
            except Exception:
                pass
        anim_state = str(getattr(player, "_anim_state", "") or "").strip().lower()
        return anim_state in {
            "attacking", "attack_light", "attack_heavy", "attack_finisher",
            "dodging", "dash_forward", "dash_back",
            "casting", "cast_prepare", "cast_release",
            "blocking", "block_hold", "block_perfect",
        }

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
        if kind == "boat":
            kind = "ship"
        return kind

    def _is_in_water(self):
        player = self._player()
        cs = getattr(player, "cs", None) if player else None
        return bool(cs and getattr(cs, "inWater", False))

    def _is_flying(self):
        player = self._player()
        return bool(player and getattr(player, "_is_flying", False))

    def _resolve_profile(self):
        state_name = self._state_name()
        if state_name in {"main_menu", "loading", "paused", "inventory"}:
            return "exploration"
        if state_name == "dialog":
            return "dialog"
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
        return "exploration"

    # ──────────────────────────────────────────────────────────────
    # Math helpers
    # ──────────────────────────────────────────────────────────────

    def _approach(self, current, target, gain):
        if abs(target - current) < 1e-4:
            return float(target)
        return float(current + ((target - current) * gain))

    def _camera_pos(self, center, base_z, yaw_rad, pitch_rad, dist, side, target_z, min_floor=0.5):
        cx = center.x + (dist * math.sin(yaw_rad) * math.cos(pitch_rad)) + (side * math.cos(yaw_rad))
        cy = center.y - (dist * math.cos(yaw_rad) * math.cos(pitch_rad)) + (side * math.sin(yaw_rad))
        cz = base_z + target_z + (dist * math.sin(-pitch_rad))
        if cz < base_z + min_floor:
            cz = base_z + min_floor
        look_at = LPoint3(center.x, center.y, base_z + target_z)
        return LPoint3(cx, cy, cz), look_at

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
        logger.info(f"[CameraDirector] Shot '{name}' → {duration:.2f}s")
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

    # ──────────────────────────────────────────────────────────────
    # Cutscene transform with easing + blend-back
    # ──────────────────────────────────────────────────────────────

    def _cutscene_transform(self, gameplay_pos, gameplay_look):
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

        return pos, look

    # ──────────────────────────────────────────────────────────────
    # Main update (called every frame from app)
    # ──────────────────────────────────────────────────────────────

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

        target_profile = self._forced_profile or self._resolve_profile()
        if target_profile not in self._profiles:
            target_profile = "exploration"
        self._active_profile = target_profile

        cfg = self._profiles[target_profile]
        gain = max(0.0, min(1.0, float(cfg.get("smooth", 8.0)) * dt))
        self.app._cam_dist = self._approach(
            float(getattr(self.app, "_cam_dist", 22.0) or 22.0),
            float(cfg.get("dist", 22.0)),
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
        self._screen_state["vignette_boost"] = max(
            0.0,
            min(1.0, (fear * 0.55) + ((1.0 - hp_ratio) * 0.65) + self._impulse_shake),
        )
        return dict(cfg)

    # ──────────────────────────────────────────────────────────────
    # Final transform resolver (used by app camera update)
    # ──────────────────────────────────────────────────────────────

    def resolve_transform(self, center, base_z, yaw_rad, pitch_rad, profile_cfg):
        cfg = profile_cfg if isinstance(profile_cfg, dict) else self._profiles.get(self._active_profile, {})
        dist     = float(getattr(self.app, "_cam_dist", cfg.get("dist",     22.0)))
        target_z = float(cfg.get("target_z", 1.8))
        side     = float(cfg.get("side",     0.0))
        yaw_rad = float(yaw_rad) + math.radians(self._impulse_yaw)
        pitch_rad = float(pitch_rad) + math.radians(self._impulse_pitch)
        side = side + (self._impulse_roll * 0.12)
        if self._impulse_shake > 1e-4:
            target_z += random.uniform(-1.0, 1.0) * self._impulse_shake * 0.12

        # Compute the "gameplay" position first (used for blend-back target)
        gameplay_pos, gameplay_look = self._camera_pos(
            center, base_z, yaw_rad, pitch_rad, dist, side, target_z
        )

        # Check if a cinematic shot is active
        shot = self._cutscene_transform(gameplay_pos, gameplay_look)
        if shot:
            return shot[0], shot[1]

        return gameplay_pos, gameplay_look
