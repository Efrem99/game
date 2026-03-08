"""Sky and weather interpolation manager.

Keeps lighting/fog/cloud state in sync with time-of-day and weather presets.
"""

import math
import os
import random

from panda3d.core import (
    CardMaker,
    ColorBlendAttrib,
    Fog,
    PNMImage,
    SamplerState,
    Texture,
    TransparencyAttrib,
    Vec3,
    Vec4,
)


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
        self.min_visibility = max(0.10, min(1.0, self._as_float(self.cfg.get("min_visibility", 0.36), 0.36)))
        self.min_ambient_light = max(0.00, min(1.0, self._as_float(self.cfg.get("min_ambient_light", 0.22), 0.22)))
        self.min_sun_light = max(0.00, min(1.0, self._as_float(self.cfg.get("min_sun_light", 0.14), 0.14)))

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
        self._rng = random.Random(7301)
        self._dt_last = 0.016
        self._lightning_timer = 0.0
        self._lightning_cooldown = 0.8
        self._lightning_flash = 0.0
        self.world_state = {
            "time": float(self.time_value),
            "hour": 12.0,
            "phase": "day",
            "is_night": False,
            "weather": self.weather_key,
            "visibility": max(0.1, min(1.0, float(self.weather_visibility))),
            "cloud_coverage": max(0.0, min(1.0, float(self.weather_blend))),
            "sun_strength": 1.0,
            "moon_strength": 0.0,
            "ambient_strength": 1.0,
            "rain_strength": 0.0,
            "storm_strength": 0.0,
            "fear_bias": 0.0,
        }

        self._fog = Fog("sky_weather_fog")
        self.app.render.setFog(self._fog)

        self._cloud_layers = []
        self._rain_layers = []
        self._sky_root = None
        self._stars_node = None
        self._sun_node = None
        self._sun_glare = None
        self._moon_node = None
        self._lightning_overlay = None
        self._sky_dome = None
        self._rain_root = None
        self._build_celestial_layers()
        self._build_cloud_layers()
        self._build_rain_layers()
        self._apply_now(force=True)

    def _as_dict(self, value):
        return value if isinstance(value, dict) else {}

    def _as_float(self, value, default):
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def compute_celestial_factors(time_value, cloud_coverage=0.0):
        t = float(time_value) % 1.0
        clouds = max(0.0, min(1.0, float(cloud_coverage)))
        raw_sun = math.sin((t - 0.25) * math.tau)
        sun_elevation = max(0.0, raw_sun)
        night_strength = max(0.0, -raw_sun)

        azimuth = (t * math.tau) + math.pi
        horiz = math.sqrt(max(0.0, 1.0 - min(0.98, abs(raw_sun)) ** 2))
        sun_dir = Vec3(math.sin(azimuth) * horiz, math.cos(azimuth) * horiz, raw_sun)
        if sun_dir.length_squared() <= 1e-6:
            sun_dir = Vec3(0.0, 1.0, 0.2)
        else:
            sun_dir.normalize()
        moon_dir = Vec3(-sun_dir.x, -sun_dir.y, -sun_dir.z)
        moon_elevation = max(0.0, moon_dir.z)

        moon_light = (0.08 + (0.42 * moon_elevation)) * (1.0 - (clouds * 0.42))
        stars_alpha = (night_strength ** 1.7) * (1.0 - (clouds * 0.55))
        sun_glare = sun_elevation * (1.0 - (clouds * 0.72))
        twilight = max(0.0, 1.0 - abs(raw_sun) * 2.0)
        return {
            "sun_elevation": float(max(0.0, min(1.0, sun_elevation))),
            "night_strength": float(max(0.0, min(1.0, night_strength))),
            "moon_light": float(max(0.0, min(1.0, moon_light))),
            "stars_alpha": float(max(0.0, min(1.0, stars_alpha))),
            "sun_glare": float(max(0.0, min(1.0, sun_glare))),
            "twilight": float(max(0.0, min(1.0, twilight))),
            "sun_dir": Vec3(sun_dir),
            "moon_dir": Vec3(moon_dir),
        }

    @staticmethod
    def weather_fx_profile(weather_key, cloud_coverage=0.0):
        token = str(weather_key or "").strip().lower()
        coverage = max(0.0, min(1.0, float(cloud_coverage)))
        profile = {
            "rain_strength": 0.0,
            "lightning_strength": 0.0,
            "cloud_darkening": 0.08,
            "wind_strength": 0.18,
        }
        if token == "partly_cloudy":
            profile["cloud_darkening"] = 0.18
            profile["wind_strength"] = 0.28
        elif token in {"overcast", "foggy"}:
            profile["cloud_darkening"] = 0.40
            profile["wind_strength"] = 0.38
        elif token in {"rainy", "rain"}:
            profile["rain_strength"] = 0.72
            profile["cloud_darkening"] = 0.54
            profile["wind_strength"] = 0.48
            profile["lightning_strength"] = 0.10
        elif token in {"stormy", "storm", "thunderstorm"}:
            profile["rain_strength"] = 1.0
            profile["cloud_darkening"] = 0.74
            profile["wind_strength"] = 0.86
            profile["lightning_strength"] = 1.0

        profile["cloud_darkening"] = max(
            profile["cloud_darkening"],
            profile["cloud_darkening"] * 0.55 + (coverage * 0.45),
        )
        profile["rain_strength"] = max(0.0, min(1.0, profile["rain_strength"] * (0.65 + (coverage * 0.45))))
        profile["lightning_strength"] = max(0.0, min(1.0, profile["lightning_strength"] * (0.6 + (coverage * 0.4))))
        profile["cloud_darkening"] = max(0.0, min(1.0, profile["cloud_darkening"]))
        return profile

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

    def _load_texture_candidate(self, candidates):
        for path in candidates:
            if not path or not os.path.exists(path):
                continue
            try:
                tex = self.app.loader.loadTexture(path)
            except Exception:
                tex = None
            if tex:
                return tex
        return None

    def _make_soft_disc_texture(self, size=256, warm=False):
        img = PNMImage(size, size, 4)
        half = max(1.0, size * 0.5)
        for y in range(size):
            ny = (y - half) / half
            for x in range(size):
                nx = (x - half) / half
                dist = math.sqrt((nx * nx) + (ny * ny))
                edge = max(0.0, 1.0 - dist)
                alpha = edge ** 2.2
                if warm:
                    r = 0.95 + (alpha * 0.05)
                    g = 0.82 + (alpha * 0.16)
                    b = 0.58 + (alpha * 0.36)
                else:
                    r = 0.72 + (alpha * 0.22)
                    g = 0.78 + (alpha * 0.18)
                    b = 0.88 + (alpha * 0.12)
                img.set_xel_a(x, y, min(1.0, r), min(1.0, g), min(1.0, b), alpha)
        tex = Texture("sky_soft_disc")
        tex.load(img)
        tex.set_wrap_u(SamplerState.WM_clamp)
        tex.set_wrap_v(SamplerState.WM_clamp)
        return tex

    def _make_star_texture(self, size=1024):
        img = PNMImage(size, size, 4)
        for y in range(size):
            for x in range(size):
                img.set_xel_a(x, y, 0.0, 0.0, 0.0, 0.0)
        points = max(220, int(size * 0.5))
        for _ in range(points):
            x = self._rng.randrange(0, size)
            y = self._rng.randrange(0, size)
            b = 0.58 + (self._rng.random() * 0.42)
            a = 0.32 + (self._rng.random() * 0.62)
            img.set_xel_a(x, y, b, b, min(1.0, b + 0.08), a)
        tex = Texture("sky_stars")
        tex.load(img)
        tex.set_wrap_u(SamplerState.WM_repeat)
        tex.set_wrap_v(SamplerState.WM_repeat)
        return tex

    def _build_celestial_layers(self):
        root = self.app.render.attachNewNode("sky_celestial_root")
        root.setLightOff(1)
        root.setShaderOff(1)
        self._sky_root = root

        try:
            dome = self.app.loader.loadModel("models/misc/sphere")
            if dome:
                dome.reparentTo(root)
                dome.setScale(260.0)
                dome.setTwoSided(True)
                dome.setDepthWrite(False)
                dome.setDepthTest(False)
                dome.setBin("background", 0)
                dome.setColorScale(0.08, 0.10, 0.18, 1.0)
                dome.setLightOff(1)
                dome.setShaderOff(1)
                self._sky_dome = dome
        except Exception:
            self._sky_dome = None

        stars_tex = self._make_star_texture(1024)
        cm_stars = CardMaker("sky_stars")
        cm_stars.setFrame(-210.0, 210.0, -210.0, 210.0)
        stars = root.attachNewNode(cm_stars.generate())
        stars.setP(-90.0)
        stars.setZ(148.0)
        stars.setTexture(stars_tex, 1)
        stars.setTransparency(TransparencyAttrib.MAlpha)
        stars.setDepthWrite(False)
        stars.setDepthTest(False)
        stars.setBin("background", 1)
        stars.setColorScale(1.0, 1.0, 1.0, 0.0)
        self._stars_node = stars

        sun_tex = self._load_texture_candidate(["assets/textures/flare.png"]) or self._make_soft_disc_texture(256, warm=True)
        moon_tex = self._make_soft_disc_texture(256, warm=False)

        cm_sun = CardMaker("sky_sun")
        cm_sun.setFrame(-9.5, 9.5, -9.5, 9.5)
        sun = root.attachNewNode(cm_sun.generate())
        sun.setTexture(sun_tex, 1)
        sun.setBillboardPointEye()
        sun.setTransparency(TransparencyAttrib.MAlpha)
        sun.setDepthWrite(False)
        sun.setDepthTest(False)
        sun.setBin("background", 3)
        sun.setColorScale(1.0, 0.90, 0.62, 0.0)
        self._sun_node = sun

        cm_glare = CardMaker("sky_sun_glare")
        cm_glare.setFrame(-15.0, 15.0, -15.0, 15.0)
        glare = root.attachNewNode(cm_glare.generate())
        glare.setTexture(sun_tex, 1)
        glare.setBillboardPointEye()
        glare.setTransparency(TransparencyAttrib.MAlpha)
        glare.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd))
        glare.setDepthWrite(False)
        glare.setDepthTest(False)
        glare.setBin("background", 4)
        glare.setColorScale(1.0, 0.84, 0.52, 0.0)
        self._sun_glare = glare

        cm_moon = CardMaker("sky_moon")
        cm_moon.setFrame(-8.8, 8.8, -8.8, 8.8)
        moon = root.attachNewNode(cm_moon.generate())
        moon.setTexture(moon_tex, 1)
        moon.setBillboardPointEye()
        moon.setTransparency(TransparencyAttrib.MAlpha)
        moon.setDepthWrite(False)
        moon.setDepthTest(False)
        moon.setBin("background", 2)
        moon.setColorScale(0.78, 0.84, 0.98, 0.0)
        self._moon_node = moon

        cm_flash = CardMaker("lightning_overlay")
        cm_flash.setFrame(-1.0, 1.0, -1.0, 1.0)
        overlay = self.app.render2d.attachNewNode(cm_flash.generate())
        overlay.setTransparency(TransparencyAttrib.MAlpha)
        overlay.setDepthWrite(False)
        overlay.setDepthTest(False)
        overlay.setBin("fixed", 48)
        overlay.setColorScale(0.95, 0.96, 1.0, 0.0)
        overlay.setLightOff(1)
        overlay.setShaderOff(1)
        self._lightning_overlay = overlay

    def _build_rain_layers(self):
        root = self.app.render.attachNewNode("sky_rain_layers")
        root.setLightOff(1)
        root.setShaderOff(1)
        self._rain_root = root
        streak_tex = self._load_texture_candidate(["assets/textures/flare.png"]) or self._make_soft_disc_texture(128, warm=False)
        rain_count = 96
        for idx in range(rain_count):
            cm = CardMaker(f"rain_streak_{idx}")
            cm.setFrame(-0.024, 0.024, 0.0, 2.0)
            node = root.attachNewNode(cm.generate())
            node.setTexture(streak_tex, 1)
            node.setBillboardPointEye()
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setDepthWrite(False)
            node.setDepthTest(False)
            node.setBin("fixed", 3)
            node.setColorScale(0.74, 0.84, 1.0, 0.0)
            self._rain_layers.append(
                {
                    "node": node,
                    "x": self._rng.uniform(-30.0, 30.0),
                    "y": self._rng.uniform(-30.0, 30.0),
                    "z": self._rng.uniform(2.0, 24.0),
                    "speed": self._rng.uniform(0.85, 1.35),
                    "span": self._rng.uniform(18.0, 27.0),
                }
            )

    def _build_cloud_layers(self):
        root = (self._sky_root if self._sky_root is not None else self.app.render).attachNewNode("sky_cloud_layers")
        root.setLightOff(1)
        root.setShaderOff(1)
        self._cloud_root = root

        cloud_tex = self._load_texture_candidate([
            "assets/textures/clouds.png",
            "assets/textures/cloud_layer.png",
            "assets/textures/flare.png",
        ]) or self._make_soft_disc_texture(256, warm=False)

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

    def _time_gradient(self, t, celestial=None, weather_profile=None):
        cel = celestial if isinstance(celestial, dict) else self.compute_celestial_factors(t, self.weather_blend)
        weather = weather_profile if isinstance(weather_profile, dict) else self.weather_fx_profile(self.weather_key, self.weather_blend)
        sun = float(cel.get("sun_elevation", 0.0))
        moon = float(cel.get("moon_light", 0.0))
        twilight = float(cel.get("twilight", 0.0))
        darkening = float(weather.get("cloud_darkening", 0.0))

        if sun <= 0.01:
            sky = Vec4(
                0.06 + (moon * 0.10),
                0.08 + (moon * 0.12),
                0.14 + (moon * 0.20),
                1.0,
            )
            fog = Vec4(
                0.07 + (moon * 0.09),
                0.09 + (moon * 0.10),
                0.15 + (moon * 0.16),
                1.0,
            )
        else:
            warm = max(0.0, 1.0 - abs(t - 0.5) * 3.0)
            sky = Vec4(
                0.22 + (0.24 * sun) + (0.15 * warm),
                0.31 + (0.28 * sun) + (0.07 * warm),
                0.46 + (0.34 * sun),
                1.0,
            )
            fog = Vec4(
                0.16 + (0.23 * sun) + (0.12 * warm),
                0.22 + (0.24 * sun) + (0.07 * warm),
                0.31 + (0.31 * sun),
                1.0,
            )

        dim = 1.0 - (darkening * 0.38)
        sky = Vec4(sky.x * dim, sky.y * dim, sky.z * dim, 1.0)
        fog = Vec4(fog.x * dim, fog.y * dim, fog.z * dim, 1.0)
        ambient_strength = 0.18 + (0.52 * sun) + (0.22 * moon) + (0.08 * twilight)
        sun_strength = 0.14 + (1.02 * sun) + (0.44 * moon)
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
            return 0.60
        if token == "dawn":
            return 0.78
        if token == "dusk":
            return 0.82
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

    def _orient_directional_light(self, dlnp, direction):
        if not dlnp:
            return
        vec = Vec3(direction)
        if vec.length_squared() <= 1e-6:
            return
        vec.normalize()
        heading = math.degrees(math.atan2(vec.x, vec.y))
        pitch = -math.degrees(math.asin(max(-0.98, min(0.98, vec.z))))
        dlnp.setHpr(heading, pitch, 0.0)

    def _update_celestial_visuals(self, now, celestial, weather_profile):
        root = self._sky_root
        if not root:
            return

        player = getattr(self.app, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if actor:
            pos = actor.getPos(self.app.render)
            root.setPos(pos.x, pos.y, 0.0)

        sun_dir = Vec3(celestial.get("sun_dir", Vec3(0.0, 1.0, 0.2)))
        moon_dir = Vec3(celestial.get("moon_dir", Vec3(0.0, -1.0, 0.4)))
        sun_pos = sun_dir * 160.0
        moon_pos = moon_dir * 156.0

        cloud_dark = max(0.0, min(1.0, float(weather_profile.get("cloud_darkening", 0.0))))
        sun_alpha = max(0.0, min(0.96, float(celestial.get("sun_glare", 0.0)))) * (1.0 - (cloud_dark * 0.62))
        moon_alpha = max(0.0, min(0.88, float(celestial.get("moon_light", 0.0) * 1.75))) * (1.0 - (cloud_dark * 0.40))
        star_alpha = max(0.0, min(0.92, float(celestial.get("stars_alpha", 0.0)))) * (1.0 - (cloud_dark * 0.45))

        if self._sun_node:
            self._sun_node.setPos(sun_pos)
            self._sun_node.setColorScale(1.0, 0.88, 0.62, sun_alpha)
        if self._sun_glare:
            self._sun_glare.setPos(sun_pos * 0.94)
            self._sun_glare.setColorScale(1.0, 0.84, 0.54, sun_alpha * 0.44)
        if self._moon_node:
            self._moon_node.setPos(moon_pos)
            self._moon_node.setColorScale(0.78, 0.84, 0.98, moon_alpha)
        if self._stars_node:
            self._stars_node.setH((now * 0.5) % 360.0)
            self._stars_node.setColorScale(1.0, 1.0, 1.0, star_alpha)
        if self._sky_dome:
            moon_tint = float(celestial.get("moon_light", 0.0))
            self._sky_dome.setColorScale(
                0.08 + (moon_tint * 0.05),
                0.09 + (moon_tint * 0.06),
                0.16 + (moon_tint * 0.10),
                1.0,
            )

    def _update_rain_fx(self, dt, weather_profile):
        if not self._rain_root:
            return
        rain_strength = max(0.0, min(1.0, float(weather_profile.get("rain_strength", 0.0))))
        if rain_strength <= 0.02:
            for row in self._rain_layers:
                row["node"].setColorScale(0.74, 0.84, 1.0, 0.0)
            return

        player = getattr(self.app, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if actor:
            ppos = actor.getPos(self.app.render)
            self._rain_root.setPos(ppos.x, ppos.y, ppos.z)

        fall_speed = 9.0 + (15.0 * rain_strength)
        for row in self._rain_layers:
            row["z"] -= dt * fall_speed * float(row["speed"])
            if row["z"] <= -1.8:
                row["z"] = float(row["span"])
                row["x"] = self._rng.uniform(-30.0, 30.0)
                row["y"] = self._rng.uniform(-30.0, 30.0)
            row["node"].setPos(float(row["x"]), float(row["y"]), float(row["z"]))
            row["node"].setColorScale(0.74, 0.84, 1.0, 0.06 + (0.36 * rain_strength))

    def _update_lightning(self, dt, weather_profile):
        strength = max(0.0, min(1.0, float(weather_profile.get("lightning_strength", 0.0))))
        self._lightning_cooldown = max(0.0, self._lightning_cooldown - dt)

        if strength > 0.08 and self._lightning_timer <= 0.0 and self._lightning_cooldown <= 0.0:
            trigger = dt * (0.06 + (0.24 * strength))
            if self._rng.random() < trigger:
                self._lightning_timer = 0.10 + (self._rng.random() * 0.16)
                self._lightning_cooldown = 1.0 + (self._rng.random() * 2.6)

        if self._lightning_timer > 0.0:
            self._lightning_timer = max(0.0, self._lightning_timer - dt)
            pulse = max(0.0, min(1.0, self._lightning_timer / 0.24))
            self._lightning_flash = pulse * strength
        else:
            self._lightning_flash = max(0.0, self._lightning_flash - (dt * 2.5))

        if self._lightning_overlay:
            self._lightning_overlay.setColorScale(0.95, 0.96, 1.0, self._lightning_flash * 0.35)

    def _apply_now(self, force=False):
        t = max(0.0, min(1.0, float(self.time_value)))
        coverage = max(0.0, min(1.0, float(self.weather_blend)))
        weather_visibility = max(0.2, min(1.0, float(self.weather_visibility)))
        phase = self._phase_from_time(t)
        vis_mul = self._time_visibility_multiplier(phase)
        celestial = self.compute_celestial_factors(t, coverage)
        weather_profile = self.weather_fx_profile(self.weather_key, coverage)
        visibility = max(
            float(self.min_visibility),
            min(1.0, weather_visibility * vis_mul * (1.0 - weather_profile["cloud_darkening"] * 0.16)),
        )

        sky, fog_color, ambient_strength, sun_strength = self._time_gradient(t, celestial, weather_profile)
        cloud_dim = 1.0 - (0.28 * coverage)
        fog_density = 0.0017 + (0.006 * (1.0 - visibility)) + (0.0036 * weather_profile["cloud_darkening"])
        lightning = float(self._lightning_flash)

        # Keep directional + ambient lights coherent with weather interpolation.
        dlight = getattr(self.app, "_dlight", None)
        alight = getattr(self.app, "_alight", None)
        if dlight:
            dlnp = getattr(self.app, "_dlnp", None)
            if dlnp:
                major_light_dir = celestial["sun_dir"] if celestial["sun_elevation"] > 0.05 else celestial["moon_dir"]
                self._orient_directional_light(dlnp, major_light_dir)
            sun_floor = max(0.01, float(self.min_sun_light))
            dlight.setColor(
                Vec4(
                    max(sun_floor, sky.x * sun_strength * cloud_dim) + (lightning * 0.34),
                    max(sun_floor * 0.95, sky.y * sun_strength * cloud_dim) + (lightning * 0.36),
                    max(sun_floor * 0.90, sky.z * sun_strength * cloud_dim) + (lightning * 0.48),
                    1.0,
                )
            )
        if alight:
            amb_floor = max(0.01, float(self.min_ambient_light))
            alight.setColor(
                Vec4(
                    max(amb_floor * 0.98, fog_color.x * ambient_strength) + (lightning * 0.16),
                    max(amb_floor * 1.00, fog_color.y * ambient_strength) + (lightning * 0.17),
                    max(amb_floor * 1.06, fog_color.z * ambient_strength) + (lightning * 0.22),
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
                (bg.x * (1.0 - blend)) + (sky.x * blend) + (lightning * 0.02),
                (bg.y * (1.0 - blend)) + (sky.y * blend) + (lightning * 0.02),
                (bg.z * (1.0 - blend)) + (sky.z * blend) + (lightning * 0.03),
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
            shade = max(0.58, 1.0 - (weather_profile["cloud_darkening"] * 0.34))
            node.setH((now * speed * 20.0) + (phase * 50.0))
            node.setColorScale(shade, shade, min(1.0, shade + 0.06), alpha)

        self._update_celestial_visuals(now, celestial, weather_profile)
        self._update_rain_fx(self._dt_last, weather_profile)

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
            "moon_strength": float(max(0.0, celestial.get("moon_light", 0.0))),
            "ambient_strength": float(max(0.0, ambient_strength)),
            "rain_strength": float(max(0.0, weather_profile.get("rain_strength", 0.0))),
            "storm_strength": float(max(0.0, weather_profile.get("lightning_strength", 0.0))),
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
        self._dt_last = max(0.001, dt)
        if self.auto_cycle:
            # Long-running day cycle: wrap on [0..1) and keep target synced.
            self.time_target = (self.time_target + (dt / self.cycle_duration)) % 1.0
        if self.auto_weather:
            self._weather_timer -= dt
            if self._weather_timer <= 0.0:
                self.set_weather_preset(self._pick_next_weather())
                span = self.weather_hold_max - self.weather_hold_min
                self._weather_timer = self.weather_hold_min + (span * 0.5)

        self._update_lightning(dt, self.weather_fx_profile(self.weather_key, self.weather_blend))

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
