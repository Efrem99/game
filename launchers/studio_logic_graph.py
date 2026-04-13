"""Helpers for turning canonical logic files into studio graph payloads."""

from __future__ import annotations

import json
from collections import deque


def _short_text(value, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."


def _format_choice_line(choice: dict) -> str:
    text = str(choice.get("text") or "Choice").strip() or "Choice"
    target = str(choice.get("next_node") or "").strip()
    line = f"{text} -> {target}".rstrip()
    extras = []
    condition = str(choice.get("condition") or "").strip()
    action = str(choice.get("action") or "").strip()
    if condition:
        extras.append(f"if {condition}")
    if action:
        extras.append(f"do {action}")
    if extras:
        line = f"{line} | {' | '.join(extras)}"
    return line


def _parse_choice_lines(raw_text: str):
    choices = []
    for raw_line in str(raw_text or "").splitlines():
        line = raw_line.strip()
        if not line or "->" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        head = parts[0]
        left, right = head.split("->", 1)
        text = left.strip()
        target = right.strip()
        if not text or not target:
            continue
        choice = {"text": text, "next_node": target}
        for extra in parts[1:]:
            lower = extra.lower()
            if lower.startswith("if "):
                value = extra[3:].strip()
                if value:
                    choice["condition"] = value
            elif lower.startswith("do "):
                value = extra[3:].strip()
                if value:
                    choice["action"] = value
        choices.append(choice)
    return choices


def _iter_dialogue_targets(node_payload: dict):
    for choice in list(node_payload.get("choices", []) or []):
        target = str(choice.get("next_node") or "").strip()
        if target:
            yield {
                "target": target,
                "kind": "choice",
                "label": str(choice.get("text") or "Choice").strip() or "Choice",
                "condition": str(choice.get("condition") or "").strip(),
                "action": str(choice.get("action") or "").strip(),
            }
    next_node = str(node_payload.get("next_node") or "").strip()
    if next_node:
        yield {"target": next_node, "kind": "next", "label": "Next", "condition": "", "action": ""}


def _compute_dialogue_depths(node_ids: list[str], dialogue_tree: dict, root_id: str):
    depths = {}
    queue = deque([(root_id, 0)])
    while queue:
        node_id, depth = queue.popleft()
        if node_id in depths:
            continue
        depths[node_id] = depth
        for target in _iter_dialogue_targets(dialogue_tree.get(node_id) or {}):
            if target["target"] not in depths:
                queue.append((target["target"], depth + 1))
    next_depth = (max(depths.values()) + 1) if depths else 0
    for node_id in node_ids:
        if node_id not in depths:
            depths[node_id] = next_depth
            next_depth += 1
    return depths


def _parse_preview_payload(preview):
    if not isinstance(preview, dict):
        return None
    if str(preview.get("kind") or "").strip().lower() != "json":
        return None
    raw_text = preview.get("raw_text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def _script_node_descriptor_value(descriptor: dict, key: str, fallback: str = "") -> str:
    return str((descriptor or {}).get(key) or fallback).strip()


def build_dialogue_graph(payload: dict, *, relative_path: str = ""):
    dialogue_tree = payload.get("dialogue_tree")
    if not isinstance(dialogue_tree, dict) or not dialogue_tree:
        return None
    node_ids = [str(node_id) for node_id in dialogue_tree.keys()]
    root_id = "start" if "start" in dialogue_tree else node_ids[0]
    depths = _compute_dialogue_depths(node_ids, dialogue_tree, root_id)
    lane_by_depth = {}
    nodes = []
    edges = []
    terminal_count = 0
    for order, node_id in enumerate(node_ids):
        node_payload = dialogue_tree.get(node_id) or {}
        outgoing = list(_iter_dialogue_targets(node_payload))
        depth = depths.get(node_id, 0)
        lane = lane_by_depth.get(depth, 0)
        lane_by_depth[depth] = lane + 1
        if not outgoing:
            terminal_count += 1
        is_script_call = str(node_payload.get("node_kind") or "").strip() == "script_call"
        script_label = str(node_payload.get("script_label") or node_payload.get("script_ref") or "").strip()
        for edge in outgoing:
            edges.append(
                {
                    "source": node_id,
                    "target": edge["target"],
                    "kind": edge["kind"],
                    "label": edge["label"],
                    "condition": edge["condition"],
                    "action": edge["action"],
                }
            )
        nodes.append(
            {
                "id": node_id,
                "title": script_label or node_id.replace("_", " ").title(),
                "speaker": "Script Node" if is_script_call else str(node_payload.get("speaker") or payload.get("npc_name") or "Unknown"),
                "text": _short_text(node_payload.get("text") or (f"Call {script_label}" if script_label else "")),
                "depth": depth,
                "lane": lane,
                "order": order,
                "is_root": node_id == root_id,
                "is_terminal": not outgoing,
                "choice_count": len(list(node_payload.get("choices", []) or [])),
                "header": f"Script | {script_label}" if is_script_call and script_label else None,
                "footer": node_payload.get("script_ref") if is_script_call else None,
            }
        )
    return {
        "kind": "dialogue",
        "title": str(payload.get("npc_name") or payload.get("npc_id") or "Dialogue"),
        "relative_path": str(relative_path or ""),
        "root_id": root_id,
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "terminal_count": terminal_count,
        },
    }


def build_dialogue_focus(payload: dict, node_id: str):
    graph = build_dialogue_graph(payload)
    if not graph:
        return None
    key = str(node_id or "").strip()
    dialogue_tree = payload.get("dialogue_tree") or {}
    node_payload = dialogue_tree.get(key)
    if not isinstance(node_payload, dict):
        return None
    node = next((item for item in graph["nodes"] if item["id"] == key), None)
    if not node:
        return None
    outgoing = list(_iter_dialogue_targets(node_payload))
    transitions = [f"{edge['label']} -> {edge['target']}" for edge in outgoing]
    conditions_actions = []
    for edge in outgoing:
        if edge["condition"]:
            conditions_actions.append(f"if {edge['condition']}")
        if edge["action"]:
            conditions_actions.append(f"do {edge['action']}")
    cards = [
        {"title": "Selected Node", "body": f"{key} | {node['speaker']} | {len(outgoing)} outgoing links"},
        {"title": "Dialogue Text", "body": str(node_payload.get("text") or "(no text)")},
    ]
    if transitions:
        cards.append({"title": "Transitions", "body": "\n".join(transitions)})
    if conditions_actions:
        cards.append({"title": "Conditions / Actions", "body": "\n".join(conditions_actions)})
    if str(node_payload.get("script_ref") or "").strip():
        cards.append({"title": "Script Ref", "body": str(node_payload.get("script_ref") or "")})
    return {
        "kind": "dialogue_node",
        "node_id": key,
        "node": {**node, "choice_count": len(list(node_payload.get("choices", []) or [])), "raw": dict(node_payload)},
        "cards": cards,
        "choice_lines": "\n".join(_format_choice_line(choice) for choice in list(node_payload.get("choices", []) or [])),
        "source_anchor": f'"{key}": {{',
    }


def apply_dialogue_focus_patch(payload: dict, node_id: str, patch: dict):
    dialogue_tree = payload.get("dialogue_tree")
    if not isinstance(dialogue_tree, dict):
        return None
    key = str(node_id or "").strip()
    node_payload = dialogue_tree.get(key)
    if not isinstance(node_payload, dict):
        return None
    updates = dict(patch or {})
    if "speaker" in updates:
        node_payload["speaker"] = str(updates.get("speaker") or "").strip()
    if "text" in updates:
        node_payload["text"] = str(updates.get("text") or "")
    if "next_node" in updates:
        next_node = str(updates.get("next_node") or "").strip()
        if next_node:
            node_payload["next_node"] = next_node
        else:
            node_payload.pop("next_node", None)
    if "choices_text" in updates:
        node_payload["choices"] = _parse_choice_lines(updates.get("choices_text"))
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def create_dialogue_node(payload: dict, source_node_id: str, new_node_id: str, *, link_text: str = "Continue"):
    dialogue_tree = payload.get("dialogue_tree")
    if not isinstance(dialogue_tree, dict):
        return None
    source_key = str(source_node_id or "").strip()
    new_key = str(new_node_id or "").strip()
    if not source_key or not new_key or new_key in dialogue_tree:
        return None
    source_node = dialogue_tree.get(source_key)
    if not isinstance(source_node, dict):
        return None
    dialogue_tree[new_key] = {
        "speaker": str(source_node.get("speaker") or payload.get("npc_name") or "Narrator"),
        "text": "New dialogue node.",
        "choices": [],
    }
    choices = list(source_node.get("choices", []) or [])
    choices.append({"text": str(link_text or "Continue"), "next_node": new_key})
    source_node["choices"] = choices
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def create_script_node(payload: dict, source_node_id: str, descriptor: dict, *, new_node_id: str | None = None, link_text: str | None = None):
    dialogue_tree = payload.get("dialogue_tree")
    if not isinstance(dialogue_tree, dict):
        return None
    source_key = str(source_node_id or "").strip()
    source_node = dialogue_tree.get(source_key)
    if not isinstance(source_node, dict):
        return None
    script_ref = _script_node_descriptor_value(descriptor, "script_ref")
    if not script_ref:
        return None
    node_key = str(new_node_id or _script_node_descriptor_value(descriptor, "default_node_id") or "").strip()
    if not node_key or node_key in dialogue_tree:
        return None
    title = _script_node_descriptor_value(descriptor, "title", "Script")
    dialogue_tree[node_key] = {
        "speaker": "System",
        "text": _script_node_descriptor_value(descriptor, "default_text", f"Script Call: {title}") or f"Script Call: {title}",
        "choices": [],
        "node_kind": "script_call",
        "script_ref": script_ref,
        "script_label": title,
    }
    choices = list(source_node.get("choices", []) or [])
    choices.append(
        {
            "text": str(link_text or _script_node_descriptor_value(descriptor, "default_link_text", f"Run {title}") or f"Run {title}"),
            "next_node": node_key,
        }
    )
    source_node["choices"] = choices
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def delete_dialogue_node(payload: dict, node_id: str):
    dialogue_tree = payload.get("dialogue_tree")
    if not isinstance(dialogue_tree, dict):
        return None
    key = str(node_id or "").strip()
    if not key or key not in dialogue_tree or len(dialogue_tree) <= 1:
        return None
    dialogue_tree.pop(key, None)
    for node_payload in dialogue_tree.values():
        if not isinstance(node_payload, dict):
            continue
        if str(node_payload.get("next_node") or "").strip() == key:
            node_payload.pop("next_node", None)
        choices = []
        for choice in list(node_payload.get("choices", []) or []):
            if str(choice.get("next_node") or "").strip() != key:
                choices.append(choice)
        node_payload["choices"] = choices
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_logic_graph_from_preview(preview):
    payload = _parse_preview_payload(preview)
    if payload is None:
        return None
    return build_dialogue_graph(payload, relative_path=str(preview.get("relative_path") or ""))


def build_logic_focus_from_preview(preview, node_id: str):
    payload = _parse_preview_payload(preview)
    if payload is None:
        return None
    return build_dialogue_focus(payload, node_id)


def apply_logic_focus_patch(preview, node_id: str, patch: dict):
    payload = _parse_preview_payload(preview)
    if payload is None:
        return None
    return apply_dialogue_focus_patch(payload, node_id, patch)


def create_logic_node_from_preview(preview, source_node_id: str, new_node_id: str, *, link_text: str = "Continue"):
    payload = _parse_preview_payload(preview)
    if payload is None:
        return None
    return create_dialogue_node(payload, source_node_id, new_node_id, link_text=link_text)


def delete_logic_node_from_preview(preview, node_id: str):
    payload = _parse_preview_payload(preview)
    if payload is None:
        return None
    return delete_dialogue_node(payload, node_id)


def create_script_node_from_preview(preview, source_node_id: str, descriptor: dict, *, new_node_id: str | None = None, link_text: str | None = None):
    payload = _parse_preview_payload(preview)
    if payload is None:
        return None
    return create_script_node(payload, source_node_id, descriptor, new_node_id=new_node_id, link_text=link_text)
