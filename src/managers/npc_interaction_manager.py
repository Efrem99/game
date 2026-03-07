"""NPC interaction manager: proximity detection, prompt, and dialogue trigger."""

from __future__ import annotations

import json
import math
import os

from direct.gui.DirectGui import OnscreenText
from direct.interval.IntervalGlobal import LerpColorScaleInterval
from panda3d.core import TextNode, Vec3

from ui.design_system import THEME, body_font, place_ui_on_top
from utils.logger import logger

INTERACT_RADIUS = 5.5
PROMPT_LABEL_Z = 2.6
DIALOGUES_DIR = "data/dialogues"
RU_KEY_MAP = {
    "q": "й",
    "w": "ц",
    "e": "у",
    "r": "к",
    "t": "е",
    "y": "н",
    "u": "г",
    "i": "ш",
    "o": "щ",
    "p": "з",
    "a": "ф",
    "s": "ы",
    "d": "в",
    "f": "а",
    "g": "п",
    "h": "р",
    "j": "о",
    "k": "л",
    "l": "д",
    "z": "я",
    "x": "ч",
    "c": "с",
    "v": "м",
    "b": "и",
    "n": "т",
    "m": "ь",
}


class NPCInteractionManager:
    def __init__(self, app):
        self.app = app

        # {npc_id: {"actor": NodePath, "dialogue_path": str, "name": str}}
        self._units: dict[str, dict] = {}

        self._nearest_id: str | None = None
        self._prompt_visible = False
        self._bound_interact_events: list[str] = []
        self._interact_token: str = ""
        self._prompt_icon = "[F]"

        self._prompt_text = None
        self._build_prompt()
        self._sync_interact_binding(force=True)

    def register_unit(self, npc_id: str, actor, dialogue_path: str = "", name: str = ""):
        """Call this from NPCManager after spawning each NPC actor."""
        self._units[npc_id] = {
            "actor": actor,
            "dialogue_path": str(dialogue_path or ""),
            "name": str(name or npc_id),
        }

    def unregister_unit(self, npc_id: str):
        self._units.pop(npc_id, None)

    def clear(self):
        self._units.clear()
        self._nearest_id = None
        self._hide_prompt()

    def _resolve_interact_binding(self):
        dm = getattr(self.app, "data_mgr", None)
        if dm and hasattr(dm, "get_binding"):
            token = str(dm.get_binding("interact") or "").strip().lower()
            if token:
                return token
        return "f"

    def _format_prompt_icon(self, token):
        key = str(token or "").strip().lower()
        if not key:
            return "[ACT]"
        pretty = key
        if key == "mouse1":
            pretty = "LMB"
        elif key == "mouse2":
            pretty = "RMB"
        elif key in {"mouse3", "middlemouse"}:
            pretty = "MMB"
        elif key.startswith("arrow_"):
            pretty = key.replace("arrow_", "ARROW ").upper()
        else:
            pretty = key.upper()
        return f"[{pretty}]"

    def _interact_tokens_for_binding(self, token):
        values = []
        key = str(token or "").strip().lower()
        if key:
            values.append(key)
            ru = RU_KEY_MAP.get(key)
            if ru:
                values.append(ru)
        out = []
        seen = set()
        for row in values:
            t = str(row or "").strip()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out

    def _sync_interact_binding(self, force=False):
        token = self._resolve_interact_binding()
        if (not force) and token == self._interact_token:
            return
        for event_name in list(self._bound_interact_events):
            try:
                self.app.ignore(event_name)
            except Exception:
                continue
        self._bound_interact_events = []
        for event_name in self._interact_tokens_for_binding(token):
            try:
                self.app.accept(event_name, self._on_interact)
                self._bound_interact_events.append(event_name)
            except Exception:
                continue
        self._interact_token = token
        self._prompt_icon = self._format_prompt_icon(token)

    def update(self, dt):
        _ = dt
        self._sync_interact_binding(force=False)
        if getattr(getattr(self.app, "dialog_cinematic", None), "is_active", lambda: False)():
            self._hide_prompt()
            return

        player_pos = self._player_pos()
        if player_pos is None:
            self._hide_prompt()
            return

        best_id = None
        best_dist = INTERACT_RADIUS

        for npc_id, unit in self._units.items():
            actor = unit.get("actor")
            if not actor:
                continue
            try:
                npc_pos = actor.getPos(self.app.render)
            except Exception:
                continue
            dist = math.sqrt((player_pos.x - npc_pos.x) ** 2 + (player_pos.y - npc_pos.y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_id = npc_id

        if best_id != self._nearest_id:
            self._nearest_id = best_id

        if best_id:
            unit = self._units[best_id]
            actor = unit["actor"]
            try:
                npc_pos = actor.getPos(self.app.render)
            except Exception:
                self._hide_prompt()
                return
            prompt_3d = Vec3(npc_pos.x, npc_pos.y, npc_pos.z + PROMPT_LABEL_Z)
            self._show_prompt(prompt_3d, unit["name"])
        else:
            self._hide_prompt()

    def _on_interact(self):
        dc = getattr(self.app, "dialog_cinematic", None)
        if dc and dc.is_active():
            return

        state_mgr = getattr(self.app, "state_mgr", None)
        gs = getattr(self.app, "GameState", None)
        if state_mgr and gs:
            state = getattr(state_mgr, "current_state", None)
            if state not in (gs.PLAYING, None):
                return

        if not self._nearest_id:
            return

        unit = self._units.get(self._nearest_id)
        if not unit:
            return

        dialogue_data = self._load_dialogue(unit["dialogue_path"])
        if not dialogue_data:
            logger.warning(f"[NPCInteraction] No dialogue data for '{self._nearest_id}'")
            return

        if dc:
            dc.start_dialogue(
                npc_id=self._nearest_id,
                dialogue_data=dialogue_data,
                npc_actor=unit.get("actor"),
            )
        logger.info(f"[NPCInteraction] Started dialogue with '{self._nearest_id}'")

    def _build_prompt(self):
        self._prompt_text = OnscreenText(
            text="",
            pos=(0, 0),
            scale=0.048,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.9),
            align=TextNode.ACenter,
            parent=self.app.aspect2d,
            mayChange=True,
            font=body_font(self.app),
        )
        self._prompt_text.setColorScale(1, 1, 1, 0)
        place_ui_on_top(self._prompt_text, 70)

    def _show_prompt(self, world_pos: Vec3, npc_name: str):
        screen_pos = self._world_to_screen(world_pos)
        if screen_pos is None:
            self._hide_prompt()
            return

        sx, sy = screen_pos
        if self._prompt_text:
            self._prompt_text["text"] = f"{self._prompt_icon}  {npc_name}"
            self._prompt_text.setPos(sx, sy)
            if not self._prompt_visible:
                LerpColorScaleInterval(
                    self._prompt_text,
                    0.18,
                    (1, 1, 1, 1),
                    startColorScale=(1, 1, 1, 0),
                    blendType="easeOut",
                ).start()
                self._prompt_visible = True

    def _hide_prompt(self):
        if self._prompt_visible and self._prompt_text:
            LerpColorScaleInterval(
                self._prompt_text,
                0.14,
                (1, 1, 1, 0),
                startColorScale=(1, 1, 1, 1),
                blendType="easeIn",
            ).start()
            self._prompt_visible = False

    def _world_to_screen(self, world_pos: Vec3):
        """Convert a 3D world position to aspect2d 2D coordinates."""
        try:
            cam = self.app.camera
            lens = self.app.camLens
            p3d = lens.getProjectionMat().xformPoint(
                self.app.render.getRelativePoint(cam, world_pos)
            )
            aspect = float(self.app.getAspectRatio() or 1.0)
            return float(p3d.x) * aspect, float(p3d.y)
        except Exception:
            return None

    def _load_dialogue(self, path: str) -> dict | None:
        if not path:
            return None
        candidates = [
            path,
            os.path.join(DIALOGUES_DIR, path),
            os.path.join(DIALOGUES_DIR, path + ".json"),
            os.path.join(DIALOGUES_DIR, os.path.basename(path) + ".json"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                try:
                    with open(candidate, encoding="utf-8") as f:
                        return json.load(f)
                except Exception as exc:
                    logger.warning(f"[NPCInteraction] Failed to load dialogue '{candidate}': {exc}")
                    return None
        logger.debug(f"[NPCInteraction] Dialogue file not found: {path!r}")
        return None

    def _player_pos(self):
        player = getattr(self.app, "player", None)
        if not player:
            return None
        actor = getattr(player, "actor", None)
        if not actor:
            return None
        try:
            return actor.getPos(self.app.render)
        except Exception:
            return None
