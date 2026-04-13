"""Docking layout helpers for the embedded studio shell."""

from __future__ import annotations


ZONE_KEYS = ("left", "top", "bottom")
PANEL_KEYS = ("navigator", "catalog", "graph", "overview", "properties", "source")
DEFAULT_LAYOUT = {
    "left": ["navigator"],
    "top": ["catalog", "graph", "overview"],
    "bottom": ["properties", "source"],
}


def normalize_studio_dock_layout(payload):
    raw = dict(payload or {})
    ordered = {zone: [] for zone in ZONE_KEYS}
    seen = set()
    for zone in ZONE_KEYS:
        for item in list(raw.get(zone, []) or []):
            key = str(item or "").strip()
            if key in PANEL_KEYS and key not in seen:
                ordered[zone].append(key)
                seen.add(key)
    for panel_key, default_zone in (("navigator", "left"), ("catalog", "top"), ("graph", "top"), ("overview", "top"), ("properties", "bottom"), ("source", "bottom")):
        if panel_key not in seen:
            ordered[default_zone].append(panel_key)
            seen.add(panel_key)
    return ordered


def find_panel_zone(layout, panel_key: str):
    normalized = normalize_studio_dock_layout(layout)
    key = str(panel_key or "").strip()
    for zone in ZONE_KEYS:
        if key in normalized[zone]:
            return zone
    return None


def move_panel(layout, panel_key: str, target_zone: str, target_index: int | None = None):
    normalized = normalize_studio_dock_layout(layout)
    key = str(panel_key or "").strip()
    zone = str(target_zone or "").strip()
    if key not in PANEL_KEYS or zone not in ZONE_KEYS:
        return normalized
    source_zone = find_panel_zone(normalized, key)
    if source_zone is None:
        return normalized
    updated = {name: list(values) for name, values in normalized.items()}
    updated[source_zone] = [item for item in updated[source_zone] if item != key]
    destination = list(updated[zone])
    index = len(destination) if target_index is None else max(0, min(int(target_index), len(destination)))
    destination.insert(index, key)
    updated[zone] = destination
    return normalize_studio_dock_layout(updated)
