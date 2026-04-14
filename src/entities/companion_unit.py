"""CompanionUnit: Physics-aware ally actor with follow, hold, and combat assist logic."""

from __future__ import annotations

import math
import random

from direct.actor.Actor import Actor
from panda3d.core import LColor, Vec3

from render.model_visuals import ensure_model_visual_defaults
from utils.asset_pathing import prefer_bam_path
from utils.logger import logger

FOLLOW_DISTANCE_MIN = 3.5
FOLLOW_DISTANCE_MAX = 7.0
TELEPORT_DISTANCE = 35.0
MOVE_SPEED = 6.5
TURN_SPEED = 180.0
STAY_LEASH_DISTANCE = 2.4


def _clean_token(value):
    return str(value or "").strip().lower()


def _clamp(value, lower, upper):
    try:
        return max(lower, min(upper, float(value)))
    except Exception:
        return lower


class CompanionUnit:
    def __init__(self, app, member_id, data):
        self.app = app
        self.render = app.render
        self.loader = app.loader

        self.id = _clean_token(member_id)
        self.data = dict(data or {})
        self.name = str(self.data.get("name", self.id) or self.id)
        self.kind = _clean_token(self.data.get("kind", "companion")) or "companion"

        self.root = None
        self.actor = None
        self.state = "idle"  # idle, follow, combat, stay
        self.behavior_state = self._normalize_behavior(self.data.get("behavior", "follow"))
        self.active = False

        self._hold_anchor = None
        self._combat_target = None
        self._attack_cooldown = 0.0
        self._heal_cooldown = 0.0
        self._attack_anim_timer = 0.0
        self._idle_timer = 0.0

        self._anim_map = {
            "idle": "idle",
            "walk": "walk",
            "run": "run",
            "attack": "attack",
            "hit": "hit",
            "death": "death",
        }
        self._current_anim = ""

    def _normalize_behavior(self, value):
        token = _clean_token(value)
        if token in {"follow", "stay"}:
            return token
        return "follow"

    def spawn(self, pos: Vec3):
        if self.root:
            self.root.removeNode()

        self.root = self.render.attachNewNode(f"companion_{self.id}")
        self.root.setPos(pos)

        model_path = "assets/models/xbot/Xbot.glb"
        try:
            self.actor = Actor(prefer_bam_path(model_path))
            self.actor.reparentTo(self.root)
            
            # If it's a 'pet', use a more visible base scale and allow data override
            custom_scale = float(self.data.get("scale", 2.4 if self.kind == "pet" else 1.0))
            self.actor.setScale(custom_scale)

            color = self.data.get("appearance", {}).get("color", (1, 1, 1, 1))
            self.actor.setColor(LColor(*color))
            ensure_model_visual_defaults(self.actor, apply_skin=False, force_two_sided=True)
        except Exception as exc:
            logger.error(f"[Companion] Failed to load model for {self.id}: {exc}")

        self.active = True
        self.set_behavior_state(self.data.get("behavior", self.behavior_state))
        logger.info(f"[Companion] Spawned {self.name} at {pos}")

    def despawn(self):
        if self.root:
            self.root.removeNode()
            self.root = None
        self.actor = None
        self.active = False

    def set_behavior_state(self, state):
        self.behavior_state = self._normalize_behavior(state)
        self.data = dict(self.data or {})
        self.data["behavior"] = self.behavior_state
        if self.behavior_state == "stay" and self.root:
            try:
                self._hold_anchor = Vec3(self.root.getPos())
            except Exception:
                self._hold_anchor = None
        elif self.behavior_state != "stay":
            self._hold_anchor = None
        return self.behavior_state

    def update(self, dt, player_pos: Vec3):
        if not self.active or not self.root:
            return

        self.set_behavior_state(self.data.get("behavior", self.behavior_state))
        dt = max(0.0, float(dt))
        self._attack_cooldown = max(0.0, float(getattr(self, "_attack_cooldown", 0.0) or 0.0) - dt)
        self._heal_cooldown = max(0.0, float(getattr(self, "_heal_cooldown", 0.0) or 0.0) - dt)
        self._attack_anim_timer = max(0.0, float(getattr(self, "_attack_anim_timer", 0.0) or 0.0) - dt)

        curr_pos = self.root.getPos()
        dist_to_player = (player_pos - curr_pos).length()

        if self.behavior_state != "stay" and dist_to_player > TELEPORT_DISTANCE:
            self.root.setPos(player_pos + Vec3(random.uniform(-2, 2), random.uniform(-2, 2), 0))
            return

        assist_profile = self._resolve_assist_profile(self.data.get("assist", {}))
        self._combat_target = self._find_best_target(search_radius=assist_profile["engage_radius"])

        if self._enemy_is_alive(self._combat_target):
            self.state = "combat"
        elif self.behavior_state == "stay":
            self.state = "stay"
        elif dist_to_player > FOLLOW_DISTANCE_MAX:
            self.state = "follow"
        else:
            self.state = "idle"

        if self.state == "follow":
            self._behavior_follow(dt, player_pos)
        elif self.state == "combat":
            self._behavior_combat(dt)
        elif self.state == "stay":
            self._behavior_hold_position(dt)
        else:
            self._behavior_idle(dt)

        self._sync_animation()

    def _follow_offset(self):
        seed = (sum(ord(ch) for ch in self.id) % 5) - 2
        return float(seed) * 0.85

    def _enemy_is_alive(self, enemy):
        if not enemy:
            return False
        state = getattr(enemy, "is_alive", True)
        if callable(state):
            try:
                return bool(state())
            except Exception:
                return True
        return bool(state)

    def _iter_active_enemies(self):
        bm = getattr(self.app, "boss_manager", None)
        if not bm:
            return []
        if hasattr(bm, "get_active_enemies"):
            try:
                rows = bm.get_active_enemies() or []
            except Exception:
                rows = []
        else:
            rows = getattr(bm, "units", [])

        out = []
        for enemy in rows:
            if not enemy or not self._enemy_is_alive(enemy):
                continue
            if not getattr(enemy, "root", None):
                continue
            out.append(enemy)
        return out

    def _move_towards(self, dt, target_pos, speed_scale=1.0):
        if not self.root or target_pos is None:
            return
        curr_pos = self.root.getPos()
        direction = target_pos - curr_pos
        direction.z = 0
        dist = direction.length()
        if dist <= 0.08:
            return
        direction.normalize()
        target_h = math.degrees(math.atan2(-direction.x, direction.y))
        curr_h = self.root.getH()
        self.root.setH(self._lerp_angle(curr_h, target_h, TURN_SPEED * max(0.2, speed_scale) * dt))

        move_speed = MOVE_SPEED * max(0.3, float(speed_scale))
        move_step = direction * move_speed * dt
        if move_step.length() > dist:
            move_step = direction * dist
        self.root.setPos(curr_pos + move_step)
        world = getattr(self.app, "world", None)
        if world and hasattr(world, "_th"):
            try:
                ground_z = world._th(self.root.getX(), self.root.getY())
                self.root.setZ(ground_z)
            except Exception:
                pass

    def _behavior_follow(self, dt, player_pos):
        desired = Vec3(player_pos)
        desired.x += self._follow_offset()
        desired.y -= 2.2
        self._move_towards(dt, desired, speed_scale=1.0)

    def _behavior_hold_position(self, dt):
        if self._hold_anchor is None and self.root:
            self._hold_anchor = Vec3(self.root.getPos())
        if not self.root or self._hold_anchor is None:
            self._behavior_idle(dt)
            return
        dist = (self._hold_anchor - self.root.getPos()).length()
        if dist > STAY_LEASH_DISTANCE:
            self._move_towards(dt, Vec3(self._hold_anchor), speed_scale=0.8)
            return
        self._behavior_idle(dt)

    def _behavior_combat(self, dt):
        support_profile = self._resolve_support_profile(self.data.get("support", {}))
        assist_profile = self._resolve_assist_profile(self.data.get("assist", {}))

        self._handle_support(dt, support_profile)
        self._combat_target = self._find_best_target(search_radius=assist_profile["engage_radius"])
        if not self._enemy_is_alive(self._combat_target):
            if self.behavior_state == "stay":
                self._behavior_hold_position(dt)
            else:
                player = getattr(self.app, "player", None)
                player_pos = player.actor.getPos(self.render) if player and getattr(player, "actor", None) else self.root.getPos()
                self._behavior_follow(dt, player_pos)
            return

        target_pos = self._combat_target.root.getPos(self.render)
        dist = (target_pos - self.root.getPos()).length()
        if dist > assist_profile["range"]:
            if self.behavior_state == "stay" and self._hold_anchor is not None:
                anchor_dist = (target_pos - self._hold_anchor).length()
                if anchor_dist > (assist_profile["range"] + 4.0):
                    self._behavior_hold_position(dt)
                    return
            approach = Vec3(target_pos)
            direction = approach - self.root.getPos()
            if direction.length() > 0.01:
                direction.normalize()
                approach -= direction * max(assist_profile["ideal_range"], 1.5)
            self._move_towards(dt, approach, speed_scale=assist_profile["move_speed_scale"])

        self._handle_assist(dt, assist_profile)

    def _find_best_target(self, search_radius=20.0):
        player = getattr(self.app, "player", None)
        target_info = None
        if player and hasattr(player, "_aim_target_info"):
            target_info = player._aim_target_info
        if not isinstance(target_info, dict):
            target_info = getattr(self.app, "_aim_target_info", None)
        if isinstance(target_info, dict) and target_info.get("locked"):
            node = target_info.get("node")
            for enemy in self._iter_active_enemies():
                if enemy.root == node or enemy.actor == node:
                    return enemy

        best_enemy = None
        best_dist = max(4.0, float(search_radius or 20.0))
        curr_pos = self.root.getPos() if self.root else Vec3(0, 0, 0)
        for enemy in self._iter_active_enemies():
            try:
                dist = (enemy.root.getPos(self.render) - curr_pos).length()
            except Exception:
                continue
            if dist < best_dist:
                best_dist = dist
                best_enemy = enemy
        return best_enemy

    def _resolve_support_profile(self, support_data):
        row = support_data if isinstance(support_data, dict) else {}
        token = _clean_token(row.get("combat_assist") or row.get("role"))
        profile = {
            "heal_ratio": _clamp(row.get("healing_pulse", 0.0), 0.0, 0.65),
            "cooldown": 10.0,
            "threshold": 0.72,
            "radius": 2.0,
            "color": (0.24, 1.0, 0.48, 0.52),
            "sfx": "spell_cast",
        }
        if token == "ember_bolt":
            profile.update(
                {
                    "cooldown": 7.6,
                    "threshold": 0.78,
                    "radius": 2.4,
                    "color": (1.0, 0.56, 0.22, 0.52),
                }
            )
        return profile

    def _resolve_assist_profile(self, assist_data):
        row = assist_data if isinstance(assist_data, dict) else {}
        token = _clean_token(row.get("combat_assist"))
        profile = {
            "combat_assist": token or "default",
            "range": 12.0,
            "ideal_range": 8.0,
            "engage_radius": 18.0,
            "cooldown": 2.4,
            "damage": 10.0,
            "damage_type": "arcane",
            "color": (1.0, 0.56, 0.22, 0.82),
            "sfx": "spell_cast",
            "move_speed_scale": 1.0,
        }
        variants = {
            "arcane_archery": {
                "range": 18.0,
                "ideal_range": 13.0,
                "engage_radius": 24.0,
                "cooldown": 1.8,
                "damage": 14.0,
                "damage_type": "arcane",
                "color": (0.62, 0.84, 1.0, 0.86),
                "sfx": "spell_cast",
                "move_speed_scale": 1.05,
            },
            "guardian_charge": {
                "range": 10.0,
                "ideal_range": 5.0,
                "engage_radius": 15.0,
                "cooldown": 3.1,
                "damage": 18.0,
                "damage_type": "physical",
                "color": (1.0, 0.68, 0.28, 0.84),
                "sfx": "spell_cast",
                "move_speed_scale": 1.18,
            },
            "training_blade_support": {
                "range": 7.5,
                "ideal_range": 3.4,
                "engage_radius": 12.0,
                "cooldown": 1.35,
                "damage": 9.0,
                "damage_type": "physical",
                "color": (0.98, 0.80, 0.42, 0.80),
                "sfx": "spell_cast",
                "move_speed_scale": 1.12,
            },
            "shield_wall": {
                "range": 8.5,
                "ideal_range": 4.0,
                "engage_radius": 12.0,
                "cooldown": 3.8,
                "damage": 8.0,
                "damage_type": "arcane",
                "color": (0.96, 0.86, 0.38, 0.78),
                "sfx": "spell_cast",
                "move_speed_scale": 0.88,
            },
            "ember_bolt": {
                "range": 15.0,
                "ideal_range": 10.0,
                "engage_radius": 18.0,
                "cooldown": 2.0,
                "damage": 7.0,
                "damage_type": "fire",
                "color": (1.0, 0.44, 0.20, 0.84),
                "sfx": "spell_cast",
                "move_speed_scale": 1.15,
            },
        }
        profile.update(variants.get(token, {}))
        for key in ("range", "ideal_range", "engage_radius", "cooldown", "damage", "move_speed_scale"):
            if key in row:
                try:
                    profile[key] = float(row.get(key))
                except Exception:
                    pass
        return profile

    def _player_hp_ratio(self):
        player = getattr(self.app, "player", None)
        if not player:
            return 1.0
        cs = getattr(player, "cs", None)
        if cs and hasattr(cs, "health"):
            try:
                hp = float(getattr(cs, "health", 100.0) or 100.0)
                max_hp = max(1.0, float(getattr(cs, "maxHealth", hp) or hp))
                return hp / max_hp
            except Exception:
                return 1.0
        if hasattr(player, "hp"):
            try:
                hp = float(getattr(player, "hp", 100.0) or 100.0)
                max_hp = max(1.0, float(getattr(player, "max_hp", hp) or hp))
                return hp / max_hp
            except Exception:
                return 1.0
        return 1.0

    def _player_pos(self):
        player = getattr(self.app, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if actor and hasattr(actor, "getPos"):
            try:
                return actor.getPos(self.render)
            except Exception:
                return actor.getPos()
        return self.root.getPos() if self.root else Vec3(0, 0, 0)

    def _apply_player_heal(self, ratio):
        amount_ratio = _clamp(ratio, 0.0, 0.8)
        if amount_ratio <= 0.0:
            return False
        player = getattr(self.app, "player", None)
        if not player:
            return False
        if hasattr(player, "apply_effect"):
            try:
                return bool(player.apply_effect("heal", amount_ratio))
            except Exception:
                pass
        cs = getattr(player, "cs", None)
        if cs and hasattr(cs, "health"):
            try:
                max_hp = max(1.0, float(getattr(cs, "maxHealth", getattr(cs, "health", 100.0)) or 100.0))
                cs.health = min(max_hp, float(getattr(cs, "health", max_hp) or max_hp) + (max_hp * amount_ratio))
                return True
            except Exception:
                pass
        if hasattr(player, "hp"):
            try:
                max_hp = max(1.0, float(getattr(player, "max_hp", getattr(player, "hp", 100.0)) or 100.0))
                player.hp = min(max_hp, float(getattr(player, "hp", max_hp) or max_hp) + (max_hp * amount_ratio))
                return True
            except Exception:
                pass
        return False

    def _play_sfx(self, key):
        token = str(key or "").strip()
        if not token:
            return False
        audio = getattr(self.app, "audio_director", None) or getattr(self.app, "audio", None)
        if audio and hasattr(audio, "play_sfx"):
            try:
                return bool(audio.play_sfx(token))
            except Exception:
                return False
        return False

    def _handle_support(self, dt, support_profile):
        del dt
        heal_ratio = float(support_profile.get("heal_ratio", 0.0) or 0.0)
        if heal_ratio <= 0.0 or self._heal_cooldown > 0.0:
            return False
        hp_ratio = self._player_hp_ratio()
        if hp_ratio > float(support_profile.get("threshold", 0.72) or 0.72):
            return False
        if not self._apply_player_heal(heal_ratio):
            return False
        self._heal_cooldown = max(2.5, float(support_profile.get("cooldown", 10.0) or 10.0))
        self._play_sfx(support_profile.get("sfx"))

        magic_vfx = getattr(self.app, "magic_vfx", None)
        if magic_vfx and hasattr(magic_vfx, "spawn_spell_telegraph_vfx"):
            try:
                magic_vfx.spawn_spell_telegraph_vfx(
                    self._player_pos(),
                    radius=float(support_profile.get("radius", 2.0) or 2.0),
                    color=support_profile.get("color"),
                    duration=0.8,
                )
            except Exception:
                pass
        logger.info(f"[Companion] {self.name} supported the player.")
        return True

    def _handle_assist(self, dt, assist_profile):
        del dt
        profile = assist_profile if isinstance(assist_profile, dict) else {}
        if "range" not in profile or "damage" not in profile:
            profile = self._resolve_assist_profile(profile)
        target = self._combat_target
        if not target or not getattr(target, "root", None):
            return False
        if self._attack_cooldown > 0.0:
            return False

        target_pos = target.root.getPos(self.render)
        if hasattr(self.root, "lookAt"):
            # Colinearity guard: prevent crash if companion and target are at same position
            if (target_pos - self.root.getPos(self.render)).length_squared() > 1e-6:
                self.root.lookAt(target_pos)
        if hasattr(self.root, "setP"):
            self.root.setP(0)

        dist = (target_pos - self.root.getPos()).length()
        if dist > float(profile.get("range", 12.0) or 12.0):
            return False

        self._attack_cooldown = max(0.8, float(profile.get("cooldown", 2.4) or 2.4))
        self._attack_anim_timer = 0.38
        damage = float(profile.get("damage", 10.0) or 10.0)
        damage_type = str(profile.get("damage_type", "arcane") or "arcane")

        if hasattr(target, "take_damage"):
            try:
                target.take_damage(damage, damage_type, self.id)
                logger.info(f"[Companion] {self.name} attacked {getattr(target, 'id', 'target')}")
            except Exception:
                return False

        self._play_sfx(profile.get("sfx"))
        magic_vfx = getattr(self.app, "magic_vfx", None)
        if magic_vfx and hasattr(magic_vfx, "spawn_spell_phase_vfx"):
            try:
                magic_vfx.spawn_spell_phase_vfx(
                    target_pos,
                    phase="impact",
                    color=profile.get("color"),
                    radius=1.0 if getattr(self, "kind", "companion") == "companion" else 0.7,
                    duration=0.16,
                )
            except Exception:
                pass
        return True

    def _behavior_idle(self, dt):
        self._idle_timer = getattr(self, "_idle_timer", 0.0) + dt
        if self._idle_timer > 3.0:
            self._idle_timer = 0.0
            self.root.setH(self.root.getH() + random.uniform(-15, 15))

    def _sync_animation(self):
        if not self.actor:
            return

        anim = "idle"
        if self.state in {"follow", "combat"} and self._attack_anim_timer <= 0.01:
            anim = "run"
        if self._attack_anim_timer > 0.01:
            anim = "attack"

        if self._current_anim != anim:
            try:
                self.actor.loop(anim)
                self._current_anim = anim
            except Exception:
                pass

    def _lerp_angle(self, curr, target, step):
        diff = (target - curr + 180) % 360 - 180
        if abs(diff) < step:
            return target
        return curr + (step if diff > 0 else -step)
