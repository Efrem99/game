"""Unified workspace tree helpers for the embedded studio shell."""

from __future__ import annotations

from pathlib import Path


def _resolve_path(root_dir, relative_path: str) -> Path:
    root = Path(root_dir).resolve()
    target = (root / str(relative_path or "")).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes root: {relative_path}")
    return target


def _relative_label(root_dir, path: Path) -> str:
    root = Path(root_dir).resolve()
    return path.resolve().relative_to(root).as_posix()


def _find_child(children: list[dict], label: str):
    for child in children:
        if str(child.get("label") or "") == label:
            return child
    return None


def _ensure_path(children: list[dict], parts: list[str], *, relative_path: str, kind: str):
    current_children = children
    built_parts = []
    node = None
    for index, part in enumerate(parts):
        built_parts.append(part)
        partial = "/".join(built_parts)
        is_leaf = index == len(parts) - 1
        child = _find_child(current_children, part)
        if child is None:
            child = {
                "label": part,
                "relative_path": relative_path if is_leaf else partial,
                "kind": kind if is_leaf else "directory",
                "children": [],
            }
            current_children.append(child)
        else:
            if is_leaf:
                child["relative_path"] = relative_path
                child["kind"] = kind
        node = child
        current_children = child.setdefault("children", [])
    return node


def _insert_target(root_dir, tree: list[dict], target: Path, *, parent_node: dict | None = None):
    rel_path = _relative_label(root_dir, target)
    if parent_node is None:
        parts = [part for part in rel_path.split("/") if part]
        if not parts:
            return
        node = _ensure_path(tree, parts, relative_path=rel_path, kind="directory" if target.is_dir() else "file")
    else:
        children = parent_node.setdefault("children", [])
        node = _find_child(children, target.name)
        if node is None:
            node = {
                "label": target.name,
                "relative_path": rel_path,
                "kind": "directory" if target.is_dir() else "file",
                "children": [],
            }
            children.append(node)
        else:
            node["relative_path"] = rel_path
            node["kind"] = "directory" if target.is_dir() else "file"
    if target.is_dir():
        for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            _insert_target(root_dir, tree, child, parent_node=node)


def build_workspace_tree(root_dir, workspace_paths):
    tree = []
    for raw_path in list(workspace_paths or []):
        rel_path = str(raw_path or "").strip()
        if not rel_path:
            continue
        target = _resolve_path(root_dir, rel_path)
        if not target.exists():
            continue
        _insert_target(root_dir, tree, target)
    return tree
