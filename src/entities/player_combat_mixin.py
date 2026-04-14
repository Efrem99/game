"""Player combat, spell casting, and combat event helpers."""

import math
from types import SimpleNamespace

from utils.core_runtime import gc, HAS_CORE
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import Vec3

from render.fx_policy import (
    DEFAULT_MELEE_WHEEL_TOKEN,
    is_melee_wheel_token,
    should_cast_selected_spell,
)


class PlayerCombatMixin:
    def _resolve_attack_direction_token(self):
        getter = getattr(self, "_get_move_axes", None)
        if not callable(getter):
            return ""
        try:
            mx, my = getter()
            mx = float(mx or 0.0)
            my = float(my or 0.0)
        except Exception:
            return ""

        if abs(mx) < 0.24 and abs(my) < 0.24:
            return ""
        if abs(mx) >= max(abs(my), 0.36):
            return "right" if mx > 0.0 else "left"
        if my > 0.32:
            return "forward"
        return ""

    def _normalize_anim_mode(self, value):
        token = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not token:
            return ""
        alias = {
            "l": "left",
            "left_hand": "left",
            "offhand": "left",
            "r": "right",
            "right_hand": "right",
            "mainhand": "right",
            "main_hand": "right",
            "single": "single",
            "one": "single",
            "onehand": "single",
            "one_handed": "single",
            "both_hands": "both",
            "bothhands": "both",
            "twohand": "both",
            "two_handed": "both",
            "twohanded": "both",
            "2h": "both",
            "dualwield": "dual",
            "dual_wield": "dual",
            "dual_wielding": "dual",
        }
        return alias.get(token, token)

    def _next_handed_token(self, attr_name):
        current = str(getattr(self, attr_name, "right") or "right").strip().lower()
        if current not in {"left", "right"}:
            current = "right"
        next_token = "left" if current == "right" else "right"
        setattr(self, attr_name, next_token)
        return current

    def _dedupe_tokens(self, tokens):
        out = []
        seen = set()
        for token in tokens:
            key = str(token or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    def _offhand_dual_capable(self):
        equipment = getattr(self, "_equipment_state", {})
        if not isinstance(equipment, dict):
            return False
        token = str(equipment.get("offhand", "") or "").strip()
        if not token:
            return False
        getter = getattr(getattr(self, "data_mgr", None), "get_item", None)
        if not callable(getter):
            return False
        payload = getter(token) or {}
        if not isinstance(payload, dict):
            return False

        weapon_class = str(payload.get("weapon_class", payload.get("weapon_type", "")) or "").strip().lower()
        if weapon_class in {"dagger", "sword", "axe", "mace", "blade", "claw"}:
            return True

        visual = payload.get("equip_visual", {})
        style = ""
        if isinstance(visual, dict):
            style = str(visual.get("style", "") or "").strip().lower()
        name = str(payload.get("name", "") or "").strip().lower()
        slot = str(payload.get("slot", "") or "").strip().lower()

        if "shield" in style or "shield" in name or slot == "shield":
            return False
        return any(
            marker in f"{weapon_class} {style} {name}"
            for marker in ("dagger", "dual", "claw", "blade", "weapon")
        )

    def _resolve_spell_cast_mode(self, spell_key, spell_data, runtime=None):
        payload = spell_data if isinstance(spell_data, dict) else {}
        run_cfg = runtime if isinstance(runtime, dict) else {}
        payload_runtime = payload.get("runtime", {})
        if not isinstance(payload_runtime, dict):
            payload_runtime = {}

        raw_mode = ""
        for source in (
            run_cfg.get("cast_mode"),
            run_cfg.get("animation_mode"),
            payload_runtime.get("cast_mode"),
            payload_runtime.get("animation_mode"),
            payload.get("cast_mode"),
            payload.get("hands"),
            payload.get("cast_hand"),
            payload.get("hand"),
            payload.get("animation_mode"),
        ):
            if isinstance(source, str) and source.strip():
                raw_mode = source
                break

        mode = self._normalize_anim_mode(raw_mode)
        if mode in {"left", "right", "both", "dual"}:
            return mode
        if mode == "single":
            return self._next_handed_token("_next_cast_hand")

        style = self._weapon_combo_style()
        if self._is_both_hand_flow_style(style):
            return "both"
        if self._offhand_dual_capable():
            return "dual"
        return self._next_handed_token("_next_cast_hand")

    def _raw_spell_anim_trigger(self, spell_key, spell_data, runtime=None):
        payload = spell_data if isinstance(spell_data, dict) else {}
        run_cfg = runtime if isinstance(runtime, dict) else {}
        return self._safe_str(
            run_cfg.get(
                "anim_trigger",
                payload.get(
                    "anim_trigger",
                    payload.get("animation_trigger", payload.get("animation", payload.get("anim", "cast_spell"))),
                ),
            ),
            default="cast_spell",
        ).lower()

    def _resolve_spell_anim_trigger(self, spell_key, spell_data, runtime=None):
        payload = spell_data if isinstance(spell_data, dict) else {}
        raw_trigger = self._raw_spell_anim_trigger(spell_key, payload, runtime)
        if raw_trigger and raw_trigger not in {"cast_spell", "casting"}:
            return raw_trigger

        spell_token = self._safe_str(payload.get("id", spell_key), default=str(spell_key)).lower()
        damage_type = self._spell_damage_type(spell_key, payload)

        effect_cfg = payload.get("effect", {})
        if not isinstance(effect_cfg, dict):
            effect_cfg = {}
        vfx_cfg = payload.get("vfx", {})
        if not isinstance(vfx_cfg, dict):
            vfx_cfg = {}

        effect_type = self._safe_str(effect_cfg.get("type", ""), default="").lower()
        particle_tag = self._safe_str(
            vfx_cfg.get("particle_tag", payload.get("particle_tag", payload.get("particleTag", ""))),
            default="",
        ).lower()

        if any(marker in spell_token for marker in ("heal", "healing")) or effect_type == "heal":
            return "cast_heal"
        if "ward" in spell_token or "shield" in spell_token or effect_type == "buff":
            return "cast_ward"
        if "ice" in spell_token or particle_tag == "ice_spike":
            return "cast_ice"
        if "lightning" in spell_token or particle_tag == "lightning_arc":
            return "cast_lightning"
        if any(marker in spell_token for marker in ("fire", "meteor")) or particle_tag == "fire_burst":
            return "cast_fire"
        if any(marker in spell_token for marker in ("force", "nova")) or particle_tag == "force_push":
            return "cast_arcane"
        if damage_type == "holy":
            return "cast_holy"
        if damage_type == "lightning":
            return "cast_lightning"
        if damage_type == "ice":
            return "cast_ice"
        if damage_type == "fire":
            return "cast_fire"
        if damage_type == "arcane":
            return "cast_arcane"
        return raw_trigger or "cast_spell"

    def _spell_cast_family(self, spell_key, spell_data):
        payload = spell_data if isinstance(spell_data, dict) else {}
        spell_token = self._safe_str(payload.get("id", spell_key), default=str(spell_key)).lower()
        runtime_cfg = payload.get("runtime", {})
        if not isinstance(runtime_cfg, dict):
            runtime_cfg = {}
        explicit_family = self._safe_str(runtime_cfg.get("cast_family", ""), default="").lower()
        if explicit_family in {"projectile", "aoe", "support", "instant"}:
            return explicit_family

        projectile = payload.get("projectile")
        if isinstance(projectile, dict) and projectile:
            return "projectile"

        effect_cfg = payload.get("effect", {})
        if not isinstance(effect_cfg, dict):
            effect_cfg = {}
        effect_type = self._safe_str(effect_cfg.get("type", ""), default="").lower()

        if payload.get("heal_value") is not None or any(marker in spell_token for marker in ("heal", "healing", "ward", "shield")):
            return "support"
        if effect_type in {"buff", "heal", "ward", "shield"}:
            return "support"

        if effect_type in {"nova", "aoe", "wave", "burst", "explosion"}:
            return "aoe"
        if any(marker in spell_token for marker in ("nova", "forcewave", "force_wave", "force")):
            return "aoe"
        return "instant"

    def _spell_default_color(self, damage_type, family=""):
        token = self._safe_str(damage_type, default="arcane").lower()
        if token == "fire":
            return [1.0, 0.42, 0.14, 0.34]
        if token == "lightning":
            return [0.72, 0.86, 1.0, 0.32]
        if token == "ice":
            return [0.58, 0.88, 1.0, 0.28]
        if token == "holy":
            if str(family or "").strip().lower() == "support":
                return [0.68, 1.0, 0.72, 0.26]
            return [0.92, 0.88, 0.52, 0.28]
        return [0.52, 0.82, 1.0, 0.30]

    def _spell_telegraph_profile(self, spell_key, spell_data, *, cast_time=0.0, damage_type="", cast_family=""):
        payload = spell_data if isinstance(spell_data, dict) else {}
        family = str(cast_family or self._spell_cast_family(spell_key, payload)).strip().lower()

        effect_cfg = payload.get("effect", {})
        if not isinstance(effect_cfg, dict):
            effect_cfg = {}
        runtime_cfg = payload.get("runtime", {})
        if not isinstance(runtime_cfg, dict):
            runtime_cfg = {}
        tele_cfg = runtime_cfg.get("telegraph", {})
        if not isinstance(tele_cfg, dict):
            tele_cfg = {}

        enabled = family in {"aoe", "support"}
        if "enabled" in tele_cfg:
            enabled = bool(tele_cfg.get("enabled"))

        radius = self._safe_float(
            tele_cfg.get(
                "radius",
                effect_cfg.get(
                    "radius",
                    4.2 if family == "support" else 5.0,
                ),
            ),
            default=4.2 if family == "support" else 5.0,
        )
        radius = max(0.5, min(24.0, radius))

        duration = self._safe_float(
            tele_cfg.get("duration", max(0.14, min(0.65, max(0.18, float(cast_time or 0.0) * 0.72)))),
            default=max(0.14, min(0.65, max(0.18, float(cast_time or 0.0) * 0.72))),
        )
        duration = max(0.08, min(2.5, duration))

        token = "telegraph_support" if family == "support" else "telegraph_aoe"
        if family not in {"aoe", "support"}:
            token = "telegraph_spell"
        token = self._safe_str(tele_cfg.get("token", token), default=token).lower()

        color = tele_cfg.get("color", effect_cfg.get("color"))
        if not (isinstance(color, (list, tuple)) and len(color) >= 3):
            color = self._spell_default_color(damage_type, family=family)
        color = [float(color[0]), float(color[1]), float(color[2]), float(color[3] if len(color) > 3 else 0.28)]

        anchor = self._safe_str(tele_cfg.get("anchor", "self"), default="self").lower()
        return {
            "enabled": bool(enabled),
            "radius": radius,
            "duration": duration,
            "color": color,
            "token": token,
            "anchor": anchor,
        }

    def _spell_vfx_windows(self, spell_key, spell_data, *, cast_family="", damage_type=""):
        payload = spell_data if isinstance(spell_data, dict) else {}
        runtime_cfg = payload.get("runtime", {})
        if not isinstance(runtime_cfg, dict):
            runtime_cfg = {}
        raw_windows = runtime_cfg.get("vfx_windows", {})
        if not isinstance(raw_windows, dict):
            raw_windows = {}

        family = str(cast_family or self._spell_cast_family(spell_key, payload)).strip().lower()
        tint = self._spell_default_color(damage_type, family=family)
        base_radius = 0.9 if family == "projectile" else 1.4
        impact_radius = 1.4 if family == "projectile" else 2.2

        def _window(phase, duration, radius, anchor):
            row = raw_windows.get(phase, {})
            if not isinstance(row, dict):
                row = {}
            enabled = bool(row.get("enabled", True))
            color = row.get("color", tint)
            if not (isinstance(color, (list, tuple)) and len(color) >= 3):
                color = tint
            return {
                "enabled": enabled,
                "duration": self._safe_float(row.get("duration", duration), default=duration),
                "radius": self._safe_float(row.get("radius", radius), default=radius),
                "anchor": self._safe_str(row.get("anchor", anchor), default=anchor).lower(),
                "color": [
                    float(color[0]),
                    float(color[1]),
                    float(color[2]),
                    float(color[3] if len(color) > 3 else tint[3]),
                ],
            }

        return {
            "prepare": _window("prepare", 0.12, base_radius, "self"),
            "release": _window("release", 0.10, base_radius * 1.05, "self"),
            "impact": _window("impact", 0.18, impact_radius, "impact"),
        }

    def _resolve_weapon_attack_mode(self, attack_kind):
        token = str(attack_kind or "light").strip().lower()

        equipment = getattr(self, "_equipment_state", {})
        weapon_item = {}
        if isinstance(equipment, dict):
            weapon_id = str(equipment.get("weapon_main", "") or "").strip()
            if weapon_id:
                getter = getattr(getattr(self, "data_mgr", None), "get_item", None)
                if callable(getter):
                    payload = getter(weapon_id) or {}
                    if isinstance(payload, dict):
                        weapon_item = payload

        raw_mode = ""
        if isinstance(weapon_item, dict):
            runtime_cfg = weapon_item.get("runtime", {})
            if not isinstance(runtime_cfg, dict):
                runtime_cfg = {}
            for source in (
                runtime_cfg.get("attack_mode"),
                weapon_item.get("attack_mode"),
                weapon_item.get("animation_mode"),
                weapon_item.get("anim_mode"),
            ):
                if isinstance(source, str) and source.strip():
                    raw_mode = source
                    break
        mode = self._normalize_anim_mode(raw_mode)
        if mode in {"left", "right", "both", "dual"}:
            return mode
        if mode == "single":
            return self._next_handed_token("_next_weapon_hand")

        style = self._weapon_combo_style()
        if self._offhand_dual_capable() and not self._is_both_hand_flow_style(style):
            return "dual"
        if self._is_both_hand_flow_style(style):
            return "both"
        if token in {"heavy", "finisher"}:
            return "both"
        return self._next_handed_token("_next_weapon_hand")

    def _apply_state_anim_hint_tokens(self, state_name, tokens):
        cleaned = self._dedupe_tokens(tokens)
        if not cleaned:
            return
        setter = getattr(self, "_set_state_anim_hints", None)
        if callable(setter):
            setter(state_name, cleaned)
            return
        # Keep a lightweight fallback for mixin-only test doubles.
        key = str(state_name or "").strip().lower()
        if not key:
            return
        hints = getattr(self, "_state_anim_hints", {})
        if not isinstance(hints, dict):
            hints = {}
            setattr(self, "_state_anim_hints", hints)
        hints[key] = list(cleaned)

    def _force_action_state(self, state_name):
        token = str(state_name or "").strip().lower()
        if token not in {"attacking", "casting", "dodging", "blocking"}:
            return
        current = str(getattr(self, "_anim_state", "") or "").strip().lower()
        if current in {"dead", "death", "falling_hard"}:
            return
        enter_state = getattr(self, "_enter_state", None)
        if callable(enter_state):
            try:
                enter_state(token)
            except Exception:
                pass

    def _resolve_spell_anim_triggers(self, spell_key, spell_data, runtime=None):
        payload = spell_data if isinstance(spell_data, dict) else {}
        run_cfg = runtime if isinstance(runtime, dict) else {}
        base_trigger = self._resolve_spell_anim_trigger(spell_key, payload, run_cfg)
        if not base_trigger:
            base_trigger = "cast_spell"
        school_specific = base_trigger not in {"cast_spell", "casting"}
        cast_family = str(
            run_cfg.get("cast_family", self._spell_cast_family(spell_key, payload)) or self._spell_cast_family(spell_key, payload)
        ).strip().lower()
        telegraph = run_cfg.get("telegraph", {})
        if not isinstance(telegraph, dict):
            telegraph = {}
        if not telegraph:
            telegraph = self._spell_telegraph_profile(
                spell_key,
                payload,
                cast_time=self._safe_float(
                    run_cfg.get("cast_time", payload.get("cast_time", 0.0)),
                    default=0.0,
                ),
                damage_type=self._spell_damage_type(spell_key, payload),
                cast_family=cast_family,
            )

        mode = self._resolve_spell_cast_mode(spell_key, payload, run_cfg)
        tokens = []
        spell_token = str(spell_key or "").strip().lower()
        cast_time = self._safe_float(
            run_cfg.get("cast_time", payload.get("cast_time", 0.0)),
            default=0.0,
        )
        # Detect whether 'both' was explicitly declared in the spell/runtime config
        # (as opposed to inferred from weapon type). Only when explicitly declared
        # should cast_both lead the token list ahead of cast_fast/cast_prepare.
        payload_runtime = payload.get("runtime", {})
        if not isinstance(payload_runtime, dict):
            payload_runtime = {}
        explicit_both = False
        for source in (
            run_cfg.get("cast_mode"),
            run_cfg.get("animation_mode"),
            payload_runtime.get("cast_mode"),
            payload_runtime.get("animation_mode"),
            payload.get("cast_mode"),
            payload.get("hands"),
            payload.get("cast_hand"),
            payload.get("hand"),
            payload.get("animation_mode"),
        ):
            if isinstance(source, str) and source.strip():
                explicit_both = self._normalize_anim_mode(source) == "both"
                break

        if cast_family in {"aoe", "support"}:
            if telegraph.get("enabled"):
                tokens.extend(
                    [
                        "cast_telegraph",
                        str(telegraph.get("token", "telegraph_aoe") or "telegraph_aoe"),
                        f"{base_trigger}_telegraph",
                    ]
                )
                anchor = self._safe_str(telegraph.get("anchor", ""), default="").lower()
                if anchor:
                    tokens.append(f"telegraph_{anchor}")
            if school_specific:
                tokens.append(base_trigger)
            if mode == "both" and explicit_both:
                tokens.extend(["cast_both", "cast_twohand", "cast_two_handed", f"{base_trigger}_both"])
            if cast_time >= 0.55:
                tokens.extend(["cast_channel", f"{base_trigger}_channel"])
        else:
            quick_cast = False
            if 0.0 < cast_time <= 0.32:
                quick_cast = True
            if any(marker in spell_token for marker in ("fireball", "bolt", "quick", "burst")):
                quick_cast = True
            if quick_cast:
                tokens.extend(["cast_fast", f"{base_trigger}_fast", "cast_quick"])
            else:
                tokens.extend(["cast_prepare", f"{base_trigger}_prepare"])
                if cast_time >= 0.55:
                    tokens.extend(["cast_channel", f"{base_trigger}_channel"])
            if school_specific:
                tokens.append(base_trigger)
            tokens.extend(["cast_release", f"{base_trigger}_release"])

        if mode == "both" and explicit_both and cast_family not in {"aoe", "support"}:
            tokens.extend(["cast_both", "cast_twohand", "cast_two_handed", f"{base_trigger}_both"])
        if cast_family in {"aoe", "support"}:
            tokens.extend([f"{base_trigger}_release"])
        if mode:
            tokens.append(f"cast_{mode}")
            tokens.append(f"{base_trigger}_{mode}")
            tokens.append(f"{mode}_{base_trigger}")
            if mode == "both" and not explicit_both:
                tokens.extend(["cast_twohand", "cast_two_handed"])
        tokens.append(base_trigger)
        if base_trigger != "cast_spell":
            tokens.append("cast_spell")
        return self._dedupe_tokens(tokens)

    def _resolve_weapon_attack_triggers(self, attack_kind):
        kind = str(attack_kind or "light").strip().lower()
        if kind not in {"light", "heavy", "thrust"}:
            kind = "light"
        base = f"attack_{kind}"
        mode = self._resolve_weapon_attack_mode(kind)
        direction = self._resolve_attack_direction_token()
        style = str(self._weapon_combo_style() or "").strip().lower()
        if self._is_ranged_weapon_style(style):
            shoot_token = "crossbow_shoot" if style == "crossbow" else "bow_shoot"
            tokens = [
                shoot_token,
                f"{shoot_token}_{kind}",
                f"{style}_shoot",
                f"{style}_shot",
            ]
            if mode:
                tokens.append(f"{base}_{mode}")
                tokens.append(f"attack_{mode}")
            # Keep legacy attack tokens for compatibility fallbacks.
            tokens.extend([f"attack_{kind}_both", "attack_both", base, "attack"])
            return self._dedupe_tokens(tokens)

        tokens = []
        if direction:
            tokens.append(f"{base}_{direction}")
            tokens.append(f"attack_{direction}")
        if mode:
            tokens.append(f"{base}_{mode}")
            tokens.append(f"attack_{mode}")
            if mode == "dual":
                tokens.append("attack_dual")
        tokens.append(base)
        tokens.append("attack")
        return self._dedupe_tokens(tokens)

    def _refresh_spell_cache(self):
        keys = []
        if hasattr(self.data_mgr, "get_spellbook_keys"):
            try:
                keys = list(self.data_mgr.get_spellbook_keys())
            except Exception:
                keys = []
        if not keys:
            keys = list(self.data_mgr.spells.keys())

        cleaned = []
        seen = set()
        for raw in keys:
            token = str(raw or "").strip()
            if not token:
                continue
            norm = token.lower()
            if norm in seen:
                continue
            seen.add(norm)
            cleaned.append(token)

        melee_idx = -1
        for idx, token in enumerate(cleaned):
            if is_melee_wheel_token(token):
                melee_idx = idx
                break
        if melee_idx < 0:
            cleaned.insert(0, DEFAULT_MELEE_WHEEL_TOKEN)
        elif melee_idx > 0:
            melee = cleaned.pop(melee_idx)
            cleaned.insert(0, melee)

        self._spell_cache = cleaned
        if not self._spell_cache:
            self._active_spell_idx = 0
            self._ultimate_spell_idx = 0
            return

        if self._active_spell_idx >= len(self._spell_cache):
            self._active_spell_idx = 0

        best_idx = 0
        best_score = float("-inf")
        for idx, spell_key in enumerate(self._spell_cache):
            if is_melee_wheel_token(spell_key):
                continue
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

    def _spell_current_fatigue(self):
        cs = getattr(self, "cs", None)
        if cs is None:
            return 0.0
        max_stamina = max(1.0, self._safe_float(getattr(cs, "maxStamina", 100.0), default=100.0))
        stamina = self._safe_float(getattr(cs, "stamina", max_stamina), default=max_stamina)
        ratio = max(0.0, min(1.0, stamina / max_stamina))
        return 1.0 - ratio

    def _spell_scatter_profile(self, spell_key, spell_data, *, cast_family="projectile", cast_time=0.0):
        payload = spell_data if isinstance(spell_data, dict) else {}
        runtime_cfg = payload.get("runtime", {})
        if not isinstance(runtime_cfg, dict):
            runtime_cfg = {}
        scatter_cfg = runtime_cfg.get("scatter", {})
        if not isinstance(scatter_cfg, dict):
            scatter_cfg = {}
        telegraph_cfg = runtime_cfg.get("telegraph", {})
        if not isinstance(telegraph_cfg, dict):
            telegraph_cfg = {}
        projectile_cfg = payload.get("projectile", {})
        if not isinstance(projectile_cfg, dict):
            projectile_cfg = {}

        speed = self._safe_float(
            projectile_cfg.get("speed", payload.get("speed", 0.0)),
            default=0.0,
        )
        impact_telegraph = bool(telegraph_cfg.get("enabled")) and (
            self._safe_str(telegraph_cfg.get("anchor", ""), default="").lower() == "impact"
        )
        default_enabled = (
            cast_family == "projectile"
            and not impact_telegraph
            and (cast_time <= 0.28 or speed >= 30.0)
        )
        return {
            "enabled": bool(scatter_cfg.get("enabled", default_enabled)),
            "max_lateral": max(0.0, self._safe_float(scatter_cfg.get("max_lateral", 0.55), default=0.55)),
            "spam_gain": max(0.0, self._safe_float(scatter_cfg.get("spam_gain", 0.22), default=0.22)),
            "decay_per_sec": max(0.0, self._safe_float(scatter_cfg.get("decay_per_sec", 1.35), default=1.35)),
            "fatigue_weight": max(0.0, self._safe_float(scatter_cfg.get("fatigue_weight", 0.46), default=0.46)),
            "spam_weight": max(0.0, self._safe_float(scatter_cfg.get("spam_weight", 0.38), default=0.38)),
            "pattern": tuple(scatter_cfg.get("pattern", (0.0, 0.38, -0.58, 0.76, -0.88, 1.0))),
            "heat": 0.0,
            "fatigue": 0.0,
            "lateral": 0.0,
            "cast_count": 0,
        }

    def _apply_spell_scatter_runtime(self, spell_key, runtime, now):
        payload = runtime if isinstance(runtime, dict) else {}
        scatter = payload.get("scatter", {})
        if not isinstance(scatter, dict) or not scatter.get("enabled"):
            return payload

        state_map = getattr(self, "_spell_scatter_state", None)
        if not isinstance(state_map, dict):
            state_map = {}
            self._spell_scatter_state = state_map

        scatter_key = self._safe_str(payload.get("id", spell_key), default=str(spell_key)).lower()
        state = state_map.get(scatter_key, {})
        if not isinstance(state, dict):
            state = {}

        heat = max(0.0, self._safe_float(state.get("heat", 0.0), default=0.0))
        last_time = self._safe_float(state.get("last_time", now), default=now)
        heat = max(
            0.0,
            heat - (max(0.0, now - last_time) * self._safe_float(scatter.get("decay_per_sec", 1.35), default=1.35)),
        )
        heat = min(1.0, heat + self._safe_float(scatter.get("spam_gain", 0.22), default=0.22))
        cast_count = max(1, int(self._safe_float(state.get("cast_count", 0), default=0.0)) + 1)
        fatigue = self._spell_current_fatigue()
        strength = min(
            1.0,
            (heat * self._safe_float(scatter.get("spam_weight", 0.38), default=0.38))
            + (fatigue * self._safe_float(scatter.get("fatigue_weight", 0.46), default=0.46)),
        )
        pattern = scatter.get("pattern", ())
        if not isinstance(pattern, (list, tuple)) or not pattern:
            pattern = (0.0, 0.38, -0.58, 0.76, -0.88, 1.0)
        direction = self._safe_float(pattern[(cast_count - 1) % len(pattern)], default=0.0)
        lateral = self._safe_float(scatter.get("max_lateral", 0.55), default=0.55) * strength * direction

        scatter["heat"] = heat
        scatter["fatigue"] = fatigue
        scatter["lateral"] = lateral
        scatter["cast_count"] = cast_count
        state_map[scatter_key] = {
            "heat": heat,
            "last_time": now,
            "cast_count": cast_count,
        }
        return payload

    def _scatter_spell_destination(self, origin, destination, runtime):
        payload = runtime if isinstance(runtime, dict) else {}
        scatter = payload.get("scatter", {})
        if not isinstance(scatter, dict) or not scatter.get("enabled"):
            return destination

        lateral = self._safe_float(scatter.get("lateral", 0.0), default=0.0)
        if abs(lateral) <= 1e-4:
            return destination

        delta_x = float(destination.x) - float(origin.x)
        delta_y = float(destination.y) - float(origin.y)
        planar_len = math.hypot(delta_x, delta_y)
        if planar_len <= 1e-4:
            return destination

        side_x = -delta_y / planar_len
        side_y = delta_x / planar_len
        return Vec3(
            destination.x + (side_x * lateral),
            destination.y + (side_y * lateral),
            destination.z,
        )

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
        anim_trigger = self._resolve_spell_anim_trigger(spell_key, payload, runtime)
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
        cast_family = self._spell_cast_family(spell_key, payload)
        telegraph = self._spell_telegraph_profile(
            spell_key,
            payload,
            cast_time=cast_time,
            damage_type=damage_type,
            cast_family=cast_family,
        )
        vfx_windows = self._spell_vfx_windows(
            spell_key,
            payload,
            cast_family=cast_family,
            damage_type=damage_type,
        )
        scatter = self._spell_scatter_profile(
            spell_key,
            payload,
            cast_family=cast_family,
            cast_time=cast_time,
        )

        return {
            "id": self._safe_str(payload.get("id", spell_key), default=str(spell_key)).lower(),
            "label": label,
            "cast_time": cast_time,
            "cooldown": cooldown,
            "anim_trigger": anim_trigger,
            "cast_family": cast_family,
            "telegraph": telegraph,
            "vfx_windows": vfx_windows,
            "scatter": scatter,
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

    def get_hud_combo_state(self):
        self._decay_combo_chain()
        count = int(getattr(self, "_combo_chain", 0) or 0)
        if count <= 0:
            return None
        now = globalClock.getFrameTime()
        remain = max(0.0, float(getattr(self, "_combo_deadline", 0.0) or 0.0) - now)
        if remain <= 0.0:
            return None
        return {
            "count": count,
            "style": str(getattr(self, "_combo_style", "unarmed") or "unarmed"),
            "kind": str(getattr(self, "_combo_kind", "melee") or "melee"),
            "remain": remain,
        }

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

    def _combat_style_config(self, style_name):
        getter = getattr(self.data_mgr, "get_combat_style", None)
        if callable(getter):
            try:
                payload = getter(style_name)
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        return {}

    def _weapon_combo_style(self):
        item = {}
        if hasattr(self, "_equipment_state") and isinstance(self._equipment_state, dict):
            token = str(self._equipment_state.get("weapon_main", "") or "").strip()
            if token:
                payload = self.data_mgr.get_item(token) if hasattr(self, "data_mgr") else {}
                if isinstance(payload, dict):
                    item = payload

        raw_class = ""
        if isinstance(item, dict):
            raw_class = str(item.get("weapon_class", "") or item.get("weapon_type", "")).strip().lower()
            if not raw_class:
                visual = item.get("equip_visual", {})
                if isinstance(visual, dict):
                    raw_class = str(visual.get("style", "") or "").strip().lower()
            if not raw_class:
                name = str(item.get("name", "") or "").strip().lower()
                if "axe" in name:
                    raw_class = "axe"
                elif "mace" in name or "hammer" in name:
                    raw_class = "mace"
                elif "bow" in name:
                    raw_class = "bow"
                elif "crossbow" in name:
                    raw_class = "crossbow"
                elif "staff" in name:
                    raw_class = "staff"
                elif any(marker in name for marker in ("focus", "orb", "wand", "arcane")):
                    raw_class = "magic"
                elif "sword" in name or "blade" in name:
                    raw_class = "sword"

        alias = {
            "blade": "sword",
            "unarmed": "unarmed",
            "sword": "sword",
            "axe": "axe",
            "mace": "mace",
            "bow": "bow",
            "crossbow": "crossbow",
            "staff": "staff",
            "focus": "magic",
            "orb": "magic",
            "wand": "magic",
            "magic": "magic",
        }
        return alias.get(raw_class, "unarmed")

    def _is_both_hand_flow_style(self, style_name):
        token = str(style_name or "").strip().lower()
        return token in {"staff", "bow", "crossbow", "magic"}

    def _is_ranged_weapon_style(self, style_name):
        token = str(style_name or "").strip().lower()
        return token in {"bow", "crossbow"}

    def _is_ranged_weapon_equipped(self):
        style = "unarmed"
        try:
            style = str(self._weapon_combo_style() or "unarmed").strip().lower()
        except Exception:
            style = "unarmed"
        return self._is_ranged_weapon_style(style)

    def _resolve_aim_mode(self, selected_label, aim_pressed=False):
        if not bool(aim_pressed):
            return ""
        if should_cast_selected_spell(
            light_pressed=True,
            selected_label=selected_label,
            explicit_cast=False,
        ):
            return "magic"
        if self._is_ranged_weapon_equipped():
            return "bow"
        return ""

    def _sync_aim_mode(self, selected_label, aim_pressed=False):
        mode = self._resolve_aim_mode(selected_label=selected_label, aim_pressed=aim_pressed)
        previous_mode = str(getattr(self, "_aim_mode", "") or "")
        self._aim_mode = str(mode or "")
        self._is_aiming = bool(mode)
        is_bow_aim = str(mode or "").strip().lower() == "bow"
        was_bow_aim = bool(getattr(self, "_bow_aim_latched", False))
        set_hints = getattr(self, "_set_state_anim_hints", None)

        if is_bow_aim:
            if callable(set_hints):
                set_hints("blocking", ["bow_aim", "aim_bow", "blocking"])
            else:
                self._apply_state_anim_hint_tokens("blocking", ["bow_aim", "aim_bow", "blocking"])
            if not was_bow_aim:
                self._bow_aim_latched = True
                queue_trigger = getattr(self, "_queue_state_trigger", None)
                if callable(queue_trigger):
                    queue_trigger("block_start")
                force_action = getattr(self, "_force_action_state", None)
                if callable(force_action):
                    force_action("blocking")
        else:
            if was_bow_aim:
                self._bow_aim_latched = False
                if callable(set_hints):
                    set_hints("blocking", [])
                if not bool(getattr(self, "_block_pressed", False)):
                    queue_trigger = getattr(self, "_queue_state_trigger", None)
                    if callable(queue_trigger):
                        queue_trigger("block_end")
            elif callable(set_hints) and previous_mode.strip().lower() == "bow":
                set_hints("blocking", [])
        return mode

    def _ranged_weapon_profile(self):
        style = str(self._weapon_combo_style() or "bow").strip().lower()
        is_crossbow = style == "crossbow"
        base_damage = 26.0 if is_crossbow else 20.0
        base_range = 48.0 if is_crossbow else 42.0
        base_falloff = 32.0 if is_crossbow else 26.0
        base_rate = 1.04 if is_crossbow else 1.15

        item = {}
        equipment = getattr(self, "_equipment_state", {})
        if isinstance(equipment, dict):
            token = str(equipment.get("weapon_main", "") or "").strip()
            if token:
                getter = getattr(getattr(self, "data_mgr", None), "get_item", None)
                if callable(getter):
                    payload = getter(token) or {}
                    if isinstance(payload, dict):
                        item = payload

        runtime_cfg = item.get("runtime", {}) if isinstance(item, dict) else {}
        if not isinstance(runtime_cfg, dict):
            runtime_cfg = {}
        ranged_cfg = runtime_cfg.get("ranged", {})
        if not isinstance(ranged_cfg, dict):
            ranged_cfg = {}

        damage = self._safe_float(
            ranged_cfg.get(
                "damage",
                runtime_cfg.get("ranged_damage", runtime_cfg.get("damage", item.get("power", base_damage))),
            ),
            default=base_damage,
        )
        range_m = self._safe_float(
            ranged_cfg.get("range", runtime_cfg.get("ranged_range", base_range)),
            default=base_range,
        )
        falloff = self._safe_float(
            ranged_cfg.get("falloff_start", runtime_cfg.get("ranged_falloff_start", base_falloff)),
            default=base_falloff,
        )
        sfx = self._safe_str(
            ranged_cfg.get("sfx", runtime_cfg.get("sfx_shot", "spell_cast")),
            default="spell_cast",
        )
        sfx_volume = self._safe_float(
            ranged_cfg.get("sfx_volume", runtime_cfg.get("sfx_volume", 0.82)),
            default=0.82,
        )
        sfx_rate = self._safe_float(
            ranged_cfg.get("sfx_rate", runtime_cfg.get("sfx_rate", base_rate)),
            default=base_rate,
        )
        label = self._safe_str(item.get("name", style), default=style)

        damage = max(1.0, min(280.0, damage))
        range_m = max(6.0, min(90.0, range_m))
        falloff = max(3.0, min(range_m, falloff))
        sfx_volume = max(0.0, min(1.6, sfx_volume))
        sfx_rate = max(0.55, min(1.65, sfx_rate))

        return {
            "style": style,
            "damage": damage,
            "range": range_m,
            "falloff_start": falloff,
            "sfx": sfx,
            "sfx_volume": sfx_volume,
            "sfx_rate": sfx_rate,
            "label": label,
        }

    def _current_aim_target(self):
        info = getattr(getattr(self, "app", None), "_aim_target_info", None)
        return info if isinstance(info, dict) else None

    def _compute_ranged_damage(self, profile, target_info):
        cfg = profile if isinstance(profile, dict) else {}
        base_damage = int(round(max(1.0, float(cfg.get("damage", 1.0) or 1.0))))
        if not isinstance(target_info, dict):
            return 0
        if str(target_info.get("kind", "") or "").strip().lower() != "enemy":
            return 0

        distance = self._safe_float(target_info.get("distance", 999.0), default=999.0)
        max_range = max(2.0, self._safe_float(cfg.get("range", 40.0), default=40.0))
        if distance > max_range:
            return 0

        falloff_start = max(1.0, min(max_range, self._safe_float(cfg.get("falloff_start", max_range), default=max_range)))
        if distance <= falloff_start or abs(max_range - falloff_start) <= 1e-4:
            return base_damage

        t = (distance - falloff_start) / max(1e-4, (max_range - falloff_start))
        t = max(0.0, min(1.0, t))
        mul = 1.0 - (0.45 * t)
        # Sneak Attack Multiplier
        ss = getattr(self, '_stealth_state_cache', {})
        if ss.get('state') == 'hidden':
            mul *= 2.5
        return max(1, int(round(base_damage * mul)))

    def _resolve_enemy_unit_for_target(self, target_info):
        if not isinstance(target_info, dict):
            return None
        enemy_id = str(target_info.get("id", "") or "").strip().lower()
        if not enemy_id:
            return None

        roster = getattr(getattr(self, "app", None), "boss_manager", None)
        units = getattr(roster, "units", []) if roster else []
        for unit in units:
            unit_id = str(getattr(unit, "id", "") or "").strip().lower()
            if unit_id and unit_id == enemy_id:
                return unit
        dragon = getattr(getattr(self, "app", None), "dragon_boss", None)
        dragon_id = str(getattr(dragon, "id", "") or "dragon_boss").strip().lower()
        if dragon and dragon_id == enemy_id:
            return dragon
        return None

    def _apply_ranged_damage(self, target_info, damage):
        amount = int(max(0, damage))
        if amount <= 0:
            return False
        unit = self._resolve_enemy_unit_for_target(target_info)
        if unit is None:
            return False

        hp_before = self._safe_float(getattr(unit, "hp", 0.0), default=0.0)
        damage_hook = getattr(unit, "take_damage", None)
        if callable(damage_hook):
            try:
                damage_hook(float(amount), "physical", source=self)
            except TypeError:
                try:
                    damage_hook(float(amount), "physical")
                except Exception:
                    return False
            except Exception:
                return False
            hp_after = self._safe_float(getattr(unit, "hp", hp_before), default=hp_before)
            return hp_after < hp_before

        hp_after = max(0.0, hp_before - float(amount))
        try:
            unit.hp = hp_after
        except Exception:
            return False

        proxy = getattr(unit, "proxy", None)
        if proxy is not None and hasattr(proxy, "health"):
            try:
                proxy.health = hp_after
            except Exception:
                pass
        if hasattr(unit, "_damage_flash"):
            try:
                unit._damage_flash = max(float(getattr(unit, "_damage_flash", 0.0) or 0.0), 0.16)
            except Exception:
                pass
        if hasattr(unit, "_pending_hit_react"):
            try:
                unit._pending_hit_react = max(float(getattr(unit, "_pending_hit_react", 0.0) or 0.0), 0.18)
            except Exception:
                pass
        return hp_after < hp_before

    def _perform_ranged_attack(self, attack_kind="light"):
        if not self._is_ranged_weapon_equipped():
            return False

        profile = self._ranged_weapon_profile()
        sfx_key = str(profile.get("sfx", "") or "").strip()
        if sfx_key:
            self._play_sfx(
                sfx_key,
                volume=float(profile.get("sfx_volume", 0.82)),
                rate=float(profile.get("sfx_rate", 1.12)),
            )

        attack_triggers = self._resolve_weapon_attack_triggers(attack_kind)
        self._apply_state_anim_hint_tokens("attacking", attack_triggers)
        for trigger in attack_triggers:
            self._queue_state_trigger(trigger)
        self._force_action_state("attacking")

        target_info = self._current_aim_target()
        damage = self._compute_ranged_damage(profile, target_info)
        hit = self._apply_ranged_damage(target_info, damage) if damage > 0 else False
        if hit:
            self._play_sfx("enemy_hit", volume=0.78)
            self._push_combat_event("physical", damage, source_label=profile.get("label", "ranged"))
            self._register_combo_step("ranged", amount=1)

            director = getattr(getattr(self, "app", None), "camera_director", None)
            if director and hasattr(director, "emit_impact"):
                try:
                    director.emit_impact("hit", intensity=0.42)
                except Exception:
                    pass
            time_fx = getattr(getattr(self, "app", None), "time_fx", None)
            if time_fx and hasattr(time_fx, "trigger"):
                try:
                    time_fx.trigger("micro_hit", duration=0.08)
                except Exception:
                    pass
        return True

    def _resolve_combo_style(self, kind):
        token = str(kind or "melee").strip().lower()
        airborne = False
        if hasattr(self, "cs") and self.cs:
            airborne = not bool(getattr(self.cs, "grounded", True))
        if token == "magic":
            return "aerial_magic" if airborne else "magic"
        base = self._weapon_combo_style()
        if airborne:
            return "aerial_melee"
        return base

    def _decay_combo_chain(self):
        now = globalClock.getFrameTime()
        if now <= float(getattr(self, "_combo_deadline", 0.0) or 0.0):
            return
        if int(getattr(self, "_combo_chain", 0) or 0) <= 0:
            return
        self._combo_chain = 0
        self._combo_kind = "melee"
        self._combo_style = "unarmed"
        cs = getattr(self, "cs", None)
        if cs and hasattr(cs, "comboCount"):
            try:
                cs.comboCount = 0
            except Exception:
                pass
        if cs and hasattr(cs, "comboTimer"):
            try:
                cs.comboTimer = 0.0
            except Exception:
                pass

    def _register_combo_step(self, kind, amount=1):
        self._decay_combo_chain()
        style = self._resolve_combo_style(kind)
        cfg = self._combat_style_config(style)
        window = self._safe_float(cfg.get("combo_window", 0.72), default=0.72)
        max_chain = int(self._safe_float(cfg.get("max_chain", 7), default=7))
        now = globalClock.getFrameTime()
        if now <= float(getattr(self, "_combo_deadline", 0.0) or 0.0):
            self._combo_chain = int(getattr(self, "_combo_chain", 0) or 0) + int(max(1, amount))
        else:
            self._combo_chain = int(max(1, amount))
        self._combo_chain = max(0, min(max_chain, int(self._combo_chain)))
        self._combo_deadline = now + max(0.15, min(2.0, window))
        self._combo_style = style
        self._combo_kind = str(kind or "melee")

        cs = getattr(self, "cs", None)
        if cs and hasattr(cs, "comboCount"):
            try:
                cs.comboCount = int(self._combo_chain)
            except Exception:
                pass
        if cs and hasattr(cs, "comboTimer"):
            try:
                cs.comboTimer = max(0.0, float(self._combo_deadline) - now)
            except Exception:
                pass

        director = getattr(getattr(self, "app", None), "camera_director", None)
        if director and hasattr(director, "emit_impact"):
            try:
                if self._combo_chain >= 5:
                    director.emit_impact("critical", intensity=0.9)
                elif self._combo_chain >= 3:
                    director.emit_impact("hit", intensity=0.35)
            except Exception:
                pass
        time_fx = getattr(getattr(self, "app", None), "time_fx", None)
        if time_fx and hasattr(time_fx, "trigger"):
            try:
                if self._combo_chain >= 5:
                    time_fx.trigger("combo_tick", duration=0.16)
                elif self._combo_chain >= 3:
                    time_fx.trigger("micro_hit", duration=0.10)
            except Exception:
                pass

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
        if HAS_CORE and not self.magic:
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

        spell_type = None
        if HAS_CORE:
            spell_type = self._resolve_spell_type(spell_key, spell_data)
            if not spell_type:
                return False

        runtime = self._apply_spell_scatter_runtime(spell_key, runtime, now)

        if runtime.get("cast_sfx"):
            self._play_sfx(runtime["cast_sfx"], volume=0.9)

        if runtime["cast_time"] > 0.0:
            self._spell_cast_lock_until = now + runtime["cast_time"]
            delay = max(0.1, runtime["cast_time"] * 0.4)
        else:
            delay = 0.0

        self._pending_spell = {
            "type": spell_type,
            "key": spell_key,
            "data": spell_data,
            "runtime": runtime,
        }
        self._pending_spell_release_time = now + delay

        self._set_weapon_drawn(True)
        cast_triggers = self._resolve_spell_anim_triggers(spell_key, spell_data, runtime)
        self._apply_state_anim_hint_tokens("casting", cast_triggers)
        for trigger in cast_triggers:
            self._queue_state_trigger(trigger)
        self._force_action_state("casting")
        self._emit_spell_telegraph(runtime)
        self._emit_spell_phase_vfx(runtime, "prepare")

        # Add a hand burst VFX for immediate feedback
        magic_vfx = getattr(self.app, "magic_vfx", None)
        if magic_vfx:
            token = getattr(self, "_next_cast_hand", "right")
            hand_node = getattr(self, "_right_hand" if token == "right" else "_left_hand", None)
            if hand_node:
                damage_type = self._spell_damage_type(spell_key, spell_data)
                color_list = self._spell_default_color(damage_type)
                from panda3d.core import Vec4
                color = Vec4(*color_list) if isinstance(color_list, (list, tuple)) else Vec4(0.4, 0.7, 1.0, 0.8)
                magic_vfx.spawn_hand_burst_vfx(hand_node, color=color)

        return True

    def _update_spell_casting(self):
        pending = getattr(self, "_pending_spell", None)
        if not pending:
            return

        now = globalClock.getFrameTime()
        if now >= getattr(self, "_pending_spell_release_time", 0.0):
            self._release_pending_spell()

    def _cancel_pending_spell(self):
        self._pending_spell = None
        self._pending_spell_release_time = 0.0

    def _spell_forward_target_pos(self, runtime=None):
        actor = getattr(self, "actor", None)
        if not actor:
            return None
        try:
            pos = actor.getPos(getattr(self, "render", None))
        except Exception:
            try:
                pos = actor.getPos()
            except Exception:
                return None

        heading_deg = 0.0
        try:
            heading_deg = float(actor.getH())
        except Exception:
            heading_deg = 0.0

        heading_rad = math.radians(heading_deg)
        dir_x = math.sin(heading_rad)
        dir_y = math.cos(heading_rad)
        target_distance = self._safe_float(
            (runtime or {}).get("target_distance", 7.0) if isinstance(runtime, dict) else 7.0,
            default=7.0,
        )
        origin = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.0)
        return Vec3(origin.x + (dir_x * target_distance), origin.y + (dir_y * target_distance), origin.z + 0.2)

    def _build_python_spell_effect(self, spell_key, runtime):
        actor = getattr(self, "actor", None)
        if not actor:
            return None
        try:
            pos = actor.getPos(getattr(self, "render", None))
        except Exception:
            try:
                pos = actor.getPos()
            except Exception:
                return None

        origin = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.0)
        destination = self._spell_forward_target_pos(runtime)
        if destination is None:
            destination = Vec3(origin.x, origin.y + 7.0, origin.z + 0.2)
        destination = self._scatter_spell_destination(origin, destination, runtime)
        damage_type = str(runtime.get("damage_type", self._spell_damage_type(spell_key, {})) or "arcane")
        particle_tag = str(runtime.get("particle_tag", "") or "").strip()
        if not particle_tag:
            particle_tag = damage_type
        return SimpleNamespace(
            pos=origin,
            destination=destination,
            radius=5.0,
            particleTag=particle_tag,
        )

    def _resolve_spell_anchor_pos(self, runtime, anchor="self"):
        token = self._safe_str(anchor, default="self").lower()
        actor = getattr(self, "actor", None)
        if not actor:
            return None
        if token == "impact":
            return self._spell_forward_target_pos(runtime)
        try:
            return actor.getPos(getattr(self, "render", None))
        except Exception:
            try:
                return actor.getPos()
            except Exception:
                return None

    def _emit_spell_telegraph(self, runtime):
        payload = runtime if isinstance(runtime, dict) else {}
        telegraph = payload.get("telegraph", {})
        if not isinstance(telegraph, dict) or not telegraph.get("enabled"):
            return None

        magic_vfx = getattr(getattr(self, "app", None), "magic_vfx", None)
        spawn = getattr(magic_vfx, "spawn_spell_telegraph_vfx", None)
        if not callable(spawn):
            return None

        pos = self._resolve_spell_anchor_pos(payload, telegraph.get("anchor", "self"))
        if pos is None:
            return None

        try:
            radius = float(telegraph.get("radius", 4.0) or 4.0)
        except Exception:
            radius = 4.0
        try:
            duration = float(telegraph.get("duration", 0.18) or 0.18)
        except Exception:
            duration = 0.18
        color = telegraph.get("color", [0.52, 0.82, 1.0, 0.28])

        try:
            return spawn(pos, radius=radius, color=color, duration=duration)
        except Exception:
            return None

    def _emit_spell_phase_vfx(self, runtime, phase, *, pos=None):
        payload = runtime if isinstance(runtime, dict) else {}
        phase_key = self._safe_str(phase, default="").lower()
        if not phase_key:
            return None

        windows = payload.get("vfx_windows", {})
        if not isinstance(windows, dict):
            return None
        window = windows.get(phase_key, {})
        if not isinstance(window, dict) or not window.get("enabled", True):
            return None

        magic_vfx = getattr(getattr(self, "app", None), "magic_vfx", None)
        spawn = getattr(magic_vfx, "spawn_spell_phase_vfx", None)
        if not callable(spawn):
            return None

        target = pos
        if target is None:
            target = self._resolve_spell_anchor_pos(payload, window.get("anchor", "self"))
        if target is None:
            return None

        try:
            return spawn(
                target,
                phase=phase_key,
                color=window.get("color"),
                radius=float(window.get("radius", 1.0) or 1.0),
                duration=float(window.get("duration", 0.12) or 0.12),
            )
        except Exception:
            return None

    def _release_pending_spell(self):
        pending = getattr(self, "_pending_spell", None)
        if not pending:
            return

        spell_type = pending["type"]
        spell_key = pending["key"]
        spell_data = pending["data"]
        runtime = pending["runtime"]
        self._pending_spell = None

        try:
            cast_family = str(runtime.get("cast_family", "") or "").strip().lower()
            anim_trigger = str(runtime.get("anim_trigger", "cast_spell") or "cast_spell")
            release_tokens = []
            if cast_family in {"aoe", "support"}:
                release_tokens.extend([f"{anim_trigger}_release", anim_trigger, "cast_release"])
            else:
                release_tokens.extend(["cast_release", f"{anim_trigger}_release", anim_trigger])
            self._apply_state_anim_hint_tokens(
                "casting",
                self._dedupe_tokens(release_tokens + ["casting"]),
            )
            self._set_anim("casting", loop=False, force=True)
        except Exception:
            pass
        self._emit_spell_phase_vfx(runtime, "release")

        effect = None
        if HAS_CORE and self.magic and self.cs and spell_type:
            effect = self.magic.castSpell(self.cs, spell_type, self.cs.facingDir, self.enemies)
        else:
            effect = self._build_python_spell_effect(spell_key, runtime)
        impact_pos = None
        if effect is not None:
            impact_pos = effect.destination if hasattr(effect, "destination") else getattr(effect, "pos", None)
        self._emit_spell_phase_vfx(runtime, "impact", pos=impact_pos)
        self._on_spell_effect(effect)
        self._register_combo_step("magic", amount=1)

        # Reactive Static Layer (World Influences)
        if hasattr(self.app, "influence_mgr") and self.app.influence_mgr and effect:
            radius = max(3.0, float(getattr(effect, "radius", 5.0)))
            strength = 1.0
            duration = 1.5
            fx_type = "force"

            if "fire" in spell_key:
                fx_type = "fire"
                duration = 2.5
            elif "ice" in spell_key or "blizzard" in spell_key:
                fx_type = "ice"
                duration = 4.0

            pos = effect.destination if hasattr(effect, "destination") else effect.pos
            self.app.influence_mgr.add_influence(fx_type, pos, radius, strength, duration)

        damage_val = 0
        if isinstance(spell_data, dict):
            damage_val = int(spell_data.get("damage", spell_data.get("heal_value", 0)) or 0)
        dmg_type = runtime.get("damage_type") or self._spell_damage_type(spell_key, spell_data)

        if runtime.get("impact_sfx"):
            self._play_sfx(runtime["impact_sfx"], volume=0.95)

        self._push_combat_event(dmg_type, damage_val, source_label=runtime.get("label") or spell_key)

        # Shadow Illusion logic: Toggle Shadow Mode on the player
        if str(spell_key).lower() == "shadowillusion":
            if hasattr(self, "set_shadow_mode"):
                self.set_shadow_mode(True)
                # Refresh/Restart the revert timer
                task_name = "revert-shadow-mode"
                self.app.taskMgr.remove(task_name)
                self.app.taskMgr.doMethodLater(
                    10.0, 
                    lambda task: self.set_shadow_mode(False), 
                    task_name
                )

        cooldowns = getattr(self, "_spell_cooldowns", None)
        if isinstance(cooldowns, dict) and runtime["cooldown"] > 0.0:
            cooldowns[spell_key] = globalClock.getFrameTime() + runtime["cooldown"]

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
            self._register_combo_step("melee", amount=1)
            director = getattr(getattr(self, "app", None), "camera_director", None)
            if director and hasattr(director, "emit_impact"):
                try:
                    director.emit_impact("hit", intensity=0.6)
                except Exception:
                    pass
            time_fx = getattr(getattr(self, "app", None), "time_fx", None)
            if time_fx and hasattr(time_fx, "trigger"):
                try:
                    time_fx.trigger("micro_hit", duration=0.10)
                except Exception:
                    pass
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
        if not fx:
            return
        
        pos = Vec3(fx.pos.x, fx.pos.y, fx.pos.z)
        tag = str(getattr(fx, "particleTag", "") or "").strip().lower()
        
        # Use advanced Python-side VFX if available for favored schools
        magic_vfx = getattr(self.app, "magic_vfx", None)
        if magic_vfx:
            if "nova" in tag:
                magic_vfx.spawn_nova_vfx(pos)
                return
            elif "meteor" in tag:
                magic_vfx.spawn_meteor_vfx(pos)
                return
            elif "ward" in tag:
                magic_vfx.spawn_ward_vfx(pos)
                return

        if self.particles and HAS_CORE:
            pos_core = gc.Vec3(fx.pos.x, fx.pos.y, fx.pos.z)
            if "fire" in tag:
                self.particles.spawnFireball(pos_core)
            elif "heal" in tag:
                self.particles.spawnHealAura(pos_core)
            else:
                self.particles.spawnFireball(pos_core)

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
            "combo_state": {
                "count": int(getattr(self, "_combo_chain", 0) or 0),
                "style": str(getattr(self, "_combo_style", "unarmed") or "unarmed"),
                "kind": str(getattr(self, "_combo_kind", "melee") or "melee"),
                "remain": max(0.0, float(getattr(self, "_combo_deadline", 0.0) or 0.0) - now),
            },
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

        combo_state = payload.get("combo_state", {})
        if isinstance(combo_state, dict):
            self._combo_chain = int(self._safe_float(combo_state.get("count", 0), default=0.0))
            self._combo_style = self._safe_str(combo_state.get("style", "unarmed"), default="unarmed")
            self._combo_kind = self._safe_str(combo_state.get("kind", "melee"), default="melee")
            remain = max(0.0, self._safe_float(combo_state.get("remain", 0.0), default=0.0))
            self._combo_deadline = now + remain
            cs = getattr(self, "cs", None)
            if cs and hasattr(cs, "comboCount"):
                try:
                    cs.comboCount = int(self._combo_chain)
                except Exception:
                    pass
            if cs and hasattr(cs, "comboTimer"):
                try:
                    cs.comboTimer = remain
                except Exception:
                    pass
