"""Studio session payload helpers for shared shell persistence."""

from __future__ import annotations

from launchers.studio_docking import normalize_studio_dock_layout


def build_studio_session_payload(*, studio_key: str, active_path: str, dock_layout) -> dict:
    return {
        "studio_key": str(studio_key or "").strip(),
        "active_path": str(active_path or "").strip(),
        "dock_layout": normalize_studio_dock_layout(dock_layout),
    }
