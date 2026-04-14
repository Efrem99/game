"""Preview helpers for internal studio file browsing."""

from __future__ import annotations

import json
import re
from pathlib import Path


EDITABLE_SUFFIXES = {
    ".json",
    ".py",
    ".txt",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".ps1",
    ".lua",
}


def _resolve_path(root_dir, relative_path: str) -> Path:
    root = Path(root_dir).resolve()
    target = (root / str(relative_path or "")).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes root: {relative_path}")
    return target


def _relative_label(root_dir, path: Path) -> str:
    root = Path(root_dir).resolve()
    return path.resolve().relative_to(root).as_posix()


def _scalar_text(value) -> str:
    text = value.strip() if isinstance(value, str) else repr(value)
    return text if len(text) <= 120 else f"{text[:117]}..."


def _describe_json_value(value) -> str:
    if isinstance(value, dict):
        return f"object • {len(value)} keys"
    if isinstance(value, list):
        return f"list • {len(value)} items"
    return _scalar_text(value)


def _build_json_cards(payload, *, limit: int = 16):
    cards = []
    if isinstance(payload, dict):
        cards.append({"title": "Object", "body": f"{len(payload)} keys"})
        for key, value in list(payload.items())[:limit]:
            cards.append({"title": str(key), "body": _describe_json_value(value)})
        return cards
    if isinstance(payload, list):
        cards.append({"title": "List", "body": f"{len(payload)} items"})
        for idx, item in enumerate(payload[:limit]):
            cards.append({"title": f"[{idx}]", "body": _describe_json_value(item)})
        return cards
    return [{"title": "Value", "body": _scalar_text(payload)}]


def _build_python_cards(text: str):
    classes = re.findall(r"(?m)^class\s+([A-Za-z_][A-Za-z0-9_]*)", text)
    defs = re.findall(r"(?m)^(?:async\s+def|def)\s+([A-Za-z_][A-Za-z0-9_]*)", text)
    cards = [{"title": "Python Module", "body": f"{len(classes)} classes • {len(defs)} functions"}]
    for name in classes[:12]:
        cards.append({"title": f"class {name}", "body": "class definition"})
    for name in defs[:20]:
        cards.append({"title": f"def {name}", "body": "callable definition"})
    return cards


def _build_text_cards(text: str):
    lines = text.splitlines()
    cards = [{"title": "Text File", "body": f"{len(lines)} lines"}]
    for idx, line in enumerate([line.strip() for line in lines if line.strip()][:8], start=1):
        cards.append({"title": f"Line {idx}", "body": _scalar_text(line)})
    return cards


def load_preview(root_dir, relative_path: str):
    target = _resolve_path(root_dir, relative_path)
    rel_label = _relative_label(root_dir, target)

    if not target.exists():
        return {
            "kind": "missing",
            "title": target.name or rel_label,
            "relative_path": rel_label,
            "editable": False,
            "raw_text": "",
            "cards": [{"title": "Missing", "body": "Path does not exist"}],
            "children": [],
        }

    if target.is_dir():
        children = [
            {
                "label": child.name,
                "relative_path": _relative_label(root_dir, child),
                "kind": "directory" if child.is_dir() else "file",
            }
            for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        ]
        return {
            "kind": "directory",
            "title": target.name or rel_label,
            "relative_path": rel_label,
            "editable": False,
            "raw_text": "",
            "cards": [{"title": "Directory", "body": f"{len(children)} items"}],
            "children": children,
        }

    text = target.read_text(encoding="utf-8", errors="replace")
    kind = "text"
    cards = _build_text_cards(text)
    if target.suffix.lower() == ".json":
        kind = "json"
        try:
            cards = _build_json_cards(json.loads(text))
        except Exception as exc:
            cards = [{"title": "JSON Parse Error", "body": str(exc)}]
    elif target.suffix.lower() == ".py":
        kind = "python"
        cards = _build_python_cards(text)

    return {
        "kind": kind,
        "title": target.name,
        "relative_path": rel_label,
        "editable": target.suffix.lower() in EDITABLE_SUFFIXES,
        "raw_text": text,
        "cards": cards,
        "children": [],
    }


def resolve_preview_focus_path(root_dir, relative_path: str, *, max_depth: int = 8) -> str:
    current = str(relative_path or "").strip()
    depth = 0
    while current and depth < max_depth:
        preview = load_preview(root_dir, current)
        if str(preview.get("kind") or "") != "directory":
            return str(preview.get("relative_path") or current)
        children = list(preview.get("children") or [])
        if not children:
            return str(preview.get("relative_path") or current)
        current = str(children[0].get("relative_path") or current)
        depth += 1
    return current


def save_preview_text(root_dir, relative_path: str, raw_text: str) -> Path:
    target = _resolve_path(root_dir, relative_path)
    if target.is_dir():
        raise IsADirectoryError(str(target))
    target.write_text(str(raw_text), encoding="utf-8")
    return target
