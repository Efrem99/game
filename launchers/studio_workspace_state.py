"""Workspace navigator state helpers for the embedded studio shell."""

from __future__ import annotations


def normalize_workspace_paths(paths, *, limit: int | None = None) -> list[str]:
    normalized = []
    seen = set()
    for raw_path in list(paths or []):
        relative_path = str(raw_path or "").strip()
        if not relative_path or relative_path in seen:
            continue
        seen.add(relative_path)
        normalized.append(relative_path)
        if limit is not None and len(normalized) >= limit:
            break
    return normalized


def record_recent_path(paths, relative_path: str, *, limit: int = 12) -> list[str]:
    candidate = str(relative_path or "").strip()
    if not candidate:
        return normalize_workspace_paths(paths, limit=limit)
    merged = [candidate]
    merged.extend(item for item in list(paths or []) if str(item or "").strip() != candidate)
    return normalize_workspace_paths(merged, limit=limit)


def toggle_favorite_path(paths, relative_path: str) -> list[str]:
    candidate = str(relative_path or "").strip()
    favorites = normalize_workspace_paths(paths)
    if not candidate:
        return favorites
    if candidate in favorites:
        return [item for item in favorites if item != candidate]
    favorites.append(candidate)
    return favorites


def filter_workspace_tree(tree, query: str):
    needle = str(query or "").strip().lower()
    if not needle:
        return list(tree or [])
    filtered = []
    for raw_node in list(tree or []):
        node = _filter_node(raw_node, needle)
        if node is not None:
            filtered.append(node)
    return filtered


def _filter_node(node: dict, needle: str):
    label = str(node.get("label") or "").lower()
    relative_path = str(node.get("relative_path") or "").lower()
    matches = needle in label or needle in relative_path
    filtered_children = []
    for child in list(node.get("children") or []):
        filtered_child = _filter_node(child, needle)
        if filtered_child is not None:
            filtered_children.append(filtered_child)
    if matches or filtered_children:
        copied = dict(node)
        copied["children"] = filtered_children
        return copied
    return None
