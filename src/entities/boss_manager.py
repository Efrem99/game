"""Procedural enemy roster manager: golems (boss), elementals, shadows, goblins."""

import hashlib
import json
import math
import random
from pathlib import Path

from direct.actor.Actor import Actor
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import CardMaker, LColor, TransparencyAttrib, Vec3

from render.fx_policy import FIRE_SPRITE_TEXTURE_CANDIDATES, load_optional_texture
from render.model_visuals import ensure_model_visual_defaults
from utils.asset_pathing import prefer_bam_path
from utils.logger import logger

try:
    import game_core as gc

    HAS_CORE = True
except ImportError:
    gc = None
    HAS_CORE = False


def _safe_read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def should_apply_enemy_visual_defaults(node_role):
    """FX cards (telegraph rings) should bypass model fallback patching."""
    role = str(node_role or "").strip().lower()
    return role not in {"telegraph", "ring", "fx"}


class EnemyUnit:
    def __init__(self, app, cfg):
        self.app = app
        self.render = app.render
        self.loader = app.loader
        self.cfg = cfg if isinstance(cfg, dict) else {}
        self._rng = random.Random(abs(hash(str(self.cfg.get("id", "enemy")))) & 0xFFFFFFFF)

        self.id = str(self.cfg.get("id") or "enemy").strip().lower() or "enemy"
        self.kind = str(self.cfg.get("kind") or "goblin").strip().lower() or "goblin"
        self.name = str(self.cfg.get("name") or self.id).strip() or self.id
        self.is_boss = bool(self.cfg.get("is_boss", self.kind == "golem"))

        self.root = None
        self.actor = None
        self.nodes = {}
        self.fire_origin = None
        self.proxy = None
        self._anim_map = {}
        self._anim_active_clip = ""
        self._anim_active_state = ""
        self._damage_flash = 0.0
        self._last_hp_seen = 0.0

        self.state = "idle"
        self.state_time = 0.0
        self.state_lock = 0.0
        self.attack_cd = 0.0
        self._attack_windup = 0.0
        self._pending_hit_react = 0.0
        self.engaged_until = 0.0
        self._is_engaged = False
        self.melee_applied = False
        self.fire_particles = []
        self.fire_emit_acc = 0.0
        self.fire_tick_acc = 0.0
        self.last_fire_sfx = -999.0
        self._fire_sprite_tex = load_optional_texture(self.loader, FIRE_SPRITE_TEXTURE_CANDIDATES)

        self.max_hp = max(1.0, self._stat("max_hp", 180.0))
        self.hp = self.max_hp
        self._last_hp_seen = self.hp
        self.armor = max(0.0, self._stat("armor", 2.0))
        self._telegraph_fx = self._parse_telegraph_fx()
        self._phase_rules = self._parse_phase_rules()
        self._phase_cursor = 0
        self._phase_damage_mul = 1.0
        self._phase_speed_mul = 1.0
        self._phase_telegraph_mul = 1.0
        self._phase_cooldown_mul = 1.0
        self._phase_anim_rate_mul = 1.0

        self.spawn()

    @property
    def is_alive(self):
        return self.hp > 0.0

    @property
    def is_engaged(self):
        return bool(self._is_engaged and self.is_alive)

    def _stat(self, key, default):
        stats = self.cfg.get("stats", {})
        if not isinstance(stats, dict):
            return float(default)
        try:
            return float(stats.get(key, default))
        except Exception:
            return float(default)

    def _ai(self, key, default):
        ai = self.cfg.get("ai", {})
        if not isinstance(ai, dict):
            return float(default)
        try:
            return float(ai.get(key, default))
        except Exception:
            return float(default)

    def _spawn_pos(self):
        p = self.cfg.get("spawn_point", [0.0, 0.0, 0.0])
        if not isinstance(p, (list, tuple)) or len(p) < 3:
            p = [0.0, 0.0, 0.0]
        x, y, z = float(p[0]), float(p[1]), float(p[2])
        world = getattr(self.app, "world", None)
        if world and hasattr(world, "_th"):
            try:
                z = float(world._th(x, y)) + float(self.cfg.get("ground_offset", 1.2))
            except Exception:
                pass
        return Vec3(x, y, z)

    def _apply_python_only_visual_fallback(self, node, debug_label="enemy"):
        if HAS_CORE or node is None:
            return
        is_animated_actor = False
        try:
            is_animated_actor = isinstance(node, Actor)
        except Exception:
            is_animated_actor = False
        if not is_animated_actor:
            is_animated_actor = all(
                hasattr(node, attr) for attr in ("getAnimNames", "loop", "play")
            )

        # Do not disable shaders on skinned actors in Python mode.
        if not is_animated_actor:
            try:
                node.setShaderOff(1002)
            except Exception:
                pass
        try:
            node.setColorScale(1.0, 1.0, 1.0, 1.0)
        except Exception:
            pass
        try:
            node.setTwoSided(True)
        except Exception:
            pass

    def _piece(self, name, parent, model, scale, pos, color):
        np = self.loader.loadModel(prefer_bam_path(model))
        np.reparentTo(parent)
        np.setName(name)
        np.setScale(*scale)
        np.setPos(*pos)
        np.setColor(LColor(*color))
        ensure_model_visual_defaults(np, apply_skin=False, force_two_sided=True, debug_label=f"enemy:{self.id}:{name}")
        self._apply_python_only_visual_fallback(np, debug_label=f"enemy:{self.id}:{name}")
        return np

    def _build_external_model(self):
        primary_path = str(self.cfg.get("model", "")).strip().replace("\\", "/")
        fallback_path = self._fallback_model_for_kind()
        candidate_paths = []
        if primary_path:
            candidate_paths.append(primary_path)
        if fallback_path and fallback_path not in candidate_paths:
            candidate_paths.append(fallback_path)
        if not candidate_paths:
            return False

        sc = float(self.cfg.get("scale", 1.0) or 1.0)
        self.actor = None
        self._anim_map = {}
        self._anim_active_clip = ""
        self._anim_active_state = ""
        prefer_actor = bool(self.cfg.get("use_actor", True))

        for path in candidate_paths:
            resolved = prefer_bam_path(path)
            if not Path(resolved).exists():
                continue
            if self._try_load_external_model(resolved, sc, prefer_actor):
                if path != primary_path:
                    logger.warning(f"[Enemy] Using fallback model for '{self.id}': {resolved}")
                return True
        return False

    def _fallback_model_for_kind(self):
        fallback = {
            "golem": "assets/models/enemies/golem_boss.glb",
            "fire_elemental": "assets/models/enemies/fire_elemental.glb",
            "shadow": "assets/models/enemies/shadow_stalker.glb",
            "goblin": "assets/models/enemies/goblin_raider.glb",
        }
        return str(fallback.get(self.kind, "") or "").strip()

    def _try_load_external_model(self, path, sc, prefer_actor):
        if prefer_actor:
            try:
                actor = Actor(path)
                actor.reparentTo(self.root)
                actor.setScale(sc)
                ensure_model_visual_defaults(
                    actor,
                    apply_skin=True,
                    force_two_sided=True,
                    debug_label=f"enemy_actor:{self.id}",
                )
                self._apply_python_only_visual_fallback(actor, debug_label=f"enemy_actor:{self.id}")
                self.actor = actor
                self._anim_map = self._build_actor_anim_map(actor)
                self.fire_origin = actor.attachNewNode("origin")
                self.fire_origin.setPos(0.0, 1.0 * sc, 1.1 * sc)
                self.nodes = {"model": actor}
                return True
            except Exception as exc:
                logger.debug(f"[Enemy] Actor load failed '{path}', fallback model: {exc}")

        try:
            model = self.loader.loadModel(path)
        except Exception as exc:
            logger.warning(f"[Enemy] Failed to load external model '{path}': {exc}")
            return False
        if not model or model.isEmpty():
            return False
        model.reparentTo(self.root)
        model.setScale(sc)
        ensure_model_visual_defaults(
            model,
            apply_skin=False,
            force_two_sided=True,
            debug_label=f"enemy_model:{self.id}",
        )
        self._apply_python_only_visual_fallback(model, debug_label=f"enemy_model:{self.id}")
        self.fire_origin = model.attachNewNode("origin")
        self.fire_origin.setPos(0.0, 1.0 * sc, 1.1 * sc)
        self.nodes = {"model": model}
        return True

    def _build_actor_anim_map(self, actor):
        mapping = {}
        try:
            available = {str(n).lower(): str(n) for n in actor.getAnimNames()}
        except Exception:
            available = {}

        def resolve_clip_name(requested):
            token = str(requested or "").strip()
            if not token:
                return ""
            low = token.lower()
            if low in available:
                return available[low]
            for key, real in available.items():
                if key.endswith(low):
                    return real
            for key, real in available.items():
                if low in key:
                    return real
            return ""

        cfg_map = self.cfg.get("animations", {})
        if isinstance(cfg_map, dict):
            for state, clip in cfg_map.items():
                s_key = str(state or "").strip().lower()
                if not s_key:
                    continue
                resolved = resolve_clip_name(clip)
                if resolved:
                    mapping[s_key] = resolved

        if mapping:
            return mapping

        def find_clip(tokens):
            for low, real in available.items():
                if all(token in low for token in tokens):
                    return real
            return ""

        mapping["idle"] = find_clip(["idle"]) or find_clip(["stand"])
        mapping["chase"] = find_clip(["run"]) or find_clip(["walk"]) or find_clip(["move"])
        mapping["telegraph"] = find_clip(["weapon"]) or find_clip(["no"]) or find_clip(["wave"])
        mapping["attack"] = find_clip(["attack"]) or find_clip(["slash"]) or find_clip(["hit"])
        mapping["recover"] = find_clip(["yes"]) or find_clip(["idle"])
        mapping["hit"] = find_clip(["hitreact"]) or find_clip(["hit"])
        mapping["dead"] = find_clip(["death"]) or find_clip(["die"])
        return {k: v for k, v in mapping.items() if v}

    def _anim_rate_for_state(self, state):
        state_key = str(state or "").strip().lower()
        cfg_rates = self.cfg.get("animation_rates", {})
        if isinstance(cfg_rates, dict) and state_key in cfg_rates:
            try:
                return _clamp(float(cfg_rates.get(state_key, 1.0)), 0.4, 2.2)
            except Exception:
                pass
        defaults = {
            "idle": 1.0,
            "chase": 1.08,
            "telegraph": 1.0,
            "attack": 1.16,
            "recover": 0.95,
            "hit": 1.0,
            "dead": 1.0,
        }
        value = float(defaults.get(state_key, 1.0))
        if state_key in {"chase", "telegraph", "attack"}:
            value *= self._phase_anim_rate_mul
        return _clamp(value, 0.4, 2.2)

    def _sync_actor_animation(self):
        if not self.actor or not self._anim_map:
            return
        state_key = str(self.state or "").strip().lower()
        clip = self._anim_map.get(self.state)
        if not clip:
            if self.state == "recover":
                clip = self._anim_map.get("idle")
            elif self.state == "telegraph":
                clip = self._anim_map.get("attack") or self._anim_map.get("idle")
            elif self.state == "hit":
                clip = self._anim_map.get("recover") or self._anim_map.get("idle")
        if not clip:
            clip = self._anim_map.get("idle")
        if not clip:
            return
        loop = self.state not in {"telegraph", "attack", "recover", "hit", "dead"}
        if self._anim_active_clip == clip and self._anim_active_state == state_key:
            return
        self._anim_active_clip = clip
        self._anim_active_state = state_key
        try:
            self.actor.setPlayRate(self._anim_rate_for_state(self.state), clip)
        except Exception:
            pass
        try:
            if loop:
                self.actor.loop(clip)
            else:
                self.actor.play(clip)
        except Exception:
            pass

    def _build_golem(self):
        body = self._piece("body", self.root, "models/misc/rgbCube", (2.2, 1.8, 2.8), (0, 0, 0), (0.33, 0.34, 0.38, 1))
        core = self._piece("core", body, "models/misc/sphere", (0.45, 0.45, 0.45), (0, 0.92, 0.1), (0.25, 0.85, 1.0, 1))
        arm_l = body.attachNewNode("arm_l")
        arm_l.setPos(-1.6, 0.0, 0.8)
        arm_r = body.attachNewNode("arm_r")
        arm_r.setPos(1.6, 0.0, 0.8)
        self._piece("arm_l_mesh", arm_l, "models/misc/rgbCube", (0.62, 0.62, 2.1), (0, 0, -0.85), (0.28, 0.28, 0.34, 1))
        self._piece("arm_r_mesh", arm_r, "models/misc/rgbCube", (0.62, 0.62, 2.1), (0, 0, -0.85), (0.28, 0.28, 0.34, 1))
        self._piece("head", body, "models/misc/rgbCube", (1.0, 0.9, 0.9), (0, 0, 1.9), (0.4, 0.42, 0.46, 1))
        self.fire_origin = core.attachNewNode("origin")
        self.fire_origin.setPos(0, 0.7, 0.0)
        self.nodes = {"body": body, "core": core, "arm_l": arm_l, "arm_r": arm_r}

    def _build_fire_elemental(self):
        core = self._piece("core", self.root, "models/misc/sphere", (1.5, 1.1, 1.8), (0, 0, 0), (1.0, 0.35, 0.05, 0.95))
        halo = self._piece("halo", core, "models/misc/sphere", (0.55, 0.55, 0.55), (0, 0.9, 0.2), (1.0, 0.8, 0.2, 0.9))
        cm = CardMaker("flame_skirt")
        cm.setFrame(-1.5, 1.5, 0.0, 2.8)
        skirt = core.attachNewNode(cm.generate())
        skirt.setP(90)
        skirt.setTwoSided(True)
        skirt.setTransparency(TransparencyAttrib.MAlpha)
        skirt.setColorScale(1.0, 0.42, 0.08, 0.58)
        skirt.setLightOff(1)
        ensure_model_visual_defaults(skirt, apply_skin=False, force_two_sided=True, debug_label=f"enemy:{self.id}:flame")
        self.fire_origin = halo.attachNewNode("origin")
        self.fire_origin.setPos(0, 0.5, 0.0)
        self.nodes = {"core": core, "halo": halo, "skirt": skirt}

    def _build_shadow(self):
        body = self._piece("body", self.root, "models/misc/sphere", (1.2, 0.9, 1.9), (0, 0, 0), (0.05, 0.05, 0.08, 0.95))
        hood = self._piece("hood", body, "models/misc/sphere", (1.0, 0.8, 0.75), (0, 0.2, 1.25), (0.02, 0.02, 0.04, 1))
        eye_l = self._piece("eye_l", hood, "models/misc/sphere", (0.08, 0.08, 0.08), (-0.2, 0.48, 0.1), (0.4, 0.8, 1, 1))
        eye_r = self._piece("eye_r", hood, "models/misc/sphere", (0.08, 0.08, 0.08), (0.2, 0.48, 0.1), (0.4, 0.8, 1, 1))
        self.fire_origin = hood.attachNewNode("origin")
        self.fire_origin.setPos(0, 0.58, 0.1)
        self.nodes = {"body": body, "hood": hood, "eye_l": eye_l, "eye_r": eye_r}

    def _build_goblin(self):
        body = self._piece("body", self.root, "models/misc/rgbCube", (0.9, 0.65, 1.3), (0, 0, 0), (0.28, 0.68, 0.20, 1))
        head = self._piece("head", body, "models/misc/sphere", (0.7, 0.65, 0.6), (0, 0.15, 1.0), (0.30, 0.75, 0.24, 1))
        arm_l = self._piece("arm_l", body, "models/misc/rgbCube", (0.2, 0.2, 0.9), (-0.62, 0, 0.2), (0.22, 0.57, 0.16, 1))
        arm_r = self._piece("arm_r", body, "models/misc/rgbCube", (0.2, 0.2, 0.9), (0.62, 0, 0.2), (0.22, 0.57, 0.16, 1))
        self.fire_origin = head.attachNewNode("origin")
        self.fire_origin.setPos(0, 0.45, 0.05)
        self.nodes = {"body": body, "head": head, "arm_l": arm_l, "arm_r": arm_r}

    def spawn(self):
        if self.root and not self.root.isEmpty():
            self.root.removeNode()
        self.root = self.render.attachNewNode(f"enemy_{self.id}")
        self.root.setPos(self._spawn_pos())
        self.root.setH(float(self.cfg.get("heading", 180.0) or 180.0))
        self.nodes = {}
        if not self._build_external_model():
            if self.kind == "golem":
                self._build_golem()
            elif self.kind == "fire_elemental":
                self._build_fire_elemental()
            elif self.kind == "shadow":
                self._build_shadow()
            else:
                self._build_goblin()
        if should_apply_enemy_visual_defaults("model"):
            ensure_model_visual_defaults(
                self.root,
                apply_skin=False,
                force_two_sided=True,
                debug_label=f"enemy_root:{self.id}",
            )
            self._apply_python_only_visual_fallback(self.root, debug_label=f"enemy_root:{self.id}")
        self._build_telegraph_ring()
        self._ensure_proxy()
        logger.info(f"[Enemy] Spawned '{self.name}' kind='{self.kind}' boss={self.is_boss}")

    def _build_telegraph_ring(self):
        self.nodes.pop("telegraph", None)
        cm = CardMaker(f"{self.id}_telegraph")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        ring = self.root.attachNewNode(cm.generate())
        ring.setP(-90)
        ring.setPos(0.0, 0.0, 0.06)
        ring.setTransparency(TransparencyAttrib.MAlpha)
        ring.setLightOff(1)
        ring.setShaderOff(1002)
        ring.setTwoSided(True)
        ring.setDepthTest(False)
        ring.setDepthWrite(False)
        ring.setBin("transparent", 30)
        try:
            tex = self.loader.loadTexture("assets/textures/flare.png")
            if tex:
                ring.setTexture(tex, 1)
        except Exception:
            pass
        ring.setColorScale(*self._fx_color("idle_color", (1.0, 0.25, 0.15, 0.0)))
        min_scale = self._fx_float("min_scale", 1.2, 0.2, 50.0)
        ring.setScale(max(min_scale, self._stat("attack_range", 2.4)))
        # Keep authored alpha values for telegraph and do not force opaque fallback color scale.
        self.nodes["telegraph"] = ring

    def _apply_visual_state(self, dt):
        if not self.root or self.root.isEmpty():
            return
        self._damage_flash = max(0.0, float(self._damage_flash) - max(0.0, dt))
        if self._damage_flash > 0.0:
            self.root.setColorScale(1.22, 0.84, 0.84, 1.0)
        else:
            self.root.setColorScale(1.0, 1.0, 1.0, 1.0)

        ring = self.nodes.get("telegraph")
        if not ring:
            return

        # Keep telegraph visuals readable without turning every enemy into a moving square.
        # "show_engaged_ring" can be enabled per unit config for debug/high-clarity testing.
        show_engaged_ring = bool(self.cfg.get("show_engaged_ring", False))
        active_ring = self.state in {"telegraph", "attack", "recover", "hit"} or (
            show_engaged_ring and self._is_engaged
        )
        if active_ring:
            ring.show()
        else:
            ring.hide()
            return

        if self.state == "telegraph":
            windup = max(0.08, float(self._attack_windup or 0.22))
            t = max(0.0, min(1.0, self.state_time / windup))
            a0 = self._fx_float("telegraph_alpha_start", 0.16, 0.0, 1.0)
            a1 = self._fx_float("telegraph_alpha_end", 0.44, 0.0, 1.0)
            alpha = a0 + ((a1 - a0) * t)
            color = self._fx_color("telegraph_color", (1.0, 0.78, 0.26, alpha))
            ring.setColorScale(color[0], color[1], color[2], alpha)
            scale = max(self._fx_float("min_scale", 1.2, 0.2, 50.0), self._stat("attack_range", 2.4))
            s0 = self._fx_float("telegraph_scale_start", 0.86, 0.1, 3.0)
            s1 = self._fx_float("telegraph_scale_end", 1.02, 0.1, 3.0)
            ring.setScale(scale * (s0 + ((s1 - s0) * t)))
        elif self.state == "attack":
            pulse_speed = self._fx_float("attack_pulse_speed", 16.0, 0.1, 64.0)
            pulse = 0.5 + (0.5 * math.sin(globalClock.getFrameTime() * pulse_speed))
            a_base = self._fx_float("attack_alpha_base", 0.36, 0.0, 1.0)
            a_pulse = self._fx_float("attack_alpha_pulse", 0.24, 0.0, 1.0)
            alpha = a_base + (a_pulse * pulse)
            color = self._fx_color("attack_color", (1.0, 0.22, 0.15, alpha))
            ring.setColorScale(color[0], color[1], color[2], alpha)
            scale = max(self._fx_float("min_scale", 1.2, 0.2, 50.0), self._stat("attack_range", 2.4))
            s_mul = self._fx_float("attack_scale_pulse", 0.08, 0.0, 1.0)
            ring.setScale(scale * (1.0 + (s_mul * math.sin(globalClock.getFrameTime() * 9.0))))
        elif self.state == "recover":
            ring.setColorScale(*self._fx_color("recover_color", (1.0, 0.55, 0.18, 0.16)))
            ring.setScale(max(self._fx_float("min_scale", 1.2, 0.2, 50.0), self._stat("attack_range", 2.4)) * 0.92)
        elif self.state == "hit":
            ring.setColorScale(*self._fx_color("hit_color", (0.82, 0.92, 1.0, 0.24)))
            ring.setScale(max(self._fx_float("min_scale", 1.2, 0.2, 50.0), self._stat("attack_range", 2.4)) * 0.88)
        elif self._is_engaged:
            ring.setColorScale(*self._fx_color("engaged_color", (0.22, 0.72, 1.0, 0.14)))
            ring.setScale(max(self._fx_float("min_scale", 1.2, 0.2, 50.0), self._stat("attack_range", 2.4)) * 0.9)
        else:
            ring.setColorScale(*self._fx_color("idle_color", (1.0, 0.2, 0.15, 0.0)))

    def _ensure_proxy(self):
        if not HAS_CORE or self.proxy is not None:
            return
        proxies = getattr(self.app, "enemy_proxies", None)
        if not isinstance(proxies, list):
            return
        try:
            e = gc.Enemy()
            digest = hashlib.md5(self.id.encode("utf-8")).digest()
            e.id = int.from_bytes(digest[:4], "little", signed=False) & 0x7FFFFFFF
            e.health = float(self.hp)
            e.armor = float(self.armor)
            e.alive = True
            e.blocking = False
            e.pos = gc.Vec3(0, 0, 0)
            e.vel = gc.Vec3(0, 0, 0)
            proxies.append(e)
            self.proxy = e
        except Exception as exc:
            logger.warning(f"[Enemy] Proxy create failed '{self.id}': {exc}")
            self.proxy = None

    def _sync_proxy_from_core(self):
        if not self.proxy:
            return
        prev = float(self.hp)
        try:
            self.hp = max(0.0, min(self.max_hp, float(self.proxy.health)))
        except Exception:
            pass
        if self.hp < (prev - 0.5):
            self._damage_flash = max(self._damage_flash, 0.18)
            self._pending_hit_react = max(self._pending_hit_react, 0.2)
        self._last_hp_seen = self.hp

    def _sync_proxy_to_core(self):
        if not self.proxy or not self.root:
            return
        try:
            p = self.root.getPos(self.render)
            self.proxy.pos = gc.Vec3(float(p.x), float(p.y), float(p.z))
            self.proxy.vel = gc.Vec3(0.0, 0.0, 0.0)
            self.proxy.health = float(self.hp)
            self.proxy.armor = float(self.armor)
            self.proxy.blocking = bool(self.kind == "golem" and self.state == "attack" and self.state_time < 0.2)
            self.proxy.alive = bool(self.is_alive)
        except Exception:
            pass

    def _emit_fire_particle(self):
        if not self.fire_origin:
            return
        cm = CardMaker(f"{self.id}_fire")
        cm.setFrame(-0.12, 0.12, -0.12, 0.12)
        node = self.render.attachNewNode(cm.generate())
        node.setBillboardPointEye()
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setLightOff(1)
        node.setDepthWrite(False)
        if self._fire_sprite_tex:
            try:
                node.setTexture(self._fire_sprite_tex, 1)
            except Exception:
                pass
        try:
            node.setShaderOff(1001)
        except Exception:
            pass
        src = self.fire_origin.getPos(self.render)
        fwd = self.fire_origin.getQuat(self.render).getForward()
        vel = (fwd + Vec3(self._rng.uniform(-0.16, 0.16), self._rng.uniform(-0.08, 0.12), self._rng.uniform(-0.12, 0.09))) * self._rng.uniform(8.0, 14.0)
        life = self._rng.uniform(0.26, 0.56)
        node.setPos(src)
        if self.kind == "shadow":
            node.setColorScale(0.25, 0.8, 1.0, 0.92)
        else:
            node.setColorScale(1.0, 0.45, 0.1, 0.92)
        self.fire_particles.append({"node": node, "vel": vel, "life": life, "max": life, "s": self._rng.uniform(0.14, 0.28)})

    def _tick_fire_particles(self, dt):
        alive = []
        for it in self.fire_particles:
            n = it.get("node")
            if not n or n.isEmpty():
                continue
            life = float(it.get("life", 0.0)) - dt
            if life <= 0:
                n.removeNode()
                continue
            vel = it.get("vel", Vec3(0, 0, 0))
            n.setPos(n.getPos(self.render) + vel * dt)
            vel.z += 1.4 * dt
            it["vel"] = vel
            it["life"] = life
            r = max(0.0, min(1.0, life / max(0.01, float(it.get("max", 1.0)))))
            n.setScale(float(it.get("s", 0.2)) * (1.0 + (1.7 * (1.0 - r))))
            n.setAlphaScale(r)
            alive.append(it)
        self.fire_particles = alive

    def _animate(self):
        t = globalClock.getFrameTime()
        if self.kind == "golem":
            core = self.nodes.get("core")
            arm_l = self.nodes.get("arm_l")
            arm_r = self.nodes.get("arm_r")
            if core:
                core.setScale(0.45 + (math.sin(t * 2.0) * 0.05))
            swing = math.sin(t * 4.0) * (28.0 if self.state == "attack" else 8.0)
            if arm_l:
                arm_l.setP(-16.0 - swing)
            if arm_r:
                arm_r.setP(-16.0 + swing)
        elif self.kind == "fire_elemental":
            core = self.nodes.get("core")
            halo = self.nodes.get("halo")
            skirt = self.nodes.get("skirt")
            if core:
                core.setScale(1.45 + (math.sin(t * 3.6) * 0.12), 1.08, 1.75 + (math.cos(t * 3.4) * 0.10))
            if halo:
                halo.setScale(0.55 + (math.sin(t * 5.2) * 0.08))
            if skirt:
                skirt.setR(math.sin(t * 1.8) * 2.8)
        elif self.kind == "shadow":
            hood = self.nodes.get("hood")
            if hood:
                hood.setH(math.sin(t * 1.2) * 7.0)
        else:
            arm_l = self.nodes.get("arm_l")
            arm_r = self.nodes.get("arm_r")
            swing = math.sin(t * 8.0) * (20.0 if self.state in {"chase", "attack"} else 4.0)
            if arm_l:
                arm_l.setP(swing)
            if arm_r:
                arm_r.setP(-swing)

    def _attack_mode(self):
        return "ranged" if self.kind in {"fire_elemental", "shadow"} else "melee"

    def _phase_time(self, key, default):
        value = _clamp(self._ai(key, default), 0.02, 8.0)
        if key == "telegraph_duration":
            value *= self._phase_telegraph_mul
        if key == "attack_cooldown":
            value *= self._phase_cooldown_mul
        return _clamp(value, 0.02, 8.0)

    def _parse_phase_rules(self):
        ai = self.cfg.get("ai", {})
        rows = ai.get("phase_transitions", []) if isinstance(ai, dict) else []
        if not isinstance(rows, list):
            return []
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                threshold = float(row.get("hp_threshold", 0.0))
            except Exception:
                continue
            if threshold <= 0.0 or threshold >= 1.0:
                continue
            out.append(dict(row, hp_threshold=threshold))
        out.sort(key=lambda item: float(item.get("hp_threshold", 0.0)), reverse=True)
        return out

    def _check_phase_transitions(self):
        if not self._phase_rules:
            return
        hp_ratio = float(self.hp) / max(1.0, float(self.max_hp))
        while self._phase_cursor < len(self._phase_rules):
            rule = self._phase_rules[self._phase_cursor]
            threshold = float(rule.get("hp_threshold", 0.0))
            if hp_ratio > threshold:
                break
            self._phase_cursor += 1
            self._apply_phase_rule(rule, phase_index=self._phase_cursor)

    def _apply_phase_rule(self, rule, phase_index=1):
        # Phase progression is additive and data-driven to avoid hardcoded behavior spikes.
        if bool(rule.get("enrage", False)):
            self._phase_damage_mul *= 1.18
            self._phase_speed_mul *= 1.08
            self._phase_telegraph_mul *= 0.90
            self._phase_cooldown_mul *= 0.88
            self._phase_anim_rate_mul *= 1.08
        try:
            self._phase_damage_mul *= max(0.5, float(rule.get("damage_mul", 1.0)))
            self._phase_speed_mul *= max(0.5, float(rule.get("speed_mul", 1.0)))
            self._phase_telegraph_mul *= max(0.35, float(rule.get("telegraph_mul", 1.0)))
            self._phase_cooldown_mul *= max(0.35, float(rule.get("cooldown_mul", 1.0)))
            self._phase_anim_rate_mul *= max(0.35, float(rule.get("anim_rate_mul", 1.0)))
        except Exception:
            pass

        rates = self.cfg.get("animation_rates", {})
        if not isinstance(rates, dict):
            rates = {}
        rates["attack"] = _clamp(float(rates.get("attack", 1.0)) * self._phase_anim_rate_mul, 0.45, 2.5)
        rates["telegraph"] = _clamp(float(rates.get("telegraph", 1.0)) * self._phase_anim_rate_mul, 0.45, 2.5)
        self.cfg["animation_rates"] = rates

        if self.state not in {"dead", "attack"}:
            telegraph = self._phase_time("telegraph_duration", self._ai("attack_windup", 0.22))
            self._attack_windup = telegraph
            self._change_state("telegraph", lock_duration=telegraph)

        logger.info(
            f"[EnemyPhase] {self.id} -> phase {int(phase_index)} "
            f"(hp<={float(rule.get('hp_threshold', 0.0)):.2f}) "
            f"damage={self._phase_damage_mul:.2f} speed={self._phase_speed_mul:.2f}"
        )

    def _phase_attack_window(self, start_key, end_key, fallback_start, fallback_end):
        start = self._phase_time(start_key, fallback_start)
        end = self._phase_time(end_key, fallback_end)
        if end < start:
            end = start
        return max(0.0, start), max(0.0, end)

    def _parse_telegraph_fx(self):
        fx = self.cfg.get("telegraph_fx", {})
        if not isinstance(fx, dict):
            return {}
        return dict(fx)

    def _fx_float(self, key, default, lo=0.0, hi=10.0):
        try:
            value = float(self._telegraph_fx.get(key, default))
        except Exception:
            value = float(default)
        return _clamp(value, lo, hi)

    def _fx_color(self, key, default):
        raw = self._telegraph_fx.get(key, default)
        if not isinstance(raw, (list, tuple)) or len(raw) < 3:
            raw = default
        alpha = default[3] if len(default) >= 4 else 1.0
        if len(raw) >= 4:
            try:
                alpha = float(raw[3])
            except Exception:
                alpha = default[3] if len(default) >= 4 else 1.0
        try:
            r = float(raw[0])
            g = float(raw[1])
            b = float(raw[2])
        except Exception:
            r, g, b = default[0], default[1], default[2]
        return (r, g, b, alpha)

    def _change_state(self, state_name, lock_duration=0.0, reset_time=True):
        target = str(state_name or "idle").strip().lower() or "idle"
        if target != self.state:
            self.state = target
            if reset_time:
                self.state_time = 0.0
        elif reset_time:
            self.state_time = 0.0
        self.state_lock = max(0.0, float(lock_duration))

    def update(self, dt, player_pos):
        if not self.root or self.root.isEmpty() or player_pos is None:
            return
        dt = max(0.0, float(dt))
        self._sync_proxy_from_core()
        self.state_time += dt
        if not self.is_alive:
            self._change_state("dead", lock_duration=0.0, reset_time=False)
            self._sync_proxy_to_core()
            return
        self._check_phase_transitions()

        pos = self.root.getPos(self.render)
        vec = player_pos - pos
        dist = vec.length()
        now = globalClock.getFrameTime()
        if dist <= self._stat("aggro_range", 18.0):
            self.engaged_until = max(self.engaged_until, now + self._ai("disengage_hold", 4.0))
        self._is_engaged = now < self.engaged_until

        self.state_lock = max(0.0, self.state_lock - dt)
        self.attack_cd = max(0.0, self.attack_cd - dt)

        if self._is_engaged:
            if vec.lengthSquared() > 1e-6:
                desired = math.degrees(math.atan2(vec.x, vec.y))
                current = self.root.getH(self.render)
                delta = ((desired - current + 180.0) % 360.0) - 180.0
                self.root.setH(self.render, current + _clamp(delta, -130.0 * dt, 130.0 * dt))

        if self.state_lock <= 0.0:
            if self.state == "telegraph":
                self._change_state("attack", lock_duration=self._phase_time("attack_duration", 0.8))
                self.melee_applied = False
                self.fire_tick_acc = 0.0
            elif self.state == "attack":
                self._change_state("recover", lock_duration=self._phase_time("recover_duration", 0.28))
            elif self.state in {"recover", "hit"}:
                self._change_state("chase" if self._is_engaged else "idle", lock_duration=0.0)

        if self.state_lock <= 0.0:
            attack_range = self._stat("attack_range", 2.6)
            if self._pending_hit_react > 0.0 and self.state not in {"telegraph", "attack"}:
                self._pending_hit_react = 0.0
                self._change_state("hit", lock_duration=self._phase_time("hit_react_duration", 0.22))
            elif self._is_engaged and dist <= attack_range and self.attack_cd <= 0.0:
                telegraph = self._phase_time("telegraph_duration", self._ai("attack_windup", 0.22))
                self._attack_windup = telegraph
                self._change_state("telegraph", lock_duration=telegraph)
                self.attack_cd = self._phase_time("attack_cooldown", 1.9)
                self.melee_applied = False
            elif self._is_engaged:
                self._change_state("chase", lock_duration=0.0, reset_time=False)
            else:
                self._change_state("idle", lock_duration=0.0, reset_time=False)
                self.state_time = min(self.state_time, 0.4)

        if self.state == "chase":
            m = vec
            m.z = 0.0
            if m.lengthSquared() > 1e-6:
                m.normalize()
                speed = self._stat("run_speed", 4.6) * self._phase_speed_mul
                pos += m * speed * dt
                world = getattr(self.app, "world", None)
                if world and hasattr(world, "_th"):
                    try:
                        base = float(world._th(pos.x, pos.y)) + float(self.cfg.get("ground_offset", 1.2))
                        if self.kind in {"fire_elemental", "shadow"}:
                            pos.z = base + float(self.cfg.get("hover_height", 1.2)) + (math.sin(now * 2.4) * 0.2)
                        else:
                            pos.z = base
                    except Exception:
                        pass
                self.root.setPos(pos)

        if self.state == "attack":
            if self._attack_mode() == "melee":
                hit_at = self._ai("melee_hit_time", 0.35)
                w_start, w_end = self._phase_attack_window(
                    "melee_window_start",
                    "melee_window_end",
                    hit_at,
                    hit_at + 0.14,
                )
                in_window = w_start <= self.state_time <= w_end
                if (not self.melee_applied) and in_window:
                    self.melee_applied = True
                    if dist <= self._stat("attack_range", 2.6) + 0.5:
                        cs = getattr(getattr(self.app, "player", None), "cs", None)
                        if cs and hasattr(cs, "health"):
                            try:
                                damage = max(1.0, float(self._ai("melee_damage", self._stat("power", 12.0))))
                                damage *= self._phase_damage_mul
                                cs.health = max(0.0, float(cs.health) - int(round(damage)))
                            except Exception:
                                pass
            else:
                self.fire_emit_acc += dt
                while self.fire_emit_acc >= 0.025:
                    self.fire_emit_acc -= 0.025
                    self._emit_fire_particle()
                self.fire_tick_acc += dt
                fire_start = self._phase_time("fire_start_time", 0.08)
                fire_end = self._phase_time("fire_end_time", self._phase_time("attack_duration", 0.82))
                in_fire_window = fire_start <= self.state_time <= max(fire_start, fire_end)
                if in_fire_window and self.fire_tick_acc >= 0.30 and dist <= self._stat("attack_range", 6.0):
                    self.fire_tick_acc = 0.0
                    cs = getattr(getattr(self.app, "player", None), "cs", None)
                    if cs and hasattr(cs, "health"):
                        try:
                            damage = max(1.0, float(self._ai("fire_tick_damage", 9.0)))
                            damage *= self._phase_damage_mul
                            cs.health = max(0.0, float(cs.health) - int(round(damage)))
                        except Exception:
                            pass
                if now - self.last_fire_sfx >= 0.34:
                    audio = getattr(self.app, "audio", None)
                    if audio:
                        try:
                            audio.play_sfx("dragon_fire", volume=0.78 if self.kind == "shadow" else 0.9, rate=0.95)
                        except Exception:
                            pass
                    self.last_fire_sfx = now

        self._sync_actor_animation()
        self._tick_fire_particles(dt)
        self._animate()
        self._apply_visual_state(dt)
        self._sync_proxy_to_core()


class BossManager:
    def __init__(
        self,
        app,
        cfg_path="data/enemies/boss_roster.json",
        state_map_path="data/enemies/state_maps.json",
    ):
        self.app = app
        self.cfg_path = str(cfg_path)
        self.state_map_path = str(state_map_path)
        self.units = []
        self._load()

    def _merge_enemy_cfg(self, base_entry, *overrides):
        merged = dict(base_entry)
        for override in overrides:
            if not isinstance(override, dict):
                continue
            for key, value in override.items():
                if key in {"animations", "animation_rates", "ai", "stats", "telegraph_fx"}:
                    prev = merged.get(key, {})
                    if not isinstance(prev, dict):
                        prev = {}
                    if isinstance(value, dict):
                        nxt = dict(prev)
                        nxt.update(value)
                        merged[key] = nxt
                else:
                    merged[key] = value
        return merged

    def _load(self):
        payload = _safe_read_json(self.cfg_path)
        state_payload = _safe_read_json(self.state_map_path)
        default_maps = state_payload.get("defaults", {}) if isinstance(state_payload, dict) else {}
        unit_maps = state_payload.get("units", {}) if isinstance(state_payload, dict) else {}
        if not isinstance(default_maps, dict):
            default_maps = {}
        if not isinstance(unit_maps, dict):
            unit_maps = {}

        entries = payload.get("enemies", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            unit_id = str(entry.get("id") or "").strip().lower()
            kind = str(entry.get("kind") or "").strip().lower()
            kind_defaults = default_maps.get(kind, {}) if kind else {}
            unit_override = unit_maps.get(unit_id, {}) if unit_id else {}
            final_entry = self._merge_enemy_cfg(entry, kind_defaults, unit_override)
            try:
                self.units.append(EnemyUnit(self.app, final_entry))
            except Exception as exc:
                logger.warning(f"[EnemyRoster] Init failed for '{entry.get('id', '?')}': {exc}")
        logger.info(f"[EnemyRoster] Spawned units: {len(self.units)}")

    def update(self, dt, player_pos):
        alive = []
        for unit in self.units:
            try:
                unit.update(dt, player_pos)
            except Exception as exc:
                logger.warning(f"[EnemyRoster] Update failed '{getattr(unit, 'id', '?')}': {exc}")
                continue
            alive.append(unit)
        self.units = alive

    def any_engaged(self):
        return any(u.is_boss and u.is_engaged for u in self.units)

    def get_primary(self, kind="golem"):
        token = str(kind or "").strip().lower()
        for u in self.units:
            if token and u.kind == token and u.is_boss:
                return u
        for u in self.units:
            if u.is_boss:
                return u
        return self.units[0] if self.units else None
