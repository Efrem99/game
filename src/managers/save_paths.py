"""Canonical save path helpers for different save backends."""

from pathlib import Path


_BACKEND_SAVE_EXTENSIONS = {
    "sqlite_msgpack": ".sav",
    "sqlite+msgpack": ".sav",
    "sqlite-msgpack": ".sav",
}

_SAVE_ALIAS_EXTENSIONS = (".sav", ".json", ".save")


def canonical_save_extension(backend_name):
    token = str(backend_name or "json").strip().lower()
    return _BACKEND_SAVE_EXTENSIONS.get(token, ".json")


def build_save_paths(save_dir, slot_count, backend_name):
    root = Path(save_dir)
    ext = canonical_save_extension(backend_name)
    slot_paths = {
        idx: root / f"slot{idx}{ext}"
        for idx in range(1, int(slot_count) + 1)
    }
    return {
        "autosave": root / f"autosave{ext}",
        "latest": root / f"latest{ext}",
        "slots": slot_paths,
    }


def save_path_aliases(path):
    base = Path(path)
    stem = base.stem
    parent = base.parent
    aliases = []
    for ext in _SAVE_ALIAS_EXTENSIONS:
        candidate = parent / f"{stem}{ext}"
        if candidate not in aliases:
            aliases.append(candidate)
    return aliases
