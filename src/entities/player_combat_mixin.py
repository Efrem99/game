"""Player combat, spell casting, and combat event helpers."""

from direct.showbase.ShowBaseGlobal import globalClock

try:
    import game_core as gc

    HAS_CORE = True
except ImportError:
    gc = None
    HAS_CORE = False


class PlayerCombatMixin:
    def _refresh_spell_cache(self):
        keys = []
        if hasattr(self.data_mgr, "get_spellbook_keys"):
            try:
                keys = list(self.data_mgr.get_spellbook_keys())
            except Exception:
                keys = []
        if not keys:
            keys = list(self.data_mgr.spells.keys())
        self._spell_cache = keys
        if not self._spell_cache:
            self._active_spell_idx = 0
            self._ultimate_spell_idx = 0
            return

        if self._active_spell_idx >= len(self._spell_cache):
            self._active_spell_idx = 0

        best_idx = 0
        best_score = float("-inf")
        for idx, spell_key in enumerate(self._spell_cache):
            payload = self.data_mgr.get_spell(spell_key) or {}
            if not isinstance(payload, dict):
                payload = {}
            if payload.get("ultimate") is True:
                best_idx = idx
                break
            mana = float(payload.get("mana_cost", 0) or 0)
            dmg = float(payload.get("damage", payload.get("heal_value", 0)) or 0)
            score = (mana * 1.4) + dmg
            if score > best_score:
                best_score = score
                best_idx = idx
        self._ultimate_spell_idx = best_idx

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safe_str(self, value, default=""):
        if not isinstance(value, str):
            return str(default)
        token = value.strip()
        return token if token else str(default)

    def _spell_runtime_profile(self, spell_key, spell_data):
        payload = spell_data if isinstance(spell_data, dict) else {}
        runtime = payload.get("runtime", {})
        if not isinstance(runtime, dict):
            runtime = {}
        sfx_cfg = payload.get("sfx", {})
        if not isinstance(sfx_cfg, dict):
            sfx_cfg = {}
        vfx_cfg = payload.get("vfx", {})
        if not isinstance(vfx_cfg, dict):
            vfx_cfg = {}

        cast_time = self._safe_float(
            runtime.get("cast_time", payload.get("cast_time", 0.0)),
            default=0.0,
        )
        cooldown = self._safe_float(
            runtime.get("cooldown", payload.get("cooldown", 0.0)),
            default=0.0,
        )
        cast_time = max(0.0, min(2.5, cast_time))
        cooldown = max(0.0, min(30.0, cooldown))

        damage_type = self._spell_damage_type(spell_key, payload)
        anim_trigger = self._safe_str(
            runtime.get(
                "anim_trigger",
                payload.get(
                    "anim_trigger",
                    payload.get("animation_trigger", payload.get("animation", payload.get("anim", "cast_spell"))),
                ),
            ),
            default="cast_spell",
        ).lower()
        if not anim_trigger:
            anim_trigger = "cast_spell"

        cast_sfx = self._safe_str(
            sfx_cfg.get("cast", runtime.get("sfx_cast", payload.get("sfx_cast", "spell_cast"))),
            default="spell_cast",
        )
        impact_sfx = self._safe_str(
            sfx_cfg.get(
                "impact",
                runtime.get(
                    "sfx_impact",
                    payload.get("sfx_impact", f"spell_{damage_type}"),
                ),
            ),
            default=f"spell_{damage_type}",
        )

        particle_tag = self._safe_str(
            vfx_cfg.get("particle_tag", payload.get("particle_tag", payload.get("particleTag", ""))),
            default="",
        )
        label = self._safe_str(payload.get("name", payload.get("id", spell_key)), default=str(spell_key))

        return {
            "id": self._safe_str(payload.get("id", spell_key), default=str(spell_key)).lower(),
            "label": label,
            "cast_time": cast_time,
            "cooldown": cooldown,
            "anim_trigger": anim_trigger,
            "cast_sfx": cast_sfx,
            "impact_sfx": impact_sfx,
            "damage_type": damage_type,
            "particle_tag": particle_tag,
        }

    def set_active_spell_index(self, index):
        self._refresh_spell_cache()
        if not self._spell_cache:
            return
        try:
            idx = int(index)
        except Exception:
            return
        if idx < 0 or idx >= len(self._spell_cache):
            return
        self._active_spell_idx = idx

    def get_skill_wheel_state(self):
        self._refresh_spell_cache()
        active_idx = int(self._active_spell_idx)
        preview_idx = getattr(self, "_skill_wheel_preview_idx", None)
        if getattr(self, "_skill_wheel_open", False):
            if isinstance(preview_idx, int) and 0 <= preview_idx < len(self._spell_cache):
                active_idx = int(preview_idx)
        return list(self._spell_cache), active_idx, int(self._ultimate_spell_idx)

    def get_hud_combat_event(self):
        event = self._last_combat_event
        if not isinstance(event, dict):
            return None
        if event.get("until", 0.0) < globalClock.getFrameTime():
            return None
        return dict(event)

    def _push_combat_event(self, damage_type, amount, source_label=None):
        try:
            value = int(amount)
        except Exception:
            value = 0
        if value == 0:
            return

        self._last_combat_event = {
            "type": str(damage_type or "physical"),
            "amount": value,
            "label": str(source_label or ""),
            "until": globalClock.getFrameTime() + 1.5,
        }

    def _spell_damage_type(self, spell_key, spell_data):
        if isinstance(spell_data, dict):
            dt = spell_data.get("damage_type")
            if isinstance(dt, str) and dt.strip():
                return dt.strip().lower()

        token = str(spell_key or "").lower()
        if "fire" in token or "meteor" in token:
            return "fire"
        if "lightning" in token:
            return "lightning"
        if "ice" in token:
            return "ice"
        if "heal" in token or "ward" in token:
            return "holy"
        if "force" in token or "nova" in token:
            return "arcane"
        return "arcane"

    def _cast_spell_by_index(self, idx):
        if not HAS_CORE or not self.magic:
            return False
        self._refresh_spell_cache()
        if not self._spell_cache:
            return False
        if idx < 0 or idx >= len(self._spell_cache):
            return False

        spell_key = self._spell_cache[idx]
        spell_data = self.data_mgr.get_spell(spell_key) or {}
        runtime = self._spell_runtime_profile(spell_key, spell_data)
        now = globalClock.getFrameTime()

        cooldowns = getattr(self, "_spell_cooldowns", None)
        if not isinstance(cooldowns, dict):
            cooldowns = {}
            self._spell_cooldowns = cooldowns
        if now < float(cooldowns.get(spell_key, 0.0)):
            return False

        cast_lock_until = float(getattr(self, "_spell_cast_lock_until", 0.0) or 0.0)
        if now < cast_lock_until:
            return False

        spell_type = self._resolve_spell_type(spell_key, spell_data)
        if not spell_type:
            return False

        effect = self.magic.castSpell(self.cs, spell_type, self.cs.facingDir, self.enemies)
        self._on_spell_effect(effect)
        if runtime.get("cast_sfx"):
            self._play_sfx(runtime["cast_sfx"], volume=0.9)

        damage_val = 0
        if isinstance(spell_data, dict):
            damage_val = int(spell_data.get("damage", spell_data.get("heal_value", 0)) or 0)
        dmg_type = runtime.get("damage_type") or self._spell_damage_type(spell_key, spell_data)
        if runtime.get("impact_sfx"):
            self._play_sfx(runtime["impact_sfx"], volume=0.95)
        self._push_combat_event(dmg_type, damage_val, source_label=runtime.get("label") or spell_key)
        if runtime["cooldown"] > 0.0:
            cooldowns[spell_key] = now + runtime["cooldown"]
        if runtime["cast_time"] > 0.0:
            self._spell_cast_lock_until = now + runtime["cast_time"]
        self._set_weapon_drawn(True)
        self._queue_state_trigger(runtime.get("anim_trigger", "cast_spell"))
        return True

    def _resolve_spell_type(self, spell_key, spell_data):
        candidates = []
        if isinstance(spell_data, dict):
            for field in ("enum", "core_type", "name", "id"):
                value = spell_data.get(field)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
        if isinstance(spell_key, str):
            candidates.append(spell_key)

        for token in candidates:
            direct = getattr(gc.SpellType, token, None)
            if direct:
                return direct
            compact = "".join(ch for ch in token if ch.isalnum()).lower()
            alias = self._spell_type_alias.get(compact)
            if alias:
                mapped = getattr(gc.SpellType, alias, None)
                if mapped:
                    return mapped
        return None

    def _on_hit(self, result):
        if result and result.hit:
            if self.particles and HAS_CORE:
                world_pos = self._sword_node.getPos(self.render)
                self.particles.spawnBloodSplat(
                    gc.Vec3(world_pos.x, world_pos.y, world_pos.z),
                    gc.Vec3(0, 0, 1),
                )
            self._play_sfx("sword_hit", volume=0.9)
            self._play_sfx("enemy_hit", volume=0.8)
        if not result:
            return
        amount = 0
        for key in ("damage", "damageDealt", "finalDamage", "value"):
            if hasattr(result, key):
                try:
                    amount = int(getattr(result, key))
                    break
                except Exception:
                    continue
        if amount <= 0 and hasattr(result, "hit") and result.hit:
            amount = 10
        self._push_combat_event("physical", amount, source_label="melee")

    def _on_spell_effect(self, fx):
        if fx and self.particles and HAS_CORE:
            pos = gc.Vec3(fx.pos.x, fx.pos.y, fx.pos.z)
            if "fire" in fx.particleTag:
                self.particles.spawnFireball(pos)
            elif "heal" in fx.particleTag:
                self.particles.spawnHealAura(pos)

    def export_combat_runtime_state(self):
        now = globalClock.getFrameTime()
        cooldowns = getattr(self, "_spell_cooldowns", {})
        out_cooldowns = {}
        if isinstance(cooldowns, dict):
            for key, until in cooldowns.items():
                remain = float(until or 0.0) - now
                if remain > 0.01:
                    out_cooldowns[str(key)] = round(remain, 3)
        return {
            "active_spell_idx": int(getattr(self, "_active_spell_idx", 0) or 0),
            "ultimate_spell_idx": int(getattr(self, "_ultimate_spell_idx", 0) or 0),
            "spell_cooldowns": out_cooldowns,
        }

    def import_combat_runtime_state(self, payload):
        if not isinstance(payload, dict):
            return
        self._refresh_spell_cache()

        try:
            self._active_spell_idx = int(payload.get("active_spell_idx", self._active_spell_idx))
        except Exception:
            pass
        try:
            self._ultimate_spell_idx = int(payload.get("ultimate_spell_idx", self._ultimate_spell_idx))
        except Exception:
            pass

        now = globalClock.getFrameTime()
        raw_cds = payload.get("spell_cooldowns", {})
        self._spell_cooldowns = {}
        if isinstance(raw_cds, dict):
            for key, remain in raw_cds.items():
                secs = self._safe_float(remain, default=0.0)
                if secs > 0.0:
                    self._spell_cooldowns[str(key)] = now + secs
