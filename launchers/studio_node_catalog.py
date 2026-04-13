"""Node catalog helpers for script-backed logic nodes in the studio shell."""

from __future__ import annotations

from pathlib import PurePosixPath
import re


def _title_from_stem(stem: str) -> str:
    text = str(stem or "").replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in text.split()) or "Script"


def _slugify_node_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")
    return f"{slug or 'script'}_node"


def build_script_node_descriptor(entry: dict):
    if not isinstance(entry, dict) or str(entry.get("kind") or "") != "script":
        return None
    relative_path = str(entry.get("relative_path") or "").strip()
    if not relative_path:
        return None
    path = PurePosixPath(relative_path)
    title = _title_from_stem(path.stem)
    category = _title_from_stem(path.parent.name if path.parent.name else str(entry.get("source_root") or "scripts"))
    return {
        "id": f"script-node::{relative_path}",
        "kind": "script_node",
        "title": title,
        "summary": f"{category} script call",
        "script_ref": relative_path,
        "category": category,
        "default_node_id": _slugify_node_id(path.stem),
        "default_link_text": f"Run {title}",
        "default_text": f"Script Call: {title}",
        "source_root": str(entry.get("source_root") or ""),
    }


def build_logic_node_catalog(entries, *, query: str = ""):
    normalized_query = str(query or "").strip().lower()
    descriptors = []
    for entry in list(entries or []):
        descriptor = build_script_node_descriptor(entry)
        if not descriptor:
            continue
        haystack = " ".join(
            [
                descriptor["title"],
                descriptor["script_ref"],
                descriptor["category"],
                descriptor["summary"],
            ]
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        descriptors.append(descriptor)
    return sorted(descriptors, key=lambda item: (item["category"].lower(), item["title"].lower(), item["script_ref"].lower()))
