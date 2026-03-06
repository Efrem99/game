"""Sky and weather interpolation manager.

Keeps lighting/fog/cloud state in sync with time-of-day and weather presets.
"""

import math
import os

from panda3d.core import CardMaker, Fog, TransparencyAttrib, Vec4


class SkyManager:
    def __init__(self, app):
        self.app = app
        cfg = getattr(getattr(app, "data_mgr", None), "sky_config", {}) or {}
        self.cfg = cfg if isinstance(cfg, dict) else {}

        self.time_presets = self._as_dict(self.cfg.get("time_presets", {}))
        self.weather_presets = self._as_dict(self.cfg.get("weather_presets", {}))
        self.auto_cycle = bool(self.cfg.get("auto_cycle", False))
        self.cycle_duration = max(30.0, self._as_float(self.cfg.get("cycle_duration", 600.0), 600.0))
        self.auto_weather = bool(self.cfg.get("auto_weather", True))
        self.weather_hold_min = max(8.0, self._as_float(self.cfg.get("weather_hold_min", 85.0), 85.0))
        self.weather_hold_max = max(self.weather_hold_min, self._as_float(self.cfg.get("weather_hold_max", 180.0), 180.0))
        self._weather_timer = self.weather_hold_min

        tr = self._as_dict(self.cfg.get("transitions", {}))
        self.time_transition_speed = max(0.01, self._as_float(tr.get("time_transition_speed", 0.08), 0.08))
        self.weather_transition_speed = max(0.05, self._as_float(tr.get("weather_transition_speed", 1.6), 1.6))

        default_time = str(self.cfg.get("default_time", "noon") or "noon").strip().lower()
        default_weather = str(self.cfg.get("default_weather", "clear") or "clear").strip().lower()

        self.time_key = default_time if default_time in self.time_presets else "noon"
        self.weather_key = default_weather if default_weather in self.weather_presets else "clear"

        self.time_value = self._preset_time_value(self.time_key)
        self.time_target = self.time_value
        self.weather_blend = self._weather_value(self.weather_key, "cloud_coverage", 0.2)
        self.weather_visibility = self._weather_value(self.weather_key, "visibility", 1.0)
        self._last_phase = None
        self._last_weather = None
        self.world_state = {
            "time": float(self.time_value),
            "hour": 12.0,
            "phase": "day",
            "is_night": False,
            "weather": self.weather_key,
            "visibility": max(0.1, min(1.0, float(self.weather_visibility))),
            "cloud_coverage": max(0.0, min(1.0, float(self.weather_blend))),
            "sun_strength": 1.0,
            "ambient_strength": 1.0,
            "fear_bias": 0.0,
        }

        self._fog = Fog("sky_weather_fog")
        self.app.render.setFog(self._fog)

        self._cloud_layers = []
        self._build_cloud_layers()
        self._apply_now(force=True)

    def _as_dict(self, value):
        return value if isinstance(value, dict) else {}

    def _as_float(self, value, default):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _preset_time_value(self, key):
        payload = self.time_presets.get(str(key or "").strip().lower(), {})
        if not isinstance(payload, dict):
            return 0.5
        return max(0.0, min(1.0, self._as_float(payload.get("time", 0.5), 0.5)))

    def _weather_value(self, key, field, default):
        payload = self.weather_presets.get(str(key or "").strip().lower(), {})
        if not isinstance(payload, dict):
            return float(default)
        return self._as_float(payload.get(field, default), default)

    def set_time_preset(self, key):
        token = str(key or "").strip().lower()
        if token in self.time_presets:
            self.time_key = token
            self.time_target = self._preset_time_value(token)
            return True
        return False

    def set_weather_preset(self, key):
        token = str(key or "").strip().lower()
        if token in self.weather_presets:
            self.weather_key = token
            return True
        return False

    def _build_cloud_layers(self):
        root = self.app.render.attachNewNode("sky_cloud_layers")
        root.setLightOff(1)
        root.setShaderOff(1)
        self._cloud_root = root

        tex_candidates = [
            "assets/textures/clouds.png",
            "assets/textures/cloud_layer.png",
            "assets/textures/flare.png",
        ]
        cloud_tex = None
        for path in tex_candidates:
            if os.path.exists(path):
                try:
                    cloud_tex = self.app.loader.loadTexture(path)
                except Exception:
                    cloud_tex = None
                if cloud_tex:
                    break

        layer_specs = [
            {"size": 260.0, "z": 52.0, "speed": 0.22, "alpha": 0.32, "tilt": 6.0},
            {"size": 320.0, "z": 66.0, "speed": -0.14, "alpha": 0.24, "tilt": -4.0},
            {"size": 380.0, "z": 86.0, "speed": 0.09, "alpha": 0.18, "tilt": 2.0},
        ]

        for idx, spec in enumerate(layer_specs):
            cm = CardMaker(f"sky_cloud_layer_{idx}")
            hs = spec["size"] * 0.5
            cm.setFrame(-hs, hs, -hs, hs)
            node = root.attachNewNode(cm.generate())
            node.setP(-90.0 + float(spec["tilt"]))
            node.setPos(0.0, 0.0, float(spec["z"]))
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setTwoSided(True)
            node.setColorScale(1.0, 1.0, 1.0, float(spec["alpha"]))
            if cloud_tex:
                try:
                    node.setTexture(cloud_tex, 1)
                except Exception:
                    pass
            self._cloud_layers.append(
                {
                    "node": node,
                    "speed": float(spec["speed"]),
                    "phase": idx * 0.4,
                    "base_alpha": float(spec["alpha"]),
                }
            )

    def _time_gradient(self, t):
        # Smooth day/night factor from normalized time value (0..1).
        sun = max(0.0, math.sin((t - 0.25) * math.tau))
        twilight = max(0.0, math.sin((t + 0.05) * math.tau))

        if sun <= 0.01:
            sky = Vec4(0.025, 0.035, 0.065, 1.0)
            fog = Vec4(0.030, 0.040, 0.075, 1.0)
        else:
            warm = max(0.0, 1.0 - abs(t - 0.5) * 3.0)
            sky = Vec4(
                0.24 + (0.22 * sun) + (0.14 * warm),
                0.34 + (0.26 * sun) + (0.06 * warm),
                0.48 + (0.30 * sun),
                1.0,
            )
            fog = Vec4(
                0.18 + (0.22 * sun) + (0.14 * warm),
                0.24 + (0.24 * sun) + (0.07 * warm),
                0.32 + (0.30 * sun),
                1.0,
            )

        ambient_strength = 0.06 + (0.40 * sun) + (0.08 * twilight)
        sun_strength = 0.10 + (1.08 * sun)
        return sky, fog, ambient_strength, sun_strength

    def _phase_from_time(self, t):
        hour = (float(t) % 1.0) * 24.0
        if hour < 4.0:
            return "midnight"
        if hour < 7.0:
            return "dawn"
        if hour < 18.0:
            return "day"
        if hour < 21.0:
            return "dusk"
        return "night"

    def _time_visibility_multiplier(self, phase):
        token = str(phase or "").strip().lower()
        if token in {"midnight", "night"}:
            return 0.32
        if token == "dawn":
            return 0.56
        if token == "dusk":
            return 0.62
        return 1.0

    def _pick_next_weather(self):
        keys = [k for k in self.weather_presets.keys() if str(k or "").strip()]
        if not keys:
            return self.weather_key
        current = str(self.weather_key or "").strip().lower()
        if len(keys) <= 1:
            return current
        ring = ["clear", "partly_cloudy", "overcast", "rainy", "stormy"]
        available = [k for k in ring if k in keys]
        if not available:
            available = keys
        if current not in available:
            return available[0]
        idx = available.index(current)
        return available[(idx + 1) % len(available)]

    def get_world_state(self):
        return dict(self.world_state)

    def _apply_now(self, force=False):
        t = max(0.0, min(1.0, float(self.time_value)))
        coverage = max(0.0, min(1.0, float(self.weather_blend)))
        weather_visibility = max(0.2, min(1.0, float(self.weather_visibility)))
        phase = self._phase_from_time(t)
        vis_mul = self._time_visibility_multiplier(phase)
        visibility = max(0.08, min(1.0, weather_visibility * vis_mul))

        sky, fog_color, ambient_strength, sun_strength = self._time_gradient(t)
        cloud_dim = 1.0 - (0.35 * coverage)
        fog_density = 0.003 + (0.010 * (1.0 - visibility)) + (0.004 * coverage)

        # Keep directional + ambient lights coherent with weather interpolation.
        dlight = getattr(self.app, "_dlight", None)
        alight = getattr(self.app, "_alight", None)
        if dlight:
            dlnp = getattr(self.app, "_dlnp", None)
            if dlnp:
                elev = max(0.0, math.sin((t - 0.25) * math.tau))
                heading = (t * 360.0) % 360.0
                pitch = -8.0 - (72.0 * elev)
                dlnp.setHpr(heading, pitch, 0.0)
            dlight.setColor(
                Vec4(
                    max(0.0, sky.x * sun_strength * cloud_dim),
                    max(0.0, sky.y * sun_strength * cloud_dim),
                    max(0.0, sky.z * sun_strength * cloud_dim),
                    1.0,
                )
            )
        if alight:
            alight.setColor(
                Vec4(
                    max(0.0, fog_color.x * ambient_strength),
                    max(0.0, fog_color.y * ambient_strength),
                    max(0.0, fog_color.z * ambient_strength),
                    1.0,
                )
            )

        self._fog.setColor(fog_color.x, fog_color.y, fog_color.z)
        self._fog.setExpDensity(float(fog_density))

        if force:
            self.app.setBackgroundColor(sky.x, sky.y, sky.z)
        else:
            bg = self.app.getBackgroundColor()
            blend = 0.12
            self.app.setBackgroundColor(
                (bg.x * (1.0 - blend)) + (sky.x * blend),
                (bg.y * (1.0 - blend)) + (sky.y * blend),
                (bg.z * (1.0 - blend)) + (sky.z * blend),
            )

        now = 0.0
        try:
            from direct.showbase.ShowBaseGlobal import globalClock

            now = float(globalClock.getFrameTime())
        except Exception:
            now = 0.0

        player = getattr(self.app, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if actor and hasattr(self, "_cloud_root"):
            pos = actor.getPos(self.app.render)
            self._cloud_root.setPos(pos.x, pos.y, 0.0)

        for layer in self._cloud_layers:
            node = layer["node"]
            speed = float(layer["speed"])
            phase = float(layer["phase"])
            alpha = max(0.04, min(0.92, float(layer["base_alpha"]) + (coverage * 0.24)))
            node.setH((now * speed * 20.0) + (phase * 50.0))
            node.setColorScale(1.0, 1.0, 1.0, alpha)

        is_night = self._phase_from_time(t) in {"night", "midnight"}
        self.world_state = {
            "time": float(t),
            "hour": float((t % 1.0) * 24.0),
            "phase": self._phase_from_time(t),
            "is_night": bool(is_night),
            "weather": str(self.weather_key),
            "visibility": float(visibility),
            "cloud_coverage": float(coverage),
            "sun_strength": float(max(0.0, sun_strength * cloud_dim)),
            "ambient_strength": float(max(0.0, ambient_strength)),
            "fear_bias": float((0.24 if is_night else 0.0) + (0.16 * max(0.0, coverage - 0.45))),
        }
        if self.world_state["phase"] != self._last_phase or self.weather_key != self._last_weather:
            self._last_phase = self.world_state["phase"]
            self._last_weather = str(self.weather_key)
            bus = getattr(self.app, "event_bus", None)
            if bus and hasattr(bus, "emit"):
                try:
                    bus.emit("world.state.changed", dict(self.world_state))
                except Exception:
                    pass

    def update(self, dt):
        dt = max(0.0, float(dt))
        if self.auto_cycle:
            # Long-running day cycle: wrap on [0..1) and keep target synced.
            self.time_target = (self.time_target + (dt / self.cycle_duration)) % 1.0
        if self.auto_weather:
            self._weather_timer -= dt
            if self._weather_timer <= 0.0:
                self.set_weather_preset(self._pick_next_weather())
                span = self.weather_hold_max - self.weather_hold_min
                self._weather_timer = self.weather_hold_min + (span * 0.5)

        time_blend = min(1.0, dt * self.time_transition_speed)
        d_time = self.time_target - self.time_value
        if d_time > 0.5:
            d_time -= 1.0
        elif d_time < -0.5:
            d_time += 1.0
        self.time_value = (self.time_value + (d_time * time_blend)) % 1.0

        weather_target = self._weather_value(self.weather_key, "cloud_coverage", self.weather_blend)
        vis_target = self._weather_value(self.weather_key, "visibility", self.weather_visibility)
        weather_blend = min(1.0, dt * self.weather_transition_speed)
        self.weather_blend = self.weather_blend + ((weather_target - self.weather_blend) * weather_blend)
        self.weather_visibility = self.weather_visibility + ((vis_target - self.weather_visibility) * weather_blend)

        self._apply_now(force=False)
