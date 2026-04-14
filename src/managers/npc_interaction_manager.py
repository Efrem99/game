"""NPC interaction manager: proximity detection, prompt, and dialogue trigger."""

from __future__ import annotations

import math
import os

from direct.gui.DirectGui import OnscreenText
from panda3d.core import TextNode, Vec3

from ui.design_system import THEME, body_font, place_ui_on_top
from managers.runtime_data_access import load_data_file_candidates
from utils.logger import logger

INTERACT_RADIUS = 7.2
PROMPT_LABEL_Z = 2.1
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
        self._prompt_interval = None
        self._prompt_update_accum: float = 0.0   # throttle proximity scan
        self._PROMPT_UPDATE_HZ: float = 10.0
        self._prompt_last_log_id: str = ""       # suppress per-frame log spam

        self._prompt_text = None
        self._build_prompt()
        self._sync_interact_binding(force=True)

    def _components_are_finite(self, value):
        try:
            return all(
                math.isfinite(float(getattr(value, axis)))
                for axis in ("x", "y", "z")
            )
        except Exception:
            pass
        try:
            return all(math.isfinite(float(token)) for token in value)
        except Exception:
            return False

    def _node_transform_looks_safe(self, node):
        if not node:
            return False
        try:
            if node.isEmpty():
                return False
        except Exception:
            return False
        for getter_name in ("getPos", "getScale", "getHpr"):
            getter = getattr(node, getter_name, None)
            if not callable(getter):
                return False
            try:
                value = getter()
            except Exception:
                return False
            if not self._components_are_finite(value):
                return False
        return True

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
                # self.app.accept(event_name, self._on_interact) # Consolidated into player.py
                self._bound_interact_events.append(event_name)
            except Exception:
                continue
        self._interact_token = token
        self._prompt_icon = self._format_prompt_icon(token)

    def update(self, dt):
        try:
            safe_dt = max(0.0, min(0.5, float(dt or 0.0)))
        except Exception:
            safe_dt = 0.0

        self._sync_interact_binding(force=False)
        if getattr(getattr(self.app, "dialog_cinematic", None), "is_active", lambda: False)():
            self._hide_prompt()
            return

        # --- Throttle the expensive proximity scan to _PROMPT_UPDATE_HZ ---
        self._prompt_update_accum += safe_dt
        update_interval = max(0.02, 1.0 / max(1.0, self._PROMPT_UPDATE_HZ))
        if self._prompt_update_accum < update_interval:
            # Between scans: just keep the prompt position refreshed if already visible.
            if self._prompt_visible and self._nearest_id:
                unit = self._units.get(self._nearest_id)
                if unit:
                    actor = unit.get("actor")
                    if actor:
                        try:
                            npc_pos = actor.getPos(self.app.render)
                            self._show_prompt(
                                Vec3(npc_pos.x, npc_pos.y, npc_pos.z + 2.1),
                                unit["name"],
                            )
                        except Exception:
                            self._hide_prompt()
            return
        self._prompt_update_accum = 0.0

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
            try:
                dist = math.sqrt(
                    (player_pos.x - npc_pos.x) ** 2
                    + (player_pos.y - npc_pos.y) ** 2
                )
            except Exception:
                continue
            if math.isnan(dist) or math.isinf(dist):
                continue
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
            prompt_3d = Vec3(npc_pos.x, npc_pos.y, npc_pos.z + 2.1)
            # Only log once per NPC ID to avoid spam
            if best_id != self._prompt_last_log_id:
                logger.debug(f"[NPCInteraction] Activating prompt for '{best_id}' at {prompt_3d}")
                self._prompt_last_log_id = best_id
            self._show_prompt(prompt_3d, unit["name"])
        else:
            if self._prompt_last_log_id:
                self._prompt_last_log_id = ""
            self._hide_prompt()

    def try_interact(self):
        return bool(self._on_interact())

    def _on_interact(self):
        dc = getattr(self.app, "dialog_cinematic", None)
        if dc and dc.is_active():
            logger.info("[NPCInteraction] Ввод взаимодействия пропущен: кинематографический диалог уже активен.")
            return False

        state_mgr = getattr(self.app, "state_mgr", None)
        gs = getattr(self.app, "GameState", None)
        if state_mgr and gs:
            state = getattr(state_mgr, "current_state", None)
            if state not in (gs.PLAYING, None):
                logger.info(f"[NPCInteraction] Ввод взаимодействия пропущен: текущее состояние={state}.")
                return False

        if not self._nearest_id:
            logger.info("[NPCInteraction] Ввод взаимодействия получен, но рядом нет NPC для диалога.")
            return False

        unit = self._units.get(self._nearest_id)
        if not unit:
            logger.warning(f"[NPCInteraction] Ближайший NPC '{self._nearest_id}' не найден в реестре взаимодействий.")
            return False

        # Defensive: Ensure NPC actor is healthy before dialogue starts
        actor = unit.get("actor")
        if actor and (not self._node_transform_looks_safe(actor)):
            logger.warning(f"[NPCInteraction] Ignoring interaction with corrupted NPC '{self._nearest_id}'")
            return False

        dialogue_data = self._load_dialogue(unit["dialogue_path"])
        if not dialogue_data:
            logger.warning(f"[NPCInteraction] No dialogue data for '{self._nearest_id}'")
            return False

        node_count = 0
        dialogue_tree = dialogue_data.get("dialogue_tree")
        if isinstance(dialogue_tree, dict):
            node_count = len(dialogue_tree)
        logger.info(
            "[NPCInteraction] Открываем диалог: npc='%s', path='%s', nodes=%d",
            self._nearest_id,
            unit.get("dialogue_path", ""),
            node_count,
        )
        if dc:
            dc.start_dialogue(
                npc_id=self._nearest_id,
                dialogue_data=dialogue_data,
                npc_actor=unit.get("actor"),
            )
        logger.info(f"[NPCInteraction] Started dialogue with '{self._nearest_id}'")
        return True

    def get_interaction_hint(self):
        if not self._nearest_id:
            return ""
        unit = self._units.get(self._nearest_id)
        if not isinstance(unit, dict):
            return ""
        label = str(unit.get("name", self._nearest_id) or "").strip()
        if not label:
            return ""
        return f"{self._prompt_icon} {label}"

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
        if math.isnan(sx) or math.isinf(sx) or math.isnan(sy) or math.isinf(sy):
            self._hide_prompt()
            return

        if self._prompt_text:
            new_text = f"{self._prompt_icon}  {npc_name}"
            if self._prompt_text["text"] != new_text:
                self._prompt_text["text"] = new_text
                
            # For OnscreenText, setPos(x, y) maps to X and Z in Panda3D
            try:
                self._prompt_text.setPos(sx, sy)
            except Exception:
                pass
            
            if not self._prompt_visible:
                self._prompt_text.setColorScale(1, 1, 1, 1)
                self._prompt_visible = True

    def _hide_prompt(self):
        if self._prompt_visible and self._prompt_text:
            self._prompt_text.setColorScale(1, 1, 1, 0)
            self._prompt_visible = False

    def _world_to_screen(self, world_pos: Vec3):
        """Convert a 3D world position to aspect2d 2D coordinates."""
        try:
            from panda3d.core import Vec3 as P3, Point2
            cam = self.app.camera
            render = self.app.render
            if not cam or cam.isEmpty() or not render or render.isEmpty():
                return None
            
            for node in (cam, render):
                if not self._node_transform_looks_safe(node):
                    return None

            wp = P3(float(world_pos.x), float(world_pos.y), float(world_pos.z))
            if any(math.isnan(c) or math.isinf(c) for c in [wp.x, wp.y, wp.z]):
                return None

            try:
                p3d = cam.getRelativePoint(render, wp)
            except Exception:
                return None
            if any(math.isnan(c) or math.isinf(c) for c in [p3d.x, p3d.y, p3d.z]):
                return None

            # Project to 2D
            lens = self.app.cam.node().getLens()
            if not lens:
                return None
            
            p2d = Point2() # Use Point2 for 2D projection result
            if not lens.project(p3d, p2d):
                return None

            aspect = float(self.app.getAspectRatio() or 1.0)
            sx = float(p2d.x) * aspect
            sy = float(p2d.y)
            if math.isnan(sx) or math.isinf(sx) or math.isnan(sy) or math.isinf(sy):
                return None
            return sx, sy
        except Exception:
            return None

    def _load_dialogue(self, path: str) -> dict | None:
        if not path:
            return None
        base_name = os.path.basename(str(path or ""))
        candidates = [
            path,
            os.path.join(DIALOGUES_DIR, path),
            os.path.join(DIALOGUES_DIR, path + ".json"),
            os.path.join(DIALOGUES_DIR, base_name),
            os.path.join(DIALOGUES_DIR, base_name + ".json"),
            os.path.join("npc", "dialogue", path),
            os.path.join("npc", "dialogue", path + ".json"),
        ]
        payload = load_data_file_candidates(self.app, candidates, default=None)
        if isinstance(payload, dict) and payload:
            return payload
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
