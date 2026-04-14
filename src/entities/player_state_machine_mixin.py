"""State machine and animation transition helpers for Player.

Implements a layered priority FSM:
  Layer priority (lower = wins):
    -1 cinematic, 0 death, 1 physics, 2 stability, 3 action, 4 locomotion, 5 modifier
"""

import math
import re

from direct.showbase.ShowBaseGlobal import globalClock

from entities.player_animation_config import (
    DEFAULT_STATE_DURATIONS,
    INTERRUPT_RULES,
    LAYER_PRIORITY,
    STATE_LAYER_MAP,
    UNINTERRUPTIBLE_STATES,
)


class PlayerStateMachineMixin:
    def _set_state_anim_hints(self, state_name, tokens):
        key = str(state_name or "").strip().lower()
        if not key:
            return
        hints = getattr(self, "_state_anim_hints", None)
        if not isinstance(hints, dict):
            hints = {}
            self._state_anim_hints = hints
        cleaned = []
        seen = set()
        for token in tokens or []:
            value = str(token or "").strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        if cleaned:
            hints[key] = cleaned
        else:
            hints.pop(key, None)

    def _parkour_action_token(self):
        raw = str(self._parkour_action_name() or "").strip().lower()
        if not raw:
            return ""
        return raw.replace("-", "_").replace(" ", "_")

    def _parkour_action_profile(self, action_token=None):
        token = str(action_token or self._parkour_action_token() or "").strip().lower()
        if not token:
            return {}

        cs = getattr(self, "cs", None)
        vx = float(getattr(getattr(cs, "velocity", None), "x", 0.0) or 0.0)
        vy = float(getattr(getattr(cs, "velocity", None), "y", 0.0) or 0.0)
        speed = math.sqrt((vx * vx) + (vy * vy))
        obstacle_ahead = "obstacle_ahead" in set(getattr(self, "_env_flags", set()) or set())
        wall_contact = "wall_contact" in set(getattr(self, "_env_flags", set()) or set())

        if token in {"vault_high"}:
            return {"state": "vaulting", "tokens": ["vault_high", "vaulting", "run"]}
        if token in {"vault", "vault_low", "vault_speed", "vaulting", "vault_over"}:
            if token == "vault_speed" or (obstacle_ahead and speed >= max(4.2, float(getattr(self, "run_speed", 8.0) or 8.0) * 0.65)):
                primary = "vault_speed"
            elif token == "vault_low" or obstacle_ahead:
                primary = "vault_low"
            else:
                primary = "vaulting"
            return {"state": "vaulting", "tokens": [primary, "vaulting", "run", "walk"]}
        if token in {"grab_ledge", "ledge_grab"}:
            return {"state": "climbing", "tokens": ["grab_ledge", "climbing", "run"], "ik": True}
        if token in {"climb", "climbing", "climb_fast", "climb_slow"}:
            primary = "climb_fast" if token == "climb_fast" or (obstacle_ahead and speed >= max(2.2, float(getattr(self, "walk_speed", 4.0) or 4.0) * 0.75)) else "climbing"
            return {"state": "climbing", "tokens": [primary, "climbing", "run", "walk"], "ik": True}
        if token in {"wallrun", "wall_run", "wallrun_start"} or wall_contact:
            timer = float(getattr(getattr(self, "ps", None), "timer", 0.0) or 0.0)
            primary = "wallrun_start" if timer <= 0.22 or token.endswith("_start") else "wallrun"
            return {"state": "wallrun", "tokens": [primary, "wallrun", "run", "walk"]}
        return {}

    def _sync_parkour_runtime_hints(self):
        clear_states = ("flying", "swim", "vaulting", "climbing", "wallrun", "recovering")
        for state_name in clear_states:
            self._set_state_anim_hints(state_name, [])

        cs = getattr(self, "cs", None)
        vx = float(getattr(getattr(cs, "velocity", None), "x", 0.0) or 0.0)
        vy = float(getattr(getattr(cs, "velocity", None), "y", 0.0) or 0.0)
        vz = float(getattr(getattr(cs, "velocity", None), "z", 0.0) or 0.0)
        speed = math.sqrt((vx * vx) + (vy * vy))
        now = float(globalClock.getFrameTime())

        if now < float(getattr(self, "_air_dash_until", 0.0) or 0.0):
            self._set_state_anim_hints("jumping", ["jump_dash", "jumping", "falling"])
            self._set_state_anim_hints("falling", ["jump_dash", "falling", "jumping"])

        if bool(getattr(self, "_is_flying", False)):
            if now < float(getattr(self, "_flight_airdash_until", 0.0) or 0.0):
                flight_hint = "flight_airdash"
            elif now < float(getattr(self, "_flight_takeoff_until", 0.0) or 0.0):
                flight_hint = "flight_takeoff"
            elif vz < -1.05:
                flight_hint = "flight_dive"
            elif speed > 2.6 or abs(vz) > 0.45:
                flight_hint = "flight_glide"
            else:
                flight_hint = "flight_hover"
            self._set_state_anim_hints("flying", [flight_hint, "flying"])

        in_water = bool(getattr(cs, "inWater", False) or getattr(self, "_py_in_water", False))
        if in_water:
            if vz < -0.35:
                swim_hint = "swim_dive"
            elif speed < 0.55 and abs(vz) < 0.4:
                swim_hint = "swim_surface"
            else:
                swim_hint = "swim"
            self._set_state_anim_hints("swim", [swim_hint, "swim"])

        action_token = self._parkour_action_token()
        profile = self._parkour_action_profile(action_token)
        if profile:
            self._set_state_anim_hints(profile.get("state"), profile.get("tokens", []))
            self._parkour_last_action = action_token
        elif str(getattr(self, "_parkour_last_action", "") or "").strip().lower().startswith("wallrun"):
            exit_until = float(getattr(self, "_parkour_exit_hint_until", -1.0) or -1.0)
            if exit_until < now:
                exit_until = now + 0.20
                self._parkour_exit_hint_until = exit_until
            if now <= exit_until:
                self._set_state_anim_hints("recovering", ["wallrun_exit", "recovering", "landing"])

    def _update_parkour_ik(self, dt):
        controls = getattr(self, "_parkour_ik_controls", None)
        action_token = str(self._parkour_action_token() or "").strip().lower()
        active = action_token in {
            "grab_ledge",
            "ledge_grab",
            "climb",
            "climbing",
            "climb_fast",
            "climb_slow",
        }
        current = float(getattr(self, "_parkour_ik_alpha", 0.0) or 0.0)
        delta = (4.0 if active else -4.5) * max(0.0, float(dt or 0.0))
        current = max(0.0, min(1.0, current + delta))
        self._parkour_ik_alpha = current
        if not active or not isinstance(controls, dict) or current <= 0.0:
            return

        profile = {
            "right_hand": (0.0, -18.0 * current, 4.0 * current),
            "left_hand": (0.0, -16.0 * current, -4.0 * current),
            "right_foot": (0.0, 8.0 * current, 0.0),
            "left_foot": (0.0, 7.0 * current, 0.0),
            "spine": (0.0, -6.0 * current, 0.0),
        }
        for key, hpr in profile.items():
            node = controls.get(key)
            if node and hasattr(node, "setHpr"):
                try:
                    node.setHpr(*hpr)
                except Exception:
                    continue

    def _resolve_flight_phase(self, context):
        if not bool((context or {}).get("is_flying", False)):
            self._flight_phase_cache = ""
            return ""

        now = float(globalClock.getFrameTime())
        if now < float(getattr(self, "_flight_airdash_until", 0.0) or 0.0):
            self._flight_phase_cache = "flight_airdash"
            return "flight_airdash"
        takeoff_until = float(getattr(self, "_flight_takeoff_until", 0.0) or 0.0)
        if now < takeoff_until:
            self._flight_phase_cache = "flight_takeoff"
            return "flight_takeoff"

        speed = float((context or {}).get("speed", 0.0) or 0.0)
        vertical_speed = float((context or {}).get("vertical_speed", 0.0) or 0.0)
        resolved = "flight_hover"
        if vertical_speed < -1.05:
            resolved = "flight_dive"
        elif speed > 2.6 or abs(vertical_speed) > 0.45:
            resolved = "flight_glide"

        current_phase = str(
            getattr(self, "_flight_phase_cache", "")
            or getattr(self, "_anim_state", "")
            or ""
        ).strip().lower()

        # Add a little hysteresis around glide/dive/hover boundaries so low-FPS
        # runs do not chatter across adjacent flight states every few frames.
        if current_phase == "flight_dive" and vertical_speed < -0.6:
            resolved = "flight_dive"
        elif current_phase == "flight_glide" and (speed > 1.8 or abs(vertical_speed) > 0.2):
            resolved = "flight_glide"
        elif current_phase == "flight_hover" and speed < 3.2 and abs(vertical_speed) < 0.7:
            resolved = "flight_hover"

        self._flight_phase_cache = resolved
        return resolved

    # ───────────────────────────────────────────────────────────
    # Queue helpers
    # ───────────────────────────────────────────────────────────

    def _queue_state_trigger(self, trigger):
        token = str(trigger or "").strip().lower()
        if not token:
            return
        if token not in self._queued_state_triggers:
            self._queued_state_triggers.append(token)

    # ───────────────────────────────────────────────────────────
    # Context Flags  (refreshed every FSM tick)
    # ───────────────────────────────────────────────────────────

    def _update_context_flags(self):
        """Build self._context_flags from physics state and environment."""
        flags: set[str] = set()

        cs = getattr(self, "cs", None)
        if cs:
            if getattr(cs, "inWater", False):
                flags.add("in_water")
            if getattr(cs, "onWall", False):
                flags.add("wall_contact")

            # Slope/terrain heuristics from velocity
            vz = float(getattr(cs.velocity, "z", 0.0) or 0.0)
            vx = float(getattr(cs.velocity, "x", 0.0) or 0.0)
            vy = float(getattr(cs.velocity, "y", 0.0) or 0.0)
            horiz_speed = math.sqrt(vx * vx + vy * vy)

            if getattr(cs, "grounded", True) and horiz_speed > 0.8:
                slope = abs(vz) / max(horiz_speed, 0.1)
                if slope > 0.6:
                    flags.add("steep_slope")
                elif slope > 0.15:
                    flags.add("uneven_ground")
        elif bool(getattr(self, "_py_in_water", False)):
            flags.add("in_water")

        # Wall run → edge_detected
        if getattr(self, "_was_wallrun", False):
            flags.add("edge_detected")

        # Let world / app inject surface flags
        extra = getattr(self, "_env_flags", set())
        flags.update(extra)

        self._context_flags = flags

    # ───────────────────────────────────────────────────────────
    # Layer helpers
    # ───────────────────────────────────────────────────────────

    def _layer_of(self, state_name: str) -> str:
        key = str(state_name or "").strip().lower()
        # Check runtime state defs first
        defs = getattr(self, "_state_defs", {})
        if isinstance(defs, dict):
            state_def = defs.get(key, {})
            if isinstance(state_def, dict) and "layer" in state_def:
                return str(state_def["layer"]).strip().lower()
        return STATE_LAYER_MAP.get(key, "locomotion")

    def _priority_of(self, state_name: str) -> int:
        """Numeric priority of a state (lower = more important)."""
        layer = self._layer_of(state_name)
        base = LAYER_PRIORITY.get(layer, 4)
        # Check for explicit numeric override in _state_defs
        defs = getattr(self, "_state_defs", {})
        if isinstance(defs, dict):
            state_def = defs.get(str(state_name or "").strip().lower(), {})
            if isinstance(state_def, dict) and "priority" in state_def:
                try:
                    return int(state_def["priority"])
                except Exception:
                    pass
        return base

    def _state_priority(self, state_name):
        """Legacy: returns 100*priority so higher value = higher importance (old usage)."""
        return self._priority_of(state_name)

    def _state_layer(self, state_name):
        return self._layer_of(state_name)

    def _rule_priority(self, rule):
        if not isinstance(rule, dict):
            return 100
        try:
            return int(rule.get("priority", 100))
        except Exception:
            return 100

    def _sort_rules(self, rules):
        if not isinstance(rules, list):
            return []
        indexed = list(enumerate(rules))
        indexed.sort(key=lambda pair: (self._rule_priority(pair[1]), pair[0]))
        return [pair[1] for pair in indexed]

    # ───────────────────────────────────────────────────────────
    # Transition permission
    # ───────────────────────────────────────────────────────────

    def _transition_allowed(self, current_state, target_state, trigger=None, force=False):
        current = str(current_state or "").strip().lower()
        target = str(target_state or "").strip().lower()
        if not target:
            return False
        if current == target:
            return False
        if force or target in {"dead", "death"}:
            return True

        target_prio = self._priority_of(target)
        current_prio = self._priority_of(current)
        trigger_token = str(trigger or "").strip().lower()
        current_def = self._state_def(current)
        state_uninterruptible = bool(
            current in UNINTERRUPTIBLE_STATES
            or (isinstance(current_def, dict) and bool(current_def.get("uninterruptible", False)))
        )

        # Hard-uninterruptible states block everything (except force/death)
        if state_uninterruptible:
            if trigger_token == "animation_finished":
                return True
            explicit_interruptors = []
            if isinstance(current_def, dict):
                raw_interruptors = current_def.get("interruptible_by", [])
                if isinstance(raw_interruptors, list):
                    explicit_interruptors = [
                        str(name or "").strip().lower()
                        for name in raw_interruptors
                        if str(name or "").strip()
                    ]
            if explicit_interruptors and target in explicit_interruptors:
                return True
            # Only lower-numbered priority can break in
            return target_prio < current_prio

        # Check per-state interrupt whitelist
        target_layer = self._layer_of(target)
        allowed_layers = INTERRUPT_RULES.get(current)
        if allowed_layers is not None:
            # This state has explicit interrupt rules
            if target_layer in allowed_layers:
                return True
            # Also allow if target_prio is strictly lower (more important)
            if target_prio < current_prio:
                return True
            # animation_finished always unlocks
            if trigger_token == "animation_finished":
                return True
            return False

        # General numeric priority rule
        if target_prio < current_prio:
            return True
        if target_prio == current_prio:
            return True
        if trigger_token == "animation_finished":
            return True
        if self._layer_of(current) == target_layer:
            return True

        # Explicit can_transition_to whitelist in state def
        if isinstance(current_def, dict):
            explicit = current_def.get("can_transition_to", [])
            if isinstance(explicit, list):
                if any(str(v or "").strip().lower() == target for v in explicit):
                    return True

        return False

    # ───────────────────────────────────────────────────────────
    # Sync helpers
    # ───────────────────────────────────────────────────────────

    def _sync_block_state_edges(self):
        pressed = bool(self._get_action("block"))
        if pressed and not self._block_pressed:
            self._queue_state_trigger("block_start")
        elif not pressed and self._block_pressed:
            self._queue_state_trigger("block_end")
        self._block_pressed = pressed

    def _parkour_action_name(self):
        if not self.ps:
            return ""
        action = getattr(self.ps, "action", None)
        if action is None:
            return ""
        if hasattr(action, "name"):
            name = getattr(action, "name", None)
            if isinstance(name, str) and name:
                return name.strip().lower()
        token = str(action).strip().lower()
        if "." in token:
            token = token.split(".")[-1]
        return token

    def _sync_wall_contact_state(self):
        action_name = self._parkour_action_name()
        token = ""
        token_getter = getattr(self, "_parkour_action_token", None)
        if callable(token_getter):
            try:
                token = str(token_getter() or "").strip().lower()
            except Exception:
                token = ""
        if not token:
            token = str(action_name or "").strip().lower().replace("-", "_").replace(" ", "_")
        in_wallrun = token.startswith("wallrun") or token.startswith("wall_run")
        if in_wallrun and not self._was_wallrun:
            self._queue_state_trigger("wall_contact")
        elif (not in_wallrun) and self._was_wallrun:
            self._queue_state_trigger("exit_wallrun")
        self._was_wallrun = in_wallrun

    # ───────────────────────────────────────────────────────────
    # State def helpers  (data-driven overrides from JSON)
    # ───────────────────────────────────────────────────────────

    def _transition_from_matches(self, current_state, from_states):
        if not isinstance(from_states, list) or not from_states:
            return False
        current = str(current_state or "").strip().lower()
        for source in from_states:
            normalized = str(source or "").strip().lower()
            if normalized == "*" or normalized == current:
                return True
        return False

    def _state_def(self, state_name):
        key = str(state_name or "").strip().lower()
        if not key:
            return {}
        defs = getattr(self, "_state_defs", {})
        if not isinstance(defs, dict):
            return {}
        value = defs.get(key)
        return value if isinstance(value, dict) else {}

    # ───────────────────────────────────────────────────────────
    # Context building
    # ───────────────────────────────────────────────────────────

    def _build_state_context(self):
        speed = 0.0
        on_ground = True
        hp = 100.0
        shift_pressed = bool(self._get_action("run"))
        mounted = False
        mounted_kind = ""
        vertical_speed = 0.0

        if self.cs:
            vx = float(getattr(self.cs.velocity, "x", 0.0) or 0.0)
            vy = float(getattr(self.cs.velocity, "y", 0.0) or 0.0)
            speed = math.sqrt(vx * vx + vy * vy)
            on_ground = bool(getattr(self.cs, "grounded", True))
            hp = float(getattr(self.cs, "health", 100.0) or 0.0)
            vertical_speed = float(getattr(self.cs.velocity, "z", 0.0) or 0.0)
        else:
            try:
                mx, my = self._get_move_axes()
                axis_mag = max(0.0, min(1.0, math.sqrt((float(mx) ** 2) + (float(my) ** 2))))
            except Exception:
                axis_mag = 0.0
            if axis_mag > 0.05:
                try:
                    base_speed = float(self.run_speed if shift_pressed else self.walk_speed)
                except Exception:
                    base_speed = 0.0
                speed = max(0.0, axis_mag * base_speed)
            on_ground = bool(getattr(self, "_py_grounded", True))
            vertical_speed = float(getattr(self, "_py_velocity_z", 0.0) or 0.0)

        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if vehicle_mgr and getattr(vehicle_mgr, "is_mounted", False):
            mounted = True
            vehicle = vehicle_mgr.mounted_vehicle() if hasattr(vehicle_mgr, "mounted_vehicle") else None
            if isinstance(vehicle, dict):
                mounted_kind = str(vehicle.get("kind", "")).strip().lower()
                vel = vehicle.get("velocity")
                if vel is not None and hasattr(vel, "x") and hasattr(vel, "y"):
                    v_speed = math.sqrt((float(vel.x) ** 2) + (float(vel.y) ** 2))
                    speed = max(speed, v_speed)
            on_ground = True

        if mounted_kind:
            self._mount_anim_kind = mounted_kind
        elif self._anim_state not in {
            "mounting",
            "mounted_idle",
            "mounted_move",
            "mounted_ship_idle",
            "mounted_ship_move",
            "dismounting",
        }:
            self._mount_anim_kind = ""

        resolved_mounted_kind = mounted_kind or str(self._mount_anim_kind or "").strip().lower()
        parkour_action = self._parkour_action_name()
        landing_impact = float(getattr(self, "_last_landing_impact_speed", 0.0) or 0.0)
        grounded_now = bool(on_ground)

        is_attacking = False
        try:
            if self.combat and hasattr(self.combat, "isAttacking"):
                is_attacking = bool(self.combat.isAttacking())
        except Exception:
            is_attacking = False

        in_water = bool(self.cs and getattr(self.cs, "inWater", False))
        if (not in_water) and bool(getattr(self, "_py_in_water", False)):
            in_water = True

        now = float(globalClock.getFrameTime())
        flight_landing = bool(
            (not bool(self._is_flying))
            and on_ground
            and (now < float(getattr(self, "_flight_land_until", 0.0) or 0.0))
        )

        context = {
            "speed":               speed,
            "shift_pressed":       shift_pressed,
            "is_crouched":         bool(getattr(self, "_stealth_crouch", False)),
            "on_ground":           on_ground,
            "hp":                  hp,
            "mounted":             mounted,
            "mounted_kind":        resolved_mounted_kind,
            "in_water":            in_water,
            "is_flying":           bool(self._is_flying),
            "vertical_speed":      vertical_speed,
            "parkour_action":      parkour_action,
            "wall_contact":        bool(getattr(self, "_was_wallrun", False)),
            "landed_hard":         bool(landing_impact >= 10.0),
            "landed_soft":         bool(landing_impact >= 3.0),
            "landing_impact_speed":landing_impact,
            "was_grounded":        bool(getattr(self, "_was_grounded", grounded_now)),
            "is_attacking":        is_attacking,
            "is_blocking":         bool(getattr(self, "_block_pressed", False)),
            "flight_landing":      flight_landing,
        }
        # Merge context flags as individual booleans for eval()
        for flag in getattr(self, "_context_flags", set()):
            context[flag] = True

        context["flight_phase"] = self._resolve_flight_phase(context)

        return context

    # ───────────────────────────────────────────────────────────
    # Condition evaluation
    # ───────────────────────────────────────────────────────────

    def _eval_transition_condition(self, condition, context):
        if not isinstance(condition, str) or not condition.strip():
            return False
        expr = condition.replace("&&", " and ").replace("||", " or ").strip()
        expr = re.sub(r"!\s*([A-Za-z_][A-Za-z0-9_]*)", r"not \1", expr)
        safe_ctx = dict(context)
        # Fill missing flags with False so eval doesn't NameError
        from entities.player_animation_config import CONTEXT_FLAG_NAMES
        for fname in CONTEXT_FLAG_NAMES:
            if fname not in safe_ctx:
                safe_ctx[fname] = False
        try:
            return bool(eval(expr, {"__builtins__": {}}, safe_ctx))
        except Exception:
            return False

    # ───────────────────────────────────────────────────────────
    # Default state computation (from physics context)
    # ───────────────────────────────────────────────────────────

    def _compute_default_state(self, context):
        speed = float(context.get("speed", 0.0) or 0.0)
        on_ground = bool(context.get("on_ground", True))
        vertical_speed = float(context.get("vertical_speed", 0.0) or 0.0)
        in_water = bool(context.get("in_water", False))
        is_flying = bool(context.get("is_flying", False))
        current_state = str(getattr(self, "_anim_state", "") or "").strip().lower()
        airborne_phase = str(getattr(self, "_airborne_phase_cache", "") or "").strip().lower()
        current_is_jump_chain = current_state in {"jumping", "falling", "landing"}
        current_is_flight_chain = current_state in {
            "flying",
            "fly",
            "flight_takeoff",
            "flight_hover",
            "flight_glide",
            "flight_dive",
            "flight_airdash",
            "flight_land",
        }
        if bool(context.get("mounted", False)):
            self._airborne_phase_cache = ""
            mounted_kind = str(context.get("mounted_kind", "") or "").strip().lower()
            if mounted_kind in {"ship", "boat"}:
                return "mounted_ship_move" if speed > 0.2 else "mounted_ship_idle"
            return "mounted_move" if speed > 0.15 else "mounted_idle"
        if bool(context.get("flight_landing", False)):
            self._airborne_phase_cache = ""
            return "flight_land"
        if is_flying:
            self._airborne_phase_cache = ""
            flight_phase = str(context.get("flight_phase", "") or "").strip().lower()
            if flight_phase in {"flight_takeoff", "flight_hover", "flight_glide", "flight_dive", "flight_airdash"}:
                return flight_phase
            return "flight_hover"
        if current_is_flight_chain and on_ground and (not in_water):
            self._airborne_phase_cache = ""
            return "flight_land"
        if current_is_flight_chain and (not on_ground) and (not in_water):
            self._airborne_phase_cache = "falling"
            return "falling"
        if in_water:
            self._airborne_phase_cache = ""
            return "swim"
        if current_is_jump_chain and on_ground:
            self._airborne_phase_cache = ""
            return "landing"
        if current_state == "falling" and (not on_ground):
            self._airborne_phase_cache = "falling"
            return "falling"
        if current_state == "jumping" and (not on_ground):
            resolved_airborne = "falling" if vertical_speed < -0.12 else "jumping"
            self._airborne_phase_cache = resolved_airborne
            return resolved_airborne
        if current_state == "landing" and (not on_ground):
            self._airborne_phase_cache = "falling"
            return "falling"
        if not on_ground:
            if airborne_phase == "falling":
                self._airborne_phase_cache = "falling"
                return "falling"
            resolved_airborne = "falling" if vertical_speed < -0.35 else "jumping"
            self._airborne_phase_cache = resolved_airborne
            return resolved_airborne
        self._airborne_phase_cache = ""
        if bool(context.get("is_crouched", False)):
            return "crouch_move" if speed > 0.08 else "crouch_idle"
        if speed > 6.0:
            return "running"
        if speed > 0.8:
            return "walking"
        return "idle"

    # ───────────────────────────────────────────────────────────
    # State entry
    # ───────────────────────────────────────────────────────────

    def _enter_state(self, state_name):
        target = str(state_name or "idle").strip().lower()
        if not target:
            return False

        resolved_clip, _, _ = self._resolve_anim_clip(
            target,
            include_state_fallback=True,
            include_global_fallback=True,
            with_meta=True,
        )
        state_def = self._state_defs.get(target, {}) if isinstance(self._state_defs, dict) else {}
        duration = 0.0
        try:
            duration = float((state_def or {}).get("duration", 0.0) or 0.0)
        except Exception:
            duration = 0.0
        if duration <= 0.0:
            duration = float(DEFAULT_STATE_DURATIONS.get(target, 0.0))

        blend_time = None
        if isinstance(state_def, dict) and "blend_time" in state_def:
            try:
                blend_time = float(state_def.get("blend_time"))
            except Exception:
                blend_time = None
            if blend_time is not None:
                blend_time = max(0.02, min(1.2, blend_time))

        loop_override = state_def.get("loop") if isinstance(state_def, dict) else None
        loop_hint = self._state_loop_hint(target, resolved_clip=resolved_clip)

        if isinstance(loop_override, bool):
            loop = loop_override
        elif isinstance(loop_hint, bool):
            loop = loop_hint
        else:
            loop = duration <= 0.0

        if not loop and duration <= 0.0:
            clip_duration = self._resolved_clip_duration(resolved_clip)
            if clip_duration > 0.0:
                duration = clip_duration
            else:
                duration = max(0.25, float(DEFAULT_STATE_DURATIONS.get(target, 0.35) or 0.35))

        force_restart = (not loop) or (duration > 0.0)
        changed = self._set_anim(
            target,
            loop=loop,
            blend_time=blend_time,
            force=force_restart,
        )
        if not changed:
            return False

        now = globalClock.getFrameTime()
        self._state_lock_until = (now + duration) if (duration > 0.0 and not loop) else 0.0
        return True

    # ───────────────────────────────────────────────────────────
    # Rule application
    # ───────────────────────────────────────────────────────────

    def _apply_runtime_rules(self, current_state, context, triggers):
        rules = self._sort_rules(getattr(self, "_state_rules", []))
        if not rules:
            return False

        trigger_set = {str(token or "").strip().lower() for token in list(triggers or [])}
        for rule in rules:
            target = str(rule.get("to", "")).strip().lower()
            if not target:
                continue
            if target in {"flying", "fly"} and bool((context or {}).get("is_flying", False)):
                explicit_flight_phase = str((context or {}).get("flight_phase", "") or "").strip().lower()
                if explicit_flight_phase in {
                    "flight_takeoff",
                    "flight_hover",
                    "flight_glide",
                    "flight_dive",
                    "flight_airdash",
                    "flight_land",
                }:
                    target = explicit_flight_phase
            if not self._transition_from_matches(current_state, rule.get("from", [])):
                continue

            required_trigger = str(rule.get("trigger", "")).strip().lower()
            if required_trigger and required_trigger not in trigger_set:
                continue

            cond = rule.get("condition")
            if isinstance(cond, str) and cond.strip():
                if not self._eval_transition_condition(cond, context):
                    continue

            force = bool(rule.get("force", False))
            if not self._transition_allowed(current_state, target, trigger=required_trigger, force=force):
                continue

            if self._enter_state(target):
                return True
        return False

    # ───────────────────────────────────────────────────────────
    # Main FSM tick
    # ───────────────────────────────────────────────────────────

    def _run_animation_state_machine(self):
        # Refresh context flags every tick
        self._update_context_flags()

        if not self._state_transitions or not getattr(self, "_anim_state", None):
            self._enter_state(self._compute_default_state(self._build_state_context()))
            return

        now = globalClock.getFrameTime()
        if self._state_lock_until > 0.0:
            if now < self._state_lock_until:
                return
            self._state_lock_until = 0.0
            self._queue_state_trigger("animation_finished")

        current = str(self._anim_state or "idle").lower()
        context = self._build_state_context()
        triggers = list(self._queued_state_triggers)
        self._queued_state_triggers = []

        if self._apply_runtime_rules(current, context, triggers):
            return

        # Trigger-based transitions
        for trigger in triggers:
            for rule in self._sort_rules(self._state_transitions):
                if rule.get("trigger") != trigger:
                    continue
                if not self._transition_from_matches(current, rule.get("from", [])):
                    continue
                if not self._transition_allowed(current, rule.get("to"), trigger=trigger, force=bool(rule.get("force", False))):
                    continue
                if self._enter_state(rule.get("to")):
                    return

        # Condition-based transitions
        for rule in self._sort_rules(self._state_transitions):
            condition = rule.get("condition")
            if not condition:
                continue
            if not self._transition_from_matches(current, rule.get("from", [])):
                continue
            if self._eval_transition_condition(condition, context):
                if not self._transition_allowed(current, rule.get("to"), trigger=rule.get("trigger"), force=bool(rule.get("force", False))):
                    continue
                if self._enter_state(rule.get("to")):
                    return

        # Fallback to locomotion default
        fallback = self._compute_default_state(context)
        locomotion_states = {
            "idle", "idle_relaxed", "idle_combat",
            "walking", "walk", "running", "run", "sprinting", "sprint",
            "crouch_idle", "crouch_move",
            "jumping", "jump", "in_air",
            "falling", "landing", "land_soft",
            "mounted_idle", "mounted_move", "mounted_ship_idle", "mounted_ship_move",
            "swim", "swim_surface", "swim_dive", "swim_underwater",
            "flying", "fly", "flight_takeoff", "flight_hover", "flight_glide", "flight_dive", "flight_airdash", "flight_land",
        }
        if current in locomotion_states and fallback != current:
            self._enter_state(fallback)
