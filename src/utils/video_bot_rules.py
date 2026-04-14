"""Context-aware helper rules for the deterministic video bot."""

from __future__ import annotations

import math


_COMBAT_RULE_PLANS = {
    "combat_marathon",
    "arena_boss_probe",
    "combat_magic_probe",
    "anim_melee_core",
    "anim_combo_chain",
    "anim_weapon_modes",
    "anim_enemy_visibility_aggro",
    "hud_combat_feedback",
    "perf_animation_stability",
}

_MAGIC_RULE_PLANS = {
    "combat_magic_probe",
    "anim_weapon_modes",
    "showcase_extended",
    "world_story_showcase",
}


def _as_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _contains_token(source, expected):
    needle = str(expected or "").strip().lower()
    if not needle:
        return True
    if source is None:
        return False
    if isinstance(source, str):
        return needle in str(source).strip().lower()
    if isinstance(source, (list, tuple, set)):
        for item in source:
            if needle in str(item or "").strip().lower():
                return True
        return False
    return needle in str(source).strip().lower()


def _match_video_bot_condition_token(token, expected, context):
    if token == "movement_requested":
        return bool(context.get("movement_requested", False)) == bool(expected)
    if token == "is_flying":
        return bool(context.get("is_flying", False)) == bool(expected)
    if token == "in_water":
        return bool(context.get("in_water", False)) == bool(expected)
    if token == "plan_completed":
        return bool(context.get("plan_completed", False)) == bool(expected)
    if token == "stuck_for_sec_gte":
        return _as_float(context.get("stuck_for_sec", 0.0), 0.0) + 1e-6 >= _as_float(expected, 0.0)
    if token == "enemy_distance_lte":
        return _as_float(context.get("enemy_distance", math.inf), math.inf) - 1e-6 <= _as_float(expected, math.inf)
    if token == "enemy_distance_gte":
        return _as_float(context.get("enemy_distance", math.inf), math.inf) + 1e-6 >= _as_float(expected, 0.0)
    if token == "npc_distance_lte":
        return _as_float(context.get("npc_distance", math.inf), math.inf) - 1e-6 <= _as_float(expected, math.inf)
    if token == "npc_distance_gte":
        return _as_float(context.get("npc_distance", math.inf), math.inf) + 1e-6 >= _as_float(expected, 0.0)
    if token == "player_y_gte":
        return _as_float(context.get("player_y", 0.0), 0.0) + 1e-6 >= _as_float(expected, 0.0)
    if token == "player_y_lte":
        return _as_float(context.get("player_y", 0.0), 0.0) - 1e-6 <= _as_float(expected, 0.0)
    if token == "player_z_gte":
        return _as_float(context.get("player_z", 0.0), 0.0) + 1e-6 >= _as_float(expected, 0.0)
    if token == "player_z_lte":
        return _as_float(context.get("player_z", 0.0), 0.0) - 1e-6 <= _as_float(expected, 0.0)
    if token == "player_z_min_lte":
        return _as_float(context.get("player_z_min", math.inf), math.inf) - 1e-6 <= _as_float(expected, math.inf)
    if token == "player_z_min_gte":
        return _as_float(context.get("player_z_min", float("-inf")), float("-inf")) + 1e-6 >= _as_float(expected, 0.0)
    if token == "player_z_max_gte":
        return _as_float(context.get("player_z_max", float("-inf")), float("-inf")) + 1e-6 >= _as_float(expected, 0.0)
    if token == "player_z_max_lte":
        return _as_float(context.get("player_z_max", math.inf), math.inf) - 1e-6 <= _as_float(expected, math.inf)
    if token == "plan_cycle_count_gte":
        return int(_as_float(context.get("plan_cycle_count", 0), 0)) >= int(_as_float(expected, 0))
    if token == "plan_cycle_count_lte":
        return int(_as_float(context.get("plan_cycle_count", 0), 0)) <= int(_as_float(expected, 0))
    if token == "active_location_contains":
        return _contains_token(context.get("active_location", ""), expected)
    if token == "visited_location_contains":
        return _contains_token(context.get("visited_locations", []), expected)
    if token == "executed_action_contains":
        return _contains_token(context.get("executed_actions", []), expected)
    if token == "executed_event_contains":
        return _contains_token(context.get("executed_event_types", []), expected)
    if token == "teleport_target_contains":
        return _contains_token(context.get("teleport_targets", []), expected)
    if token == "triggered_rule_contains":
        return _contains_token(context.get("triggered_rule_ids", []), expected)
    return False


def match_video_bot_condition(condition, context):
    if not isinstance(context, dict):
        return False
    if condition is None:
        return False
    if isinstance(condition, list):
        return all(match_video_bot_condition(row, context) for row in condition)
    if not isinstance(condition, dict):
        return False
    if not condition:
        return True

    for key, expected in condition.items():
        token = str(key or "").strip().lower()
        if token in {"all_of", "all", "and"}:
            if not isinstance(expected, (list, tuple)):
                return False
            if not all(match_video_bot_condition(row, context) for row in expected):
                return False
            continue
        if token in {"any_of", "any", "or"}:
            if not isinstance(expected, (list, tuple)) or not expected:
                return False
            if not any(match_video_bot_condition(row, context) for row in expected):
                return False
            continue
        if token in {"not", "not_of"}:
            if match_video_bot_condition(expected, context):
                return False
            continue
        if not _match_video_bot_condition_token(token, expected, context):
            return False
    return True


def evaluate_video_bot_verdict_status(success_if, fail_if, context):
    if not isinstance(context, dict):
        return ("pending", "invalid_context")
    if isinstance(fail_if, dict) and fail_if and match_video_bot_condition(fail_if, context):
        return ("failure", "fail_if")
    if isinstance(success_if, dict) and success_if:
        if match_video_bot_condition(success_if, context):
            return ("success", "success_if")
        return ("pending", "success_if_pending")
    return ("pending", "no_rules")


def build_default_video_bot_context_rules(plan_name):
    plan = str(plan_name or "").strip().lower()
    rules = [
        {
            "type": "context_rule",
            "id": "unstick_jump",
            "when": {
                "movement_requested": True,
                "stuck_for_sec_gte": 0.85,
                "is_flying": False,
                "in_water": False,
            },
            "then": {"type": "tap", "action": "jump"},
            "cooldown_sec": 1.1,
        },
        {
            "type": "context_rule",
            "id": "unstick_strafe",
            "when": {
                "movement_requested": True,
                "stuck_for_sec_gte": 1.7,
                "is_flying": False,
                "in_water": False,
            },
            "then": {"type": "hold", "action": "right", "duration": 0.34},
            "cooldown_sec": 2.4,
        },
    ]

    if plan == "flight":
        rules.append(
            {
                "type": "context_rule",
                "id": "flight_recover_lift",
                "when": {
                    "movement_requested": True,
                    "stuck_for_sec_gte": 0.65,
                    "is_flying": True,
                },
                "then": [
                    {"type": "hold", "action": "flight_up", "duration": 0.42},
                    {"type": "hold", "action": "forward", "duration": 0.55},
                ],
                "cooldown_sec": 1.25,
            }
        )

    if plan in _COMBAT_RULE_PLANS:
        rules.extend(
            [
                {
                    "type": "context_rule",
                    "id": "enemy_close_block",
                    "when": {"enemy_distance_lte": 3.2},
                    "then": {"type": "tap", "action": "block", "duration": 0.24},
                    "cooldown_sec": 1.6,
                },
                {
                    "type": "context_rule",
                    "id": "enemy_close_attack",
                    "when": {"enemy_distance_lte": 2.2},
                    "then": {"type": "tap", "action": "attack_light"},
                    "cooldown_sec": 1.1,
                },
            ]
        )

    if plan in _MAGIC_RULE_PLANS:
        rules.append(
            {
                "type": "context_rule",
                "id": "enemy_midrange_spell",
                "when": {
                    "enemy_distance_gte": 2.4,
                    "enemy_distance_lte": 9.0,
                },
                "then": [
                    {"type": "tap", "action": "spell_1"},
                    {"type": "tap", "action": "spell_cast"},
                ],
                "cooldown_sec": 2.8,
            }
        )

    return rules


def should_trigger_video_bot_context_rule(rule, context, now_sec, last_trigger_at=None, trigger_count=0):
    if not isinstance(rule, dict):
        return False
    if not isinstance(context, dict):
        return False

    now = max(0.0, _as_float(now_sec, 0.0))
    when = rule.get("when", {})
    if not isinstance(when, dict):
        return False

    after_sec = max(0.0, _as_float(rule.get("after_sec", 0.0), 0.0))
    until_sec = max(0.0, _as_float(rule.get("until_sec", 0.0), 0.0))
    if now + 1e-6 < after_sec:
        return False
    if until_sec > 0.0 and now - 1e-6 > until_sec:
        return False

    max_triggers = int(max(0, int(rule.get("max_triggers", 0) or 0)))
    if max_triggers > 0 and int(trigger_count or 0) >= max_triggers:
        return False

    cooldown_sec = max(0.0, _as_float(rule.get("cooldown_sec", 0.0), 0.0))
    if last_trigger_at is not None:
        last = _as_float(last_trigger_at, float("-inf"))
        if math.isfinite(last) and now + 1e-6 < last + cooldown_sec:
            return False

    return match_video_bot_condition(when, context)
