"""State machine and animation transition helpers for Player."""

import math
import re

from direct.showbase.ShowBaseGlobal import globalClock

from entities.player_animation_config import DEFAULT_STATE_DURATIONS


class PlayerStateMachineMixin:
    def _queue_state_trigger(self, trigger):
        token = str(trigger or "").strip().lower()
        if not token:
            return
        if token not in self._queued_state_triggers:
            self._queued_state_triggers.append(token)

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
        in_wallrun = action_name in {"wallrun", "wall_run"}
        if in_wallrun and not self._was_wallrun:
            self._queue_state_trigger("wall_contact")
        elif (not in_wallrun) and self._was_wallrun:
            self._queue_state_trigger("exit_wallrun")
        self._was_wallrun = in_wallrun

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

    def _state_layer(self, state_name):
        state_def = self._state_def(state_name)
        layer = state_def.get("layer", "locomotion")
        token = str(layer or "locomotion").strip().lower()
        return token if token else "locomotion"

    def _state_priority(self, state_name):
        state_def = self._state_def(state_name)
        try:
            return int(state_def.get("priority", 50))
        except Exception:
            return 50

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

    def _transition_allowed(self, current_state, target_state, trigger=None, force=False):
        current = str(current_state or "").strip().lower()
        target = str(target_state or "").strip().lower()
        if not target:
            return False
        if current == target:
            return False
        if force or target == "dead":
            return True

        current_def = self._state_def(current)
        target_priority = self._state_priority(target)
        current_priority = self._state_priority(current)
        trigger_token = str(trigger or "").strip().lower()

        if bool(current_def.get("uninterruptible", False)):
            if trigger_token == "animation_finished":
                return True
            allowed_by = current_def.get("interruptible_by", [])
            if isinstance(allowed_by, list):
                target_layer = self._state_layer(target)
                for token in allowed_by:
                    marker = str(token or "").strip().lower()
                    if marker in {"*", target, target_layer}:
                        return True
            if target_priority < current_priority:
                return True
            return False

        if target_priority < current_priority:
            return True
        if target_priority == current_priority:
            return True

        if trigger_token == "animation_finished":
            return True
        if self._state_layer(current) == self._state_layer(target):
            return True

        explicit = current_def.get("can_transition_to", [])
        if isinstance(explicit, list):
            target_norm = str(target).strip().lower()
            if any(str(v or "").strip().lower() == target_norm for v in explicit):
                return True

        return False

    def _build_state_context(self):
        speed = 0.0
        on_ground = True
        hp = 100.0
        shift_pressed = bool(self._get_action("run"))
        mounted = False
        mounted_kind = ""
        if self.cs:
            speed = math.sqrt((self.cs.velocity.x**2) + (self.cs.velocity.y**2))
            on_ground = bool(getattr(self.cs, "grounded", True))
            hp = float(getattr(self.cs, "health", 100.0) or 0.0)
            vertical_speed = float(getattr(self.cs.velocity, "z", 0.0) or 0.0)
        else:
            vertical_speed = 0.0

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
        elif self._anim_state not in {"mounting", "mounted_idle", "mounted_move", "dismounting"}:
            self._mount_anim_kind = ""

        resolved_mounted_kind = mounted_kind or str(self._mount_anim_kind or "").strip().lower()
        parkour_action = self._parkour_action_name()
        landing_impact = float(getattr(self, "_last_landing_impact_speed", 0.0) or 0.0)
        grounded_now = bool(on_ground)
        was_grounded = bool(getattr(self, "_was_grounded", grounded_now))
        is_attacking = False
        try:
            if self.combat and hasattr(self.combat, "isAttacking"):
                is_attacking = bool(self.combat.isAttacking())
        except Exception:
            is_attacking = False

        return {
            "speed": speed,
            "shift_pressed": shift_pressed,
            "on_ground": on_ground,
            "hp": hp,
            "mounted": mounted,
            "mounted_kind": resolved_mounted_kind,
            "in_water": bool(self.cs and getattr(self.cs, "inWater", False)),
            "is_flying": bool(self._is_flying),
            "vertical_speed": vertical_speed,
            "parkour_action": parkour_action,
            "wall_contact": bool(getattr(self, "_was_wallrun", False)),
            "landed_hard": bool(landing_impact >= 10.0),
            "landed_soft": bool(landing_impact >= 3.0),
            "landing_impact_speed": landing_impact,
            "was_grounded": was_grounded,
            "is_attacking": is_attacking,
            "is_blocking": bool(getattr(self, "_block_pressed", False)),
        }

    def _eval_transition_condition(self, condition, context):
        if not isinstance(condition, str) or not condition.strip():
            return False
        expr = condition.replace("&&", " and ").replace("||", " or ").strip()
        expr = re.sub(r"!\s*([A-Za-z_][A-Za-z0-9_]*)", r"not \1", expr)
        try:
            return bool(eval(expr, {"__builtins__": {}}, dict(context)))
        except Exception:
            return False

    def _compute_default_state(self, context):
        speed = float(context.get("speed", 0.0) or 0.0)
        on_ground = bool(context.get("on_ground", True))
        if bool(context.get("mounted", False)):
            return "mounted_move" if speed > 0.15 else "mounted_idle"
        if bool(context.get("is_flying", False)):
            return "flying"
        if bool(context.get("in_water", False)):
            return "swim"
        if not on_ground:
            vz = float(getattr(self.cs.velocity, "z", 0.0)) if self.cs else 0.0
            return "falling" if vz < -0.35 else "jumping"
        if speed > 6.0:
            return "running"
        if speed > 0.5:
            return "walking"
        return "idle"

    def _enter_state(self, state_name):
        target = str(state_name or "idle").strip().lower()
        if not target:
            return False

        state_def = self._state_defs.get(target, {})
        duration = 0.0
        try:
            duration = float(state_def.get("duration", 0.0) or 0.0)
        except Exception:
            duration = 0.0
        if duration <= 0.0:
            duration = float(DEFAULT_STATE_DURATIONS.get(target, 0.0))
        loop = duration <= 0.0
        force_restart = duration > 0.0
        changed = self._set_anim(target, loop=loop, force=force_restart)
        if not changed:
            return False
        now = globalClock.getFrameTime()
        self._state_lock_until = (now + duration) if duration > 0.0 else 0.0
        return True

    def _apply_runtime_rules(self, current_state, context, triggers):
        rules = self._sort_rules(getattr(self, "_state_rules", []))
        if not rules:
            return False

        trigger_set = {str(token or "").strip().lower() for token in list(triggers or [])}
        for rule in rules:
            target = str(rule.get("to", "")).strip().lower()
            if not target:
                continue
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
            if not self._transition_allowed(
                current_state,
                target,
                trigger=required_trigger,
                force=force,
            ):
                continue

            if self._enter_state(target):
                return True
        return False

    def _run_animation_state_machine(self):
        if not self._state_transitions:
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

        for trigger in triggers:
            for rule in self._sort_rules(self._state_transitions):
                if rule.get("trigger") != trigger:
                    continue
                if not self._transition_from_matches(current, rule.get("from", [])):
                    continue
                if not self._transition_allowed(
                    current,
                    rule.get("to"),
                    trigger=trigger,
                    force=bool(rule.get("force", False)),
                ):
                    continue
                if self._enter_state(rule.get("to")):
                    return

        for rule in self._sort_rules(self._state_transitions):
            condition = rule.get("condition")
            if not condition:
                continue
            if not self._transition_from_matches(current, rule.get("from", [])):
                continue
            if self._eval_transition_condition(condition, context):
                if not self._transition_allowed(
                    current,
                    rule.get("to"),
                    trigger=rule.get("trigger"),
                    force=bool(rule.get("force", False)),
                ):
                    continue
                if self._enter_state(rule.get("to")):
                    return

        fallback = self._compute_default_state(context)
        locomotion = {
            "idle",
            "walking",
            "running",
            "jumping",
            "falling",
            "landing",
            "mounted_idle",
            "mounted_move",
            "swim",
            "flying",
            "fly",
        }
        if current in locomotion and fallback != current:
            self._enter_state(fallback)
