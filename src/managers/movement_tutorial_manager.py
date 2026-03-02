"""Runtime tutorial flow used by both test demos and main game."""

import math


class MovementTutorialManager:
    """Data-driven onboarding for movement, combat and traversal basics."""

    def __init__(self, app):
        self.app = app
        self.enabled = False
        self.mode = "main"

        self._core_steps = [
            {"id": "move", "text_key": "ui.tutorial_move", "default": "Move with W/A/S/D"},
            {"id": "sprint", "text_key": "ui.tutorial_sprint", "default": "Sprint with Shift + movement"},
            {"id": "jump", "text_key": "ui.tutorial_jump", "default": "Jump with Space"},
            {"id": "interact", "text_key": "ui.tutorial_interact", "default": "Interact with X near NPC/object"},
            {"id": "dodge", "text_key": "ui.tutorial_dodge", "default": "Dodge with Z"},
            {"id": "attack", "text_key": "ui.tutorial_attack", "default": "Use light attack (LMB) or heavy attack (E)"},
            {"id": "skill_wheel", "text_key": "ui.tutorial_skill_wheel", "default": "Hold TAB and choose a skill with mouse"},
            {"id": "cast", "text_key": "ui.tutorial_cast", "default": "Cast your selected spell"},
        ]
        self._advanced_steps = [
            {"id": "parkour", "text_key": "ui.tutorial_parkour", "default": "Use parkour: vault, climb or wallrun"},
            {"id": "swim", "text_key": "ui.tutorial_swim", "default": "Enter water to test swimming"},
            {"id": "fly", "text_key": "ui.tutorial_fly", "default": "Toggle flight and move in air"},
            {"id": "mount", "text_key": "ui.tutorial_mount", "default": "Mount a horse/carriage/boat with interact"},
        ]
        self._core_target = (18.0, 24.0, 0.0)
        self._step_targets = {
            "move": (18.0, 24.0, 0.0),
            "sprint": (18.0, 13.0, 0.0),
            "jump": (12.5, 30.8, 0.0),
            "interact": (5.0, 45.0, 0.0),
            "dodge": (18.0, 24.0, 0.0),
            "attack": (18.0, 24.0, 0.0),
            "skill_wheel": (18.0, 24.0, 0.0),
            "cast": (18.0, 24.0, 0.0),
            "parkour": (29.5, 26.0, 0.0),
            "swim": (4.0, 36.0, 0.0),
            "fly": (18.0, 24.0, 8.0),
            "mount": (9.0, 6.0, 0.0),
        }
        self._required_index = 0
        self._bonus_index = 0

    def set_mode(self, mode, reset=False):
        token = str(mode or "main").strip().lower()
        if token not in {"main", "demo"}:
            token = "main"
        self.mode = token
        if reset:
            self._required_index = 0
            self._bonus_index = 0

    def enable(self, reset=True, mode=None):
        if mode is not None:
            self.set_mode(mode, reset=reset)
        elif reset:
            self._required_index = 0
            self._bonus_index = 0
        self.enabled = True

    def disable(self):
        self.enabled = False

    def has_progress(self):
        return bool(self._required_index > 0 or self._bonus_index > 0)

    def is_required_complete(self):
        return self._required_index >= len(self._core_steps)

    def is_bonus_complete(self):
        return self._bonus_index >= len(self._advanced_steps)

    def is_complete(self):
        return self.is_required_complete() and self.is_bonus_complete()

    def _player_speed(self, player):
        cs = getattr(player, "cs", None)
        if not cs or not hasattr(cs, "velocity"):
            return 0.0
        vx = float(getattr(cs.velocity, "x", 0.0) or 0.0)
        vy = float(getattr(cs.velocity, "y", 0.0) or 0.0)
        return math.sqrt((vx * vx) + (vy * vy))

    def _on_ground(self, player):
        cs = getattr(player, "cs", None)
        if not cs:
            return True
        return bool(getattr(cs, "grounded", True))

    def _in_water(self, player):
        cs = getattr(player, "cs", None)
        if not cs:
            return False
        return bool(getattr(cs, "inWater", False))

    def _combat_event(self, player):
        getter = getattr(player, "get_hud_combat_event", None)
        if not callable(getter):
            return {}
        try:
            event = getter() or {}
            return event if isinstance(event, dict) else {}
        except Exception:
            return {}

    def _is_in_training_location(self):
        world = getattr(self.app, "world", None)
        name = str(getattr(world, "active_location", "") or "").strip().lower()
        return "training" in name

    def _should_show_bonus(self):
        if self.mode == "demo":
            return True
        return self._is_in_training_location()

    def _step_done(self, step_id, player):
        speed = self._player_speed(player)
        anim_state = str(getattr(player, "_anim_state", "") or "").strip().lower()
        event = self._combat_event(player)

        if step_id == "move":
            return speed > 0.45
        if step_id == "sprint":
            is_run_pressed = bool(getattr(player, "_get_action", lambda _k: False)("run"))
            run_ref = max(1.0, float(getattr(player, "run_speed", 8.0) or 8.0))
            return is_run_pressed and speed > (run_ref * 0.55)
        if step_id == "jump":
            return not self._on_ground(player)
        if step_id == "interact":
            interact_pressed = bool(getattr(player, "_get_action", lambda _k: False)("interact"))
            vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
            mounted = bool(vehicle_mgr and getattr(vehicle_mgr, "is_mounted", False))
            return interact_pressed or mounted
        if step_id == "dodge":
            return anim_state == "dodging"
        if step_id == "attack":
            label = str(event.get("label", "")).strip().lower()
            return anim_state == "attacking" or label == "melee"
        if step_id == "skill_wheel":
            return bool(getattr(player, "_skill_wheel_open", False))
        if step_id == "cast":
            label = str(event.get("label", "")).strip().lower()
            return anim_state == "casting" or (label not in {"", "melee"})
        if step_id == "parkour":
            return anim_state in {"vaulting", "climbing", "wallrun"} or bool(getattr(player, "_was_wallrun", False))
        if step_id == "swim":
            return self._in_water(player)
        if step_id == "fly":
            return bool(getattr(player, "_is_flying", False))
        if step_id == "mount":
            vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
            return bool(vehicle_mgr and getattr(vehicle_mgr, "is_mounted", False))
        return False

    def _advance(self, steps, index, player):
        idx = max(0, int(index))
        while idx < len(steps):
            if not self._step_done(steps[idx]["id"], player):
                break
            idx += 1
        return idx

    def update(self, dt):
        del dt
        if not self.enabled:
            return

        player = getattr(self.app, "player", None)
        if not player:
            return

        self._required_index = self._advance(self._core_steps, self._required_index, player)
        if self._required_index >= len(self._core_steps):
            if self._should_show_bonus():
                self._bonus_index = self._advance(self._advanced_steps, self._bonus_index, player)
                if self._bonus_index >= len(self._advanced_steps):
                    self.enabled = False
            elif self.mode == "demo":
                self.enabled = False

    def get_hud_message(self):
        if not self.enabled:
            return ""

        t = self.app.data_mgr.t
        if not self.is_required_complete():
            step = self._core_steps[self._required_index]
            text = t(step["text_key"], step["default"])
            header = t("ui.tutorial_header", "Movement Tutorial")
            total = len(self._core_steps)
            return f"{header} [{self._required_index + 1}/{total}] {text}"

        if self._should_show_bonus():
            header = t("ui.tutorial_header_advanced", "Advanced Training")
            total = len(self._advanced_steps)
            if self._bonus_index >= total:
                done = t("ui.tutorial_complete", "Tutorial complete")
                return f"{header} [{total}/{total}] {done}"
            step = self._advanced_steps[self._bonus_index]
            text = t(step["text_key"], step["default"])
            return f"{header} [{self._bonus_index + 1}/{total}] {text}"

        return ""

    def get_status_snapshot(self):
        return {
            "enabled": bool(self.enabled),
            "mode": str(self.mode),
            "required_done": int(self._required_index),
            "required_total": len(self._core_steps),
            "bonus_done": int(self._bonus_index),
            "bonus_total": len(self._advanced_steps),
            "core_complete": self.is_required_complete(),
            "full_complete": self.is_required_complete() and self.is_bonus_complete(),
        }

    def _active_step(self):
        if not self.is_required_complete():
            if 0 <= self._required_index < len(self._core_steps):
                return dict(self._core_steps[self._required_index]), "core", self._required_index + 1, len(self._core_steps)
            return None, "core", 0, len(self._core_steps)
        if self._should_show_bonus() and self._bonus_index < len(self._advanced_steps):
            return dict(self._advanced_steps[self._bonus_index]), "advanced", self._bonus_index + 1, len(self._advanced_steps)
        return None, "done", 0, 0

    def _distance_to_target(self, player_pos, target):
        if player_pos is None or target is None:
            return None
        try:
            px, py, pz = float(player_pos.x), float(player_pos.y), float(player_pos.z)
        except Exception:
            if isinstance(player_pos, (list, tuple)) and len(player_pos) >= 3:
                try:
                    px, py, pz = float(player_pos[0]), float(player_pos[1]), float(player_pos[2])
                except Exception:
                    return None
            else:
                return None
        dx = px - float(target[0])
        dy = py - float(target[1])
        dz = pz - float(target[2])
        return math.sqrt((dx * dx) + (dy * dy) + (dz * dz))

    def get_checkpoint_entry(self, player_pos=None):
        if not self.enabled:
            return None
        step, phase, idx, total = self._active_step()
        if not step:
            return None

        target = self._step_targets.get(step.get("id"), self._core_target)
        if not (isinstance(target, (list, tuple)) and len(target) >= 3):
            return None

        t = self.app.data_mgr.t
        objective_text = t(step.get("text_key", ""), step.get("default", "Objective"))
        distance = self._distance_to_target(player_pos, target)
        return {
            "quest_id": "movement_tutorial",
            "title": t("ui.tutorial_checkpoint_title", "Training Objective"),
            "objective": objective_text,
            "objective_type": "reach_location",
            "objective_index": int(idx),
            "objective_total": int(total),
            "status": t("hud.reach", "Reach"),
            "target": [float(target[0]), float(target[1]), float(target[2])],
            "distance": distance,
            "radius": 6.0 if phase == "core" else 5.0,
        }

    def get_journal_lines(self):
        t = self.app.data_mgr.t
        snap = self.get_status_snapshot()
        lines = [t("ui.tutorial_journal_header", "Training Program:")]
        lines.append(
            f"- {t('ui.tutorial_journal_core', 'Core')} "
            f"[{snap['required_done']}/{snap['required_total']}]"
        )
        lines.append(
            f"- {t('ui.tutorial_journal_advanced', 'Advanced')} "
            f"[{snap['bonus_done']}/{snap['bonus_total']}]"
        )
        lines.append(
            "- " + t("ui.tutorial_journal_restart", "F8: restart tutorial, Shift+F8: full training")
        )
        return lines

    def export_state(self):
        return {
            "version": 2,
            "mode": str(self.mode),
            "enabled": bool(self.enabled),
            "required_index": int(self._required_index),
            "bonus_index": int(self._bonus_index),
        }

    def import_state(self, payload):
        if not isinstance(payload, dict):
            return

        self.set_mode(payload.get("mode", "main"), reset=False)

        req = payload.get("required_index")
        bonus = payload.get("bonus_index")
        if req is None and "step_index" in payload:
            # Legacy migration from old flat-step tutorial.
            try:
                legacy_idx = max(0, int(payload.get("step_index", 0) or 0))
            except Exception:
                legacy_idx = 0
            legacy_ids = ["move", "sprint", "jump", "dodge", "parkour", "swim", "fly"]
            done = set(legacy_ids[:legacy_idx])
            req = 0
            while req < len(self._core_steps) and self._core_steps[req]["id"] in done:
                req += 1
            bonus = 0
            while bonus < len(self._advanced_steps) and self._advanced_steps[bonus]["id"] in done:
                bonus += 1

        try:
            self._required_index = max(0, min(len(self._core_steps), int(req or 0)))
        except Exception:
            self._required_index = 0
        try:
            self._bonus_index = max(0, min(len(self._advanced_steps), int(bonus or 0)))
        except Exception:
            self._bonus_index = 0
        self.enabled = bool(payload.get("enabled", self.enabled))
