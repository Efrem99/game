"""Ambient NPC animation and movement manager."""

import math
import random
import zlib
from pathlib import Path

from utils.core_runtime import HAS_CORE, gc
from direct.actor.Actor import Actor
from panda3d.core import Vec3

from entities.mannequin import build_mannequin, create_procedural_actor
from render.model_visuals import ensure_model_visual_defaults
from utils.asset_pathing import prefer_bam_path
from utils.logger import logger


class NPCManager:
    def __init__(self, app):
        self.app = app
        self._rng = random.Random(7731)
        self.units = []
        self._core_runtime = None
        self._core_runtime_announced = False
        if HAS_CORE and hasattr(gc, "NpcRuntimeSystem"):
            try:
                self._core_runtime = gc.NpcRuntimeSystem()
            except Exception as exc:
                logger.warning(f"[NPCManager] C++ runtime path unavailable, using Python loop: {exc}")
        self._default_model = "assets/models/xbot/Xbot.glb"
        self._base_anims = {
            "idle": "assets/models/xbot/idle.glb",
            "walk": "assets/models/xbot/walk.glb",
            "run": "assets/models/xbot/run.glb",
        }
        self._dialogue_profile_markers = (
            ("guard_dialogue", ("guard", "sentry", "sentinel", "watch", "captain", "knight", "soldier", "patrol")),
            ("merchant_dialogue", ("merchant", "shopkeeper", "trader", "vendor", "wares")),
            ("villager_dialogue", ("miner", "woodcutter", "lumberjack", "villager", "elder", "child", "worker", "guide", "servant", "attendant")),
        )

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

        try:
            x = float(pos[0])
            y = float(pos[1])
            z_raw = float(pos[2])
            if math.isnan(x) or math.isinf(x): x = 0.0
            if math.isnan(y) or math.isinf(y): y = 0.0
            if math.isnan(z_raw) or math.isinf(z_raw): z_raw = 0.0
        except Exception:
            x, y, z_raw = 0.0, 0.0, 0.0
            
        z = self._ground_height(x, y, fallback=z_raw)

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

        # Determine age and gender for visuals
        name_lower = str(payload.get("name", "")).lower()
        role_lower = str(payload.get("role", "")).lower()
        
        age = "adult"
        if "child" in role_lower or "kid" in role_lower:
            age = "child"
        elif "old" in name_lower or "elder" in role_lower or "grand" in name_lower:
            age = "elderly"

        gender = "male"
        if any(mark in (role_lower + name_lower) for mark in ("woman", "lady", "girl", "adalin", "female", "she")):
            gender = "female"
            
        from entities.mannequin import dress_actor
        dress_actor(actor, role_lower, gender=gender, age=age)

        actor.reparentTo(self.app.render)
        # Apply spatial safety
        actor.setPos(x, y, z)
        try:
            fs = float(scale or 1.0)
            if math.isnan(fs) or math.isinf(fs): fs = 1.0
            actor.setScale(max(0.01, fs))
        except Exception:
            actor.setScale(1.0)
        actor.setTag("npc_id", npc_id)
        actor.setTag("npc_name", str(payload.get("name", npc_id)))
        # Level Editor 2.0 Tags (Strict SQLite + Msgpack)
        actor.setTag("entity_id", npc_id)
        actor.setTag("type", "npc")
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
        dracolid_visual = self._attach_dracolid_visual(actor, npc_id, payload, appr)

        dialogue_path = self._resolve_dialogue_path(npc_id, payload)
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
            "dracolid_visual": dracolid_visual,
        }

    def _resolve_dialogue_path(self, npc_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        explicit = str(payload.get("dialogue", "") or "").strip()
        if explicit:
            return explicit

        token_blob = " ".join(
            str(value or "").strip().lower()
            for value in (
                npc_id,
                payload.get("name"),
                payload.get("role"),
                payload.get("archetype"),
            )
            if str(value or "").strip()
        )
        for profile_name, markers in self._dialogue_profile_markers:
            if any(marker in token_blob for marker in markers):
                logger.info(
                    "[NPCManager] У NPC '%s' не задан отдельный dialogue, используем профиль '%s' по роли '%s'.",
                    npc_id,
                    profile_name,
                    str(payload.get("role", "") or "").strip(),
                )
                return profile_name

        logger.info(
            "[NPCManager] У NPC '%s' не задан отдельный dialogue, используем общий профиль жителя.",
            npc_id,
        )
        return "villager_dialogue"

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

    def _collect_profile_tokens(self, npc_id, payload, appearance):
        payload = payload if isinstance(payload, dict) else {}
        appearance = appearance if isinstance(appearance, dict) else {}
        values = [
            npc_id,
            payload.get("name"),
            payload.get("role"),
            payload.get("archetype"),
            payload.get("species"),
            payload.get("race"),
            appearance.get("species"),
            appearance.get("race"),
            appearance.get("kind"),
            appearance.get("archetype"),
            appearance.get("lineage"),
            appearance.get("model"),
        ]
        tokens = set()
        for value in values:
            text = str(value or "").strip().lower()
            if not text:
                continue
            tokens.add(text)
            normalized = text.replace("-", " ").replace("_", " ").replace("/", " ")
            for part in normalized.split():
                token = str(part or "").strip()
                if token:
                    tokens.add(token)
        return tokens

    def _is_dracolid_profile(self, npc_id, payload, appearance):
        markers = (
            "draco",
            "dracol",
            "dragonkin",
            "dragonfolk",
            "dracon",
            "argonian",
            "lizardfolk",
            "reptile",
        )
        for token in self._collect_profile_tokens(npc_id, payload, appearance):
            if any(marker in token for marker in markers):
                return True
        return False

    def _is_armored_appearance(self, payload, appearance):
        payload = payload if isinstance(payload, dict) else {}
        appearance = appearance if isinstance(appearance, dict) else {}
        armor_token = str(
            appearance.get("armor_type")
            or payload.get("armor_type")
            or appearance.get("armor")
            or payload.get("armor")
            or ""
        ).strip().lower()
        role_token = str(payload.get("role", "") or "").strip().lower()

        unarmored_markers = ("none", "civilian", "worker", "cloth", "robe", "tunic")
        armored_markers = ("armor", "armour", "plate", "mail", "steel", "guard", "knight", "heavy")

        if armor_token and any(mark in armor_token for mark in unarmored_markers):
            return False
        if armor_token and any(mark in armor_token for mark in armored_markers):
            return True
        if any(mark in role_token for mark in ("guard", "captain", "knight", "sentinel", "soldier")):
            return True
        return False

    def _build_dracolid_visual_spec(self, npc_id, payload, appearance):
        if not self._is_dracolid_profile(npc_id, payload, appearance):
            return {"enabled": False}

        appearance = appearance if isinstance(appearance, dict) else {}
        armored = self._is_armored_appearance(payload, appearance)
        raw_skin = appearance.get("skin_color")
        skin = (0.42, 0.64, 0.46)
        if isinstance(raw_skin, (list, tuple)) and len(raw_skin) >= 3:
            try:
                skin = (
                    max(0.0, min(1.0, float(raw_skin[0]))),
                    max(0.0, min(1.0, float(raw_skin[1]))),
                    max(0.0, min(1.0, float(raw_skin[2]))),
                )
            except Exception:
                skin = (0.42, 0.64, 0.46)

        body_color = (
            max(0.18, min(0.95, skin[0] * 0.88)),
            max(0.24, min(0.98, skin[1] * 0.92)),
            max(0.18, min(0.95, skin[2] * 0.90)),
        )
        scale = float(appearance.get("scale", 1.0) or 1.0)
        scale = max(0.65, min(1.6, scale))
        wing_span = max(1.05, min(2.5, scale * (1.38 if armored else 1.58)))
        crest_spines = 3 if armored else 2
        snout_length = 0.42 if armored else 0.36
        jaw_length = snout_length * 0.84
        shoulder_spines = 2 if armored else 1

        return {
            "enabled": True,
            "armored": bool(armored),
            "body_style": "humanoid",
            "head_style": "dragon_humanoid",
            "has_wings": True,
            "has_tail": True,
            "has_dragon_head": True,
            "armor_shell": bool(armored),
            "wing_span": wing_span,
            "wing_segments": 3,
            "tail_segments": 5 if armored else 4,
            "crest_spines": crest_spines,
            "snout_length": snout_length,
            "jaw_length": jaw_length,
            "shoulder_spines": shoulder_spines,
            "body_color": body_color,
            "scale": scale,
        }

    def _try_expose_joint(self, actor, names):
        if not actor or not hasattr(actor, "exposeJoint"):
            return None
        for bone in names:
            try:
                node = actor.exposeJoint(None, "modelRoot", bone)
                if node and not node.isEmpty():
                    return node
            except Exception:
                continue
        return None

    def _attach_dracolid_visual(self, actor, npc_id, payload, appearance):
        spec = self._build_dracolid_visual_spec(npc_id, payload, appearance)
        if not spec.get("enabled") or not actor:
            return None

        spine = self._try_expose_joint(actor, ["mixamorig:Spine2", "Spine2", "Spine", "spine_03"])
        head = self._try_expose_joint(actor, ["mixamorig:Head", "Head", "head", "Dragon_Head"])
        hips = self._try_expose_joint(actor, ["mixamorig:Hips", "Hips", "hips", "pelvis"])

        body_color = spec.get("body_color", (0.42, 0.64, 0.46))
        wing_color = (
            max(0.10, body_color[0] * 0.70),
            max(0.12, body_color[1] * 0.72),
            max(0.10, body_color[2] * 0.70),
        )
        horn_color = (
            max(0.35, min(0.88, body_color[0] + 0.24)),
            max(0.33, min(0.86, body_color[1] + 0.20)),
            max(0.28, min(0.80, body_color[2] + 0.15)),
        )
        root = actor.attachNewNode(f"dracolid_visual_{npc_id}")

        # Humanoid armor shell stays centered on spine so the base body remains readable.
        armor_parent = spine or actor
        if spec.get("armor_shell"):
            build_mannequin(
                armor_parent,
                f"dracolid_armor_{npc_id}",
                0.74,
                0.30,
                0.92,
                0.0,
                0.20,
                0.36,
                0.34,
                0.36,
                0.40,
            )
            build_mannequin(
                armor_parent,
                f"dracolid_armor_collar_{npc_id}",
                0.46,
                0.26,
                0.22,
                0.0,
                0.26,
                0.76,
                0.72,
                0.72,
                0.76,
            )
        shoulder_spines = max(0, int(spec.get("shoulder_spines", 0) or 0))
        for idx in range(shoulder_spines):
            z = 0.60 - (idx * 0.06)
            y = -0.08 - (idx * 0.02)
            for side_sign, side_name in ((-1.0, "l"), (1.0, "r")):
                build_mannequin(
                    armor_parent,
                    f"dracolid_shoulder_spine_{side_name}_{idx}_{npc_id}",
                    0.06,
                    0.12,
                    0.24,
                    side_sign * (0.28 + (idx * 0.04)),
                    y,
                    z,
                    horn_color[0] * 0.92,
                    horn_color[1] * 0.90,
                    horn_color[2] * 0.88,
                )

        head_parent = head or actor
        head_root = head_parent.attachNewNode(f"dracolid_head_root_{npc_id}")
        head_root.setPos(0.0, 0.06, 0.02)
        snout_length = float(spec.get("snout_length", 0.36) or 0.36)
        jaw_length = float(spec.get("jaw_length", snout_length * 0.84) or (snout_length * 0.84))
        build_mannequin(
            head_root,
            f"dracolid_muzzle_{npc_id}",
            0.28,
            snout_length,
            0.22,
            0.0,
            0.44,
            -0.02,
            body_color[0] * 0.92,
            body_color[1] * 0.94,
            body_color[2] * 0.92,
        )
        build_mannequin(
            head_root,
            f"dracolid_jaw_{npc_id}",
            0.24,
            jaw_length,
            0.12,
            0.0,
            0.34,
            -0.14,
            body_color[0] * 0.88,
            body_color[1] * 0.90,
            body_color[2] * 0.88,
        )
        build_mannequin(
            head_root,
            f"dracolid_brow_{npc_id}",
            0.32,
            0.20,
            0.10,
            0.0,
            0.14,
            0.16,
            body_color[0] * 0.84,
            body_color[1] * 0.86,
            body_color[2] * 0.84,
        )
        crest_spines = max(2, int(spec.get("crest_spines", 2) or 2))
        for idx in range(crest_spines):
            taper = 1.0 - (idx * 0.14)
            build_mannequin(
                head_root,
                f"dracolid_head_crest_{idx}_{npc_id}",
                max(0.05, 0.08 * taper),
                max(0.05, 0.14 * taper),
                max(0.08, 0.24 * taper),
                0.0,
                -0.02 - (idx * 0.08),
                0.24 + (idx * 0.08),
                horn_color[0],
                horn_color[1],
                horn_color[2],
            )
        build_mannequin(
            head_root,
            f"dracolid_horn_l_{npc_id}",
            0.08,
            0.22,
            0.24,
            -0.15,
            -0.02,
            0.26,
            horn_color[0],
            horn_color[1],
            horn_color[2],
        )
        build_mannequin(
            head_root,
            f"dracolid_horn_r_{npc_id}",
            0.08,
            0.22,
            0.24,
            0.15,
            -0.02,
            0.26,
            horn_color[0],
            horn_color[1],
            horn_color[2],
        )

        wings_parent = (spine or actor).attachNewNode(f"dracolid_wings_{npc_id}")
        wings_parent.setPos(0.0, -0.18, 0.52)
        wing_span = float(spec.get("wing_span", 1.4) or 1.4)
        wing_l = wings_parent.attachNewNode("wing_left")
        wing_r = wings_parent.attachNewNode("wing_right")
        wing_l.setPos(-0.42, 0.02, 0.10)
        wing_r.setPos(0.42, 0.02, 0.10)
        wing_l.setHpr(-18.0, 0.0, 8.0)
        wing_r.setHpr(18.0, 0.0, -8.0)
        wing_l_mid = wing_l.attachNewNode("wing_left_mid")
        wing_r_mid = wing_r.attachNewNode("wing_right_mid")
        wing_l_mid.setPos(-wing_span * 0.34, wing_span * 0.20, 0.06)
        wing_r_mid.setPos(wing_span * 0.34, wing_span * 0.20, 0.06)
        wing_l_tip = wing_l_mid.attachNewNode("wing_left_tip")
        wing_r_tip = wing_r_mid.attachNewNode("wing_right_tip")
        wing_l_tip.setPos(-wing_span * 0.28, wing_span * 0.18, 0.02)
        wing_r_tip.setPos(wing_span * 0.28, wing_span * 0.18, 0.02)
        for idx, wing_root in enumerate((wing_l, wing_r)):
            side_sign = -1.0 if idx == 0 else 1.0
            build_mannequin(
                wing_root,
                f"dracolid_wing_bone_{idx}_{npc_id}",
                0.12,
                wing_span * 0.75,
                0.10,
                side_sign * 0.14,
                side_sign * (wing_span * 0.30),
                0.02,
                wing_color[0],
                wing_color[1],
                wing_color[2],
            )
            membrane = build_mannequin(
                wing_root,
                f"dracolid_wing_membrane_{idx}_{npc_id}",
                0.16,
                wing_span * 0.72,
                0.05,
                side_sign * 0.14,
                side_sign * (wing_span * 0.34),
                -0.10,
                wing_color[0] * 0.92,
                wing_color[1] * 0.95,
                wing_color[2] * 0.92,
            )
            try:
                membrane.setColorScale(1.0, 1.0, 1.0, 0.72)
            except Exception:
                pass
        for idx, wing_mid in enumerate((wing_l_mid, wing_r_mid)):
            side_sign = -1.0 if idx == 0 else 1.0
            build_mannequin(
                wing_mid,
                f"dracolid_wing_mid_bone_{idx}_{npc_id}",
                0.10,
                wing_span * 0.48,
                0.08,
                side_sign * 0.10,
                side_sign * (wing_span * 0.18),
                0.02,
                wing_color[0] * 0.96,
                wing_color[1] * 0.98,
                wing_color[2] * 0.96,
            )
            membrane = build_mannequin(
                wing_mid,
                f"dracolid_wing_mid_membrane_{idx}_{npc_id}",
                0.12,
                wing_span * 0.56,
                0.04,
                side_sign * 0.12,
                side_sign * (wing_span * 0.24),
                -0.08,
                wing_color[0] * 0.88,
                wing_color[1] * 0.92,
                wing_color[2] * 0.88,
            )
            try:
                membrane.setColorScale(1.0, 1.0, 1.0, 0.64)
            except Exception:
                pass
        for idx, wing_tip in enumerate((wing_l_tip, wing_r_tip)):
            side_sign = -1.0 if idx == 0 else 1.0
            build_mannequin(
                wing_tip,
                f"dracolid_wing_claw_{idx}_{npc_id}",
                0.05,
                0.12,
                0.16,
                side_sign * 0.04,
                side_sign * 0.10,
                0.0,
                horn_color[0],
                horn_color[1],
                horn_color[2],
            )

        tail_parent = (hips or actor).attachNewNode(f"dracolid_tail_{npc_id}")
        tail_parent.setPos(0.0, -0.24, 0.92)
        tail_segments = max(3, int(spec.get("tail_segments", 4) or 4))
        tail_joints = []
        chain = tail_parent
        for idx in range(tail_segments):
            taper = 1.0 - (idx * 0.14)
            seg = build_mannequin(
                chain,
                f"dracolid_tail_seg_{idx}_{npc_id}",
                max(0.05, 0.18 * taper),
                max(0.05, 0.22 * taper),
                max(0.10, 0.46 * taper),
                0.0,
                -0.18,
                -0.06,
                body_color[0] * 0.82,
                body_color[1] * 0.84,
                body_color[2] * 0.82,
            )
            chain = seg.attachNewNode(f"dracolid_tail_joint_{idx}_{npc_id}")
            chain.setPos(0.0, -0.23, -0.02)
            tail_joints.append(chain)

        try:
            root.setTwoSided(True)
        except Exception:
            pass
        ensure_model_visual_defaults(
            root,
            force_two_sided=True,
            debug_label=f"npc:{npc_id}:dracolid",
        )
        return {
            "root": root,
            "wing_l": wing_l,
            "wing_r": wing_r,
            "wing_l_mid": wing_l_mid,
            "wing_r_mid": wing_r_mid,
            "wing_l_tip": wing_l_tip,
            "wing_r_tip": wing_r_tip,
            "tail_joints": tail_joints,
            "phase": self._rng.uniform(0.0, math.tau),
        }

    def _update_dracolid_visual(self, unit, dt, moving):
        visual = unit.get("dracolid_visual")
        if not isinstance(visual, dict):
            return
        phase = float(visual.get("phase", 0.0) or 0.0) + (max(0.0, float(dt)) * (5.8 if moving else 2.1))
        visual["phase"] = phase
        flap = math.sin(phase)
        wing_amp = 22.0 if moving else 8.0
        wing_l = visual.get("wing_l")
        wing_r = visual.get("wing_r")
        wing_l_mid = visual.get("wing_l_mid")
        wing_r_mid = visual.get("wing_r_mid")
        wing_l_tip = visual.get("wing_l_tip")
        wing_r_tip = visual.get("wing_r_tip")
        if wing_l:
            try:
                wing_l.setP(-4.0 + (wing_amp * flap))
            except Exception:
                pass
        if wing_r:
            try:
                wing_r.setP(4.0 - (wing_amp * flap))
            except Exception:
                pass
        if wing_l_mid:
            try:
                wing_l_mid.setP(-6.0 + ((wing_amp * 0.62) * flap))
            except Exception:
                pass
        if wing_r_mid:
            try:
                wing_r_mid.setP(6.0 - ((wing_amp * 0.62) * flap))
            except Exception:
                pass
        if wing_l_tip:
            try:
                wing_l_tip.setP(-4.0 + ((wing_amp * 0.38) * flap))
            except Exception:
                pass
        if wing_r_tip:
            try:
                wing_r_tip.setP(4.0 - ((wing_amp * 0.38) * flap))
            except Exception:
                pass

        tail_joints = visual.get("tail_joints", [])
        for idx, joint in enumerate(tail_joints):
            if not joint:
                continue
            sway = math.sin((phase * 0.72) - (idx * 0.45)) * (10.0 / float(idx + 1))
            try:
                joint.setH(sway)
            except Exception:
                continue

    def _build_actor(self, npc_id, payload, appearance):
        candidates = []
        for raw in (
            (appearance or {}).get("model"),
            (payload or {}).get("model"),
            self._default_model,
        ):
            path = prefer_bam_path(str(raw or "").strip().replace("\\", "/"))
            if not path:
                continue
            if path not in candidates:
                candidates.append(path)

        anim_map = self._base_anims
        raw_anims = (appearance or {}).get("animations")
        if not isinstance(raw_anims, dict):
            raw_anims = (payload or {}).get("animations")
        if isinstance(raw_anims, dict) and raw_anims:
            anim_map = {
                str(k): prefer_bam_path(str(v))
                for k, v in raw_anims.items()
                if str(k).strip() and str(v).strip()
            }
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
        # Precise check for Sandbox Ground (Z=5)
        world = getattr(self.app, "world", None)
        if world and (getattr(world, "world_type", "") == "ultimate_sandbox" or str(getattr(world, "active_location", "")).lower() == "ultimate_sandbox"):
             return 5.0

        if world and hasattr(world, "_th"):
            try:
                h = float(world._th(float(x), float(y)))
                return h if h > -200 else float(fallback)
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

    def _build_core_runtime_context(self, dt, world_state):
        if not self._core_runtime or not hasattr(gc, "NpcRuntimeContext"):
            return None
        context = gc.NpcRuntimeContext()
        context.dt = float(dt)
        context.weather = str(world_state.get("weather", "") or "")
        context.phase = str(world_state.get("phase", "") or "")
        context.isNight = bool(world_state.get("is_night", False))
        context.visibility = float(world_state.get("visibility", 1.0) or 1.0)
        return context

    def _build_core_runtime_unit(self, unit, actor):
        runtime_unit = gc.NpcRuntimeUnit()
        runtime_unit.id = int(zlib.crc32(str(unit.get("id", "")).encode("utf-8")) & 0x7FFFFFFF)
        pos = actor.getPos(self.app.render)
        target = unit.get("target", unit.get("home", Vec3(0, 0, 0)))
        home = unit.get("home", Vec3(0, 0, 0))
        runtime_unit.home = gc.Vec3(float(home.x), float(home.y), float(home.z))
        runtime_unit.target = gc.Vec3(float(target.x), float(target.y), float(target.z))
        runtime_unit.actorPos = gc.Vec3(float(pos.x), float(pos.y), float(pos.z))
        runtime_unit.baseWalkSpeed = float(unit.get("base_walk_speed", unit.get("walk_speed", 1.5)) or 1.5)
        runtime_unit.walkSpeed = float(unit.get("walk_speed", runtime_unit.baseWalkSpeed) or runtime_unit.baseWalkSpeed)
        runtime_unit.baseWanderRadius = float(unit.get("base_wander_radius", unit.get("wander_radius", 0.0)) or 0.0)
        runtime_unit.wanderRadius = float(unit.get("wander_radius", runtime_unit.baseWanderRadius) or runtime_unit.baseWanderRadius)
        runtime_unit.baseIdleMin = float(unit.get("base_idle_min", unit.get("idle_min", 1.5)) or 1.5)
        runtime_unit.baseIdleMax = float(unit.get("base_idle_max", unit.get("idle_max", 4.2)) or 4.2)
        runtime_unit.idleMin = float(unit.get("idle_min", runtime_unit.baseIdleMin) or runtime_unit.baseIdleMin)
        runtime_unit.idleMax = float(unit.get("idle_max", runtime_unit.baseIdleMax) or runtime_unit.baseIdleMax)
        runtime_unit.idleTimer = float(unit.get("idle_timer", 1.0) or 1.0)
        runtime_unit.suspicion = float(unit.get("suspicion", 0.0) or 0.0)
        runtime_unit.alerted = bool(unit.get("alerted", False))
        runtime_unit.detectedPlayer = bool(unit.get("detected_player", False))
        runtime_unit.role = str(unit.get("role", "") or "")
        runtime_unit.activity = str(unit.get("activity", "") or "")
        runtime_unit.anim = str(unit.get("anim", "idle") or "idle")
        runtime_unit.actionRoll = float(self._rng.random())
        runtime_unit.targetAngle = float(self._rng.uniform(0.0, math.tau))
        runtime_unit.targetDistance01 = float(self._rng.random())
        runtime_unit.idleReset01 = float(self._rng.random())
        return runtime_unit

    def _apply_core_runtime_result(self, unit, actor, runtime_unit):
        unit["walk_speed"] = float(runtime_unit.walkSpeed)
        unit["wander_radius"] = float(runtime_unit.wanderRadius)
        unit["idle_min"] = float(runtime_unit.idleMin)
        unit["idle_max"] = float(runtime_unit.idleMax)
        unit["idle_timer"] = float(runtime_unit.idleTimer)
        if bool(runtime_unit.targetChanged):
            tx = float(runtime_unit.target.x)
            ty = float(runtime_unit.target.y)
            tz = self._ground_height(tx, ty, fallback=float(runtime_unit.home.z))
            unit["target"] = Vec3(tx, ty, tz)
        if bool(runtime_unit.moving):
            px = float(runtime_unit.actorPos.x)
            py = float(runtime_unit.actorPos.y)
            pz = self._ground_height(px, py, fallback=float(runtime_unit.actorPos.z))
            actor.setPos(px, py, pz)
            actor.setH(float(runtime_unit.desiredHeading))
            desired_anim = str(runtime_unit.desiredAnim or "walk")
            if unit.get("anim") != desired_anim:
                self._play_anim(actor, desired_anim, loop=True)
                unit["anim"] = desired_anim
            try:
                actor.setPlayRate(float(runtime_unit.desiredPlayRate), desired_anim)
            except Exception:
                pass
            self._update_dracolid_visual(unit, 0.0, moving=True)
            return

        desired_anim = str(runtime_unit.desiredAnim or "idle")
        if unit.get("anim") != desired_anim:
            self._play_anim(actor, desired_anim, loop=True)
            unit["anim"] = desired_anim
        self._update_dracolid_visual(unit, 0.0, moving=False)

    def _update_with_core_runtime(self, dt, world_state, stealth_state):
        if not self._core_runtime or not hasattr(self._core_runtime, "updateUnits"):
            return False
        if not self._core_runtime_announced:
            logger.info("[NPCManager] Crowd runtime path: C++ batch update")
            self._core_runtime_announced = True

        context = self._build_core_runtime_context(dt, world_state)
        if context is None:
            return False

        active = []
        runtime_units = []
        for unit in self.units:
            actor = unit.get("actor")
            if not actor:
                continue
            self._update_player_detection(unit, dt, stealth_state if isinstance(stealth_state, dict) else {})
            self._update_activity_state(unit, world_state, dt)
            active.append((unit, actor))
            runtime_units.append(self._build_core_runtime_unit(unit, actor))

        if not runtime_units:
            return True

        try:
            updated_units = self._core_runtime.updateUnits(runtime_units, context)
        except Exception as exc:
            logger.warning(f"[NPCManager] C++ runtime update failed, using Python loop: {exc}")
            return False

        for (unit, actor), runtime_unit in zip(active, updated_units):
            self._apply_core_runtime_result(unit, actor, runtime_unit)
        return True

    def _update_python(self, dt, world_state=None, stealth_state=None):
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
                self._update_dracolid_visual(unit, dt, moving=True)
                unit["idle_timer"] = self._rng.uniform(unit["idle_min"], unit["idle_max"])
                continue

            unit["idle_timer"] -= dt
            if unit["anim"] != "idle":
                self._play_anim(actor, "idle", loop=True)
                unit["anim"] = "idle"
            self._update_dracolid_visual(unit, dt, moving=False)

            if unit["idle_timer"] <= 0.0:
                self._pick_next_target(unit)
                unit["idle_timer"] = self._rng.uniform(unit["idle_min"], unit["idle_max"])

    def update(self, dt, world_state=None, stealth_state=None):
        dt = max(0.0, float(dt))
        ws = world_state if isinstance(world_state, dict) else {}
        if self._update_with_core_runtime(dt, ws, stealth_state):
            return
        self._update_python(dt, ws, stealth_state)
