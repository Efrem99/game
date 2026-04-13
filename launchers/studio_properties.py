"""Context-aware properties payload helpers for the embedded studio shell."""

from __future__ import annotations


def _preview_fields(preview: dict):
    raw_text = str(preview.get("raw_text") or "")
    return {
        "path": str(preview.get("relative_path") or ""),
        "type": str(preview.get("kind") or "preview"),
        "editable": "yes" if preview.get("editable") else "no",
        "lines": str(len(raw_text.splitlines())) if raw_text else "0",
    }


def build_properties_payload(*, preview=None, graph_focus=None, story_focus=None, asset_properties=None):
    if asset_properties:
        return dict(asset_properties)
    if graph_focus:
        node = dict(graph_focus.get("node") or {})
        raw = dict(node.get("raw") or {})
        return {
            "kind": "graph_node",
            "title": str(graph_focus.get("node_id") or "Graph Node"),
            "fields": {
                "path": str((preview or {}).get("relative_path") or ""),
                "node_id": str(graph_focus.get("node_id") or ""),
                "speaker": str(raw.get("speaker") or ""),
                "next_node": str(raw.get("next_node") or ""),
                "choice_count": str(node.get("choice_count") or 0),
            },
            "cards": list(graph_focus.get("cards", []) or []),
        }
    if story_focus:
        fields = dict(story_focus.get("fields") or {})
        normalized_fields = {"path": str((preview or {}).get("relative_path") or ""), "selection_kind": str(story_focus.get("kind") or "story")}
        for key, value in fields.items():
            normalized_fields[key] = str(value or "")
        return {
            "kind": "story",
            "title": str(story_focus.get("kind") or "Story"),
            "fields": normalized_fields,
            "cards": list(story_focus.get("cards", []) or []),
        }
    preview = dict(preview or {})
    return {
        "kind": "preview",
        "title": str(preview.get("title") or "Selection"),
        "fields": _preview_fields(preview),
        "cards": list(preview.get("cards", []) or []),
    }
