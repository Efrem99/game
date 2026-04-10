"""Studio manifest helpers for embedded developer authoring surfaces."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_MANIFEST = {
    "studios": {
        "logic_studio": {
            "title": "Logic Studio",
            "summary": "Standalone data and behavior authoring surface for quests, dialogues, states, and progression.",
            "status": "Draft-first; edits apply to canonical content files.",
            "domains": ["quests", "dialogues", "scenes", "state-data"],
            "workspaces": [
                {"title": "Dialogues", "paths": ["data/dialogues"]},
                {"title": "Quests", "paths": ["data/quests"]},
                {"title": "Scenes", "paths": ["data/scenes"]},
            ],
        },
        "visual_studio": {
            "title": "Visual Studio",
            "summary": "Visual authoring surface for layouts, presentation, scenes, and UI-facing content.",
            "status": "Panels stay inside Dev Hub; source stays canonical.",
            "domains": ["ui", "presentation", "scenes", "world-layout"],
            "workspaces": [
                {"title": "UI Scripts", "paths": ["src/ui"]},
                {"title": "Scene Data", "paths": ["data/scenes"]},
                {"title": "World Data", "paths": ["data/world"]},
            ],
        },
    }
}


def _deep_merge(base: dict, override: dict):
    merged = dict(base)
    for key, value in dict(override or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_studio_manifest(payload):
    data = payload if isinstance(payload, dict) else {}
    manifest = _deep_merge(DEFAULT_MANIFEST, data)
    studios = dict(manifest.get("studios") or {})
    normalized = {}
    for key in ("logic_studio", "visual_studio"):
        normalized[key] = _deep_merge(DEFAULT_MANIFEST["studios"][key], studios.get(key, {}))
        normalized[key]["workspaces"] = list(normalized[key].get("workspaces") or [])
        normalized[key]["domains"] = list(normalized[key].get("domains") or [])
    manifest["studios"] = normalized
    return manifest


def load_studio_manifest(path):
    manifest_path = Path(path)
    if manifest_path.exists():
        try:
            return normalize_studio_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return normalize_studio_manifest({})


def list_studio_keys(manifest: dict):
    return list(normalize_studio_manifest(manifest).get("studios", {}).keys())


def resolve_studio_key(manifest: dict, studio_key: str):
    normalized = normalize_studio_manifest(manifest)
    key = str(studio_key or "").strip()
    if key in normalized["studios"]:
        return key
    return "logic_studio"


def get_studio_definition(manifest: dict, studio_key: str):
    normalized = normalize_studio_manifest(manifest)
    return dict(normalized["studios"][resolve_studio_key(normalized, studio_key)])
