"""Asset and script catalog helpers for the embedded studio shell."""

from __future__ import annotations

from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MODEL_SUFFIXES = {".glb", ".bam", ".gltf"}
SCRIPT_SUFFIXES = {".py", ".lua"}
DATA_SUFFIXES = {".json", ".toml", ".yaml", ".yml"}
AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3"}
CATALOG_SUFFIXES = IMAGE_SUFFIXES | MODEL_SUFFIXES | SCRIPT_SUFFIXES | DATA_SUFFIXES | AUDIO_SUFFIXES


def _resolve_root(root_dir, relative_root: str) -> Path:
    root = Path(root_dir).resolve()
    target = (root / str(relative_root or "")).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes root: {relative_root}")
    return target


def _relative_label(root_dir, path: Path) -> str:
    root = Path(root_dir).resolve()
    return path.resolve().relative_to(root).as_posix()


def _kind_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in MODEL_SUFFIXES:
        return "model"
    if suffix in SCRIPT_SUFFIXES:
        return "script"
    if suffix in AUDIO_SUFFIXES:
        return "audio"
    if suffix in DATA_SUFFIXES:
        return "data"
    return "file"


def _preview_hint(kind: str) -> str:
    return {
        "image": "image",
        "model": "model",
        "script": "script",
        "audio": "audio",
        "data": "data",
    }.get(kind, "file")


def build_asset_catalog(root_dir, asset_roots, *, query: str = ""):
    normalized_query = str(query or "").strip().lower()
    entries = []
    for raw_root in list(asset_roots or []):
        rel_root = str(raw_root or "").strip()
        if not rel_root:
            continue
        target_root = _resolve_root(root_dir, rel_root)
        if not target_root.exists() or not target_root.is_dir():
            continue
        for path in sorted(target_root.rglob("*"), key=lambda item: item.as_posix().lower()):
            if not path.is_file() or path.suffix.lower() not in CATALOG_SUFFIXES:
                continue
            relative_path = _relative_label(root_dir, path)
            haystack = f"{relative_path} {path.name} {rel_root}".lower()
            if normalized_query and normalized_query not in haystack:
                continue
            kind = _kind_from_suffix(path)
            entries.append(
                {
                    "label": path.name,
                    "relative_path": relative_path,
                    "kind": kind,
                    "source_root": rel_root,
                    "preview_hint": _preview_hint(kind),
                    "extension": path.suffix.lower(),
                }
            )
    return sorted(entries, key=lambda item: item["relative_path"].lower())


def build_asset_properties(root_dir, entry: dict):
    if not isinstance(entry, dict):
        return None
    relative_path = str(entry.get("relative_path") or "").strip()
    if not relative_path:
        return None
    target = _resolve_root(root_dir, relative_path)
    kind = str(entry.get("kind") or _kind_from_suffix(target))
    size = target.stat().st_size if target.exists() and target.is_file() else 0
    size_kb = f"{(size / 1024.0):.1f} KB"
    return {
        "kind": "asset",
        "title": str(entry.get("label") or target.name),
        "fields": {
            "path": relative_path,
            "type": kind,
            "source_root": str(entry.get("source_root") or ""),
            "extension": str(entry.get("extension") or target.suffix.lower()),
            "size": size_kb,
            "preview_hint": str(entry.get("preview_hint") or _preview_hint(kind)),
        },
        "cards": [
            {"title": "Asset Type", "body": kind},
            {"title": "Catalog Root", "body": str(entry.get("source_root") or "")},
            {"title": "Size", "body": size_kb},
        ],
    }
