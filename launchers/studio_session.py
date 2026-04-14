"""Studio session payload helpers for shared shell persistence."""

from __future__ import annotations

from launchers.studio_docking import normalize_studio_dock_layout
from launchers.studio_workspace_state import normalize_workspace_paths


def build_studio_session_payload(*, studio_key: str, active_path: str, dock_layout, favorite_paths=None, recent_paths=None) -> dict:
    return {
        "studio_key": str(studio_key or "").strip(),
        "active_path": str(active_path or "").strip(),
        "dock_layout": normalize_studio_dock_layout(dock_layout),
        "favorite_paths": normalize_workspace_paths(favorite_paths),
        "recent_paths": normalize_workspace_paths(recent_paths, limit=12),
    }
