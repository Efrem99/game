"""Quest and scene graph/inspector helpers for studio overview panels."""

from __future__ import annotations

import json
from pathlib import PurePosixPath


def _parse_preview_payload(preview):
    if not isinstance(preview, dict):
        return None
    if str(preview.get("kind") or "").lower() != "json":
        return None
    raw_text = preview.get("raw_text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def _short_text(value, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."


def _parse_node_index(node_id: str, prefix: str) -> int | None:
    raw = str(node_id or "").strip()
    if not raw.startswith(prefix):
        return None
    try:
        return int(raw.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _parse_int(value, *, default: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _parse_float(value, *, default: float = 0.0) -> float:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _split_lines(value) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _scene_asset_type(entry: dict) -> str:
    relative_path = str((entry or {}).get("relative_path") or "").strip()
    stem = PurePosixPath(relative_path).stem if relative_path else str((entry or {}).get("label") or "asset")
    text = str(stem or "asset").strip().replace(" ", "_").replace("-", "_")
    return text or "asset"


def _quest_type(payload: dict, *, relative_path: str = ""):
    objectives = list(payload.get("objectives", []) or [])
    rewards = dict(payload.get("rewards") or {})
    prerequisites = list(payload.get("prerequisites", []) or [])
    nodes = [
        {
            "id": "quest",
            "header": f"Quest | {str(payload.get('title') or payload.get('id') or 'Quest')}",
            "text": _short_text(payload.get("description") or "Quest root"),
            "footer": f"{len(objectives)} objectives | {len(prerequisites)} prerequisites",
            "depth": 0,
            "lane": 0,
            "order": 0,
            "is_root": True,
            "is_terminal": False,
        }
    ]
    edges = []
    lane = 0
    order = 1
    for index, objective in enumerate(objectives):
        nodes.append(
            {
                "id": f"objective:{index}",
                "header": f"Objective {index + 1} | {str(objective.get('type') or 'objective')}",
                "text": _short_text(objective.get("description") or objective.get("target") or "Objective details"),
                "footer": f"Target {str(objective.get('target') or 'unknown')} x{int(objective.get('count', 1) or 1)}",
                "depth": 1,
                "lane": lane,
                "order": order,
                "is_root": False,
                "is_terminal": True,
            }
        )
        edges.append({"source": "quest", "target": f"objective:{index}", "kind": "objective", "label": f"Objective {index + 1}"})
        lane += 1
        order += 1
    if rewards:
        reward_parts = []
        if rewards.get("gold") is not None:
            reward_parts.append(f"{int(rewards.get('gold') or 0)} gold")
        if rewards.get("experience") is not None:
            reward_parts.append(f"{int(rewards.get('experience') or 0)} xp")
        items = list(rewards.get("items", []) or [])
        if items:
            reward_parts.append(f"{len(items)} items")
        nodes.append(
            {
                "id": "rewards",
                "header": "Rewards",
                "text": " | ".join(reward_parts) or "Reward bundle",
                "footer": "Quest completion payout",
                "depth": 2,
                "lane": 0,
                "order": order,
                "is_root": False,
                "is_terminal": True,
            }
        )
        edges.append({"source": "quest", "target": "rewards", "kind": "reward", "label": "Rewards"})
        order += 1
    if prerequisites:
        nodes.append(
            {
                "id": "prerequisites",
                "header": "Prerequisites",
                "text": _short_text(", ".join(str(item) for item in prerequisites)),
                "footer": f"{len(prerequisites)} required flags",
                "depth": 2,
                "lane": 1,
                "order": order,
                "is_root": False,
                "is_terminal": True,
            }
        )
        edges.append({"source": "quest", "target": "prerequisites", "kind": "prerequisite", "label": "Prerequisites"})
    return {
        "kind": "quest",
        "title": str(payload.get("title") or payload.get("id") or "Quest"),
        "relative_path": str(relative_path or ""),
        "root_id": "quest",
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "terminal_count": len(nodes) - 1,
        },
    }


def _scene_graph(payload: dict, *, relative_path: str = ""):
    name = str(payload.get("name") or payload.get("id") or "Scene")
    environment = dict(payload.get("environment") or {})
    nodes = [
        {
            "id": "scene",
            "header": f"Scene | {name}",
            "text": _short_text(payload.get("description") or "Scene root"),
            "footer": f"{len(list(payload.get('enemies', []) or []))} enemies | {len(list(payload.get('props', []) or []))} props",
            "depth": 0,
            "lane": 0,
            "order": 0,
            "is_root": True,
            "is_terminal": False,
        }
    ]
    edges = []
    sections = []
    if "environment" in payload:
        sections.append(
            {
                "id": "environment",
                "header": "Environment",
                "text": " | ".join(part for part in [str(environment.get("time_of_day") or "").strip(), str(environment.get("weather") or "").strip()] if part) or "Environment settings",
                "footer": "Weather and time of day",
                "depth": 1,
                "lane": 0,
                "kind": "environment",
            }
        )
    if "spawn_point" in payload:
        spawn = list(payload.get("spawn_point", []) or [])
        coords = ", ".join(str(value) for value in spawn[:3]) if spawn else "0, 0, 0"
        sections.append(
            {
                "id": "spawn_point",
                "header": "Spawn Point",
                "text": coords,
                "footer": "Entry position",
                "depth": 1,
                "lane": 1,
                "kind": "spawn",
            }
        )
    summary_groups = (
        ("npcs", "NPCs"),
        ("enemies", "Enemies"),
        ("animals", "Animals"),
        ("props", "Props"),
    )
    next_lane = 0
    for key, title in summary_groups:
        if key in payload:
            entries = list(payload.get(key, []) or [])
            types = sorted({str((item or {}).get("type") or "unknown") for item in entries if isinstance(item, dict)})
            sections.append(
                {
                    "id": key,
                    "header": title,
                    "text": ", ".join(types[:4]) if types else f"No {key}",
                    "footer": f"{len(entries)} entries",
                    "depth": 2,
                    "lane": next_lane,
                    "kind": key,
                }
            )
            next_lane += 1
    for order, section in enumerate(sections, start=1):
        nodes.append(
            {
                "id": section["id"],
                "header": section["header"],
                "text": _short_text(section["text"]),
                "footer": section["footer"],
                "depth": section["depth"],
                "lane": section["lane"],
                "order": order,
                "is_root": False,
                "is_terminal": True,
            }
        )
        edges.append({"source": "scene", "target": section["id"], "kind": section["kind"], "label": section["header"]})
    return {
        "kind": "scene",
        "title": name,
        "relative_path": str(relative_path or ""),
        "root_id": "scene",
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "terminal_count": len(nodes) - 1,
        },
    }


def build_story_graph_from_preview(preview):
    payload = _parse_preview_payload(preview)
    if not isinstance(payload, dict):
        return None
    rel_path = str(preview.get("relative_path") or "")
    if rel_path.startswith("data/quests/"):
        return _quest_type(payload, relative_path=rel_path)
    if rel_path.startswith("data/scenes/"):
        return _scene_graph(payload, relative_path=rel_path)
    return None


def build_story_focus_from_preview(preview, node_id: str | None = None):
    payload = _parse_preview_payload(preview)
    if not isinstance(payload, dict):
        return None
    rel_path = str(preview.get("relative_path") or "")
    selected = str(node_id or "").strip()
    if rel_path.startswith("data/quests/"):
        objectives = list(payload.get("objectives", []) or [])
        rewards = dict(payload.get("rewards") or {})
        prerequisites = list(payload.get("prerequisites", []) or [])
        if not selected:
            return {
                "kind": "quest",
                "fields": {
                    "title": str(payload.get("title") or ""),
                    "description": str(payload.get("description") or ""),
                },
                "cards": [
                    {"title": "Objectives", "body": f"{len(objectives)} objectives"},
                    {"title": "Reward Gold", "body": str(rewards.get("gold", 0))},
                ],
                "source_anchor": '"title":',
            }
        if selected == "quest":
            return {
                "kind": "quest",
                "fields": {
                    "title": str(payload.get("title") or ""),
                    "description": str(payload.get("description") or ""),
                },
                "cards": [
                    {"title": "Objectives", "body": f"{len(objectives)} objectives"},
                    {"title": "Prerequisites", "body": f"{len(prerequisites)} required flags"},
                ],
                "source_anchor": '"title":',
            }
        objective_index = _parse_node_index(selected, "objective:")
        if objective_index is not None and 0 <= objective_index < len(objectives):
            objective = dict(objectives[objective_index] or {})
            return {
                "kind": "quest_objective",
                "fields": {
                    "type": str(objective.get("type") or ""),
                    "target": str(objective.get("target") or ""),
                    "count": str(objective.get("count") or ""),
                    "description": str(objective.get("description") or ""),
                },
                "cards": [
                    {"title": "Objective Node", "body": f"Objective {objective_index + 1} of {len(objectives)}"},
                    {"title": "Summary", "body": _short_text(objective.get("description") or objective.get("target") or "Objective")},
                ],
                "source_anchor": str(objective.get("description") or '"objectives": ['),
            }
        if selected == "rewards":
            return {
                "kind": "quest_rewards",
                "fields": {
                    "gold": str(rewards.get("gold") or ""),
                    "experience": str(rewards.get("experience") or ""),
                    "items_text": "\n".join(str(item) for item in list(rewards.get("items", []) or [])),
                },
                "cards": [
                    {"title": "Reward Bundle", "body": f"{len(list(rewards.get('items', []) or []))} items"},
                    {"title": "Gold / XP", "body": f"{int(rewards.get('gold') or 0)} gold | {int(rewards.get('experience') or 0)} xp"},
                ],
                "source_anchor": '"rewards":',
            }
        if selected == "prerequisites":
            return {
                "kind": "quest_prerequisites",
                "fields": {
                    "prerequisites_text": "\n".join(str(item) for item in prerequisites),
                },
                "cards": [
                    {"title": "Prerequisites", "body": f"{len(prerequisites)} entries"},
                ],
                "source_anchor": '"prerequisites":',
            }
        return None
    if rel_path.startswith("data/scenes/"):
        environment = dict(payload.get("environment") or {})
        spawn = list(payload.get("spawn_point", []) or [0, 0, 0])
        if not selected:
            return {
                "kind": "scene",
                "fields": {
                    "name": str(payload.get("name") or ""),
                    "description": str(payload.get("description") or ""),
                    "time_of_day": str(environment.get("time_of_day") or ""),
                    "weather": str(environment.get("weather") or ""),
                },
                "cards": [
                    {"title": "Enemies", "body": str(len(list(payload.get("enemies", []) or [])))},
                    {"title": "Props", "body": str(len(list(payload.get("props", []) or [])))},
                ],
                "source_anchor": '"name":',
            }
        if selected == "scene":
            return {
                "kind": "scene",
                "fields": {
                    "name": str(payload.get("name") or ""),
                    "description": str(payload.get("description") or ""),
                },
                "cards": [
                    {"title": "Environment", "body": "Open the Environment node for weather and time"},
                    {"title": "Spawn Point", "body": ", ".join(str(value) for value in spawn[:3])},
                ],
                "source_anchor": '"name":',
            }
        if selected == "environment":
            return {
                "kind": "scene_environment",
                "fields": {
                    "time_of_day": str(environment.get("time_of_day") or ""),
                    "weather": str(environment.get("weather") or ""),
                },
                "cards": [
                    {"title": "Environment Node", "body": "Weather and time-of-day tuning"},
                    {"title": "Fog Enabled", "body": str(bool(dict(environment.get("fog") or {}).get("enabled")))},
                ],
                "source_anchor": '"environment":',
            }
        if selected == "spawn_point":
            x, y, z = (spawn + [0, 0, 0])[:3]
            return {
                "kind": "scene_spawn_point",
                "fields": {
                    "x": str(x),
                    "y": str(y),
                    "z": str(z),
                },
                "cards": [
                    {"title": "Spawn Point", "body": f"{x}, {y}, {z}"},
                ],
                "source_anchor": '"spawn_point":',
            }
        if selected in {"npcs", "enemies", "animals", "props"}:
            entries = list(payload.get(selected, []) or [])
            body = "\n".join(
                _short_text(
                    f"{index + 1}. {str((entry or {}).get('type') or 'unknown')} @ {str((entry or {}).get('position') or (entry or {}).get('spawn_area') or '')}"
                )
                for index, entry in enumerate(entries[:8])
            ) or "No entries"
            return {
                "kind": "scene_group",
                "fields": {},
                "cards": [
                    {"title": selected.replace("_", " ").title(), "body": body},
                    {"title": "Count", "body": str(len(entries))},
                ],
                "source_anchor": f'"{selected}":',
            }
        return None
    return None


def apply_story_focus_patch(preview, patch: dict, node_id: str | None = None):
    payload = _parse_preview_payload(preview)
    if not isinstance(payload, dict):
        return None
    rel_path = str(preview.get("relative_path") or "")
    updates = dict(patch or {})
    selected = str(node_id or "").strip()
    if rel_path.startswith("data/quests/"):
        if not selected or selected == "quest":
            if "title" in updates:
                payload["title"] = str(updates.get("title") or "")
            if "description" in updates:
                payload["description"] = str(updates.get("description") or "")
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        objective_index = _parse_node_index(selected, "objective:")
        if objective_index is not None:
            objectives = list(payload.get("objectives", []) or [])
            if 0 <= objective_index < len(objectives):
                objective = dict(objectives[objective_index] or {})
                if "type" in updates:
                    objective["type"] = str(updates.get("type") or "")
                if "target" in updates:
                    objective["target"] = str(updates.get("target") or "")
                if "count" in updates:
                    objective["count"] = _parse_int(updates.get("count"), default=0)
                if "description" in updates:
                    objective["description"] = str(updates.get("description") or "")
                objectives[objective_index] = objective
                payload["objectives"] = objectives
                return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            return None
        if selected == "rewards":
            rewards = dict(payload.get("rewards") or {})
            if "gold" in updates:
                rewards["gold"] = _parse_int(updates.get("gold"), default=0)
            if "experience" in updates:
                rewards["experience"] = _parse_int(updates.get("experience"), default=0)
            if "items_text" in updates:
                rewards["items"] = _split_lines(updates.get("items_text"))
            payload["rewards"] = rewards
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if selected == "prerequisites":
            payload["prerequisites"] = _split_lines(updates.get("prerequisites_text"))
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        return None
    if rel_path.startswith("data/scenes/"):
        if not selected:
            if "name" in updates:
                payload["name"] = str(updates.get("name") or "")
            if "description" in updates:
                payload["description"] = str(updates.get("description") or "")
            env = dict(payload.get("environment") or {})
            if "time_of_day" in updates:
                env["time_of_day"] = str(updates.get("time_of_day") or "")
            if "weather" in updates:
                env["weather"] = str(updates.get("weather") or "")
            payload["environment"] = env
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if selected == "scene":
            if "name" in updates:
                payload["name"] = str(updates.get("name") or "")
            if "description" in updates:
                payload["description"] = str(updates.get("description") or "")
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if selected == "environment":
            env = dict(payload.get("environment") or {})
            if "time_of_day" in updates:
                env["time_of_day"] = str(updates.get("time_of_day") or "")
            if "weather" in updates:
                env["weather"] = str(updates.get("weather") or "")
            payload["environment"] = env
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if selected == "spawn_point":
            payload["spawn_point"] = [
                _parse_float(updates.get("x"), default=0.0),
                _parse_float(updates.get("y"), default=0.0),
                _parse_float(updates.get("z"), default=0.0),
            ]
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        return None
    return None


def insert_scene_asset_from_preview(preview, asset_entry: dict, *, node_id: str | None = None):
    payload = _parse_preview_payload(preview)
    if not isinstance(payload, dict):
        return None
    rel_path = str(preview.get("relative_path") or "")
    if not rel_path.startswith("data/scenes/"):
        return None
    entry = dict(asset_entry or {})
    asset_path = str(entry.get("relative_path") or "").strip()
    if not asset_path:
        return None
    props = list(payload.get("props", []) or [])
    props.append(
        {
            "type": _scene_asset_type(entry),
            "asset": asset_path,
            "asset_kind": str(entry.get("kind") or "asset"),
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        }
    )
    payload["props"] = props
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
