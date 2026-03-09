"""Ambient NPC animation and movement manager."""

import math
import random
from pathlib import Path

from direct.actor.Actor import Actor
from panda3d.core import Vec3

from entities.mannequin import create_procedural_actor
from render.model_visuals import ensure_model_visual_defaults
from utils.logger import logger


class NPCManager:
    def __init__(self, app):
        self.app = app
        self._rng = random.Random(7731)
        self.units = []
        self._default_model = "assets/models/xbot/Xbot.glb"
        self._base_anims = {
            "idle": "assets/models/xbot/idle.glb",
            "walk": "assets/models/xbot/walk.glb",
            "run": "assets/models/xbot/run.glb",
        }

    def clear(self):
        for unit in self.units:
            actor = unit.get("actor")
            npc_id = unit.get("id")
            if actor:
                try:
                    actor.removeNode()
                except Exception:
                    pass
            sim_tier_mgr = getattr(self.app, "sim_tier_mgr", None)
            if sim_tier_mgr and npc_id:
                sim_tier_mgr.unregister(npc_id)
            interaction_mgr = getattr(self.app, "npc_interaction", None)
            if interaction_mgr and npc_id:
                interaction_mgr.unregister_unit(npc_id)

        self.units = []

    def spawn_from_data(self, npcs_data):
        self.clear()
        if not isinstance(npcs_data, dict):
            return

        for npc_id, payload in npcs_data.items():
            if not isinstance(payload, dict):
                continue
            unit = self._spawn_single(str(npc_id), payload)
            if unit:
                self.units.append(unit)
        logger.info(f"[NPCManager] Spawned animated NPCs: {len(self.units)}")

    def _spawn_single(self, npc_id, payload):
        pos = payload.get("pos", [0.0, 0.0, 0.0])
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            pos = [0.0, 0.0, 0.0]

        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2])
        z = self._ground_height(x, y, fallback=z)

        appr = payload.get("appearance", {})
        if not isinstance(appr, dict):
            appr = {}

        scale = float(appr.get("scale", 1.0) or 1.0)
        wander_radius = float(payload.get("wander_radius", appr.get("wander_radius", 3.0)) or 3.0)
        walk_speed = float(payload.get("walk_speed", appr.get("walk_speed", 1.5)) or 1.5)
        idle_min = float(payload.get("idle_min", appr.get("idle_min", 1.5)) or 1.5)
        idle_max = float(payload.get("idle_max", appr.get("idle_max", 4.2)) or 4.2)
        if idle_max < idle_min:
            idle_max = idle_min + 0.5

        actor = self._build_actor(npc_id, payload, appr)
        if not actor:
            return None

        actor.reparentTo(self.app.render)
        actor.setScale(scale)
        actor.setPos(x, y, z)
        actor.setTag("npc_id", npc_id)
        actor.setTag("npc_name", str(payload.get("name", npc_id)))
        ensure_model_visual_defaults(
            actor,
            apply_skin=True,
            debug_label=f"npc:{npc_id}",
        )
        self._apply_non_core_visual_fallback(
            actor,
            python_mode=(getattr(self.app, "char_state", None) is None),
        )
        self._apply_appearance_tint(actor, appr)

        dialogue_path = str(payload.get("dialogue", npc_id))
        npc_name = str(payload.get("name", npc_id))

        interaction_mgr = getattr(self.app, "npc_interaction", None)
        if interaction_mgr:
            interaction_mgr.register_unit(npc_id, actor, dialogue_path, npc_name)

        sim_tier_mgr = getattr(self.app, "sim_tier_mgr", None)
        if sim_tier_mgr:
            sim_tier_mgr.register(npc_id, actor)

        self._play_anim(actor, "idle", loop=True)
        role = str(payload.get("role", "") or "")
        initial_activity = self._choose_background_activity({"role": role}, {})
        return {
            "id": npc_id,
            "name": str(payload.get("name", npc_id)),
            "role": role,
            "actor": actor,
            "home": Vec3(x, y, z),
            "target": Vec3(x, y, z),
            "wander_radius": max(0.0, wander_radius),
            "base_wander_radius": max(0.0, wander_radius),
            "walk_speed": max(0.2, walk_speed),
            "base_walk_speed": max(0.2, walk_speed),
            "idle_timer": self._rng.uniform(idle_min, idle_max),
            "idle_min": max(0.1, idle_min),
            "idle_max": max(idle_min, idle_max),
            "base_idle_min": max(0.1, idle_min),
            "base_idle_max": max(idle_min, idle_max),
            "activity": initial_activity,
            # Spawn with mid-cycle timers so settlements look active, not freshly started.
            "activity_timer": self._rng.uniform(2.8, 9.2),
            "activity_live": False,
            "activity_sequence": [],
            "activity_index": -1,
            "activity_story": "",
            "activity_seed": self._rng.uniform(0.0, 1.0),
            "anim": "idle",
            "suspicion": 0.0,
            "alerted": False,
            "detected_player": False,
        }

    def _apply_appearance_tint(self, actor, appearance):
        if not actor or not isinstance(appearance, dict):
            return
        skin = appearance.get("skin_color")
        if not (isinstance(skin, (list, tuple)) and len(skin) >= 3):
            return
        try:
            r = max(0.55, min(1.0, float(skin[0]) + 0.25))
            g = max(0.50, min(1.0, float(skin[1]) + 0.20))
            b = max(0.45, min(1.0, float(skin[2]) + 0.18))
            actor.setColorScale(r, g, b, 1.0)
        except Exception:
            pass

    def _build_actor(self, npc_id, payload, appearance):
        candidates = []
        for raw in (
            (appearance or {}).get("model"),
            (payload or {}).get("model"),
            self._default_model,
        ):
            path = str(raw or "").strip().replace("\\", "/")
            if not path:
                continue
            if path not in candidates:
                candidates.append(path)

        anim_map = self._base_anims
        raw_anims = (appearance or {}).get("animations")
        if not isinstance(raw_anims, dict):
            raw_anims = (payload or {}).get("animations")
        if isinstance(raw_anims, dict) and raw_anims:
            anim_map = {str(k): str(v) for k, v in raw_anims.items() if str(k).strip() and str(v).strip()}
            if not anim_map:
                anim_map = self._base_anims

        for model_path in candidates:
            actor = self._try_build_actor(model_path, anim_map)
            if actor:
                return actor
            static_model = self._try_build_static_model(model_path)
            if static_model:
                logger.warning(
                    f"[NPCManager] Using static model fallback for NPC '{npc_id}': {model_path}"
                )
                return static_model

        # Last-resort procedural actor keeps the game running if all model paths are broken.
        try:
            logger.warning(f"[NPCManager] Falling back to procedural NPC for '{npc_id}'")
            node, *_ = create_procedural_actor(self.app.render)
            return node
        except Exception:
            return None

    def _try_build_actor(self, model_path, anim_map):
        try:
            if not Path(model_path).exists():
                return None
        except Exception:
            return None
        try:
            return Actor(model_path, anim_map)
        except Exception as exc:
            logger.warning(f"[NPCManager] Actor load failed '{model_path}': {exc}")
            return None

    def _try_build_static_model(self, model_path):
        try:
            if not Path(model_path).exists():
                return None
        except Exception:
            return None
        try:
            model = self.app.loader.loadModel(model_path)
        except Exception as exc:
            logger.warning(f"[NPCManager] Static model load failed '{model_path}': {exc}")
            return None
        if not model or model.isEmpty():
            return None
        return model

    def _apply_non_core_visual_fallback(self, actor, python_mode=False):
        if not actor or not python_mode:
            return
        is_animated_actor = False
        try:
            is_animated_actor = isinstance(actor, Actor)
        except Exception:
            is_animated_actor = False
        if not is_animated_actor:
            is_animated_actor = all(
                hasattr(actor, attr) for attr in ("getAnimNames", "loop", "play")
            )

        # Keep skinned characters on shader path so animations do not freeze.
        if not is_animated_actor:
            try:
                actor.setShaderOff(1002)
            except Exception:
                pass

        try:
            actor.setColorScale(1.0, 1.0, 1.0, 1.0)
        except Exception:
            pass
        try:
            actor.setTwoSided(True)
        except Exception:
            pass

    def _ground_height(self, x, y, fallback=0.0):
        world = getattr(self.app, "world", None)
        if world and hasattr(world, "_th"):
            try:
                return float(world._th(float(x), float(y)))
            except Exception:
                pass
        return float(fallback)

    def _pick_next_target(self, unit):
        home = unit["home"]
        radius = float(unit.get("wander_radius", unit.get("base_wander_radius", 0.0)))
        if radius <= 0.01:
            unit["target"] = Vec3(home)
            return
        ang = self._rng.uniform(0.0, math.tau)
        dist = self._rng.uniform(0.3, radius)
        tx = home.x + math.cos(ang) * dist
        ty = home.y + math.sin(ang) * dist
        tz = self._ground_height(tx, ty, fallback=home.z)
        unit["target"] = Vec3(tx, ty, tz)

    def _is_guard_role(self, role_token):
        token = str(role_token or "").strip().lower()
        return any(mark in token for mark in ("guard", "patrol", "watch", "captain", "knight", "soldier"))

    def _world_motion_modifiers(self, unit, world_state):
        role = str(unit.get("role", "") or "")
        is_guard = self._is_guard_role(role)
        weather = str(world_state.get("weather", "") or "").strip().lower()
        phase = str(world_state.get("phase", "") or "").strip().lower()
        is_night = bool(world_state.get("is_night", False))
        visibility = float(world_state.get("visibility", 1.0) or 1.0)

        speed_scale = 1.0
        idle_scale = 1.0
        wander_scale = 1.0
        force_home = False

        if weather in {"rainy", "stormy"}:
            if is_guard:
                speed_scale *= 0.95
                wander_scale *= 1.15
                idle_scale *= 0.85
            else:
                speed_scale *= 0.58
                wander_scale *= 0.42
                idle_scale *= 1.65
                force_home = True
        elif weather == "overcast" and not is_guard:
            speed_scale *= 0.9
            wander_scale *= 0.84
            idle_scale *= 1.15

        if is_night or phase in {"night", "midnight"}:
            if is_guard:
                speed_scale *= 1.12
                wander_scale *= 1.28
                idle_scale *= 0.80
            else:
                speed_scale *= 0.62
                wander_scale *= 0.36
                idle_scale *= 1.35
                force_home = True
        elif phase in {"dawn", "dusk"} and not is_guard:
            speed_scale *= 0.9
            idle_scale *= 1.12

        if visibility < 0.45 and not is_guard:
            speed_scale *= 0.84
            idle_scale *= 1.24

        activity = str(unit.get("activity", "idle") or "idle").strip().lower()
        alerted = bool(unit.get("alerted", False))
        suspicion = float(unit.get("suspicion", 0.0) or 0.0)
        if alerted:
            if is_guard:
                speed_scale *= 1.22
                wander_scale *= 1.34
                idle_scale *= 0.72
            else:
                speed_scale *= 1.08
                wander_scale *= 0.48
                idle_scale *= 1.15
        elif suspicion >= 0.35 and is_guard:
            speed_scale *= 1.08
            wander_scale *= 1.12
            idle_scale *= 0.90

        if activity in {"patrol", "inspect", "escort"}:
            speed_scale *= 1.14
            wander_scale *= 1.28
            idle_scale *= 0.82
        elif activity in {"work", "repair", "haul"}:
            speed_scale *= 0.9
            wander_scale *= 1.05
            idle_scale *= 0.92
        elif activity in {"talk", "rest"}:
            speed_scale *= 0.74
            wander_scale *= 0.62
            idle_scale *= 1.22
        elif activity in {"shelter", "panic"}:
            speed_scale *= 0.65
            wander_scale *= 0.30
            idle_scale *= 1.35
            force_home = True
        return {
            "speed_scale": max(0.3, min(1.8, float(speed_scale))),
            "idle_scale": max(0.6, min(2.5, float(idle_scale))),
            "wander_scale": max(0.2, min(2.2, float(wander_scale))),
            "force_home": bool(force_home),
        }

    def _choose_background_activity(self, unit, world_state):
        weather = str(world_state.get("weather", "") or "").strip().lower()
        phase = str(world_state.get("phase", "") or "").strip().lower()
        is_guard = self._is_guard_role(unit.get("role", ""))
        if weather in {"stormy", "rainy"} and not is_guard:
            return "shelter"
        if phase in {"night", "midnight"}:
            return "patrol" if is_guard else "rest"
        if is_guard:
            return "patrol"
        return self._rng.choice(["work", "talk", "haul", "idle"])

    def _choose_live_activity(self, unit, world_state):
        weather = str(world_state.get("weather", "") or "").strip().lower()
        phase = str(world_state.get("phase", "") or "").strip().lower()
        is_guard = self._is_guard_role(unit.get("role", ""))
        if weather in {"stormy", "rainy"} and not is_guard:
            return "shelter"
        if phase in {"night", "midnight"}:
            return "patrol" if is_guard else "rest"
        if is_guard:
            return self._rng.choice(["patrol", "inspect", "escort"])
        return self._rng.choice(["work", "repair", "talk", "haul", "idle"])

    def _build_live_sequence(self, unit, world_state):
        weather = str(world_state.get("weather", "") or "").strip().lower()
        phase = str(world_state.get("phase", "") or "").strip().lower()
        is_guard = self._is_guard_role(unit.get("role", ""))
        if weather in {"stormy", "rainy"} and not is_guard:
            return "storm_shelter", [
                {"activity": "shelter", "min": 8.0, "max": 14.0},
                {"activity": "rest", "min": 5.0, "max": 9.0},
                {"activity": "repair", "min": 6.0, "max": 11.0},
            ]

        if is_guard:
            templates = [
                (
                    "guard_patrol",
                    [
                        {"activity": "inspect", "min": 4.5, "max": 7.5},
                        {"activity": "patrol", "min": 7.0, "max": 12.0},
                        {"activity": "escort", "min": 5.0, "max": 8.0},
                    ],
                ),
                (
                    "guard_watch",
                    [
                        {"activity": "patrol", "min": 6.0, "max": 10.0},
                        {"activity": "inspect", "min": 4.0, "max": 7.0},
                        {"activity": "patrol", "min": 7.5, "max": 11.5},
                    ],
                ),
            ]
        elif phase in {"night", "midnight"}:
            templates = [
                (
                    "town_night",
                    [
                        {"activity": "talk", "min": 4.0, "max": 7.0},
                        {"activity": "rest", "min": 6.0, "max": 10.0},
                        {"activity": "shelter", "min": 5.0, "max": 9.0},
                    ],
                ),
                (
                    "closing_shift",
                    [
                        {"activity": "haul", "min": 5.0, "max": 8.0},
                        {"activity": "repair", "min": 6.0, "max": 10.0},
                        {"activity": "rest", "min": 6.0, "max": 11.0},
                    ],
                ),
            ]
        else:
            templates = [
                (
                    "market_loop",
                    [
                        {"activity": "talk", "min": 4.0, "max": 7.0},
                        {"activity": "work", "min": 7.0, "max": 12.0},
                        {"activity": "haul", "min": 5.0, "max": 8.0},
                    ],
                ),
                (
                    "craft_loop",
                    [
                        {"activity": "repair", "min": 5.0, "max": 9.0},
                        {"activity": "work", "min": 7.0, "max": 11.0},
                        {"activity": "talk", "min": 4.0, "max": 7.0},
                    ],
                ),
            ]

        if not templates:
            return "ambient_loop", [{"activity": self._choose_live_activity(unit, world_state), "min": 4.0, "max": 8.0}]

        # Deterministic template pick per NPC to avoid jarring random flips near the player.
        seed_key = f"{unit.get('id', '')}:{phase}:{weather}"
        seed_num = sum(ord(ch) for ch in seed_key) + int(float(unit.get("activity_seed", 0.0)) * 1000.0)
        idx = abs(seed_num) % len(templates)
        story, sequence = templates[idx]
        return story, list(sequence)

    def _set_activity_step(self, unit, step, start_mid_progress=False):
        if not isinstance(step, dict):
            step = {"activity": "idle", "min": 4.0, "max": 7.0}
        activity = str(step.get("activity", "idle") or "idle").strip().lower()
        min_d = max(1.2, float(step.get("min", 4.0) or 4.0))
        max_d = max(min_d, float(step.get("max", min_d + 1.0) or (min_d + 1.0)))
        duration = self._rng.uniform(min_d, max_d)
        if start_mid_progress:
            # Enter steps part-way through to fake ongoing activity in the location.
            duration *= self._rng.uniform(0.35, 0.85)
        unit["activity"] = activity
        unit["activity_timer"] = duration
        if activity in {"patrol", "inspect", "escort", "haul", "work", "repair"}:
            self._pick_next_target(unit)

    def _advance_live_sequence(self, unit, world_state, reset=False):
        sequence = unit.get("activity_sequence", [])
        if reset or not isinstance(sequence, list) or not sequence:
            story, sequence = self._build_live_sequence(unit, world_state)
            unit["activity_story"] = story
            unit["activity_sequence"] = sequence
            unit["activity_index"] = -1

        idx = int(unit.get("activity_index", -1)) + 1
        if idx >= len(sequence):
            story, sequence = self._build_live_sequence(unit, world_state)
            unit["activity_story"] = story
            unit["activity_sequence"] = sequence
            idx = 0
        unit["activity_index"] = idx
        step = sequence[idx] if sequence else {"activity": self._choose_live_activity(unit, world_state), "min": 4.0, "max": 7.0}
        self._set_activity_step(unit, step, start_mid_progress=bool(reset))

    def _emit_activity_event(self, unit, trigger, distance):
        bus = getattr(self.app, "event_bus", None)
        if not bus or not hasattr(bus, "emit"):
            return
        actor = unit.get("actor")
        npc_pos = None
        if actor:
            try:
                pos = actor.getPos(self.app.render)
                npc_pos = [float(pos.x), float(pos.y), float(pos.z)]
            except Exception:
                npc_pos = None
        payload = {
            "npc_id": str(unit.get("id", "") or ""),
            "name": str(unit.get("name", "") or ""),
            "role": str(unit.get("role", "") or ""),
            "activity": str(unit.get("activity", "") or ""),
            "story": str(unit.get("activity_story", "") or ""),
            "trigger": str(trigger or ""),
            "live": bool(unit.get("activity_live", False)),
            "distance": float(distance) if distance is not None else None,
            "npc_pos": npc_pos,
        }
        try:
            bus.emit("npc.activity.changed", payload, immediate=False)
        except Exception:
            pass

    def _distance_to_player(self, actor):
        player = getattr(self.app, "player", None)
        player_actor = getattr(player, "actor", None) if player else None
        if not actor or not player_actor:
            return None
        try:
            return float((player_actor.getPos(self.app.render) - actor.getPos(self.app.render)).length())
        except Exception:
            return None

    def _update_player_detection(self, unit, dt, stealth_state):
        if not isinstance(stealth_state, dict):
            stealth_state = {}
        actor = unit.get("actor")
        if not actor:
            return

        is_guard = self._is_guard_role(unit.get("role", ""))
        dist = self._distance_to_player(actor)
        if dist is None:
            return

        base_range = 18.5 if is_guard else 12.5
        range_mult = float(stealth_state.get("detection_radius_mult", 1.0) or 1.0)
        awareness_gain_mult = float(stealth_state.get("awareness_gain_mult", 1.0) or 1.0)
        awareness_decay_mult = float(stealth_state.get("awareness_decay_mult", 1.0) or 1.0)
        exposure = max(0.0, min(1.0, float(stealth_state.get("exposure", 0.9) or 0.9)))
        noise = max(0.0, min(1.0, float(stealth_state.get("noise", 0.9) or 0.9)))

        detect_range = max(3.5, base_range * max(0.4, min(1.6, range_mult)))
        suspicion = float(unit.get("suspicion", 0.0) or 0.0)

        if dist <= detect_range:
            proximity = 1.0 - (dist / detect_range)
            gain = (0.30 + (proximity * 0.95) + (exposure * 0.50) + (noise * 0.42)) * awareness_gain_mult
            if is_guard:
                gain *= 1.10
            else:
                gain *= 0.72
            suspicion += max(0.0, float(dt)) * gain
        else:
            decay = (0.20 if is_guard else 0.28) * awareness_decay_mult
            suspicion -= max(0.0, float(dt)) * decay

        suspicion = max(0.0, min(1.0, suspicion))
        was_alerted = bool(unit.get("alerted", False))
        now_alerted = suspicion >= 0.74
        unit["suspicion"] = suspicion
        unit["detected_player"] = bool(suspicion >= 0.92)
        unit["alerted"] = now_alerted

        if now_alerted:
            if is_guard:
                unit["activity"] = "inspect"
                unit["activity_timer"] = max(2.0, float(unit.get("activity_timer", 0.0) or 0.0))
            else:
                unit["activity"] = "shelter"
                unit["activity_timer"] = max(2.0, float(unit.get("activity_timer", 0.0) or 0.0))

        if was_alerted != now_alerted:
            bus = getattr(self.app, "event_bus", None)
            if bus and hasattr(bus, "emit"):
                try:
                    bus.emit(
                        "npc.stealth.alert",
                        {
                            "npc_id": str(unit.get("id", "") or ""),
                            "name": str(unit.get("name", "") or ""),
                            "alerted": bool(now_alerted),
                            "suspicion": float(suspicion),
                            "distance": float(dist),
                            "is_guard": bool(is_guard),
                        },
                        immediate=False,
                    )
                except Exception:
                    pass

    def _update_activity_state(self, unit, world_state, dt):
        actor = unit.get("actor")
        if not actor:
            return
        dist = self._distance_to_player(actor)
        activation_radius = 34.0
        was_live = bool(unit.get("activity_live", False))
        is_near = dist is not None and dist <= activation_radius
        if is_near:
            if not was_live:
                unit["activity_live"] = True
                self._advance_live_sequence(unit, world_state, reset=True)
                self._emit_activity_event(unit, "live_enter", dist)
            else:
                unit["activity_timer"] -= dt
                if unit["activity_timer"] <= 0.0:
                    prev_activity = str(unit.get("activity", "") or "")
                    self._advance_live_sequence(unit, world_state, reset=False)
                    if str(unit.get("activity", "") or "") != prev_activity:
                        self._emit_activity_event(unit, "live_step", dist)
            return

        if was_live:
            unit["activity_live"] = False
            unit["activity_sequence"] = []
            unit["activity_index"] = -1
            unit["activity_story"] = ""
            unit["activity"] = self._choose_background_activity(unit, world_state)
            unit["activity_timer"] = self._rng.uniform(7.0, 14.0)
            self._emit_activity_event(unit, "background_resume", dist)
            return

        unit["activity_live"] = False
        unit["activity_timer"] -= dt
        if unit["activity_timer"] <= 0.0:
            unit["activity"] = self._choose_background_activity(unit, world_state)
            unit["activity_timer"] = self._rng.uniform(8.0, 16.0)

    def _play_anim(self, actor, clip, loop=True):
        if not actor or not hasattr(actor, "getAnimNames"):
            return
        try:
            anims = {str(name) for name in actor.getAnimNames()}
        except Exception:
            anims = set()
        if clip not in anims:
            return
        try:
            if loop:
                actor.loop(clip)
            else:
                actor.play(clip)
        except Exception:
            pass

    def update(self, dt, world_state=None, stealth_state=None):
        dt = max(0.0, float(dt))
        ws = world_state if isinstance(world_state, dict) else {}
        for unit in self.units:
            actor = unit.get("actor")
            if not actor:
                continue
            self._update_player_detection(unit, dt, stealth_state if isinstance(stealth_state, dict) else {})
            self._update_activity_state(unit, ws, dt)
            modifiers = self._world_motion_modifiers(unit, ws) if ws else {
                "speed_scale": 1.0,
                "idle_scale": 1.0,
                "wander_scale": 1.0,
                "force_home": False,
            }
            base_speed = float(unit.get("base_walk_speed", unit.get("walk_speed", 1.5)))
            speed = max(0.2, base_speed * float(modifiers.get("speed_scale", 1.0)))
            unit["walk_speed"] = speed

            base_radius = float(unit.get("base_wander_radius", unit.get("wander_radius", 0.0)))
            unit["wander_radius"] = max(0.0, base_radius * float(modifiers.get("wander_scale", 1.0)))

            idle_scale = float(modifiers.get("idle_scale", 1.0))
            unit["idle_min"] = max(0.1, float(unit.get("base_idle_min", 1.5)) * idle_scale)
            unit["idle_max"] = max(unit["idle_min"], float(unit.get("base_idle_max", 4.2)) * idle_scale)
            if bool(modifiers.get("force_home", False)):
                unit["target"] = Vec3(unit["home"])
            activity = str(unit.get("activity", "") or "").strip().lower()
            if activity in {"talk", "rest", "shelter"}:
                unit["target"] = Vec3(unit["home"])
            elif activity in {"work", "repair"}:
                if self._rng.random() < (dt * 0.12):
                    self._pick_next_target(unit)
            elif activity in {"patrol", "inspect", "escort", "haul"}:
                if self._rng.random() < (dt * 0.20):
                    self._pick_next_target(unit)

            pos = actor.getPos(self.app.render)
            target = unit["target"]
            to_target = target - pos
            to_target.z = 0.0
            dist = to_target.length()

            moving = dist > 0.18
            if moving:
                to_target.normalize()
                step = min(dist, speed * dt)
                pos += to_target * step
                pos.z = self._ground_height(pos.x, pos.y, fallback=pos.z)
                actor.setPos(pos)
                actor.setH(180.0 - math.degrees(math.atan2(to_target.x, to_target.y)))
                if unit["anim"] != "walk":
                    self._play_anim(actor, "walk", loop=True)
                    unit["anim"] = "walk"
                try:
                    actor.setPlayRate(max(0.65, min(1.35, speed / 1.5)), "walk")
                except Exception:
                    pass
                unit["idle_timer"] = self._rng.uniform(unit["idle_min"], unit["idle_max"])
                continue

            unit["idle_timer"] -= dt
            if unit["anim"] != "idle":
                self._play_anim(actor, "idle", loop=True)
                unit["anim"] = "idle"

            if unit["idle_timer"] <= 0.0:
                self._pick_next_target(unit)
                unit["idle_timer"] = self._rng.uniform(unit["idle_min"], unit["idle_max"])
