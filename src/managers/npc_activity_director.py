"""NPC activity orchestration for location-aware micro-scenes via EventBus."""

import math
import os
import random

from direct.showbase.ShowBaseGlobal import globalClock


def _clamp(value, lo, hi):
    try:
        f = float(value)
    except Exception:
        f = float(lo)
    return max(float(lo), min(float(hi), f))


def _norm_token(value):
    token = str(value or "").strip().lower().replace("\\", "/")
    while "//" in token:
        token = token.replace("//", "/")
    return token


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return bool(default)


class NPCActivityDirector:
    def __init__(self, app):
        self.app = app
        self._rng = random.Random(9481)
        self._world_state = {}

        cfg = getattr(getattr(self.app, "data_mgr", None), "sound_config", {}) or {}
        npc_cfg = cfg.get("npc_activity", {}) if isinstance(cfg, dict) else {}
        self._voices_path = str(cfg.get("voices_path", "data/audio/voices") or "data/audio/voices").strip().replace("\\", "/")

        self._max_distance = _clamp(npc_cfg.get("max_distance", 36.0), 8.0, 120.0)
        self._global_cooldown = _clamp(npc_cfg.get("global_cooldown", 0.35), 0.0, 6.0)
        self._npc_cooldown = _clamp(npc_cfg.get("npc_cooldown", 2.4), 0.2, 18.0)
        self._voice_cooldown = _clamp(npc_cfg.get("voice_cooldown", 10.0), 1.0, 60.0)
        self._camera_cooldown = _clamp(npc_cfg.get("camera_cooldown", 5.0), 0.5, 60.0)
        self._base_sfx_volume = _clamp(npc_cfg.get("base_sfx_volume", 0.38), 0.05, 1.0)

        self._default_activity_sfx = {
            "patrol": ["npc_patrol_step", "footstep_stone", "footstep_wood"],
            "inspect": ["npc_patrol_step", "ui_hover"],
            "escort": ["npc_patrol_step", "footstep_stone"],
            "haul": ["npc_crate_move", "item_pickup", "footstep_wood"],
            "work": ["npc_work_hammer", "item_pickup", "footstep_wood"],
            "repair": ["npc_repair_tool", "item_pickup", "ui_hover"],
            "talk": ["npc_talk_murmur", "ui_hover"],
            "rest": ["ui_hover"],
            "shelter": ["footstep_wood"],
            "panic": ["npc_alarm", "enemy_hit", "sword_hit"],
            "idle": ["footstep_wood"],
        }
        self._activity_sfx = self._build_activity_sfx(npc_cfg.get("activity_sfx", {}))
        self._profiles = self._build_profiles(npc_cfg.get("profiles", {}))
        self._layout = self._load_world_layout()
        self._scene_anchors = self._build_scene_anchors(self._layout)
        self._scene_anchor_radius = _clamp(npc_cfg.get("scene_anchor_radius", 10.0), 2.0, 50.0)
        self._scene_anchor_bonus = _clamp(npc_cfg.get("scene_anchor_bonus", 0.14), 0.0, 0.45)
        self._debug_overlay = _as_bool(npc_cfg.get("debug_overlay", True), True)

        self._last_global_at = -9999.0
        self._last_camera_at = -9999.0
        self._last_npc_at = {}
        self._last_voice_at = {}

        self._bind_event_bus()

    def _build_activity_sfx(self, payload):
        out = {k: list(v) for k, v in self._default_activity_sfx.items()}
        if not isinstance(payload, dict):
            return out
        for key, value in payload.items():
            activity = _norm_token(key)
            if not activity:
                continue
            rows = value if isinstance(value, list) else [value]
            candidates = []
            for row in rows:
                token = _norm_token(row)
                if token:
                    candidates.append(token)
            if candidates:
                out[activity] = candidates
        return out

    def _base_profile(self):
        return {
            "intensity_mul": 1.0,
            "sfx_volume_mul": 1.0,
            "voice_chance_mul": 1.0,
            "camera_chance_mul": 1.0,
            "route_hold_mul": 1.0,
            "voice_enabled": True,
            "camera_enabled": True,
            "route_enabled": True,
            "camera_profile": "cinematic",
            "camera_side_min": 1.5,
            "camera_side_max": 2.6,
            "camera_yaw_min": 8.0,
            "camera_yaw_max": 22.0,
            "override_ambient": "",
            "music_on_panic": "combat",
            "ambient_by_story": {
                "storm_shelter": "wind",
            },
            "activity_sfx": {k: list(v) for k, v in self._activity_sfx.items()},
        }

    def _merge_profile(self, base, payload):
        out = dict(base)
        out["activity_sfx"] = {k: list(v) for k, v in base.get("activity_sfx", {}).items()}
        out["ambient_by_story"] = dict(base.get("ambient_by_story", {}))
        if not isinstance(payload, dict):
            return out

        out["intensity_mul"] = _clamp(payload.get("intensity_mul", out["intensity_mul"]), 0.4, 2.0)
        out["sfx_volume_mul"] = _clamp(payload.get("sfx_volume_mul", out["sfx_volume_mul"]), 0.2, 2.0)
        out["voice_chance_mul"] = _clamp(payload.get("voice_chance_mul", out["voice_chance_mul"]), 0.0, 2.0)
        out["camera_chance_mul"] = _clamp(payload.get("camera_chance_mul", out["camera_chance_mul"]), 0.0, 2.0)
        out["route_hold_mul"] = _clamp(payload.get("route_hold_mul", out["route_hold_mul"]), 0.4, 3.0)

        out["voice_enabled"] = _as_bool(payload.get("voice_enabled", out["voice_enabled"]), out["voice_enabled"])
        out["camera_enabled"] = _as_bool(payload.get("camera_enabled", out["camera_enabled"]), out["camera_enabled"])
        out["route_enabled"] = _as_bool(payload.get("route_enabled", out["route_enabled"]), out["route_enabled"])
        out["camera_profile"] = str(payload.get("camera_profile", out["camera_profile"]) or out["camera_profile"]).strip().lower()

        out["camera_side_min"] = _clamp(payload.get("camera_side_min", out["camera_side_min"]), -8.0, 8.0)
        out["camera_side_max"] = _clamp(payload.get("camera_side_max", out["camera_side_max"]), -8.0, 8.0)
        if out["camera_side_max"] < out["camera_side_min"]:
            out["camera_side_max"] = out["camera_side_min"]
        out["camera_yaw_min"] = _clamp(payload.get("camera_yaw_min", out["camera_yaw_min"]), -120.0, 120.0)
        out["camera_yaw_max"] = _clamp(payload.get("camera_yaw_max", out["camera_yaw_max"]), -120.0, 120.0)
        if out["camera_yaw_max"] < out["camera_yaw_min"]:
            out["camera_yaw_max"] = out["camera_yaw_min"]

        out["override_ambient"] = _norm_token(payload.get("override_ambient", out["override_ambient"]))
        out["music_on_panic"] = _norm_token(payload.get("music_on_panic", out["music_on_panic"]))

        amb_story = payload.get("ambient_by_story", {})
        if isinstance(amb_story, dict):
            for key, value in amb_story.items():
                story = _norm_token(key)
                ambient = _norm_token(value)
                if story and ambient:
                    out["ambient_by_story"][story] = ambient

        sfx_map = payload.get("activity_sfx", {})
        if isinstance(sfx_map, dict):
            for key, value in sfx_map.items():
                activity = _norm_token(key)
                if not activity:
                    continue
                rows = value if isinstance(value, list) else [value]
                candidates = []
                for row in rows:
                    token = _norm_token(row)
                    if token:
                        candidates.append(token)
                if candidates:
                    out["activity_sfx"][activity] = candidates
        return out

    def _build_profiles(self, payload):
        base = self._base_profile()
        profiles = {"default": dict(base)}
        if not isinstance(payload, dict):
            return profiles
        if isinstance(payload.get("default"), dict):
            profiles["default"] = self._merge_profile(base, payload.get("default", {}))
        for key, row in payload.items():
            name = _norm_token(key)
            if not name or name == "default":
                continue
            profiles[name] = self._merge_profile(profiles["default"], row)
        return profiles

    def _load_world_layout(self):
        dm = getattr(self.app, "data_mgr", None)
        getter = getattr(dm, "get_world_layout", None)
        if callable(getter):
            try:
                payload = getter()
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        payload = getattr(dm, "world_layout", {}) if dm else {}
        return payload if isinstance(payload, dict) else {}

    def _coerce_xyz(self, value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                x = float(value[0]); y = float(value[1])
                z = float(value[2]) if len(value) >= 3 else 0.0
                return x, y, z
            except Exception:
                return None
        return None

    def _build_scene_anchors(self, layout):
        if not isinstance(layout, dict):
            return []
        anchors = []

        def _add(anchor_id, pos, activities, profile, radius=8.0, ambient=""):
            xyz = self._coerce_xyz(pos)
            if not xyz:
                return
            tokens = []
            if isinstance(activities, list):
                for row in activities:
                    token = _norm_token(row)
                    if token:
                        tokens.append(token)
            if not tokens:
                tokens = ["idle"]
            anchors.append(
                {
                    "id": str(anchor_id),
                    "x": float(xyz[0]),
                    "y": float(xyz[1]),
                    "z": float(xyz[2]),
                    "radius": _clamp(radius, 2.0, 28.0),
                    "profile": _norm_token(profile) or "default",
                    "activities": set(tokens),
                    "ambient": _norm_token(ambient),
                }
            )

        port = layout.get("port", {}) if isinstance(layout.get("port"), dict) else {}
        dock_segments = port.get("dock_segments", [])
        if isinstance(dock_segments, list):
            for idx, row in enumerate(dock_segments):
                if not isinstance(row, dict):
                    continue
                _add(
                    f"port_dock_{idx}",
                    row.get("pos"),
                    ["patrol", "haul", "inspect", "escort"],
                    "docks",
                    radius=10.0,
                    ambient="docks",
                )
        market_stalls = port.get("market_stalls", [])
        if isinstance(market_stalls, list):
            for idx, row in enumerate(market_stalls):
                pos = row.get("pos") if isinstance(row, dict) else row
                _add(
                    f"port_stall_{idx}",
                    pos,
                    ["talk", "work", "haul", "repair"],
                    "docks",
                    radius=8.5,
                    ambient="docks",
                )

        castle = layout.get("castle", {}) if isinstance(layout.get("castle"), dict) else {}
        inner = castle.get("inner_buildings", [])
        if isinstance(inner, list):
            for idx, row in enumerate(inner):
                if not isinstance(row, dict):
                    continue
                b_type = _norm_token(row.get("type", "hall"))
                acts = ["talk", "rest"]
                if b_type in {"smith", "workshop"}:
                    acts = ["work", "repair", "haul"]
                elif b_type in {"barracks"}:
                    acts = ["patrol", "inspect", "escort"]
                elif b_type in {"chapel"}:
                    acts = ["rest", "talk", "shelter"]
                _add(
                    f"castle_{b_type}_{idx}",
                    row.get("pos"),
                    acts,
                    "castle",
                    radius=9.0,
                    ambient="castle_courtyard",
                )

        routes = layout.get("routes", {}) if isinstance(layout.get("routes"), dict) else {}
        serp = routes.get("serpentine_path", [])
        if isinstance(serp, list):
            for idx, pos in enumerate(serp):
                if idx % 2 != 0:
                    continue
                _add(
                    f"serpentine_{idx}",
                    pos,
                    ["patrol", "escort", "inspect"],
                    "forest",
                    radius=7.5,
                    ambient="forest",
                )
        return anchors

    def _nearest_anchor(self, npc_pos, activity, profile_name):
        xyz = self._coerce_xyz(npc_pos)
        if not xyz or not self._scene_anchors:
            return None, None
        px, py, _ = xyz
        best = None
        best_dist = None
        for anchor in self._scene_anchors:
            if not isinstance(anchor, dict):
                continue
            anchor_profile = _norm_token(anchor.get("profile", "default"))
            if anchor_profile not in {"default", _norm_token(profile_name)}:
                continue
            acts = anchor.get("activities", set())
            if isinstance(acts, set) and (activity not in acts):
                continue
            dx = float(anchor.get("x", 0.0)) - px
            dy = float(anchor.get("y", 0.0)) - py
            dist = math.sqrt((dx * dx) + (dy * dy))
            radius = float(anchor.get("radius", self._scene_anchor_radius) or self._scene_anchor_radius)
            if dist > radius:
                continue
            if best is None or dist < best_dist:
                best = anchor
                best_dist = dist
        return best, best_dist

    def _bind_event_bus(self):
        bus = getattr(self.app, "event_bus", None)
        if not bus or not hasattr(bus, "subscribe"):
            return
        try:
            bus.subscribe("npc.activity.changed", self._on_npc_activity, priority=74)
            bus.subscribe("world.state.changed", self._on_world_state, priority=52)
        except Exception:
            pass

    def _now(self):
        try:
            return float(globalClock.getFrameTime())
        except Exception:
            return 0.0

    def _on_world_state(self, event_name, payload):
        _ = event_name
        if isinstance(payload, dict):
            self._world_state = dict(payload)

    def _world_location_key(self):
        world = getattr(self.app, "world", None)
        token = _norm_token(getattr(world, "active_location", "") if world else "")
        if token:
            return token
        return _norm_token(self._world_state.get("location", ""))

    def _resolve_profile_name(self):
        key = self._world_location_key()
        if any(mark in key for mark in ("dock", "port", "harbor", "coast", "shore", "sea")):
            return "docks"
        if any(mark in key for mark in ("castle", "keep", "fort", "citadel", "wall")):
            return "castle"
        if any(mark in key for mark in ("forest", "grove", "wood", "wild")):
            return "forest"
        return "default"

    def _resolve_profile(self):
        profile_name = self._resolve_profile_name()
        profile = self._profiles.get(profile_name)
        if not isinstance(profile, dict):
            profile_name = "default"
            profile = self._profiles.get("default", self._base_profile())
        return profile_name, profile

    def _on_npc_activity(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return

        npc_id = _norm_token(payload.get("npc_id", ""))
        if not npc_id:
            return
        activity = _norm_token(payload.get("activity", "idle")) or "idle"
        trigger = _norm_token(payload.get("trigger", "live_step")) or "live_step"
        story = _norm_token(payload.get("story", ""))
        role = _norm_token(payload.get("role", ""))
        live = bool(payload.get("live", False))
        distance = payload.get("distance")
        npc_pos = payload.get("npc_pos")
        try:
            distance = float(distance) if distance is not None else None
        except Exception:
            distance = None

        if distance is not None and distance > self._max_distance:
            return

        profile_name, profile = self._resolve_profile()
        now = self._now()
        if (now - self._last_global_at) < self._global_cooldown:
            return
        last_npc = float(self._last_npc_at.get(npc_id, -9999.0))
        if trigger != "live_enter" and (now - last_npc) < self._npc_cooldown:
            return

        anchor, anchor_dist = self._nearest_anchor(npc_pos, activity, profile_name)
        intensity = self._scene_intensity(activity, trigger, live, distance, profile, anchor_dist=anchor_dist)
        if trigger == "live_enter" and self._debug_overlay:
            self._emit_event(
                "npc.micro_scene.started",
                {
                    "npc_id": npc_id,
                    "activity": activity,
                    "story": story,
                    "profile": profile_name,
                    "intensity": float(intensity),
                    "anchor_id": str(anchor.get("id", "")) if isinstance(anchor, dict) else "",
                },
            )
        self._emit_activity_sfx(activity, trigger, intensity, profile)
        self._emit_activity_voice(npc_id, role, activity, trigger, story, intensity, now, profile)
        self._emit_activity_camera(activity, trigger, story, intensity, now, profile)
        self._emit_activity_route_override(activity, story, intensity, profile, anchor=anchor)

        self._last_global_at = now
        self._last_npc_at[npc_id] = now

    def _scene_intensity(self, activity, trigger, live, distance, profile, anchor_dist=None):
        val = 0.35
        if trigger == "live_enter":
            val += 0.20
        if trigger == "live_step":
            val += 0.08
        if activity in {"panic", "inspect", "escort"}:
            val += 0.18
        if activity in {"talk", "rest"}:
            val -= 0.06
        if not live:
            val -= 0.08
        if distance is not None:
            t = 1.0 - min(1.0, max(0.0, distance / max(1.0, self._max_distance)))
            val += 0.18 * t
        fear_bias = float(self._world_state.get("fear_bias", 0.0) or 0.0)
        val += min(0.2, max(0.0, fear_bias))
        if anchor_dist is not None:
            norm = 1.0 - min(1.0, max(0.0, float(anchor_dist) / max(1.0, self._scene_anchor_radius)))
            val += float(self._scene_anchor_bonus) * norm
        val *= float(profile.get("intensity_mul", 1.0) or 1.0)
        return _clamp(val, 0.12, 1.0)

    def _emit_event(self, event_name, payload):
        bus = getattr(self.app, "event_bus", None)
        if not bus or not hasattr(bus, "emit"):
            return
        try:
            bus.emit(event_name, payload, immediate=False)
        except Exception:
            pass

    def _pick_activity_sfx(self, activity, profile):
        profile_map = profile.get("activity_sfx", {}) if isinstance(profile, dict) else {}
        candidates = profile_map.get(activity) if isinstance(profile_map, dict) else None
        if not isinstance(candidates, list) or not candidates:
            candidates = self._activity_sfx.get(activity) or self._activity_sfx.get("idle", [])
        if not isinstance(candidates, list) or not candidates:
            return ""
        return str(self._rng.choice(candidates) or "").strip().lower()

    def _emit_activity_sfx(self, activity, trigger, intensity, profile):
        key = self._pick_activity_sfx(activity, profile)
        if not key:
            return
        trig_mul = 1.0
        if trigger == "background_resume":
            trig_mul = 0.84
        elif trigger == "live_enter":
            trig_mul = 1.08
        profile_mul = float(profile.get("sfx_volume_mul", 1.0) or 1.0)
        vol = _clamp(self._base_sfx_volume * float(intensity) * trig_mul * profile_mul, 0.06, 0.85)
        rate = _clamp(1.0 + self._rng.uniform(-0.08, 0.08), 0.82, 1.18)
        self._emit_event(
            "audio.sfx.play",
            {
                "key": key,
                "volume": vol,
                "rate": rate,
            },
        )

    def _role_activity_voice_stems(self, role, activity, story):
        stems = []
        if "guard" in role:
            if activity == "panic":
                stems.extend(["guard_city/trouble", "guard_city/accept_patrol"])
            elif activity in {"patrol", "inspect", "escort"}:
                stems.extend(["guard_city/passing_through", "guard_city/castle_directions", "guard_city/directions"])
            else:
                stems.append("guard_city/start")
        if "merchant" in role or "trader" in role:
            if activity in {"talk", "work", "repair", "haul"}:
                stems.extend(["merchant_general/browsing", "merchant_general/open_shop", "merchant/start"])
            else:
                stems.append("merchant_general/start")
        if story == "storm_shelter":
            stems.extend(["guard_city/trouble", "merchant_general/farewell"])
        return [f"{self._voices_path}/{_norm_token(item)}" for item in stems if _norm_token(item)]

    def _voice_candidates(self, npc_id, role, activity, story):
        candidates = [
            f"{self._voices_path}/{npc_id}/{activity}",
            f"{self._voices_path}/{npc_id}/start",
            f"{self._voices_path}/{role}/{activity}" if role else "",
            f"{self._voices_path}/{role}/start" if role else "",
        ]
        candidates.extend(self._role_activity_voice_stems(role, activity, story))
        out = []
        for item in candidates:
            token = _norm_token(item)
            if token and token not in out:
                out.append(token)
        return out

    def _resolve_existing_voice_path(self, npc_id, role, activity, story):
        for stem in self._voice_candidates(npc_id, role, activity, story):
            token = _norm_token(stem)
            if not token:
                continue
            for ext in (".ogg", ".mp3", ".wav"):
                path = f"{token}{ext}"
                if os.path.exists(path):
                    return path
        return ""

    def _emit_activity_voice(self, npc_id, role, activity, trigger, story, intensity, now, profile):
        if not bool(profile.get("voice_enabled", True)):
            return
        if trigger not in {"live_enter", "live_step"}:
            return
        if activity not in {"talk", "inspect", "escort", "panic", "work", "repair"}:
            return

        last = float(self._last_voice_at.get(npc_id, -9999.0))
        if (now - last) < self._voice_cooldown:
            return

        chance = 0.20 + (0.15 * float(intensity))
        if trigger == "live_enter":
            chance += 0.10
        chance *= float(profile.get("voice_chance_mul", 1.0) or 1.0)
        if self._rng.random() > min(0.76, max(0.0, chance)):
            return

        path = self._resolve_existing_voice_path(npc_id, role, activity, story)
        if not path:
            return
        rate = _clamp(0.95 + self._rng.uniform(-0.05, 0.07), 0.82, 1.16)
        vol = _clamp(0.50 + (0.32 * float(intensity)), 0.2, 0.95)
        self._emit_event(
            "audio.voice.play",
            {
                "path": path,
                "volume": vol,
                "rate": rate,
            },
        )
        self._last_voice_at[npc_id] = now

    def _emit_activity_camera(self, activity, trigger, story, intensity, now, profile):
        if not bool(profile.get("camera_enabled", True)):
            return
        if (now - self._last_camera_at) < self._camera_cooldown:
            return
        if activity not in {"panic", "inspect"} and story not in {"storm_shelter"}:
            return

        cam_mul = float(profile.get("camera_chance_mul", 1.0) or 1.0)
        chance = (0.45 if activity == "panic" else 0.24) * cam_mul
        if trigger == "live_enter":
            chance += 0.10
        if self._rng.random() > min(0.92, max(0.0, chance)):
            return

        if activity == "panic":
            self._emit_event(
                "camera.impact",
                {
                    "kind": "near_miss" if trigger == "live_enter" else "hit",
                    "intensity": _clamp(0.32 + (0.62 * float(intensity)), 0.2, 1.1),
                    "direction_deg": self._rng.uniform(70.0, 140.0),
                },
            )
            self._last_camera_at = now
            return

        if trigger == "live_enter":
            side_min = float(profile.get("camera_side_min", 1.5) or 1.5)
            side_max = float(profile.get("camera_side_max", max(side_min, 2.6)) or max(side_min, 2.6))
            yaw_min = float(profile.get("camera_yaw_min", 8.0) or 8.0)
            yaw_max = float(profile.get("camera_yaw_max", max(yaw_min, 22.0)) or max(yaw_min, 22.0))
            self._emit_event(
                "camera.shot.request",
                {
                    "name": "location",
                    "duration": 0.85,
                    "profile": str(profile.get("camera_profile", "cinematic") or "cinematic"),
                    "side": self._rng.uniform(side_min, side_max),
                    "yaw_bias_deg": self._rng.uniform(yaw_min, yaw_max),
                    "priority": 56,
                    "owner": "npc_activity",
                },
            )
            self._last_camera_at = now

    def _emit_activity_route_override(self, activity, story, intensity, profile, anchor=None):
        if not bool(profile.get("route_enabled", True)):
            return
        if activity not in {"panic"} and story not in {"storm_shelter"}:
            return

        story_key = _norm_token(story)
        ambient_map = profile.get("ambient_by_story", {}) if isinstance(profile, dict) else {}
        ambient_key = _norm_token(ambient_map.get(story_key, "")) if isinstance(ambient_map, dict) else ""
        if not ambient_key and isinstance(anchor, dict):
            ambient_key = _norm_token(anchor.get("ambient", ""))
        if not ambient_key:
            ambient_key = _norm_token(profile.get("override_ambient", "")) or ("docks" if activity != "panic" else "wind")

        music_key = ""
        if activity == "panic":
            music_key = _norm_token(profile.get("music_on_panic", "combat")) or "combat"
        hold_mul = float(profile.get("route_hold_mul", 1.0) or 1.0)
        hold_seconds = _clamp((1.3 + (1.6 * float(intensity))) * hold_mul, 1.0, 4.8)
        self._emit_event(
            "audio.route.override",
            {
                "music_key": music_key if music_key else None,
                "ambient_key": ambient_key if ambient_key else None,
                "priority": 78 if activity == "panic" else 72,
                "hold_seconds": hold_seconds,
                "owner": "npc_activity",
            },
        )

    def update(self, dt):
        _ = dt
        # Keep per-NPC cooldown maps bounded in long sessions.
        now = self._now()
        if len(self._last_npc_at) <= 240 and len(self._last_voice_at) <= 240:
            return
        cutoff = now - 180.0
        self._last_npc_at = {k: v for k, v in self._last_npc_at.items() if float(v) >= cutoff}
        self._last_voice_at = {k: v for k, v in self._last_voice_at.items() if float(v) >= cutoff}
