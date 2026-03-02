"""Runtime movement tutorial flow for training/testing profiles."""

import math


class MovementTutorialManager:
    def __init__(self, app):
        self.app = app
        self.enabled = False
        self._step_index = 0
        self._steps = [
            {"id": "move", "text_key": "ui.tutorial_move", "default": "Move with W/A/S/D"},
            {"id": "sprint", "text_key": "ui.tutorial_sprint", "default": "Sprint with Shift + movement"},
            {"id": "jump", "text_key": "ui.tutorial_jump", "default": "Jump with Space"},
            {"id": "dodge", "text_key": "ui.tutorial_dodge", "default": "Dodge with Z / roll input"},
            {"id": "parkour", "text_key": "ui.tutorial_parkour", "default": "Use parkour: vault, climb or wallrun"},
            {"id": "swim", "text_key": "ui.tutorial_swim", "default": "Enter water to test swimming"},
            {"id": "fly", "text_key": "ui.tutorial_fly", "default": "Toggle flight and move in air"},
        ]

    def enable(self, reset=True):
        self.enabled = True
        if reset:
            self._step_index = 0

    def disable(self):
        self.enabled = False

    def is_complete(self):
        return self._step_index >= len(self._steps)

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

    def _step_done(self, step_id, player):
        speed = self._player_speed(player)
        anim_state = str(getattr(player, "_anim_state", "") or "").strip().lower()

        if step_id == "move":
            return speed > 0.45
        if step_id == "sprint":
            is_run_pressed = bool(getattr(player, "_get_action", lambda _k: False)("run"))
            run_ref = max(1.0, float(getattr(player, "run_speed", 8.0) or 8.0))
            return is_run_pressed and speed > (run_ref * 0.55)
        if step_id == "jump":
            return (not self._on_ground(player)) and (anim_state in {"jumping", "falling", "landing"} or True)
        if step_id == "dodge":
            return anim_state == "dodging"
        if step_id == "parkour":
            return anim_state in {"vaulting", "climbing", "wallrun"} or bool(getattr(player, "_was_wallrun", False))
        if step_id == "swim":
            return self._in_water(player)
        if step_id == "fly":
            return bool(getattr(player, "_is_flying", False))
        return False

    def update(self, dt):
        if not self.enabled:
            return
        if self.is_complete():
            return

        player = getattr(self.app, "player", None)
        if not player:
            return

        step = self._steps[self._step_index]
        if self._step_done(step["id"], player):
            self._step_index += 1

    def get_hud_message(self):
        if not self.enabled:
            return ""

        header = self.app.data_mgr.t("ui.tutorial_header", "Movement Tutorial")
        total = len(self._steps)
        if self.is_complete():
            done = self.app.data_mgr.t("ui.tutorial_complete", "Tutorial complete")
            return f"{header} [{total}/{total}] {done}"

        step = self._steps[self._step_index]
        text = self.app.data_mgr.t(step["text_key"], step["default"])
        return f"{header} [{self._step_index + 1}/{total}] {text}"
