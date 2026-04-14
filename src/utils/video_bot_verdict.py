"""Runtime verdict tracking for deterministic video bot scenarios."""

from __future__ import annotations

import json
import msgpack
import re
from pathlib import Path

from utils.video_bot_rules import evaluate_video_bot_verdict_status


_LOOSE_KEY_PATTERN = re.compile(r'([{\[,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)')
_LOOSE_VALUE_PATTERN = re.compile(r'(:\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*[,}\]])')


def _coerce_loose_rule_json(token):
    quoted_keys = _LOOSE_KEY_PATTERN.sub(r'\1"\2"\3', token)

    def _replace_value(match):
        prefix, raw_value, suffix = match.groups()
        lowered = str(raw_value or "").strip().lower()
        if lowered in {"true", "false", "null"}:
            return f"{prefix}{lowered}{suffix}"
        return f'{prefix}"{raw_value}"{suffix}'

    return _LOOSE_VALUE_PATTERN.sub(_replace_value, quoted_keys)


def parse_video_bot_rule(raw_value):
    token = str(raw_value or "").strip()
    if not token:
        return None
    try:
        payload = json.loads(token)
    except Exception:
        try:
            payload = json.loads(_coerce_loose_rule_json(token))
        except Exception:
            return None
    return payload if isinstance(payload, dict) else None


class VideoBotVerdictTracker:
    def __init__(self, verdict_path, plan_name="", success_if=None, fail_if=None):
        self.verdict_path = Path(verdict_path)
        self.success_if = success_if if isinstance(success_if, dict) else None
        self.fail_if = fail_if if isinstance(fail_if, dict) else None
        self.plan_name = str(plan_name or "").strip()
        self.reset(plan_name=self.plan_name)

    def reset(self, plan_name=""):
        self.plan_name = str(plan_name or self.plan_name or "").strip()
        self.executed_actions = set()
        self.executed_event_types = set()
        self.teleport_targets = set()
        self.visited_locations = set()
        self.triggered_rule_ids = set()
        self.player_z_min = None
        self.player_z_max = None
        self.status = "pending"
        self.reason = "no_rules"
        self.write_payload(self.status, self.reason, {})

    def note_event(self, event_row):
        if not isinstance(event_row, dict):
            return
        kind = str(event_row.get("type", "") or "").strip().lower()
        if kind:
            self.executed_event_types.add(kind)
        action = str(event_row.get("action", "") or "").strip().lower()
        if action and kind in {"tap", "hold", "ui_action", "quest_action"}:
            self.executed_actions.add(action)
        target = str(event_row.get("target", "") or "").strip().lower()
        if target and kind in {"teleport", "portal_jump"}:
            self.teleport_targets.add(target)
        rule_id = str(event_row.get("id", "") or "").strip().lower()
        if rule_id and kind == "context_rule":
            self.triggered_rule_ids.add(rule_id)

    def note_context(self, context):
        if not isinstance(context, dict):
            return
        active_location = str(context.get("active_location", "") or "").strip()
        if active_location:
            self.visited_locations.add(active_location)
        try:
            player_z = float(context.get("player_z", 0.0) or 0.0)
        except Exception:
            return
        if self.player_z_min is None or player_z < self.player_z_min:
            self.player_z_min = player_z
        if self.player_z_max is None or player_z > self.player_z_max:
            self.player_z_max = player_z

    def build_context(self, context, *, plan_completed=False, plan_cycle_count=0):
        merged = dict(context) if isinstance(context, dict) else {}
        merged["plan_completed"] = bool(plan_completed)
        merged["plan_cycle_count"] = int(plan_cycle_count or 0)
        merged["executed_actions"] = sorted(self.executed_actions)
        merged["executed_event_types"] = sorted(self.executed_event_types)
        merged["teleport_targets"] = sorted(self.teleport_targets)
        merged["visited_locations"] = sorted(self.visited_locations)
        merged["triggered_rule_ids"] = sorted(self.triggered_rule_ids)
        merged["player_z_min"] = float(self.player_z_min) if self.player_z_min is not None else float(
            merged.get("player_z", 0.0) or 0.0
        )
        merged["player_z_max"] = float(self.player_z_max) if self.player_z_max is not None else float(
            merged.get("player_z", 0.0) or 0.0
        )
        return merged

    def write_payload(self, status, reason, context):
        payload = {
            "status": str(status or "pending"),
            "reason": str(reason or ""),
            "plan_name": self.plan_name,
            "context": dict(context) if isinstance(context, dict) else {},
        }
        self.verdict_path.parent.mkdir(parents=True, exist_ok=True)
        self.verdict_path.write_bytes(
            msgpack.packb(payload, use_bin_type=True),
        )
        self.status = payload["status"]
        self.reason = payload["reason"]
        return payload

    def update(self, context, *, plan_completed=False, plan_cycle_count=0):
        merged = self.build_context(
            context,
            plan_completed=plan_completed,
            plan_cycle_count=plan_cycle_count,
        )
        status, reason = evaluate_video_bot_verdict_status(
            self.success_if,
            self.fail_if,
            merged,
        )
        self.write_payload(status, reason, merged)
        return status
