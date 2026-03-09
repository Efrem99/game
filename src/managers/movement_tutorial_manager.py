"""Runtime tutorial flow used by both test demos and main game."""

import math
import os
import shutil


class MovementTutorialManager:
    """Data-driven onboarding for movement, combat and traversal basics."""

    def __init__(self, app):
        self.app = app
        self.enabled = False
        self.mode = "main"

        self._core_steps = [
            {
                "id": "move",
                "title_key": "ui.tutorial_step_move_title",
                "title_default": "Footwork",
                "text_key": "ui.tutorial_move",
                "default": "Move with W/A/S/D",
                "bindings": ["forward", "left", "backward", "right"],
                "target": (18.0, 24.0, 0.0),
                "radius": 7.0,
            },
            {
                "id": "sprint",
                "title_key": "ui.tutorial_step_sprint_title",
                "title_default": "Momentum",
                "text_key": "ui.tutorial_sprint",
                "default": "Sprint with Shift + movement",
                "bindings": ["run", "forward"],
                "target": (18.0, 13.0, 0.0),
                "radius": 6.0,
            },
            {
                "id": "jump",
                "title_key": "ui.tutorial_step_jump_title",
                "title_default": "Verticality",
                "text_key": "ui.tutorial_jump",
                "default": "Jump with Space",
                "bindings": ["jump"],
                "target": (12.5, 30.8, 0.0),
                "radius": 6.0,
            },
            {
                "id": "interact",
                "title_key": "ui.tutorial_step_interact_title",
                "title_default": "Interaction",
                "text_key": "ui.tutorial_interact",
                "default": "Interact with X near NPC/object",
                "bindings": ["interact"],
                "target": (5.0, 45.0, 0.0),
                "radius": 6.5,
            },
            {
                "id": "dodge",
                "title_key": "ui.tutorial_step_dodge_title",
                "title_default": "Evasion",
                "text_key": "ui.tutorial_dodge",
                "default": "Dodge with Z",
                "bindings": ["dash"],
                "target": (18.0, 24.0, 0.0),
                "radius": 6.0,
            },
            {
                "id": "attack",
                "title_key": "ui.tutorial_step_attack_title",
                "title_default": "Melee Basics",
                "text_key": "ui.tutorial_attack",
                "default": "Use light attack (LMB) or heavy attack (E)",
                "bindings": ["attack_light", "attack_heavy"],
                "target": (18.0, 24.0, 0.0),
                "radius": 6.0,
            },
            {
                "id": "skill_wheel",
                "title_key": "ui.tutorial_step_skill_wheel_title",
                "title_default": "Skill Wheel",
                "text_key": "ui.tutorial_skill_wheel",
                "default": "Hold TAB and choose a skill with mouse",
                "bindings": ["skill_wheel"],
                "target": (18.0, 24.0, 0.0),
                "radius": 6.0,
            },
            {
                "id": "cast",
                "title_key": "ui.tutorial_step_cast_title",
                "title_default": "Spell Casting",
                "text_key": "ui.tutorial_cast",
                "default": "Cast your selected spell",
                "bindings": ["attack_light", "block"],
                "target": (18.0, 24.0, 0.0),
                "radius": 6.0,
            },
        ]

        self._advanced_steps = [
            {
                "id": "parkour",
                "title_key": "ui.tutorial_step_parkour_title",
                "title_default": "Parkour Route",
                "text_key": "ui.tutorial_parkour",
                "default": "Use parkour: vault, climb or wallrun",
                "bindings": ["roll", "jump", "forward"],
                "target": (29.5, 26.0, 0.0),
                "radius": 5.0,
            },
            {
                "id": "swim",
                "title_key": "ui.tutorial_step_swim_title",
                "title_default": "Water Trial",
                "text_key": "ui.tutorial_swim",
                "default": "Enter water to test swimming",
                "bindings": ["forward", "jump"],
                "target": (4.0, 36.0, 0.0),
                "radius": 5.0,
            },
            {
                "id": "fly",
                "title_key": "ui.tutorial_step_fly_title",
                "title_default": "Flight Trial",
                "text_key": "ui.tutorial_fly",
                "default": "Toggle flight and move in air",
                "bindings": ["flight_toggle", "flight_up", "flight_down", "run"],
                "target": (18.0, 24.0, 8.0),
                "radius": 5.0,
            },
            {
                "id": "mount",
                "title_key": "ui.tutorial_step_mount_title",
                "title_default": "Mount Handling",
                "text_key": "ui.tutorial_mount",
                "default": "Mount a horse/carriage/boat with interact",
                "bindings": ["interact", "run", "forward"],
                "target": (9.0, 6.0, 0.0),
                "radius": 5.0,
            },
        ]

        self._core_target = (18.0, 24.0, 0.0)
        self._step_targets = {}
        self._step_radius = {}
        for step in self._core_steps + self._advanced_steps:
            self._step_targets[str(step["id"])] = tuple(step.get("target", self._core_target))
            self._step_radius[str(step["id"])] = float(step.get("radius", 6.0) or 6.0)

        self._required_index = 0
        self._bonus_index = 0
        self._step_flash_ttl = 0.0
        self._completion_banner_ttl = 0.0
        self._last_completion_text = ""
        self._last_completed_step = ""
        self._last_focused_step = ""
        self._voice_root = "data/audio/voices/tutorial"
        self._fallback_voice_keys = {
            "move": "guard_city/start",
            "sprint": "guard_city/directions",
            "jump": "quest_giver_main/encourage",
            "interact": "merchant/start",
            "dodge": "guard_city/trouble",
            "attack": "quest_giver_main/quest_offer",
            "skill_wheel": "merchant_general/rare_items",
            "cast": "quest_giver_main/quest_details",
            "parkour": "opening_memory/sebastian_training",
            "swim": "opening_memory/flight_escape",
            "fly": "opening_memory/flight_escape",
            "mount": "guard_city/passing_through",
        }
        self._completion_voice_key = "quest_giver_main/reward"
        self._step_focus_sfx = {
            "move": ("ui_hover", 0.22, 0.96),
            "sprint": ("ui_hover", 0.24, 1.01),
            "jump": ("jump", 0.22, 1.06),
            "interact": ("ui_hover", 0.24, 1.0),
            "dodge": ("ui_click", 0.26, 1.08),
            "attack": ("ui_click", 0.28, 1.12),
            "skill_wheel": ("ui_hover", 0.24, 1.02),
            "cast": ("spell_cast", 0.24, 1.0),
            "parkour": ("ui_hover", 0.24, 1.04),
            "swim": ("footstep_water", 0.24, 0.96),
            "fly": ("spell_arcane", 0.24, 1.02),
            "mount": ("ui_click", 0.26, 0.98),
        }
        self._voice_exts = (".ogg", ".mp3", ".wav")
        self._autocreated_step_voice = set()
        self._bootstrap_tutorial_voice_bank()

    def set_mode(self, mode, reset=False):
        token = str(mode or "main").strip().lower()
        if token not in {"main", "demo"}:
            token = "main"
        self.mode = token
        if reset:
            self._required_index = 0
            self._bonus_index = 0
            self._step_flash_ttl = 0.0
            self._completion_banner_ttl = 0.0
            self._last_completion_text = ""
            self._last_completed_step = ""
            self._last_focused_step = ""

    def enable(self, reset=True, mode=None):
        if mode is not None:
            self.set_mode(mode, reset=reset)
        elif reset:
            self._required_index = 0
            self._bonus_index = 0
            self._step_flash_ttl = 0.0
            self._completion_banner_ttl = 0.0
            self._last_completion_text = ""
            self._last_completed_step = ""
            self._last_focused_step = ""
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

    def _emit_event(self, event_name, payload):
        bus = getattr(self.app, "event_bus", None)
        if not bus or not hasattr(bus, "emit"):
            return
        try:
            bus.emit(event_name, payload, immediate=False)
        except Exception:
            pass

    def _step_phase_label(self, phase):
        t = self.app.data_mgr.t
        if phase == "advanced":
            return t("ui.tutorial_hud_stage_advanced", "Advanced")
        if phase == "complete":
            return t("ui.tutorial_hud_stage_complete", "Complete")
        return t("ui.tutorial_hud_stage_core", "Core")

    def _on_step_completed(self, step, phase, index, total):
        if not isinstance(step, dict):
            return
        t = self.app.data_mgr.t
        step_id = str(step.get("id", "") or "")
        step_title = t(step.get("title_key", ""), step.get("title_default", step_id))
        self._last_completion_text = f"{self._step_phase_label(phase)}: {step_title}"
        self._step_flash_ttl = 1.25
        self._last_completed_step = f"{phase}:{step_id}:{index}"

        self._emit_event(
            "tutorial.step.completed",
            {
                "step_id": step_id,
                "phase": phase,
                "index": int(index),
                "total": int(total),
                "title": step_title,
            },
        )
        self._emit_event(
            "audio.sfx.play",
            {
                "key": "ui_click",
                "volume": 0.42 if phase == "core" else 0.52,
                "rate": 1.02 if phase == "core" else 1.08,
            },
        )
        if phase == "advanced" and step_id in {"parkour", "fly", "mount"}:
            self._emit_event(
                "camera.shot.request",
                {
                    "name": "location",
                    "duration": 0.62,
                    "profile": "tutorial",
                    "side": 1.35,
                    "yaw_bias_deg": 9.0,
                    "priority": 57,
                    "owner": "tutorial",
                },
            )

    def _on_tutorial_completed(self):
        t = self.app.data_mgr.t
        self._last_completion_text = t("ui.tutorial_complete", "Tutorial complete")
        self._completion_banner_ttl = 5.0
        self._step_flash_ttl = 1.4
        self._emit_event(
            "tutorial.completed",
            {
                "mode": str(self.mode),
                "required_total": len(self._core_steps),
                "bonus_total": len(self._advanced_steps),
            },
        )
        self._emit_event(
            "audio.sfx.play",
            {
                "key": "item_pickup",
                "volume": 0.58,
                "rate": 1.14,
            },
        )
        self._emit_event(
            "camera.impact",
            {
                "kind": "parry",
                "intensity": 0.48,
                "direction_deg": 0.0,
            },
        )
        if self._completion_voice_key:
            self._emit_event(
                "audio.voice.play",
                {
                    "key": str(self._completion_voice_key),
                    "volume": 0.82,
                    "rate": 1.0,
                },
            )

    def _try_play_step_voice(self, phase, step_id):
        phase_token = str(phase or "core").strip().lower()
        step_token = str(step_id or "").strip().lower()
        if not step_token:
            return

        rel_path = self._resolve_step_voice_rel(phase_token, step_token)
        if rel_path or self._ensure_step_voice_asset(phase_token, step_token):
            rel_path = self._resolve_step_voice_rel(phase_token, step_token)
        if rel_path:
            self._emit_event(
                "audio.voice.play",
                {
                    "path": rel_path,
                    "volume": 0.78,
                    "rate": 1.0,
                },
            )
            return

        fallback_key = str(self._fallback_voice_keys.get(step_token, "") or "").strip()
        if fallback_key:
            self._emit_event(
                "audio.voice.play",
                {
                    "key": fallback_key,
                    "volume": 0.74,
                    "rate": 1.0,
                },
            )

    def _voices_base_abs(self):
        return os.path.join(self.app.project_root, "data", "audio", "voices")

    def _tutorial_voice_root_abs(self):
        return os.path.join(self.app.project_root, self._voice_root.replace("/", os.sep))

    def _resolve_voice_key_abs(self, voice_key):
        token = str(voice_key or "").strip().replace("\\", "/")
        if not token:
            return None
        base = self._voices_base_abs()
        stem_abs = os.path.join(base, token.replace("/", os.sep))
        for ext in self._voice_exts:
            candidate = stem_abs + ext
            if os.path.exists(candidate):
                return candidate
        return None

    def _resolve_step_voice_rel(self, phase_token, step_token):
        phase_norm = str(phase_token or "core").strip().lower()
        step_norm = str(step_token or "").strip().lower()
        if not step_norm:
            return None
        root = self._tutorial_voice_root_abs()
        for ext in self._voice_exts:
            abs_path = os.path.join(root, f"{phase_norm}_{step_norm}{ext}")
            if os.path.exists(abs_path):
                return f"{self._voice_root}/{phase_norm}_{step_norm}{ext}".replace("\\", "/")
        return None

    def _ensure_step_voice_asset(self, phase_token, step_token):
        phase_norm = str(phase_token or "core").strip().lower()
        step_norm = str(step_token or "").strip().lower()
        if not step_norm:
            return False
        if self._resolve_step_voice_rel(phase_norm, step_norm):
            return True

        fallback_key = str(self._fallback_voice_keys.get(step_norm, "") or "").strip()
        source_abs = self._resolve_voice_key_abs(fallback_key)
        if not source_abs:
            return False

        target_root = self._tutorial_voice_root_abs()
        try:
            os.makedirs(target_root, exist_ok=True)
        except Exception:
            return False

        ext = os.path.splitext(source_abs)[1] or ".mp3"
        target_abs = os.path.join(target_root, f"{phase_norm}_{step_norm}{ext}")
        if os.path.exists(target_abs):
            return True
        try:
            # Keep generated tutorial clips as concrete files so future runs are instant.
            shutil.copy2(source_abs, target_abs)
            self._autocreated_step_voice.add(f"{phase_norm}:{step_norm}")
            return True
        except Exception:
            return False

    def _bootstrap_tutorial_voice_bank(self):
        for step in self._core_steps:
            step_id = str(step.get("id", "") or "").strip().lower()
            if step_id:
                self._ensure_step_voice_asset("core", step_id)
        for step in self._advanced_steps:
            step_id = str(step.get("id", "") or "").strip().lower()
            if step_id:
                self._ensure_step_voice_asset("advanced", step_id)

    def _on_step_focused(self, step, phase, index, total):
        if not isinstance(step, dict):
            return
        step_id = str(step.get("id", "") or "").strip().lower()
        if not step_id:
            return

        self._emit_event(
            "tutorial.step.focused",
            {
                "step_id": step_id,
                "phase": str(phase or "core"),
                "index": int(index),
                "total": int(total),
            },
        )
        sfx_key, volume, rate = self._step_focus_sfx.get(step_id, ("ui_hover", 0.22, 1.0))
        self._emit_event(
            "audio.sfx.play",
            {
                "key": sfx_key,
                "volume": float(volume),
                "rate": float(rate),
            },
        )
        self._try_play_step_voice(phase, step_id)

    def _announce_active_step(self):
        step, phase, idx, total = self._active_step()
        if not isinstance(step, dict):
            return
        step_id = str(step.get("id", "") or "").strip().lower()
        if not step_id:
            return

        # Signature-based dedupe prevents repeated intro pings while staying on one step.
        signature = f"{phase}:{step_id}:{idx}:{total}"
        if signature == self._last_focused_step:
            return
        self._last_focused_step = signature
        self._on_step_focused(step, phase, idx, total)

    def _binding_label(self, action_name):
        token = str(action_name or "").strip().lower()
        if not token:
            return ""
        bound = str(getattr(self.app.data_mgr, "get_binding", lambda _a: "")(token) or token).strip().lower()
        aliases = {
            "mouse1": "LMB",
            "mouse2": "RMB",
            "mouse3": "MMB",
            "space": "SPACE",
            "lcontrol": "LCTRL",
            "rcontrol": "RCTRL",
            "lshift": "SHIFT",
            "rshift": "SHIFT",
            "shift": "SHIFT",
            "tab": "TAB",
            "enter": "ENTER",
            "escape": "ESC",
            "wheel_up": "MWHEEL+",
            "wheel_down": "MWHEEL-",
        }
        return aliases.get(bound, bound.upper())

    def _step_bindings(self, step):
        if not isinstance(step, dict):
            return []
        out = []
        for action in step.get("bindings", []):
            label = self._binding_label(action)
            if label and label not in out:
                out.append(label)
        return out

    def update(self, dt):
        dt = max(0.0, float(dt or 0.0))
        self._step_flash_ttl = max(0.0, self._step_flash_ttl - dt)
        self._completion_banner_ttl = max(0.0, self._completion_banner_ttl - dt)

        if not self.enabled:
            return

        player = getattr(self.app, "player", None)
        if not player:
            return

        old_required = int(self._required_index)
        old_bonus = int(self._bonus_index)

        self._required_index = self._advance(self._core_steps, self._required_index, player)
        if self._required_index > old_required:
            start = max(0, old_required)
            end = min(len(self._core_steps), self._required_index)
            for idx in range(start, end):
                self._on_step_completed(self._core_steps[idx], "core", idx + 1, len(self._core_steps))

        if self._required_index >= len(self._core_steps):
            if self._should_show_bonus():
                self._bonus_index = self._advance(self._advanced_steps, self._bonus_index, player)
                if self._bonus_index > old_bonus:
                    start = max(0, old_bonus)
                    end = min(len(self._advanced_steps), self._bonus_index)
                    for idx in range(start, end):
                        self._on_step_completed(self._advanced_steps[idx], "advanced", idx + 1, len(self._advanced_steps))
                if self._bonus_index >= len(self._advanced_steps):
                    self.enabled = False
                    self._on_tutorial_completed()
            elif self.mode == "demo":
                self.enabled = False
                self._on_tutorial_completed()

        if self.enabled:
            self._announce_active_step()

    def _active_step(self):
        if not self.is_required_complete():
            if 0 <= self._required_index < len(self._core_steps):
                return dict(self._core_steps[self._required_index]), "core", self._required_index + 1, len(self._core_steps)
            return None, "core", 0, len(self._core_steps)
        if self._should_show_bonus() and self._bonus_index < len(self._advanced_steps):
            return dict(self._advanced_steps[self._bonus_index]), "advanced", self._bonus_index + 1, len(self._advanced_steps)
        if self._should_show_bonus():
            return None, "done", len(self._advanced_steps), len(self._advanced_steps)
        return None, "await_advanced", len(self._core_steps), len(self._core_steps)

    def get_hud_payload(self):
        t = self.app.data_mgr.t
        if not self.enabled and self._completion_banner_ttl <= 0.0:
            return {"visible": False}

        if not self.enabled and self._completion_banner_ttl > 0.0:
            header = t("ui.tutorial_header_advanced", "Advanced Training")
            return {
                "visible": True,
                "phase": "complete",
                "display_mode": "banner",
                "header": header,
                "title": t("ui.tutorial_hud_stage_complete", "Complete"),
                "text": self._last_completion_text or t("ui.tutorial_complete", "Tutorial complete"),
                "progress_label": "100%",
                "progress_ratio": 1.0,
                "keys": [],
                "flash": bool(self._step_flash_ttl > 0.0),
                "completion_ttl": float(self._completion_banner_ttl),
            }

        step, phase, idx, total = self._active_step()
        if phase == "await_advanced":
            header = t("ui.tutorial_header_advanced", "Advanced Training")
            return {
                "visible": True,
                "phase": "await_advanced",
                "display_mode": "banner",
                "header": header,
                "title": t("ui.tutorial_core_complete_title", "Core training complete"),
                "text": t("ui.tutorial_core_complete_hint", "Reach the Training Grounds to unlock advanced drills."),
                "progress_label": "100%",
                "progress_ratio": 1.0,
                "keys": [self._binding_label("inventory"), "F8", "SHIFT+F8"],
                "flash": bool(self._step_flash_ttl > 0.0),
            }

        if step is None and phase == "done":
            return {
                "visible": True,
                "phase": "complete",
                "display_mode": "banner",
                "header": t("ui.tutorial_header_advanced", "Advanced Training"),
                "title": t("ui.tutorial_hud_stage_complete", "Complete"),
                "text": t("ui.tutorial_complete", "Tutorial complete"),
                "progress_label": "100%",
                "progress_ratio": 1.0,
                "keys": [],
                "flash": bool(self._step_flash_ttl > 0.0),
                "completion_ttl": float(self._completion_banner_ttl),
            }

        if not isinstance(step, dict):
            return {"visible": False}

        header = t("ui.tutorial_header", "Movement Tutorial") if phase == "core" else t("ui.tutorial_header_advanced", "Advanced Training")
        title = t(step.get("title_key", ""), step.get("title_default", step.get("id", "Step")))
        text = t(step.get("text_key", ""), step.get("default", ""))
        if total <= 0:
            progress_ratio = 0.0
        else:
            progress_ratio = max(0.0, min(1.0, float(idx - 1) / float(total)))
        progress_label = f"{idx}/{total}" if total > 0 else "--"
        return {
            "visible": True,
            "phase": phase,
            "display_mode": "banner",
            "header": header,
            "title": title,
            "text": text,
            "progress_label": progress_label,
            "progress_ratio": progress_ratio,
            "keys": self._step_bindings(step),
            "flash": bool(self._step_flash_ttl > 0.0),
            "step_id": str(step.get("id", "")),
        }

    def get_hud_message(self):
        payload = self.get_hud_payload()
        if not isinstance(payload, dict) or not payload.get("visible", False):
            return ""
        header = str(payload.get("header", "") or "").strip()
        title = str(payload.get("title", "") or "").strip()
        text = str(payload.get("text", "") or "").strip()
        progress = str(payload.get("progress_label", "") or "").strip()
        if header and progress:
            prefix = f"{header} [{progress}]"
        elif header:
            prefix = header
        else:
            prefix = ""
        detail = ": ".join(part for part in [title, text] if part)
        if prefix and detail:
            return f"{prefix} {detail}"
        return prefix or detail

    def get_status_snapshot(self):
        step, phase, _, _ = self._active_step()
        return {
            "enabled": bool(self.enabled),
            "mode": str(self.mode),
            "required_done": int(self._required_index),
            "required_total": len(self._core_steps),
            "bonus_done": int(self._bonus_index),
            "bonus_total": len(self._advanced_steps),
            "core_complete": self.is_required_complete(),
            "full_complete": self.is_required_complete() and self.is_bonus_complete(),
            "phase": str(phase),
            "active_step_id": str(step.get("id", "") if isinstance(step, dict) else ""),
        }

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
        t = self.app.data_mgr.t
        if phase == "await_advanced":
            objective_text = t("ui.tutorial_core_complete_hint", "Reach the Training Grounds to unlock advanced drills.")
            target = self._core_target
            radius = 12.0
            objective_total = len(self._core_steps)
            objective_index = len(self._core_steps)
        else:
            if not step:
                return None
            step_id = str(step.get("id", "") or "")
            target = self._step_targets.get(step_id, self._core_target)
            radius = float(self._step_radius.get(step_id, 6.0))
            objective_text = t(step.get("text_key", ""), step.get("default", "Objective"))
            objective_total = int(total)
            objective_index = int(idx)

        if not (isinstance(target, (list, tuple)) and len(target) >= 3):
            return None
        distance = self._distance_to_target(player_pos, target)
        return {
            "quest_id": "movement_tutorial",
            "title": t("ui.tutorial_checkpoint_title", "Training Objective"),
            "objective": objective_text,
            "objective_type": "reach_location",
            "objective_index": int(objective_index),
            "objective_total": int(objective_total),
            "status": t("hud.reach", "Reach"),
            "target": [float(target[0]), float(target[1]), float(target[2])],
            "distance": distance,
            "radius": float(radius),
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
        step_id = str(snap.get("active_step_id", "") or "")
        if step_id:
            lines.append(f"- Active Step: {step_id}")
        lines.append(
            "- " + t("ui.tutorial_journal_restart", "F8: restart tutorial, Shift+F8: full training")
        )
        return lines

    def export_state(self):
        return {
            "version": 3,
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
        self._last_completed_step = ""
        self._last_focused_step = ""
