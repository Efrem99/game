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

        return {
            "speed": speed,
            "shift_pressed": shift_pressed,
            "on_ground": on_ground,
            "hp": hp,
            "mounted": mounted,
            "mounted_kind": resolved_mounted_kind,
            "in_water": bool(self.cs and getattr(self.cs, "inWater", False)),
            "is_flying": bool(self._is_flying),
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

        for trigger in triggers:
            for rule in self._state_transitions:
                if rule.get("trigger") != trigger:
                    continue
                if not self._transition_from_matches(current, rule.get("from", [])):
                    continue
                if self._enter_state(rule.get("to")):
                    return

        for rule in self._state_transitions:
            condition = rule.get("condition")
            if not condition:
                continue
            if not self._transition_from_matches(current, rule.get("from", [])):
                continue
            if self._eval_transition_condition(condition, context):
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

