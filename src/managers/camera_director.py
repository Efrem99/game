"""Context-aware camera director with lightweight cutscene support."""

import math

from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import LPoint3, Vec3

from utils.logger import logger


class CameraDirector:
    def __init__(self, app):
        self.app = app
        self._default_profiles = {
            "exploration": {"dist": 22.0, "pitch": -20.0, "target_z": 1.8, "side": 0.0, "smooth": 7.5},
            "combat": {"dist": 17.5, "pitch": -15.0, "target_z": 1.9, "side": 0.0, "smooth": 10.0},
            "boss": {"dist": 29.0, "pitch": -12.0, "target_z": 2.4, "side": 0.0, "smooth": 5.8},
            "tutorial": {"dist": 20.0, "pitch": -18.0, "target_z": 1.9, "side": 0.0, "smooth": 8.5},
            "swim": {"dist": 18.5, "pitch": -10.0, "target_z": 1.4, "side": 0.0, "smooth": 7.2},
            "flight": {"dist": 30.0, "pitch": -26.0, "target_z": 2.6, "side": 0.0, "smooth": 5.3},
            "mounted": {"dist": 24.0, "pitch": -17.0, "target_z": 2.2, "side": 0.0, "smooth": 6.8},
            "dialog": {"dist": 11.5, "pitch": -8.0, "target_z": 1.85, "side": 2.0, "smooth": 9.0},
        }
        self._profiles = {k: dict(v) for k, v in self._default_profiles.items()}
        self._default_shots = {
            "dialog": {"duration": 1.0, "profile": "dialog", "side": 2.3, "yaw_bias_deg": 8.0},
            "boss_intro": {"duration": 1.45, "profile": "boss", "side": 5.2, "yaw_bias_deg": 18.0},
        }
        self._shots = {k: dict(v) for k, v in self._default_shots.items()}
        self._auto_boss_intro = True
        self._boss_intro_cooldown_sec = 9.0
        self._active_profile = "exploration"
        self._forced_profile = None
        self._forced_until = 0.0
        self._cutscene = None
        self._last_state_name = ""
        self._boss_prev = False
        self._boss_intro_cooldown_until = 0.0
        self._load_config()

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

    def _merge_profile(self, base, payload):
        if not isinstance(payload, dict):
            return dict(base)
        out = dict(base)
        out["dist"] = self._coerce_float(payload.get("dist", out.get("dist", 22.0)), out.get("dist", 22.0), 4.0, 80.0)
        out["pitch"] = self._coerce_float(payload.get("pitch", out.get("pitch", -20.0)), out.get("pitch", -20.0), -85.0, 85.0)
        out["target_z"] = self._coerce_float(payload.get("target_z", out.get("target_z", 1.8)), out.get("target_z", 1.8), 0.0, 8.0)
        out["side"] = self._coerce_float(payload.get("side", out.get("side", 0.0)), out.get("side", 0.0), -20.0, 20.0)
        out["smooth"] = self._coerce_float(payload.get("smooth", out.get("smooth", 7.5)), out.get("smooth", 7.5), 0.1, 30.0)
        return out

    def _merge_shot(self, base, payload):
        if not isinstance(payload, dict):
            return dict(base)
        out = dict(base)
        out["duration"] = self._coerce_float(payload.get("duration", out.get("duration", 1.0)), out.get("duration", 1.0), 0.2, 10.0)
        out["side"] = self._coerce_float(payload.get("side", out.get("side", 0.0)), out.get("side", 0.0), -30.0, 30.0)
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
                self._boss_intro_cooldown_sec,
                0.0,
                60.0,
            )

        logger.info(
            f"[CameraDirector] Loaded camera profiles: {len(self._profiles)} "
            f"shots: {len(self._shots)} auto_boss_intro={self._auto_boss_intro}"
        )

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
        return anim_state in {"attacking", "dodging", "casting", "blocking"}

    def _is_tutorial_context(self):
        tutorial = getattr(self.app, "movement_tutorial", None)
        return bool(tutorial and getattr(tutorial, "enabled", False))

    def _is_mounted(self):
        vm = getattr(self.app, "vehicle_mgr", None)
        return bool(vm and getattr(vm, "is_mounted", False))

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
            return "mounted"
        if self._is_flying():
            return "flight"
        if self._is_in_water():
            return "swim"
        if self._is_tutorial_context():
            return "tutorial"
        return "exploration"

    def _approach(self, current, target, gain):
        if abs(target - current) < 1e-4:
            return float(target)
        return float(current + ((target - current) * gain))

    def _camera_pos(
        self,
        center,
        base_z,
        yaw_rad,
        pitch_rad,
        dist,
        side,
        target_z,
        min_floor=0.5,
    ):
        cx = center.x + (dist * math.sin(yaw_rad) * math.cos(pitch_rad)) + (side * math.cos(yaw_rad))
        cy = center.y - (dist * math.cos(yaw_rad) * math.cos(pitch_rad)) + (side * math.sin(yaw_rad))
        cz = base_z + target_z + (dist * math.sin(-pitch_rad))
        if cz < base_z + min_floor:
            cz = base_z + min_floor
        look_at = LPoint3(center.x, center.y, base_z + target_z)
        return LPoint3(cx, cy, cz), look_at

    def set_profile(self, profile_name, hold_seconds=0.0):
        token = str(profile_name or "").strip().lower()
        if token not in self._profiles:
            return False
        self._forced_profile = token
        self._forced_until = self._now() + max(0.0, float(hold_seconds))
        return True

    def clear_profile_override(self):
        self._forced_profile = None
        self._forced_until = 0.0

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
    ):
        center, base_z = self._player_center()
        if center is None:
            return False
        profile_name = str(profile or "boss").strip().lower()
        cfg = dict(self._profiles.get(profile_name, self._profiles["boss"]))
        duration = max(0.2, min(6.0, float(duration)))

        from_pos = self.app.camera.getPos(self.app.render)
        from_look = center + Vec3(0.0, 0.0, 1.8)

        yaw_rad = math.radians(float(getattr(self.app, "_cam_yaw", 0.0) or 0.0) + float(yaw_bias_deg))
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
            "name": str(name or "shot"),
            "start_t": now,
            "end_t": now + duration,
            "from_pos": from_pos,
            "to_pos": to_pos,
            "from_look": LPoint3(from_look.x, from_look.y, from_look.z),
            "to_look": LPoint3(to_look.x, to_look.y, to_look.z),
        }
        logger.info(f"[CameraDirector] Shot '{name}' started for {duration:.2f}s")
        return True

    def play_dialog_shot(self, duration=1.0):
        cfg = self._shots.get("dialog", self._default_shots["dialog"])
        return self.play_camera_shot(
            name="dialog",
            duration=duration if duration is not None else cfg.get("duration", 1.0),
            profile=cfg.get("profile", "dialog"),
            side=cfg.get("side", 2.3),
            yaw_bias_deg=cfg.get("yaw_bias_deg", 8.0),
        )

    def play_boss_intro_shot(self, duration=1.6):
        cfg = self._shots.get("boss_intro", self._default_shots["boss_intro"])
        return self.play_camera_shot(
            name="boss_intro",
            duration=duration if duration is not None else cfg.get("duration", 1.45),
            profile=cfg.get("profile", "boss"),
            side=cfg.get("side", 5.2),
            yaw_bias_deg=cfg.get("yaw_bias_deg", 18.0),
        )

    def _cutscene_transform(self):
        if not self.is_cutscene_active():
            self._cutscene = None
            return None
        shot = self._cutscene
        now = self._now()
        start_t = float(shot.get("start_t", now))
        end_t = float(shot.get("end_t", now))
        span = max(1e-4, end_t - start_t)
        raw_t = max(0.0, min(1.0, (now - start_t) / span))
        t = raw_t * raw_t * (3.0 - (2.0 * raw_t))

        fp = shot["from_pos"]
        tp = shot["to_pos"]
        fl = shot["from_look"]
        tl = shot["to_look"]
        pos = LPoint3(
            fp.x + ((tp.x - fp.x) * t),
            fp.y + ((tp.y - fp.y) * t),
            fp.z + ((tp.z - fp.z) * t),
        )
        look = LPoint3(
            fl.x + ((tl.x - fl.x) * t),
            fl.y + ((tl.y - fl.y) * t),
            fl.z + ((tl.z - fl.z) * t),
        )
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
        if self._auto_boss_intro and boss_now and (not self._boss_prev) and now >= self._boss_intro_cooldown_until:
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
        return dict(cfg)

    def resolve_transform(self, center, base_z, yaw_rad, pitch_rad, profile_cfg):
        shot = self._cutscene_transform()
        if shot:
            return shot[0], shot[1]

        cfg = profile_cfg if isinstance(profile_cfg, dict) else self._profiles.get(self._active_profile, {})
        dist = float(getattr(self.app, "_cam_dist", cfg.get("dist", 22.0)))
        target_z = float(cfg.get("target_z", 1.8))
        side = float(cfg.get("side", 0.0))
        return self._camera_pos(center, base_z, yaw_rad, pitch_rad, dist, side, target_z)
