"""Dragon boss controller with procedural fallback model and fire breath VFX."""

import json
import math
import random
from pathlib import Path

from direct.actor.Actor import Actor
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import CardMaker, LColor, NodePath, TransparencyAttrib, Vec3

from render.model_visuals import ensure_model_visual_defaults
from utils.logger import logger


def _safe_read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _normalize(token):
    return "".join(ch for ch in str(token or "").lower() if ch.isalnum())


class DragonBoss:
    def __init__(self, app):
        self.app = app
        self.render = app.render
        self.loader = app.loader
        self._rng = random.Random(94173)

        self.root = None
        self.actor = None
        self._state = "idle"
        self._state_time = 0.0
        self._state_lock = 0.0
        self._next_roar_time = 0.0
        self._fire_cooldown = 1.5
        self._fire_emit_accum = 0.0
        self._fire_tick_accum = 0.0
        self._fire_particles = []
        self._is_engaged = False

        self._neck = None
        self._head = None
        self._jaw = None
        self._wing_l = None
        self._wing_r = None
        self._wing_l_mid = None
        self._wing_r_mid = None
        self._wing_l_tip = None
        self._wing_r_tip = None
        self._tail_nodes = []
        self._fire_origin = None
        self._clip_map = {}
        self._state_clip_order = {}
        self._active_clip = ""
        self._body_base_scale = Vec3(1.0, 1.0, 1.0)
        self._last_fire_sfx_time = -999.0

        self.cfg = self._load_dragon_config()
        self.spawn()

    @property
    def is_engaged(self):
        return bool(self._is_engaged)

    def _load_dragon_config(self):
        enemy_cfg = _safe_read_json("data/enemies/dragon.json")
        anim_cfg = _safe_read_json("data/actors/dragon_animations.json")
        state_cfg = _safe_read_json("data/states/dragon_states.json")
        return {
            "enemy": enemy_cfg if isinstance(enemy_cfg, dict) else {},
            "anim": anim_cfg if isinstance(anim_cfg, dict) else {},
            "state": state_cfg if isinstance(state_cfg, dict) else {},
        }

    def _resolve_spawn_position(self):
        enemy_cfg = self.cfg["enemy"]
        spawn = enemy_cfg.get("spawn_point", [34.0, -6.0, 0.0])
        if not isinstance(spawn, (list, tuple)) or len(spawn) < 3:
            spawn = [34.0, -6.0, 0.0]
        x = float(spawn[0])
        y = float(spawn[1])
        z = float(spawn[2])
        if hasattr(self.app, "world") and self.app.world and hasattr(self.app.world, "_th"):
            try:
                z = float(self.app.world._th(x, y)) + 3.4
            except Exception:
                z = float(spawn[2])
        return Vec3(x, y, z)

    def _stat(self, key, default):
        stats = self.cfg["enemy"].get("stats", {})
        try:
            return float(stats.get(key, default))
        except Exception:
            return float(default)

    def _ai_value(self, key, default):
        ai_cfg = self.cfg["enemy"].get("ai", {})
        try:
            return float(ai_cfg.get(key, default))
        except Exception:
            return float(default)

    def spawn(self):
        if self.root and not self.root.isEmpty():
            self.root.removeNode()

        self.root = self.render.attachNewNode("dragon_boss_root")
        self.root.setPos(self._resolve_spawn_position())
        self.root.setH(180.0)
        self._state = "idle"
        self._state_time = 0.0
        self._state_lock = 0.0
        self._fire_cooldown = 1.5
        self._fire_emit_accum = 0.0
        self._fire_tick_accum = 0.0
        self._is_engaged = False

        if not self._build_actor_dragon():
            self._build_procedural_dragon()

        ensure_model_visual_defaults(
            self.root,
            apply_skin=False,
            force_two_sided=True,
            debug_label="dragon_boss_root",
        )
        logger.info("[Dragon] Spawned upgraded dragon boss.")

    def _build_actor_dragon(self):
        anim_cfg = self.cfg["anim"]
        model_path = str(anim_cfg.get("model", "")).strip().replace("\\", "/")
        if not model_path or not Path(model_path).exists():
            if model_path:
                logger.info(f"[Dragon] External dragon model not found: {model_path}. Using procedural fallback.")
            return False

        clip_entries = anim_cfg.get("animations", {})
        clip_map = {}
        if isinstance(clip_entries, dict):
            for key, value in clip_entries.items():
                clip = str(value or "").strip().replace("\\", "/")
                if clip and Path(clip).exists():
                    clip_map[str(key)] = clip

        try:
            if clip_map:
                self.actor = Actor(model_path, clip_map)
            else:
                self.actor = Actor(model_path)
        except Exception as exc:
            logger.warning(f"[Dragon] Failed to load actor dragon model '{model_path}': {exc}")
            self.actor = None
            return False

        self.actor.reparentTo(self.root)
        try:
            scale = float(anim_cfg.get("scale", self.cfg["enemy"].get("visuals", {}).get("scale", 1.0)) or 1.0)
        except Exception:
            scale = 1.0
        self.actor.setScale(scale)
        self._body_base_scale = Vec3(scale, scale, scale)
        ensure_model_visual_defaults(
            self.actor,
            apply_skin=True,
            force_two_sided=True,
            debug_label="dragon_boss_actor",
        )

        self._clip_map = {str(k): str(k) for k in self.actor.getAnimNames()}
        self._state_clip_order = self._load_state_clip_order()
        self._init_actor_attachment_points()
        return True

    def _load_state_clip_order(self):
        anim_cfg = self.cfg["anim"]
        mapping = anim_cfg.get("state_map", {})
        out = {}
        if isinstance(mapping, dict):
            for state_name, raw in mapping.items():
                key = str(state_name or "").strip().lower()
                if not key:
                    continue
                tokens = []
                if isinstance(raw, str):
                    tokens = [raw]
                elif isinstance(raw, list):
                    tokens = [str(v) for v in raw if isinstance(v, str)]
                if tokens:
                    out[key] = tokens
        if not out:
            out = {
                "idle": ["idle", "hover", "fly_idle"],
                "patrol": ["fly", "glide", "run"],
                "fire_breath": ["fire_breath", "attack_fire", "attack"],
                "roar": ["roar", "taunt", "attack_roar"],
            }
        return out

    def _init_actor_attachment_points(self):
        head_joint_names = [
            "Head",
            "head",
            "mixamorig:Head",
            "Dragon_Head",
            "Neck_03",
        ]
        fire_socket = None
        for joint in head_joint_names:
            try:
                np = self.actor.exposeJoint(None, "modelRoot", joint)
                if np and not np.isEmpty():
                    fire_socket = np
                    break
            except Exception:
                continue
        if fire_socket is None:
            fire_socket = self.actor.attachNewNode("dragon_fire_origin")
            fire_socket.setPos(0.0, 1.5, 0.8)
        self._fire_origin = fire_socket.attachNewNode("dragon_fire_origin_offset")
        self._fire_origin.setPos(0.0, 0.72, 0.08)

    def _make_piece(
        self,
        name,
        parent,
        model,
        *,
        scale=(1.0, 1.0, 1.0),
        pos=(0.0, 0.0, 0.0),
        hpr=(0.0, 0.0, 0.0),
        color=(1.0, 1.0, 1.0, 1.0),
    ):
        np = self.loader.loadModel(model)
        np.reparentTo(parent)
        np.setName(name)
        np.setScale(*scale)
        np.setPos(*pos)
        np.setHpr(*hpr)
        np.setColor(LColor(*color))
        ensure_model_visual_defaults(
            np,
            apply_skin=False,
            force_two_sided=True,
            debug_label=f"dragon_piece:{name}",
        )
        return np

    def _build_procedural_dragon(self):
        base_scale = float(self.cfg["enemy"].get("visuals", {}).get("scale", 0.85) or 0.85)
        self.root.setScale(base_scale)
        self._body_base_scale = Vec3(base_scale, base_scale, base_scale)

        body = self._make_piece(
            "dragon_body",
            self.root,
            "models/misc/sphere",
            scale=(2.8, 4.3, 1.25),
            color=(0.20, 0.09, 0.08, 1.0),
        )
        self._make_piece(
            "dragon_chest",
            body,
            "models/misc/sphere",
            scale=(1.6, 1.7, 1.0),
            pos=(0.0, 1.35, 0.25),
            color=(0.34, 0.15, 0.10, 1.0),
        )
        self._make_piece(
            "dragon_spine",
            body,
            "models/misc/rgbCube",
            scale=(0.22, 3.7, 0.20),
            pos=(0.0, 0.10, 1.0),
            color=(0.56, 0.33, 0.18, 1.0),
        )

        self._neck = body.attachNewNode("dragon_neck_pivot")
        self._neck.setPos(0.0, 2.15, 0.55)
        neck_mesh = self._make_piece(
            "dragon_neck",
            self._neck,
            "models/misc/sphere",
            scale=(0.68, 1.2, 0.5),
            hpr=(0.0, -18.0, 0.0),
            color=(0.25, 0.11, 0.08, 1.0),
        )

        self._head = self._neck.attachNewNode("dragon_head_pivot")
        self._head.setPos(0.0, 1.0, 0.25)
        self._make_piece(
            "dragon_head",
            self._head,
            "models/misc/sphere",
            scale=(0.85, 1.2, 0.56),
            hpr=(0.0, -10.0, 0.0),
            color=(0.30, 0.14, 0.09, 1.0),
        )

        self._jaw = self._head.attachNewNode("dragon_jaw_pivot")
        self._jaw.setPos(0.0, 0.72, -0.08)
        self._make_piece(
            "dragon_jaw",
            self._jaw,
            "models/misc/rgbCube",
            scale=(0.34, 0.76, 0.15),
            hpr=(0.0, -6.0, 0.0),
            color=(0.39, 0.19, 0.11, 1.0),
        )

        self._make_piece(
            "dragon_horn_l",
            self._head,
            "models/misc/rgbCube",
            scale=(0.08, 0.42, 0.08),
            pos=(-0.20, -0.10, 0.43),
            hpr=(22.0, 48.0, 18.0),
            color=(0.69, 0.56, 0.31, 1.0),
        )
        self._make_piece(
            "dragon_horn_r",
            self._head,
            "models/misc/rgbCube",
            scale=(0.08, 0.42, 0.08),
            pos=(0.20, -0.10, 0.43),
            hpr=(-22.0, 48.0, -18.0),
            color=(0.69, 0.56, 0.31, 1.0),
        )

        self._wing_l = body.attachNewNode("dragon_wing_l")
        self._wing_l.setPos(-1.55, 0.75, 0.68)
        self._wing_r = body.attachNewNode("dragon_wing_r")
        self._wing_r.setPos(1.55, 0.75, 0.68)

        self._wing_l_mid = self._wing_l.attachNewNode("dragon_wing_l_mid")
        self._wing_l_mid.setPos(-0.95, 0.45, 0.12)
        self._wing_r_mid = self._wing_r.attachNewNode("dragon_wing_r_mid")
        self._wing_r_mid.setPos(0.95, 0.45, 0.12)

        self._wing_l_tip = self._wing_l_mid.attachNewNode("dragon_wing_l_tip")
        self._wing_l_tip.setPos(-0.88, 0.35, 0.08)
        self._wing_r_tip = self._wing_r_mid.attachNewNode("dragon_wing_r_tip")
        self._wing_r_tip.setPos(0.88, 0.35, 0.08)

        self._attach_wing_membrane(self._wing_l, True)
        self._attach_wing_membrane(self._wing_r, False)

        leg_offsets = [
            (-0.9, 1.5, -0.8),
            (0.9, 1.5, -0.8),
            (-1.1, -1.5, -0.8),
            (1.1, -1.5, -0.8),
        ]
        for idx, (lx, ly, lz) in enumerate(leg_offsets):
            leg = self._make_piece(
                f"dragon_leg_{idx}",
                body,
                "models/misc/rgbCube",
                scale=(0.24, 0.24, 0.95),
                pos=(lx, ly, lz),
                color=(0.33, 0.16, 0.10, 1.0),
            )
            self._make_piece(
                f"dragon_claw_{idx}",
                leg,
                "models/misc/rgbCube",
                scale=(0.18, 0.30, 0.10),
                pos=(0.0, 0.0, -0.62),
                color=(0.82, 0.54, 0.19, 1.0),
            )

        self._tail_nodes = []
        tail_parent = body
        for idx in range(6):
            tail_parent = tail_parent.attachNewNode(f"dragon_tail_{idx}")
            tail_parent.setPos(0.0, -1.12 if idx == 0 else -0.84, 0.06 - (idx * 0.03))
            self._make_piece(
                f"dragon_tail_mesh_{idx}",
                tail_parent,
                "models/misc/sphere",
                scale=(0.58 - (idx * 0.06), 0.82, 0.40 - (idx * 0.04)),
                color=(0.23 + (idx * 0.01), 0.10, 0.07, 1.0),
            )
            self._tail_nodes.append(tail_parent)

        self._fire_origin = self._jaw.attachNewNode("dragon_fire_origin")
        self._fire_origin.setPos(0.0, 0.58, -0.02)

    def _attach_wing_membrane(self, wing_root, is_left):
        cm = CardMaker("dragon_wing_membrane")
        cm.setFrame(0.0, 2.8, -0.22, 1.15)
        membrane = wing_root.attachNewNode(cm.generate())
        membrane.setTransparency(TransparencyAttrib.MAlpha)
        membrane.setColorScale(0.52, 0.24, 0.14, 0.70)
        membrane.setTwoSided(True)
        membrane.setLightOff(1)
        membrane.setP(-6.0)
        if is_left:
            membrane.setH(168.0)
        else:
            membrane.setH(12.0)
            membrane.setSx(-1.0)
        ensure_model_visual_defaults(
            membrane,
            apply_skin=False,
            force_two_sided=True,
            debug_label="dragon_wing_membrane",
        )

    def _pick_actor_clip(self, state_name):
        if not self.actor:
            return None
        available = {str(name): str(name) for name in self.actor.getAnimNames()}
        available_norm = {_normalize(name): name for name in available}
        tokens = self._state_clip_order.get(str(state_name).lower(), [state_name])
        for token in tokens:
            tkn = str(token or "").strip()
            if not tkn:
                continue
            if tkn in available:
                return tkn
            norm = _normalize(tkn)
            if norm in available_norm:
                return available_norm[norm]
        return None

    def _set_state(self, state_name, lock=0.0):
        new_state = str(state_name or "idle").strip().lower()
        if new_state == self._state and lock <= 0.0:
            return
        self._state = new_state
        self._state_time = 0.0
        self._state_lock = max(0.0, float(lock))
        if self.actor:
            clip = self._pick_actor_clip(new_state)
            if clip and clip != self._active_clip:
                try:
                    if self._state_lock > 0.0:
                        self.actor.play(clip)
                    else:
                        self.actor.loop(clip)
                    self._active_clip = clip
                except Exception:
                    self._active_clip = ""

    def _update_facing(self, target_pos, dt):
        if not self.root or self.root.isEmpty():
            return
        origin = self.root.getPos(self.render)
        vec = target_pos - origin
        if vec.lengthSquared() <= 1e-4:
            return
        desired = math.degrees(math.atan2(vec.x, vec.y))
        current = self.root.getH(self.render)
        delta = ((desired - current + 180.0) % 360.0) - 180.0
        turn_speed = 120.0 if self._state == "fire_breath" else 75.0
        step = _clamp(delta, -turn_speed * dt, turn_speed * dt)
        self.root.setH(self.render, current + step)

    def _emit_fire_particle(self):
        if not self._fire_origin:
            return

        cm = CardMaker("dragon_fire_particle")
        cm.setFrame(-0.12, 0.12, -0.12, 0.12)
        node = self.render.attachNewNode(cm.generate())
        node.setBillboardPointEye()
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setLightOff(1)

        src = self._fire_origin.getPos(self.render)
        fwd = self._fire_origin.getQuat(self.render).getForward()
        spread = Vec3(
            self._rng.uniform(-0.16, 0.16),
            self._rng.uniform(-0.08, 0.10),
            self._rng.uniform(-0.10, 0.08),
        )
        vel = (fwd + spread) * self._rng.uniform(9.0, 15.0)
        life = self._rng.uniform(0.30, 0.58)
        size = self._rng.uniform(0.17, 0.31)

        node.setPos(src)
        node.setScale(size)
        node.setColorScale(1.0, self._rng.uniform(0.55, 0.82), 0.12, 0.95)
        self._fire_particles.append(
            {
                "node": node,
                "vel": vel,
                "life": life,
                "max_life": life,
                "size": size,
            }
        )

    def _tick_fire_particles(self, dt):
        if not self._fire_particles:
            return
        alive = []
        for item in self._fire_particles:
            node = item.get("node")
            if not node or node.isEmpty():
                continue
            life = float(item.get("life", 0.0)) - dt
            if life <= 0.0:
                node.removeNode()
                continue

            vel = item.get("vel", Vec3(0, 0, 0))
            pos = node.getPos(self.render) + (vel * dt)
            vel.z += 1.6 * dt
            item["vel"] = vel
            item["life"] = life
            item["node"] = node

            ratio = max(0.0, min(1.0, life / max(0.01, float(item.get("max_life", 1.0)))))
            size = float(item.get("size", 0.2)) * (1.0 + ((1.0 - ratio) * 1.9))
            node.setPos(pos)
            node.setScale(size)
            node.setColorScale(1.0, 0.3 + (0.7 * ratio), 0.08 + (0.22 * ratio), ratio)
            alive.append(item)
        self._fire_particles = alive

    def _apply_fire_damage(self, player_pos, dt):
        if self._state != "fire_breath" or not self._fire_origin:
            return
        target = player_pos - self._fire_origin.getPos(self.render)
        dist = target.length()
        fire_range = self._ai_value("fire_range", 19.0)
        if dist <= 0.2 or dist > fire_range:
            return
        target.normalize()
        forward = self._fire_origin.getQuat(self.render).getForward()
        forward.normalize()
        cone_cos = math.cos(math.radians(self._ai_value("fire_cone_degrees", 26.0)))
        if forward.dot(target) < cone_cos:
            return

        self._fire_tick_accum += dt
        if self._fire_tick_accum < 0.30:
            return
        self._fire_tick_accum = 0.0

        player = getattr(self.app, "player", None)
        if not player:
            return
        char_state = getattr(player, "cs", None)
        if not char_state or not hasattr(char_state, "health"):
            return
        damage = int(self._ai_value("fire_tick_damage", 12.0))
        try:
            char_state.health = max(0.0, float(char_state.health) - damage)
        except Exception:
            pass

    def _animate_procedural(self, dt):
        if self.actor:
            return
        t = globalClock.getFrameTime()
        wing_speed = 4.0
        wing_amp = 10.0
        jaw_open = 4.0
        neck_pitch = -6.0

        if self._state in {"patrol", "chase"}:
            wing_speed = 6.6
            wing_amp = 22.0
            neck_pitch = -10.0
        elif self._state == "fire_breath":
            wing_speed = 8.5
            wing_amp = 28.0
            jaw_open = 30.0
            neck_pitch = -20.0
        elif self._state == "roar":
            wing_speed = 3.6
            wing_amp = 12.0
            jaw_open = 24.0
            neck_pitch = -14.0

        flap = math.sin(t * wing_speed)
        wing_base = wing_amp * flap
        wing_mid = wing_amp * 0.65 * flap
        wing_tip = wing_amp * 0.50 * flap

        if self._wing_l:
            self._wing_l.setHpr(-110.0 + wing_base, -8.0, 16.0)
        if self._wing_r:
            self._wing_r.setHpr(110.0 - wing_base, -8.0, -16.0)
        if self._wing_l_mid:
            self._wing_l_mid.setHpr(-34.0 + wing_mid, 10.0, 7.0)
        if self._wing_r_mid:
            self._wing_r_mid.setHpr(34.0 - wing_mid, 10.0, -7.0)
        if self._wing_l_tip:
            self._wing_l_tip.setHpr(-28.0 + wing_tip, 4.0, 3.0)
        if self._wing_r_tip:
            self._wing_r_tip.setHpr(28.0 - wing_tip, 4.0, -3.0)

        if self._neck:
            self._neck.setP(neck_pitch + (math.sin(t * 1.7) * 2.6))
        if self._jaw:
            self._jaw.setP(-jaw_open)
        if self._head:
            self._head.setR(math.sin(t * 1.2) * 2.1)

        tail_phase = t * 4.8
        for idx, segment in enumerate(self._tail_nodes):
            sway = math.sin(tail_phase - (idx * 0.58)) * (10.0 + (idx * 2.0))
            segment.setH(sway)
            segment.setP(math.cos(tail_phase - (idx * 0.62)) * 4.0)

        breath = 1.0 + (math.sin(t * 2.4) * 0.025)
        self.root.setScale(
            self._body_base_scale.x * breath,
            self._body_base_scale.y * (1.0 + ((breath - 1.0) * 0.5)),
            self._body_base_scale.z * breath,
        )

    def _tick_state_machine(self, dt, player_pos):
        origin = self.root.getPos(self.render)
        to_player = player_pos - origin
        dist = to_player.length()
        aggro = self._stat("aggro_range", 28.0)
        fire_range = self._ai_value("fire_range", 19.0)

        self._is_engaged = dist <= (aggro * 1.2)
        if self._state_lock > 0.0:
            self._state_lock = max(0.0, self._state_lock - dt)

        if self._state_lock <= 0.0:
            if self._is_engaged and dist <= fire_range and self._fire_cooldown <= 0.0:
                self._set_state("fire_breath", lock=self._ai_value("fire_duration", 2.2))
                self._fire_cooldown = self._ai_value("fire_cooldown", 5.8)
                self._fire_emit_accum = 0.0
                self._fire_tick_accum = 0.0
            elif self._is_engaged and globalClock.getFrameTime() >= self._next_roar_time:
                self._set_state("roar", lock=1.15)
                self._next_roar_time = globalClock.getFrameTime() + self._rng.uniform(6.0, 9.0)
            elif self._is_engaged:
                self._set_state("patrol")
            else:
                self._set_state("idle")

        self._fire_cooldown = max(0.0, self._fire_cooldown - dt)

    def update(self, dt, player_pos):
        if not self.root or self.root.isEmpty():
            return
        if player_pos is None:
            return

        self._state_time += max(0.0, float(dt))
        self._tick_state_machine(dt, player_pos)
        self._update_facing(player_pos, dt)
        self._animate_procedural(dt)

        if self._state == "fire_breath":
            self._fire_emit_accum += dt
            emit_rate = 0.02
            while self._fire_emit_accum >= emit_rate:
                self._fire_emit_accum -= emit_rate
                self._emit_fire_particle()

            now = globalClock.getFrameTime()
            if now - self._last_fire_sfx_time >= 0.32:
                audio = getattr(self.app, "audio", None)
                if audio:
                    try:
                        audio.play_sfx("dragon_fire", volume=0.92, rate=0.86)
                    except Exception:
                        pass
                self._last_fire_sfx_time = now

            self._apply_fire_damage(player_pos, dt)

        self._tick_fire_particles(dt)
