"""Ambient NPC animation and movement manager."""

import math
import random

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
        self._base_anims = {
            "idle": "assets/models/xbot/idle.glb",
            "walk": "assets/models/xbot/walk.glb",
            "run": "assets/models/xbot/run.glb",
        }

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

        actor = self._build_actor(npc_id)
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
        return {
            "id": npc_id,
            "name": str(payload.get("name", npc_id)),
            "actor": actor,
            "home": Vec3(x, y, z),
            "target": Vec3(x, y, z),
            "wander_radius": max(0.0, wander_radius),
            "walk_speed": max(0.2, walk_speed),
            "idle_timer": self._rng.uniform(idle_min, idle_max),
            "idle_min": max(0.1, idle_min),
            "idle_max": max(idle_min, idle_max),
            "anim": "idle",
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

    def _build_actor(self, npc_id):
        try:
            actor = Actor("assets/models/xbot/Xbot.glb", self._base_anims)
            return actor
        except Exception as exc:
            logger.warning(f"[NPCManager] Failed to build Actor '{npc_id}': {exc}")
        try:
            node, *_ = create_procedural_actor(self.app.render)
            return node
        except Exception:
            return None

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
        radius = unit["wander_radius"]
        if radius <= 0.01:
            unit["target"] = Vec3(home)
            return
        ang = self._rng.uniform(0.0, math.tau)
        dist = self._rng.uniform(0.3, radius)
        tx = home.x + math.cos(ang) * dist
        ty = home.y + math.sin(ang) * dist
        tz = self._ground_height(tx, ty, fallback=home.z)
        unit["target"] = Vec3(tx, ty, tz)

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

    def update(self, dt):
        dt = max(0.0, float(dt))
        for unit in self.units:
            actor = unit.get("actor")
            if not actor:
                continue

            pos = actor.getPos(self.app.render)
            target = unit["target"]
            to_target = target - pos
            to_target.z = 0.0
            dist = to_target.length()

            moving = dist > 0.18
            if moving:
                to_target.normalize()
                speed = unit["walk_speed"]
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
