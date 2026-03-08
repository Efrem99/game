"""Story interaction anchors for authored setpieces (e.g., dwarven cave sectors)."""

from __future__ import annotations

import math

from panda3d.core import Vec3

from utils.logger import logger

INTERACT_RADIUS = 5.4
TARGET_SCAN_RADIUS = 28.0

class StoryInteractionManager:
    def __init__(self, app):
        self.app = app
        self._anchors: dict[str, dict] = {}
        self._nearest_id: str | None = None
        self._interact_token: str = ""
        self._prompt_icon: str = "[F]"
        self._sync_interact_binding(force=True)

    def _flags_store(self):
        profile = getattr(self.app, "profile", None)
        if not isinstance(profile, dict):
            profile = {}
            self.app.profile = profile
        world_flags = profile.get("world_flags")
        if not isinstance(world_flags, dict):
            world_flags = {}
            profile["world_flags"] = world_flags
        flags = world_flags.get("story_interactions")
        if not isinstance(flags, dict):
            flags = {}
            world_flags["story_interactions"] = flags
        return flags

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

    def _sync_interact_binding(self, force=False):
        token = self._resolve_interact_binding()
        if (not force) and token == self._interact_token:
            return
        self._interact_token = token
        self._prompt_icon = self._format_prompt_icon(token)

    def _node_pos(self, node):
        if not node:
            return None
        try:
            if hasattr(node, "isEmpty") and node.isEmpty():
                return None
            return node.getPos(self.app.render)
        except Exception:
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

    def _distance(self, a, b):
        return math.sqrt(((a.x - b.x) ** 2) + ((a.y - b.y) ** 2) + ((a.z - b.z) ** 2))

    def _find_nearest(self, player_pos, radius=INTERACT_RADIUS):
        if player_pos is None:
            return None, None
        best_id = None
        best_dist = float(radius)
        for anchor_id, row in self._anchors.items():
            if not isinstance(row, dict):
                continue
            if bool(row.get("consumed", False)):
                continue
            node = row.get("node")
            pos = self._node_pos(node)
            if pos is None:
                continue
            dist = self._distance(player_pos, pos)
            if dist <= best_dist:
                best_dist = dist
                best_id = str(anchor_id)
        if not best_id:
            return None, None
        return best_id, self._anchors.get(best_id)

    def clear(self):
        self._anchors.clear()
        self._nearest_id = None

    def register_anchor(
        self,
        anchor_id,
        node,
        *,
        name="",
        hint="",
        single_use=True,
        rewards=None,
        codex_unlocks=None,
        event_name="",
        event_payload=None,
        location_name="",
    ):
        token = str(anchor_id or "").strip().lower()
        if not token or not node:
            return False
        flags = self._flags_store()
        consumed = bool(flags.get(token, False)) if bool(single_use) else False
        self._anchors[token] = {
            "id": token,
            "node": node,
            "name": str(name or token).strip(),
            "hint": str(hint or name or token).strip(),
            "single_use": bool(single_use),
            "consumed": consumed,
            "rewards": rewards if isinstance(rewards, dict) else {},
            "codex_unlocks": codex_unlocks if isinstance(codex_unlocks, list) else [],
            "event_name": str(event_name or "").strip(),
            "event_payload": event_payload if isinstance(event_payload, dict) else {},
            "location_name": str(location_name or "").strip(),
        }
        return True

    def update(self, dt):
        _ = dt
        self._sync_interact_binding(force=False)
        dialog = getattr(self.app, "dialog_cinematic", None)
        if dialog and hasattr(dialog, "is_active") and dialog.is_active():
            self._nearest_id = None
            return
        player_pos = self._player_pos()
        anchor_id, _ = self._find_nearest(player_pos, radius=INTERACT_RADIUS)
        self._nearest_id = anchor_id

    def get_anchor(self, anchor_id):
        token = str(anchor_id or "").strip().lower()
        if not token:
            return None
        row = self._anchors.get(token)
        if not isinstance(row, dict):
            return None
        if bool(row.get("consumed", False)):
            return None
        return row

    def iter_target_rows(self, max_dist=TARGET_SCAN_RADIUS):
        rows = []
        player_pos = self._player_pos()
        for anchor_id, row in self._anchors.items():
            if not isinstance(row, dict):
                continue
            if bool(row.get("consumed", False)):
                continue
            node = row.get("node")
            pos = self._node_pos(node)
            if pos is None:
                continue
            if player_pos is not None and self._distance(player_pos, pos) > float(max_dist):
                continue
            rows.append(
                {
                    "id": str(anchor_id),
                    "name": str(row.get("name", anchor_id)),
                    "node": node,
                    "codex_unlocks": list(row.get("codex_unlocks", [])),
                    "location_name": str(row.get("location_name", "") or ""),
                }
            )
        return rows

    def get_interaction_hint(self):
        if not self._nearest_id:
            return ""
        row = self._anchors.get(self._nearest_id)
        if not isinstance(row, dict):
            return ""
        if bool(row.get("consumed", False)):
            return ""
        label = str(row.get("hint", row.get("name", "")) or "").strip()
        if not label:
            return ""
        return f"{self._prompt_icon} {label}"

    def _apply_codex_unlocks(self, row):
        unlocks = row.get("codex_unlocks", [])
        if not isinstance(unlocks, list):
            return
        mark = getattr(self.app, "_codex_mark", None)
        if not callable(mark):
            return
        for unlock in unlocks:
            if not isinstance(unlock, dict):
                continue
            section = str(unlock.get("section", "") or "").strip().lower()
            token = str(unlock.get("id", "") or "").strip()
            title = str(unlock.get("title", token) or token).strip()
            details = str(unlock.get("details", "") or "").strip()
            if section and token:
                mark(section, token, title, details)

    def try_interact(self, player_pos):
        if player_pos is None:
            player_pos = self._player_pos()
        anchor_id, row = self._find_nearest(player_pos, radius=INTERACT_RADIUS)
        if not anchor_id or not isinstance(row, dict):
            return False
        if bool(row.get("consumed", False)):
            return False

        self._apply_codex_unlocks(row)
        rewards = row.get("rewards", {})
        if isinstance(rewards, dict) and rewards:
            grant_rewards = getattr(self.app, "grant_rewards", None)
            if callable(grant_rewards):
                try:
                    grant_rewards(rewards)
                except Exception as exc:
                    logger.debug(f"[StoryInteraction] Reward grant failed for '{anchor_id}': {exc}")

        event_name = str(row.get("event_name", "") or "").strip()
        if event_name:
            emit = getattr(self.app, "_emit_cutscene_event", None)
            if callable(emit):
                payload = row.get("event_payload", {})
                if not isinstance(payload, dict):
                    payload = {}
                emit(event_name, payload)

        if bool(row.get("single_use", True)):
            row["consumed"] = True
            flags = self._flags_store()
            flags[str(anchor_id)] = True
            if self._nearest_id == anchor_id:
                self._nearest_id = None

        logger.info(f"[StoryInteraction] Interacted with '{anchor_id}'")
        return True

