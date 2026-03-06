"""NPC Interaction Manager — proximity detection, interaction icons, dialog trigger.

Each frame:
  1. Finds the nearest NPC unit within INTERACT_RADIUS
  2. Shows/hides a floating interaction prompt icon above their head
  3. When player presses E (interact_key) → starts DialogCinematicManager

NPCs must be registered via  register_unit(npc_id, actor, dialogue_path)
The NPCManager calls this after spawning each unit.
"""

from __future__ import annotations

import json
import math
import os

from direct.gui.DirectGui import DirectFrame, OnscreenText
from direct.interval.IntervalGlobal import LerpColorScaleInterval
from panda3d.core import TextNode, Vec3

from ui.design_system import THEME, body_font, place_ui_on_top
from utils.logger import logger

INTERACT_RADIUS  = 5.5   # metres — within this range the prompt appears
INTERACT_KEY     = "e"   # key that triggers dialog
PROMPT_ICON      = "[E]"
PROMPT_LABEL_Z   = 2.6   # height above NPC origin where the icon floats
DIALOGUES_DIR    = "data/dialogues"


class NPCInteractionManager:
    def __init__(self, app):
        self.app = app

        # {npc_id: {"actor": NodePath, "dialogue_path": str, "name": str}}
        self._units: dict[str, dict] = {}

        self._nearest_id: str | None = None
        self._prompt_visible = False

        # Build floating prompt widget (hidden by default)
        self._prompt_frame = None
        self._prompt_text  = None
        self._build_prompt()

        # Listen for interact key
        self.app.accept(INTERACT_KEY, self._on_interact)
        self.app.accept("\u0443", self._on_interact)   # Cyrillic У → same physical key

    # ────────────────────────────────────────────────────────────────
    # Registration
    # ────────────────────────────────────────────────────────────────

    def register_unit(self, npc_id: str, actor, dialogue_path: str = "", name: str = ""):
        """Call this from NPCManager after spawning each NPC actor."""
        self._units[npc_id] = {
            "actor":         actor,
            "dialogue_path": str(dialogue_path or ""),
            "name":          str(name or npc_id),
        }

    def unregister_unit(self, npc_id: str):
        self._units.pop(npc_id, None)

    def clear(self):
        self._units.clear()
        self._nearest_id = None
        self._hide_prompt()

    # ────────────────────────────────────────────────────────────────
    # Update (called every frame from app.py)
    # ────────────────────────────────────────────────────────────────

    def update(self, dt):
        if getattr(getattr(self.app, "dialog_cinematic", None), "is_active", lambda: False)():
            self._hide_prompt()
            return

        player_pos = self._player_pos()
        if player_pos is None:
            self._hide_prompt()
            return

        best_id   = None
        best_dist = INTERACT_RADIUS

        for npc_id, unit in self._units.items():
            actor = unit.get("actor")
            if not actor:
                continue
            try:
                npc_pos = actor.getPos(self.app.render)
            except Exception:
                continue
            dist = math.sqrt(
                (player_pos.x - npc_pos.x) ** 2 +
                (player_pos.y - npc_pos.y) ** 2
            )
            if dist < best_dist:
                best_dist = dist
                best_id   = npc_id

        if best_id != self._nearest_id:
            self._nearest_id = best_id

        if best_id:
            unit  = self._units[best_id]
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

    # ────────────────────────────────────────────────────────────────
    # Interaction handler
    # ────────────────────────────────────────────────────────────────

    def _on_interact(self):
        # Ignore if another UI is open
        dc = getattr(self.app, "dialog_cinematic", None)
        if dc and dc.is_active():
            return

        state_mgr = getattr(self.app, "state_mgr", None)
        gs        = getattr(self.app, "GameState", None)
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

    # ────────────────────────────────────────────────────────────────
    # Prompt UI
    # ────────────────────────────────────────────────────────────────

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
        # Project 3D world position to 2D screen
        screen_pos = self._world_to_screen(world_pos)
        if screen_pos is None:
            self._hide_prompt()
            return

        sx, sy = screen_pos
        if self._prompt_text:
            self._prompt_text["text"] = f"{PROMPT_ICON}  {npc_name}"
            self._prompt_text.setPos(sx, sy)
            if not self._prompt_visible:
                LerpColorScaleInterval(
                    self._prompt_text, 0.18, (1, 1, 1, 1),
                    startColorScale=(1, 1, 1, 0), blendType="easeOut"
                ).start()
                self._prompt_visible = True

    def _hide_prompt(self):
        if self._prompt_visible and self._prompt_text:
            LerpColorScaleInterval(
                self._prompt_text, 0.14, (1, 1, 1, 0),
                startColorScale=(1, 1, 1, 1), blendType="easeIn"
            ).start()
            self._prompt_visible = False

    def _world_to_screen(self, world_pos: Vec3):
        """Convert a 3D world position to aspect2d 2D coordinates."""
        try:
            cam  = self.app.camera
            lens = self.app.camLens
            p3d  = lens.getProjectionMat().xformPoint(
                self.app.render.getRelativePoint(cam, world_pos)
            )
            # p3d.x/y are NDC [-1..1]
            aspect = float(self.app.getAspectRatio() or 1.0)
            return float(p3d.x) * aspect, float(p3d.y)
        except Exception:
            return None

    # ────────────────────────────────────────────────────────────────
    # Data loading
    # ────────────────────────────────────────────────────────────────

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

    # ────────────────────────────────────────────────────────────────
    # Player position
    # ────────────────────────────────────────────────────────────────

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
