"""Deterministic gameplay input plans for automated video capture runs."""

from __future__ import annotations

import json


DEFAULT_ACTION_BINDINGS = {
    "forward": "w",
    "backward": "s",
    "left": "a",
    "right": "d",
    "interact": "f",
    "jump": "space",
    "run": "shift",
    "crouch_toggle": "c",
    "crouch_hold": "lcontrol",
    "flight_toggle": "v",
    "flight_up": "space",
    "flight_down": "lcontrol",
    "attack_light": "mouse1",
    "attack_heavy": "e",
    "attack_thrust": "mouse3",
    "block": "q",
    "aim": "mouse2",
    "roll": "r",
    "dash": "z",
    "spell_1": "1",
    "spell_2": "2",
    "spell_3": "3",
    "spell_4": "4",
    "spell_cast": "mouse1",
    "target_lock": "t",
}

_PLAN_ALIASES = {
    "idle": "idle",
    "static": "idle",
    "none": "idle",
    "": "ground",
    "ground": "ground",
    "mechanics": "ground",
    "movement": "ground",
    "base": "ground",
    "default": "ground",
    "swim": "swim",
    "water": "swim",
    "pool": "swim",
    "flight": "flight",
    "air": "flight",
    "flying": "flight",
    "parkour": "parkour",
    "vault": "parkour",
    "jump_course": "parkour",
    "excursion": "excursion",
    "tour": "excursion",
    "touring": "excursion",
    "location_tour": "excursion",
    "environment_probe": "environment_visual_probe",
    "environment_visual_probe": "environment_visual_probe",
    "caves_visual_probe": "caves_visual_probe",
    "caves_visual": "caves_visual_probe",
    "cave_visual": "caves_visual_probe",
    "cave_probe": "caves_visual_probe",
    "dwarven_caves": "caves_visual_probe",
    "nature": "environment_visual_probe",
    "sky_water": "environment_visual_probe",
    "forest_water": "environment_visual_probe",
    "showcase": "showcase_extended",
    "showcase_extended": "showcase_extended",
    "showcase_marathon": "showcase_extended",
    "cinematic_showcase": "showcase_extended",
    "mixed": "mixed",
    "full": "mixed",
    "combat_marathon": "combat_marathon",
    "combat_showcase": "combat_marathon",
    "arena_boss_probe": "arena_boss_probe",
    "arena_boss": "arena_boss_probe",
    "boss_arena": "arena_boss_probe",
    "arena_combat": "arena_boss_probe",
    "boss_hp_demo": "arena_boss_probe",
    "combat_magic_probe": "combat_magic_probe",
    "combat_magic": "combat_magic_probe",
    "magic_probe": "combat_magic_probe",
    "anim_melee_core": "anim_melee_core",
    "anim_melee": "anim_melee_core",
    "melee_core": "anim_melee_core",
    "anim_combo_chain": "anim_combo_chain",
    "combo_chain": "anim_combo_chain",
    "anim_combo": "anim_combo_chain",
    "anim_weapon_modes": "anim_weapon_modes",
    "weapon_modes": "anim_weapon_modes",
    "anim_weapons": "anim_weapon_modes",
    "anim_defense_stealth": "anim_defense_stealth",
    "defense_stealth": "anim_defense_stealth",
    "shield_roll_stealth": "anim_defense_stealth",
    "anim_locomotion_transitions": "anim_locomotion_transitions",
    "locomotion_transitions": "anim_locomotion_transitions",
    "anim_locomotion": "anim_locomotion_transitions",
    "anim_enemy_visibility_aggro": "anim_enemy_visibility_aggro",
    "enemy_visibility": "anim_enemy_visibility_aggro",
    "enemy_aggro_visibility": "anim_enemy_visibility_aggro",
    "anim_camera_variation": "anim_camera_variation",
    "camera_variation": "anim_camera_variation",
    "camera_variants": "anim_camera_variation",
    "camera_context_modes": "camera_context_modes",
    "context_camera_modes": "camera_context_modes",
    "camera_combat_modes": "camera_context_modes",
    "hud_combat_feedback": "hud_combat_feedback",
    "hud_feedback": "hud_combat_feedback",
    "hud_combat": "hud_combat_feedback",
    "perf_animation_stability": "perf_animation_stability",
    "perf_animation": "perf_animation_stability",
    "animation_stability": "perf_animation_stability",
    "location_dialogue_probe": "location_dialogue_probe",
    "location_dialogue": "location_dialogue_probe",
    "all_locations_grand_tour": "all_locations_grand_tour",
    "location_grand_tour": "all_locations_grand_tour",
    "grand_location_tour": "all_locations_grand_tour",
    "all_locations": "all_locations_grand_tour",
    "grand_tour": "all_locations_grand_tour",
    "tour_dialogue": "location_dialogue_probe",
    "castle_debug": "combat_magic_probe",
    "caves_debug": "caves_visual_probe",
    "cinematic": "world_story_showcase",
    "story_showcase": "world_story_showcase",
    "world_story_showcase": "world_story_showcase",
    "ui": "ui_full",
    "menu": "ui_pause",
    "pause": "ui_pause",
    "inventory_ui": "ui_inventory",
    "inventory": "ui_inventory",
    "map": "ui_inventory",
    "ui_inventory": "ui_inventory",
    "ui_menu": "ui_pause",
    "ui_pause": "ui_pause",
    "ui_full": "ui_full",
    "dialog": "dialogue",
    "dialogue": "dialogue",
    "npc_talk": "dialogue",
    "loot": "loot_chest",
    "chest": "loot_chest",
    "loot_chest": "loot_chest",
    "stealth": "crouch_stealth",
    "crouch": "crouch_stealth",
    "crouch_stealth": "crouch_stealth",
    "stealth_climb": "stealth_climb",
    "climb_stealth": "stealth_climb",
    "storm": "storm_quake",
    "quake": "storm_quake",
    "earthquake": "storm_quake",
    "storm_quake": "storm_quake",
    "catastrophe": "quake_escape",
    "quake_escape": "quake_escape",
    "earthquake_escape": "quake_escape",
    "wallrun": "wallcrawl",
    "wallcrawl": "wallcrawl",
    "ultimate_sandbox_probe": "ultimate_sandbox_probe",
    "ultimate_sandbox": "ultimate_sandbox_probe",
    "sandbox_probe": "ultimate_sandbox_probe",
    "sandbox_colliders": "ultimate_sandbox_probe",
    "bot_nav_test": "bot_nav_test",
    "nav_test": "bot_nav_test",
}


def resolve_video_bot_plan_name(raw_name):
    token = str(raw_name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if token in _PLAN_ALIASES:
        return _PLAN_ALIASES[token]
    return "ground"


def resolve_action_binding(action, bindings):
    action_key = str(action or "").strip().lower()
    source = bindings if isinstance(bindings, dict) else {}
    token = str(source.get(action_key, "") or "").strip().lower()
    if (not token) or token == "none":
        token = str(DEFAULT_ACTION_BINDINGS.get(action_key, "") or "").strip().lower()
    if token == "none":
        return ""
    return token


def _shift_events(events, offset_sec):
    out = []
    try:
        offset = float(offset_sec)
    except Exception:
        offset = 0.0
    for row in events:
        if not isinstance(row, dict):
            continue
        clone = dict(row)
        try:
            at = float(clone.get("at", 0.0) or 0.0)
        except Exception:
            at = 0.0
        clone["at"] = round(max(0.0, at + offset), 3)
        out.append(clone)
    return out


def _normalize_event_rows(rows):
    out = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        clone = dict(row)
        try:
            at = float(clone.get("at", 0.0) or 0.0)
        except Exception:
            at = 0.0
        clone["at"] = round(max(0.0, at), 3)
        out.append(clone)
    out.sort(key=lambda row: float(row.get("at", 0.0) or 0.0))
    return out


def parse_video_bot_events_json(raw_json):
    bundle = parse_video_bot_plan_json(raw_json)
    if not isinstance(bundle, dict):
        return None
    return list(bundle.get("events", []))


def _event_duration_sec(row):
    if not isinstance(row, dict):
        return 0.0
    kind = str(row.get("type", "") or "").strip().lower()
    try:
        if kind in {"hold", "force_aggro", "set_flag"}:
            return max(0.0, float(row.get("duration", 0.0) or 0.0))
        if kind == "camera_profile":
            return max(0.0, float(row.get("hold_seconds", 0.0) or 0.0))
        if kind == "tap":
            return max(0.0, float(row.get("duration", 0.18) or 0.18))
    except Exception:
        return 0.0
    return 0.0


def _events_end_sec(rows):
    end_at = 0.0
    for row in _normalize_event_rows(rows):
        try:
            at = float(row.get("at", 0.0) or 0.0)
        except Exception:
            at = 0.0
        end_at = max(end_at, at + _event_duration_sec(row))
    return round(max(0.0, end_at), 3)


def _normalize_action_tokens(value):
    if isinstance(value, str):
        token = str(value).strip().lower()
        return [token] if token else []
    if isinstance(value, (list, tuple)):
        out = []
        for row in value:
            token = str(row or "").strip().lower()
            if token:
                out.append(token)
        return out
    return []


def _ui_inventory_tab_cursor(tab_name):
    token = str(tab_name or "").strip().lower()
    mapping = {
        "inventory": (-0.58, 0.46),
        "map": (-0.20, 0.46),
        "skills": (0.20, 0.46),
        "skill_tree": (0.20, 0.46),
        "journal": (0.58, 0.46),
    }
    x, y = mapping.get(token, (-0.58, 0.46))
    return {"x": float(x), "y": float(y), "click": True}


def _route_ui_events(ui_token, at_sec, state):
    token = str(ui_token or "").strip().lower()
    if not token:
        return ([], round(max(0.0, float(at_sec or 0.0)), 3))

    try:
        now = float(at_sec or 0.0)
    except Exception:
        now = 0.0
    events = []
    inventory_open = bool(state.get("inventory_open", False))
    pause_open = bool(state.get("pause_open", False))

    def _push(delta, payload):
        row = dict(payload)
        row["at"] = round(now + max(0.0, float(delta or 0.0)), 3)
        events.append(row)

    if token in {"inventory", "map", "skills", "skill_tree", "journal"}:
        target_tab = "skills" if token == "skill_tree" else token
        if not inventory_open:
            _push(0.0, {"type": "ui_action", "action": "open_inventory", "cursor": {"x": 0.0, "y": 0.25, "click": True}})
            now += 0.65
            inventory_open = True
            pause_open = False
        _push(0.0, {"type": "ui_action", "action": "inventory_tab", "tab": target_tab, "cursor": _ui_inventory_tab_cursor(target_tab)})
        now += 1.05
        state["inventory_open"] = True
        state["pause_open"] = False
        return (_normalize_event_rows(events), round(now, 3))

    if token in {"close_inventory", "inventory_close"}:
        if inventory_open:
            _push(0.0, {"type": "ui_action", "action": "close_inventory", "cursor": {"x": 0.0, "y": -0.66, "click": True}})
            now += 0.7
        state["inventory_open"] = False
        return (_normalize_event_rows(events), round(now, 3))

    if token in {"pause", "menu"}:
        if not pause_open:
            _push(0.0, {"type": "ui_action", "action": "open_pause", "cursor": {"x": 0.0, "y": 0.10, "click": True}})
            now += 0.75
        state["pause_open"] = True
        state["inventory_open"] = False
        return (_normalize_event_rows(events), round(now, 3))

    if token == "settings":
        if not pause_open:
            open_rows, now = _route_ui_events("pause", now, state)
            events.extend(open_rows)
        _push(0.0, {"type": "ui_action", "action": "pause_open_settings", "cursor": {"x": 0.0, "y": -0.30, "click": True}})
        now += 0.95
        state["pause_open"] = True
        state["inventory_open"] = False
        return (_normalize_event_rows(events), round(now, 3))

    if token == "load":
        if not pause_open:
            open_rows, now = _route_ui_events("pause", now, state)
            events.extend(open_rows)
        _push(0.0, {"type": "ui_action", "action": "pause_open_load", "cursor": {"x": 0.0, "y": -0.16, "click": True}})
        now += 0.95
        state["pause_open"] = True
        state["inventory_open"] = False
        return (_normalize_event_rows(events), round(now, 3))

    if token in {"resume", "close_pause"}:
        if pause_open:
            _push(0.0, {"type": "ui_action", "action": "close_pause", "cursor": {"x": 0.0, "y": 0.12, "click": True}})
            now += 0.7
        state["pause_open"] = False
        return (_normalize_event_rows(events), round(now, 3))

    return ([], round(now, 3))


def _compile_route_step(step, at_sec, ui_state):
    if not isinstance(step, dict):
        return ([], round(max(0.0, float(at_sec or 0.0)), 3))

    try:
        now = float(at_sec or 0.0)
    except Exception:
        now = 0.0
    now += max(0.0, float(step.get("wait_before", step.get("delay", 0.0)) or 0.0))
    events = []

    include_plan = str(step.get("include_plan", "") or "").strip()
    if include_plan:
        included = _shift_events(build_video_bot_events(include_plan), now)
        events.extend(included)
        now = _events_end_sec(included) + max(0.0, float(step.get("wait_after", 0.35) or 0.35))
        if include_plan in {"ui_inventory", "ui_pause", "ui_full"}:
            ui_state["inventory_open"] = False
            ui_state["pause_open"] = False
        return (_normalize_event_rows(events), round(now, 3))

    teleport_target = str(step.get("teleport", "") or step.get("target", "") or "").strip()
    if teleport_target and bool(step.get("portal", False)):
        kind = str(step.get("kind", "arcane") or "arcane").strip().lower()
        events.append({"at": round(now, 3), "type": "portal_jump", "target": teleport_target, "kind": kind})
        now += max(0.0, float(step.get("wait_after", 0.65) or 0.65))
        return (_normalize_event_rows(events), round(now, 3))
    if teleport_target and ("teleport" in step):
        events.append({"at": round(now, 3), "type": "teleport", "target": teleport_target})
        now += max(0.0, float(step.get("wait_after", 0.35) or 0.35))
        return (_normalize_event_rows(events), round(now, 3))

    if bool(step.get("transition_next", False)):
        events.append({"at": round(now, 3), "type": "transition_next"})
        now += max(0.0, float(step.get("wait_after", 0.60) or 0.60))
        return (_normalize_event_rows(events), round(now, 3))

    ui_token = step.get("ui", "")
    if ui_token:
        ui_events, now = _route_ui_events(ui_token, now, ui_state)
        events.extend(ui_events)
        return (_normalize_event_rows(events), round(now, 3))

    move_actions = _normalize_action_tokens(step.get("move"))
    if bool(step.get("run", False)) and "run" not in move_actions:
        move_actions.append("run")
    if move_actions:
        try:
            duration = max(0.0, float(step.get("duration", 0.0) or 0.0))
        except Exception:
            duration = 0.0
        if duration <= 0.0:
            duration = 1.0
        for action in move_actions:
            events.append({"at": round(now, 3), "type": "hold", "action": action, "duration": round(duration, 3)})
        now += duration + max(0.0, float(step.get("wait_after", 0.25) or 0.25))

    hold_action = str(step.get("hold", "") or "").strip().lower()
    if hold_action:
        try:
            duration = max(0.0, float(step.get("duration", 0.0) or 0.0))
        except Exception:
            duration = 0.0
        if duration <= 0.0:
            duration = 0.35
        events.append({"at": round(now, 3), "type": "hold", "action": hold_action, "duration": round(duration, 3)})
        now += duration + max(0.0, float(step.get("wait_after", 0.20) or 0.20))

    tap_action = ""
    if step.get("interact", False):
        tap_action = "interact"
    elif step.get("jump", False):
        tap_action = "jump"
    elif step.get("attack", False):
        tap_action = "attack_light"
    elif step.get("cast", False):
        tap_action = "spell_cast"
    else:
        tap_action = str(step.get("tap", "") or "").strip().lower()
    if tap_action:
        row = {"at": round(now, 3), "type": "tap", "action": tap_action}
        if "duration" in step and not move_actions and not hold_action:
            try:
                row["duration"] = max(0.0, float(step.get("duration", 0.18) or 0.18))
            except Exception:
                row["duration"] = 0.18
        events.append(row)
        now += max(0.0, float(step.get("wait_after", 0.45) or 0.45))

    sub_actions = step.get("actions")
    if isinstance(sub_actions, list):
        for sub_step in sub_actions:
            sub_events, now = _compile_route_step(sub_step, now, ui_state)
            events.extend(sub_events)

    return (_normalize_event_rows(events), round(now, 3))


def _compile_route_events(route_rows):
    ui_state = {"inventory_open": False, "pause_open": False}
    events = []
    now = 0.0
    for row in route_rows if isinstance(route_rows, list) else []:
        step_events, now = _compile_route_step(row, now, ui_state)
        events.extend(step_events)
    return _normalize_event_rows(events)


def parse_video_bot_plan_json(raw_json):
    text = str(raw_json or "").strip()
    if not text:
        return None
    payload = json.loads(text)
    if isinstance(payload, list):
        return {
            "events": _normalize_event_rows(payload),
            "context_rules": [],
            "success_if": None,
            "fail_if": None,
        }
    if not isinstance(payload, dict):
        return None

    route_rows = payload.get("route", payload.get("tour"))
    if route_rows is not None:
        events = _compile_route_events(route_rows)
    else:
        events = _normalize_event_rows(payload.get("events", []))

    context_rules = payload.get("context_rules", [])
    if isinstance(context_rules, dict):
        context_rules = [context_rules]
    if not isinstance(context_rules, list):
        context_rules = []

    success_if = payload.get("success_if")
    if not isinstance(success_if, dict):
        success_if = None
    fail_if = payload.get("fail_if")
    if not isinstance(fail_if, dict):
        fail_if = None

    return {
        "events": events,
        "context_rules": context_rules,
        "success_if": success_if,
        "fail_if": fail_if,
    }


def _ground_events():
    base = [
        {"at": 0.15, "type": "hold", "action": "forward", "duration": 2.4},
        {"at": 0.35, "type": "hold", "action": "run", "duration": 1.7},
        {"at": 2.45, "type": "tap", "action": "jump"},
        {"at": 3.10, "type": "hold", "action": "left", "duration": 1.1},
        {"at": 4.65, "type": "tap", "action": "crouch_toggle"},
        {"at": 5.55, "type": "tap", "action": "crouch_toggle"},
        {"at": 6.25, "type": "tap", "action": "attack_light"},
        {"at": 6.95, "type": "tap", "action": "attack_heavy"},
        {"at": 7.65, "type": "tap", "action": "spell_1"},
        {"at": 8.05, "type": "tap", "action": "attack_light"},
        {"at": 8.85, "type": "hold", "action": "backward", "duration": 1.1},
        {"at": 10.20, "type": "hold", "action": "right", "duration": 0.9},
        {"at": 11.55, "type": "tap", "action": "attack_light"},
        {"at": 12.25, "type": "tap", "action": "spell_2"},
        {"at": 12.65, "type": "tap", "action": "attack_light"},
        {"at": 13.40, "type": "tap", "action": "jump"},
    ]
    return base + _shift_events(base, 15.0)


def _swim_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "training_pool"},
        {"at": 0.06, "type": "set_flag", "flag": "in_water", "value": True, "duration": 7.8},
        {"at": 0.20, "type": "hold", "action": "forward", "duration": 2.8},
        {"at": 0.35, "type": "hold", "action": "run", "duration": 1.8},
        {"at": 1.95, "type": "tap", "action": "jump"},
        {"at": 3.55, "type": "hold", "action": "right", "duration": 1.1},
        {"at": 4.85, "type": "tap", "action": "attack_light"},
        {"at": 5.50, "type": "tap", "action": "spell_1"},
        {"at": 5.90, "type": "tap", "action": "attack_light"},
        {"at": 6.70, "type": "tap", "action": "crouch_toggle"},
        {"at": 7.45, "type": "tap", "action": "crouch_toggle"},
        {"at": 8.10, "type": "set_flag", "flag": "in_water", "value": False},
        {"at": 8.30, "type": "hold", "action": "forward", "duration": 1.9},
        {"at": 10.45, "type": "tap", "action": "jump"},
        {"at": 11.20, "type": "tap", "action": "attack_heavy"},
        {"at": 12.00, "type": "tap", "action": "spell_2"},
        {"at": 12.40, "type": "tap", "action": "attack_light"},
    ]
    return base + _shift_events(base, 13.8)


def _flight_events():
    base = [
        {"at": 0.05, "type": "set_flag", "flag": "is_flying", "value": True, "duration": 11.8},
        {"at": 0.20, "type": "hold", "action": "forward", "duration": 2.9},
        {"at": 0.35, "type": "hold", "action": "run", "duration": 1.9},
        {"at": 0.85, "type": "hold", "action": "flight_up", "duration": 1.4},
        {"at": 1.35, "type": "tap", "action": "dash"},
        {"at": 2.40, "type": "hold", "action": "right", "duration": 1.3},
        {"at": 3.95, "type": "hold", "action": "flight_down", "duration": 1.1},
        {"at": 4.45, "type": "tap", "action": "dash"},
        {"at": 5.20, "type": "tap", "action": "attack_light"},
        {"at": 5.95, "type": "tap", "action": "spell_1"},
        {"at": 6.30, "type": "tap", "action": "attack_light"},
        {"at": 7.05, "type": "tap", "action": "attack_heavy"},
        {"at": 8.00, "type": "hold", "action": "left", "duration": 1.0},
        {"at": 8.55, "type": "tap", "action": "dash"},
        {"at": 9.10, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 10.00, "type": "tap", "action": "spell_2"},
        {"at": 10.35, "type": "tap", "action": "attack_light"},
        {"at": 11.20, "type": "set_flag", "flag": "is_flying", "value": False},
        {"at": 12.35, "type": "tap", "action": "crouch_toggle"},
        {"at": 13.15, "type": "tap", "action": "crouch_toggle"},
    ]
    return base + _shift_events(base, 14.5)


def _parkour_events():
    base = [
        {"at": 0.15, "type": "hold", "action": "forward", "duration": 3.4},
        {"at": 0.25, "type": "hold", "action": "run", "duration": 3.0},
        {"at": 1.05, "type": "tap", "action": "jump"},
        {"at": 2.05, "type": "tap", "action": "jump"},
        {"at": 2.90, "type": "hold", "action": "right", "duration": 1.1},
        {"at": 4.35, "type": "hold", "action": "forward", "duration": 2.4},
        {"at": 4.55, "type": "hold", "action": "run", "duration": 2.0},
        {"at": 5.25, "type": "tap", "action": "jump"},
        {"at": 6.30, "type": "tap", "action": "jump"},
        {"at": 7.25, "type": "hold", "action": "left", "duration": 1.2},
        {"at": 8.70, "type": "tap", "action": "crouch_toggle"},
        {"at": 9.40, "type": "tap", "action": "crouch_toggle"},
        {"at": 10.05, "type": "tap", "action": "attack_light"},
        {"at": 10.70, "type": "tap", "action": "attack_heavy"},
        {"at": 11.45, "type": "tap", "action": "spell_1"},
        {"at": 11.90, "type": "tap", "action": "attack_light"},
        {"at": 12.60, "type": "hold", "action": "backward", "duration": 1.0},
        {"at": 13.85, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 14.00, "type": "hold", "action": "run", "duration": 1.4},
        {"at": 14.80, "type": "tap", "action": "jump"},
    ]
    return base + _shift_events(base, 16.0)


def _excursion_events():
    return [
        {"at": 0.00, "type": "teleport", "target": "town"},
        {"at": 0.25, "type": "hold", "action": "forward", "duration": 2.2},
        {"at": 0.45, "type": "hold", "action": "run", "duration": 1.7},
        {"at": 1.80, "type": "tap", "action": "jump"},
        {"at": 2.60, "type": "tap", "action": "attack_light"},
        {"at": 3.25, "type": "tap", "action": "spell_1"},
        {"at": 3.60, "type": "tap", "action": "attack_light"},
        {"at": 5.20, "type": "transition_next"},
        {"at": 7.20, "type": "teleport", "target": "castle"},
        {"at": 7.50, "type": "hold", "action": "forward", "duration": 2.3},
        {"at": 8.35, "type": "tap", "action": "jump"},
        {"at": 9.15, "type": "tap", "action": "attack_heavy"},
        {"at": 10.00, "type": "tap", "action": "crouch_toggle"},
        {"at": 10.75, "type": "tap", "action": "crouch_toggle"},
        {"at": 12.30, "type": "teleport", "target": "docks"},
        {"at": 12.55, "type": "hold", "action": "forward", "duration": 2.4},
        {"at": 13.50, "type": "tap", "action": "spell_2"},
        {"at": 13.90, "type": "tap", "action": "attack_light"},
        {"at": 15.80, "type": "transition_next"},
        {"at": 17.90, "type": "teleport", "target": "parkour"},
        {"at": 18.20, "type": "hold", "action": "forward", "duration": 2.6},
        {"at": 18.30, "type": "hold", "action": "run", "duration": 2.1},
        {"at": 18.95, "type": "tap", "action": "jump"},
        {"at": 19.85, "type": "tap", "action": "jump"},
        {"at": 21.90, "type": "teleport", "target": "training_pool"},
        {"at": 22.00, "type": "set_flag", "flag": "in_water", "value": True, "duration": 5.6},
        {"at": 22.15, "type": "hold", "action": "forward", "duration": 2.3},
        {"at": 22.95, "type": "tap", "action": "jump"},
        {"at": 24.05, "type": "tap", "action": "attack_light"},
        {"at": 25.70, "type": "teleport", "target": "flight"},
        {"at": 25.90, "type": "set_flag", "flag": "is_flying", "value": True, "duration": 7.2},
        {"at": 26.00, "type": "hold", "action": "forward", "duration": 2.4},
        {"at": 26.10, "type": "hold", "action": "run", "duration": 1.7},
        {"at": 26.70, "type": "hold", "action": "flight_up", "duration": 1.5},
        {"at": 28.60, "type": "hold", "action": "flight_down", "duration": 1.0},
        {"at": 29.80, "type": "tap", "action": "spell_1"},
        {"at": 30.20, "type": "tap", "action": "attack_light"},
        {"at": 31.40, "type": "transition_next"},
    ]


def _environment_visual_probe_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "kremor_forest"},
        {"at": 0.06, "type": "set_time", "preset": "morning"},
        {"at": 0.12, "type": "set_weather", "preset": "clear"},
        {"at": 0.18, "type": "camera_profile", "profile": "shoulder_right", "hold_seconds": 3.4},
        {"at": 0.82, "type": "camera_sequence", "name": "portal_arrival", "priority": 78},
        {"at": 0.28, "type": "hold", "action": "forward", "duration": 1.0},
        {"at": 2.30, "type": "set_weather", "preset": "overcast"},
        {"at": 2.52, "type": "camera_shot", "name": "forest_canopy", "profile": "exploration", "duration": 1.00, "side": 1.7, "yaw_bias_deg": -12},
        {"at": 4.10, "type": "teleport", "target": "kremor_forest_cage"},
        {"at": 4.18, "type": "set_time", "preset": "noon"},
        {"at": 4.28, "type": "camera_profile", "profile": "exploration", "hold_seconds": 3.0},
        {"at": 4.94, "type": "camera_shot", "name": "forest_ruins", "profile": "exploration", "duration": 1.05, "side": 2.0, "yaw_bias_deg": 14},
        {"at": 4.40, "type": "hold", "action": "forward", "duration": 0.8},
        {"at": 6.60, "type": "set_weather", "preset": "rainy"},
        {"at": 6.84, "type": "camera_shot", "name": "forest_rain", "profile": "exploration", "duration": 1.15, "side": -1.5, "yaw_bias_deg": 8},
        {"at": 8.50, "type": "teleport", "target": "kremor_forest"},
        {"at": 8.58, "type": "set_time", "preset": "dusk"},
        {"at": 8.68, "type": "camera_profile", "profile": "exploration", "hold_seconds": 3.1},
        {"at": 9.36, "type": "camera_shot", "name": "forest_dusk", "profile": "exploration", "duration": 1.10, "side": 1.6, "yaw_bias_deg": -9},
        {"at": 9.52, "type": "hold", "action": "left", "duration": 0.6},
        {"at": 11.25, "type": "set_weather", "preset": "clear"},
        {"at": 11.55, "type": "camera_shot", "name": "forest_clear_reset", "profile": "exploration", "duration": 0.96, "side": -1.3, "yaw_bias_deg": 6},
        {"at": 12.60, "type": "hold", "action": "forward", "duration": 0.8},
        # docks — water/harbour environment visual check
        {"at": 13.80, "type": "teleport", "target": "docks"},
        {"at": 13.88, "type": "set_time", "preset": "dusk"},
        {"at": 13.96, "type": "set_weather", "preset": "overcast"},
        {"at": 14.10, "type": "camera_profile", "profile": "shoulder_left", "hold_seconds": 3.0},
        {"at": 14.76, "type": "camera_shot", "name": "docks_dusk", "profile": "exploration", "duration": 1.05, "side": 1.8, "yaw_bias_deg": -10},
        {"at": 14.20, "type": "hold", "action": "forward", "duration": 1.0},
        {"at": 16.30, "type": "set_weather", "preset": "rainy"},
        {"at": 16.54, "type": "camera_shot", "name": "docks_rain", "profile": "exploration", "duration": 0.95, "side": -1.4, "yaw_bias_deg": 12},
        # training_pool — water surface / in-water visual check
        {"at": 18.00, "type": "teleport", "target": "training_pool"},
        {"at": 18.06, "type": "set_time", "preset": "noon"},
        {"at": 18.14, "type": "set_weather", "preset": "clear"},
        {"at": 18.20, "type": "set_flag", "flag": "in_water", "value": True, "duration": 5.0},
        {"at": 18.30, "type": "camera_profile", "profile": "exploration", "hold_seconds": 2.8},
        {"at": 18.96, "type": "camera_shot", "name": "pool_surface", "profile": "exploration", "duration": 1.00, "side": 1.2, "yaw_bias_deg": 6},
        {"at": 18.40, "type": "hold", "action": "forward", "duration": 1.4},
        {"at": 20.10, "type": "tap", "action": "jump"},
        {"at": 21.00, "type": "set_flag", "flag": "in_water", "value": False},
        {"at": 21.50, "type": "set_weather", "preset": "clear"},
    ]
    return (
        base
        + _shift_events(base, 23.0)
        + _shift_events(base, 46.0)
        + _shift_events(base, 69.0)
    )


def _caves_visual_probe_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "dwarven_caves_gate"},
        {"at": 0.06, "type": "set_time", "preset": "noon"},
        {"at": 0.12, "type": "set_weather", "preset": "clear"},
        {"at": 0.18, "type": "camera_profile", "profile": "exploration", "hold_seconds": 3.4},
        {"at": 0.86, "type": "camera_shot", "name": "shot", "profile": "exploration", "duration": 0.95, "side": -2.4, "yaw_bias_deg": 18},
        {"at": 0.24, "type": "hold", "action": "forward", "duration": 2.4},
        {"at": 0.38, "type": "hold", "action": "run", "duration": 1.6},
        {"at": 1.95, "type": "hold", "action": "right", "duration": 1.2},
        {"at": 3.35, "type": "tap", "action": "jump"},
        {"at": 4.00, "type": "teleport", "target": "dwarven_caves_halls"},
        {"at": 4.08, "type": "camera_profile", "profile": "combat", "hold_seconds": 3.8},
        {"at": 4.76, "type": "camera_shot", "name": "shot", "profile": "combat", "duration": 1.05, "side": 1.9, "yaw_bias_deg": -20},
        {"at": 4.20, "type": "hold", "action": "forward", "duration": 2.6},
        {"at": 4.34, "type": "hold", "action": "run", "duration": 1.7},
        {"at": 6.70, "type": "hold", "action": "left", "duration": 1.1},
        {"at": 8.05, "type": "tap", "action": "jump"},
        {"at": 8.55, "type": "camera_impact", "kind": "heavy", "intensity": 0.36, "direction_deg": 14},
        {"at": 9.10, "type": "teleport", "target": "dwarven_caves_throne"},
        {"at": 9.22, "type": "camera_profile", "profile": "boss", "hold_seconds": 3.9},
        {"at": 9.98, "type": "camera_shot", "name": "boss_intro", "profile": "boss", "duration": 1.22, "side": 5.0, "yaw_bias_deg": 16},
        {"at": 9.26, "type": "hold", "action": "forward", "duration": 2.8},
        {"at": 9.40, "type": "hold", "action": "run", "duration": 1.8},
        {"at": 11.95, "type": "hold", "action": "right", "duration": 1.3},
        {"at": 13.45, "type": "tap", "action": "jump"},
        {"at": 13.95, "type": "tap", "action": "crouch_toggle"},
        {"at": 14.50, "type": "tap", "action": "crouch_toggle"},
        {"at": 15.00, "type": "teleport", "target": "dwarven_caves_halls"},
        {"at": 15.12, "type": "camera_profile", "profile": "exploration", "hold_seconds": 3.2},
        {"at": 15.86, "type": "camera_shot", "name": "shot", "profile": "exploration", "duration": 0.96, "side": -1.8, "yaw_bias_deg": 26},
        {"at": 15.16, "type": "hold", "action": "forward", "duration": 2.3},
        {"at": 15.32, "type": "hold", "action": "run", "duration": 1.5},
        {"at": 17.65, "type": "hold", "action": "left", "duration": 1.2},
        {"at": 19.00, "type": "tap", "action": "jump"},
        {"at": 19.58, "type": "camera_impact", "kind": "heavy", "intensity": 0.40, "direction_deg": -20},
        {"at": 20.20, "type": "teleport", "target": "dwarven_caves_gate"},
        {"at": 20.32, "type": "camera_profile", "profile": "exploration", "hold_seconds": 2.8},
        {"at": 20.98, "type": "camera_shot", "name": "shot", "profile": "exploration", "duration": 0.90, "side": 2.1, "yaw_bias_deg": -18},
        {"at": 20.35, "type": "hold", "action": "forward", "duration": 2.2},
        {"at": 20.48, "type": "hold", "action": "run", "duration": 1.4},
        {"at": 22.65, "type": "hold", "action": "right", "duration": 1.0},
        {"at": 23.80, "type": "tap", "action": "jump"},
    ]
    return base + _shift_events(base, 26.0)


def _ui_inventory_events():
    return [
        {"at": 0.20, "type": "hold", "action": "forward", "duration": 1.7},
        {"at": 0.30, "type": "hold", "action": "run", "duration": 1.2},
        {"at": 2.20, "type": "ui_action", "action": "open_inventory", "cursor": {"x": 0.0, "y": 0.25, "click": True}},
        {"at": 2.80, "type": "ui_action", "action": "inventory_tab", "tab": "inventory", "cursor": {"x": -0.58, "y": 0.46, "click": True}},
        {"at": 4.20, "type": "ui_action", "action": "inventory_tab", "tab": "map", "cursor": {"x": -0.20, "y": 0.46, "click": True}},
        {"at": 5.80, "type": "ui_action", "action": "inventory_tab", "tab": "skills", "cursor": {"x": 0.20, "y": 0.46, "click": True}},
        {"at": 7.40, "type": "ui_action", "action": "inventory_tab", "tab": "journal", "cursor": {"x": 0.58, "y": 0.46, "click": True}},
        {"at": 9.20, "type": "ui_action", "action": "inventory_tab", "tab": "map", "cursor": {"x": -0.20, "y": 0.46, "click": True}},
        {"at": 10.80, "type": "ui_action", "action": "close_inventory", "cursor": {"x": 0.0, "y": -0.66, "click": True}},
        {"at": 11.35, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 11.55, "type": "hold", "action": "run", "duration": 1.3},
        {"at": 13.20, "type": "tap", "action": "jump"},
        {"at": 14.00, "type": "tap", "action": "attack_light"},
    ]


def _ui_pause_events():
    return [
        {"at": 0.15, "type": "hold", "action": "forward", "duration": 1.6},
        {"at": 0.25, "type": "hold", "action": "run", "duration": 1.0},
        {"at": 2.10, "type": "ui_action", "action": "open_pause", "cursor": {"x": 0.0, "y": 0.10, "click": True}},
        {"at": 2.90, "type": "ui_action", "action": "pause_open_settings", "cursor": {"x": 0.0, "y": -0.30, "click": True}},
        {"at": 4.10, "type": "ui_action", "action": "pause_toggle_quality", "cursor": {"x": 0.18, "y": 0.08, "click": True}},
        {"at": 5.20, "type": "ui_action", "action": "pause_toggle_vsync", "cursor": {"x": 0.18, "y": -0.02, "click": True}},
        {"at": 6.30, "type": "ui_action", "action": "pause_close_settings", "cursor": {"x": 0.0, "y": -0.56, "click": True}},
        {"at": 7.10, "type": "ui_action", "action": "pause_open_load", "cursor": {"x": 0.0, "y": -0.16, "click": True}},
        {"at": 8.70, "type": "ui_action", "action": "pause_close_load", "cursor": {"x": 0.0, "y": -0.56, "click": True}},
        {"at": 9.40, "type": "ui_action", "action": "close_pause", "cursor": {"x": 0.0, "y": 0.12, "click": True}},
        {"at": 9.90, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 10.10, "type": "hold", "action": "run", "duration": 1.2},
        {"at": 11.70, "type": "tap", "action": "jump"},
        {"at": 12.35, "type": "tap", "action": "spell_1"},
        {"at": 12.70, "type": "tap", "action": "attack_light"},
    ]


def _ui_full_events():
    return (
        _shift_events(_ui_inventory_events(), 0.0)
        + _shift_events(_ui_pause_events(), 15.0)
        + _shift_events(_ground_events(), 29.0)
    )


def _dialogue_stop_events(
    start_at,
    location_target,
    *,
    move_to=None,
    profile="exploration",
    shot_name="dialogue_focus",
    shot_duration=1.05,
    side=1.0,
    yaw_bias_deg=8.0,
    hold_seconds=2.4,
    interact_offsets=(),
    close_offsets=(),
):
    target = str(location_target or "").strip()
    if not target:
        return []
    try:
        start = float(start_at or 0.0)
    except Exception:
        start = 0.0
    events = [
        {"at": round(start, 3), "type": "teleport", "target": target},
        {
            "at": round(start + 0.12, 3),
            "type": "camera_profile",
            "profile": str(profile or "exploration"),
            "hold_seconds": round(max(0.0, float(hold_seconds or 0.0)), 3),
        },
    ]
    if isinstance(move_to, (list, tuple)) and len(move_to) >= 3:
        try:
            events.append(
                {
                    "at": round(start + 0.18, 3),
                    "type": "teleport",
                    "target": f"{float(move_to[0]):.2f},{float(move_to[1]):.2f},{float(move_to[2]):.2f}",
                }
            )
        except Exception:
            pass
    if shot_name:
        events.append(
            {
                "at": round(start + 1.55, 3),
                "type": "camera_shot",
                "name": str(shot_name),
                "profile": str(profile or "exploration"),
                "duration": round(max(0.0, float(shot_duration or 0.0)), 3),
                "side": float(side),
                "yaw_bias_deg": float(yaw_bias_deg),
            }
        )
    for offset in interact_offsets:
        try:
            at = start + float(offset)
        except Exception:
            continue
        events.append({"at": round(max(0.0, at), 3), "type": "tap", "action": "interact", "duration": 0.22})
    for offset in close_offsets:
        try:
            at = start + float(offset)
        except Exception:
            continue
        events.append(
            {
                "at": round(max(0.0, at), 3),
                "type": "ui_action",
                "action": "close_dialogue",
            }
        )
    return _normalize_event_rows(events)


def _dialogue_probe_events(
    location_target="castle_interior",
    move_to=(4.6, 43.2, 0.0),
    profile="shoulder_right",
    shot_name="dialogue_castle_miner",
    interact_offsets=(3.10, 4.55, 6.00, 7.45, 8.95, 9.35),
):
    return _dialogue_stop_events(
        0.0,
        location_target,
        move_to=move_to,
        profile=profile,
        shot_name=shot_name,
        shot_duration=1.18,
        side=0.96,
        yaw_bias_deg=8.0,
        hold_seconds=3.0,
        interact_offsets=interact_offsets,
    )


def _dialogue_events():
    return _dialogue_probe_events()


def _bot_nav_test_events():
    """Test plan for coordinate-based navigation and debug overlay."""
    return [
        {"at": 0.00, "type": "teleport", "target": "town"},
        {"at": 0.50, "type": "move_to", "x": 10.0, "y": 0.0, "z": 0.0},
        {"at": 5.00, "type": "move_to", "x": 0.0, "y": 10.0, "z": 0.0},
        {"at": 10.00, "type": "ui_action", "action": "open_inventory", "cursor": {"x": 0.0, "y": 0.0, "click": True}},
        {"at": 12.00, "type": "ui_action", "action": "close_inventory", "cursor": {"x": 0.0, "y": 0.0, "click": True}},
        {"at": 14.00, "type": "move_to", "x": -5.0, "y": -5.0, "z": 0.0},
    ]


def _loot_chest_events():
    return [
        {"at": 0.00, "type": "teleport", "target": "training"},
        {"at": 0.20, "type": "hold", "action": "forward", "duration": 2.0},
        {"at": 2.35, "type": "tap", "action": "interact", "duration": 0.22},
        {"at": 3.15, "type": "tap", "action": "interact", "duration": 0.22},
        {"at": 3.95, "type": "tap", "action": "attack_light"},
        {"at": 4.70, "type": "hold", "action": "right", "duration": 1.2},
        {"at": 6.05, "type": "tap", "action": "interact", "duration": 0.20},
        {"at": 6.95, "type": "tap", "action": "spell_1"},
        {"at": 7.30, "type": "tap", "action": "attack_light"},
        {"at": 8.20, "type": "transition_next"},
    ]


def _crouch_stealth_events():
    return [
        {"at": 0.00, "type": "teleport", "target": "town"},
        {"at": 0.05, "type": "equip_item", "item_id": "training_shield"},
        {"at": 0.10, "type": "equip_item", "item_id": "rune_charm"},
        {"at": 0.12, "type": "force_aggro", "duration": 7.0, "teleport_to_enemy": True},
        {"at": 0.15, "type": "tap", "action": "crouch_toggle"},
        {"at": 0.30, "type": "hold", "action": "forward", "duration": 2.3},
        {"at": 2.85, "type": "hold", "action": "right", "duration": 1.4},
        {"at": 4.45, "type": "hold", "action": "forward", "duration": 1.7},
        {"at": 6.40, "type": "tap", "action": "interact", "duration": 0.20},
        {"at": 6.72, "type": "tap", "action": "spell_1"},
        {"at": 6.98, "type": "tap", "action": "spell_cast"},
        {"at": 7.15, "type": "tap", "action": "crouch_toggle"},
        {"at": 7.35, "type": "hold", "action": "run", "duration": 1.4},
        {"at": 7.40, "type": "hold", "action": "forward", "duration": 1.9},
        {"at": 8.25, "type": "tap", "action": "block", "duration": 0.32},
        {"at": 8.64, "type": "tap", "action": "attack_light"},
        {"at": 9.55, "type": "tap", "action": "jump"},
    ]


def _stealth_climb_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "stealth_climb"},
        {"at": 0.05, "type": "equip_item", "item_id": "chainmail_armor"},
        {"at": 0.10, "type": "equip_item", "item_id": "training_shield"},
        {"at": 0.15, "type": "equip_item", "item_id": "rune_charm"},
        {"at": 0.16, "type": "force_aggro", "duration": 7.8, "teleport_to_enemy": True},
        {"at": 0.18, "type": "tap", "action": "crouch_toggle"},
        {"at": 0.32, "type": "hold", "action": "forward", "duration": 1.9},
        {"at": 2.45, "type": "hold", "action": "right", "duration": 1.1},
        {"at": 3.85, "type": "tap", "action": "jump"},
        {"at": 4.40, "type": "hold", "action": "forward", "duration": 2.2},
        {"at": 4.52, "type": "hold", "action": "run", "duration": 1.3},
        {"at": 5.35, "type": "tap", "action": "jump"},
        {"at": 6.85, "type": "tap", "action": "interact", "duration": 0.20},
        {"at": 7.50, "type": "tap", "action": "crouch_toggle"},
        {"at": 7.70, "type": "hold", "action": "left", "duration": 1.2},
        {"at": 9.00, "type": "tap", "action": "jump"},
        {"at": 9.35, "type": "tap", "action": "spell_2"},
        {"at": 9.62, "type": "tap", "action": "spell_cast"},
        {"at": 10.05, "type": "tap", "action": "block", "duration": 0.34},
        {"at": 10.45, "type": "tap", "action": "attack_heavy"},
        {"at": 9.70, "type": "hold", "action": "forward", "duration": 1.7},
        {"at": 11.60, "type": "tap", "action": "crouch_toggle"},
        {"at": 11.90, "type": "tap", "action": "spell_3"},
        {"at": 12.18, "type": "tap", "action": "spell_cast"},
    ]
    return base + _shift_events(base, 13.4)


def _storm_quake_events():
    return [
        {"at": 0.00, "type": "teleport", "target": "docks"},
        {"at": 0.10, "type": "set_time", "preset": "dusk"},
        {"at": 0.18, "type": "set_weather", "preset": "stormy"},
        {"at": 0.35, "type": "hold", "action": "forward", "duration": 2.0},
        {"at": 0.45, "type": "hold", "action": "run", "duration": 1.4},
        {"at": 2.65, "type": "camera_impact", "kind": "heavy", "intensity": 1.2, "direction_deg": 0},
        {"at": 3.05, "type": "camera_impact", "kind": "heavy", "intensity": 1.0, "direction_deg": 110},
        {"at": 3.45, "type": "camera_impact", "kind": "heavy", "intensity": 1.1, "direction_deg": -95},
        {"at": 4.10, "type": "tap", "action": "crouch_toggle"},
        {"at": 4.40, "type": "hold", "action": "left", "duration": 1.2},
        {"at": 5.90, "type": "tap", "action": "crouch_toggle"},
        {"at": 6.35, "type": "tap", "action": "attack_light"},
        {"at": 7.05, "type": "tap", "action": "spell_2"},
        {"at": 8.25, "type": "set_weather", "preset": "overcast"},
    ]


def _quake_escape_events():
    return [
        {"at": 0.00, "type": "teleport", "target": "stealth_climb"},
        {"at": 0.08, "type": "set_time", "preset": "dusk"},
        {"at": 0.16, "type": "set_weather", "preset": "stormy"},
        {"at": 0.25, "type": "tap", "action": "crouch_toggle"},
        {"at": 0.40, "type": "hold", "action": "forward", "duration": 2.1},
        {"at": 1.05, "type": "camera_impact", "kind": "heavy", "intensity": 1.25, "direction_deg": 0},
        {"at": 1.45, "type": "tap", "action": "jump"},
        {"at": 2.10, "type": "hold", "action": "right", "duration": 1.1},
        {"at": 2.55, "type": "camera_impact", "kind": "heavy", "intensity": 1.15, "direction_deg": -110},
        {"at": 3.20, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 3.35, "type": "hold", "action": "run", "duration": 1.2},
        {"at": 4.05, "type": "tap", "action": "jump"},
        {"at": 4.55, "type": "camera_impact", "kind": "heavy", "intensity": 1.05, "direction_deg": 95},
        {"at": 5.10, "type": "tap", "action": "crouch_toggle"},
        {"at": 5.40, "type": "hold", "action": "left", "duration": 1.0},
        {"at": 6.35, "type": "tap", "action": "attack_light"},
        {"at": 7.00, "type": "tap", "action": "spell_2"},
        {"at": 7.90, "type": "camera_impact", "kind": "heavy", "intensity": 1.1, "direction_deg": 30},
        {"at": 8.30, "type": "set_weather", "preset": "overcast"},
    ]


def _wallcrawl_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "parkour"},
        {"at": 0.20, "type": "hold", "action": "forward", "duration": 2.8},
        {"at": 0.30, "type": "hold", "action": "run", "duration": 2.4},
        {"at": 1.10, "type": "tap", "action": "jump"},
        {"at": 2.10, "type": "hold", "action": "right", "duration": 1.6},
        {"at": 2.95, "type": "tap", "action": "jump"},
        {"at": 3.80, "type": "hold", "action": "left", "duration": 1.3},
        {"at": 4.70, "type": "tap", "action": "jump"},
        {"at": 5.55, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 6.20, "type": "tap", "action": "jump"},
        {"at": 7.30, "type": "tap", "action": "attack_light"},
        {"at": 8.05, "type": "tap", "action": "spell_1"},
    ]
    return base + _shift_events(base, 9.5) + _shift_events(base, 19.0) + _shift_events(base, 28.5)


def _ultimate_sandbox_probe_events():
    """Safe sandbox showcase that reanchors between authored probes."""
    return [
        {"at": 0.00, "type": "teleport", "target": "sandbox_stairs_approach"},
        {"at": 0.10, "type": "camera_profile", "profile": "exploration", "hold_seconds": 3.0},
        {"at": 0.28, "type": "hold", "action": "forward", "duration": 0.95},
        {"at": 1.30, "type": "tap", "action": "jump"},
        {"at": 2.00, "type": "camera_shot", "name": "sandbox_stairs_intro", "profile": "exploration", "duration": 1.15, "side": 1.8, "yaw_bias_deg": 10},

        {"at": 3.40, "type": "teleport", "target": "sandbox_traversal_approach"},
        {"at": 3.56, "type": "hold", "action": "right", "duration": 0.82},
        {"at": 4.48, "type": "hold", "action": "forward", "duration": 0.92},
        {"at": 5.48, "type": "tap", "action": "attack_light"},
        {"at": 6.12, "type": "camera_shot", "name": "sandbox_traversal_pass", "profile": "exploration", "duration": 1.05, "side": -1.4, "yaw_bias_deg": -8},

        {"at": 7.30, "type": "teleport", "target": "sandbox_wallrun_approach"},
        {"at": 7.48, "type": "hold", "action": "run", "duration": 1.10},
        {"at": 7.56, "type": "hold", "action": "forward", "duration": 1.00},
        {"at": 8.34, "type": "tap", "action": "jump"},
        {"at": 8.96, "type": "tap", "action": "jump"},
        {"at": 9.62, "type": "camera_shot", "name": "sandbox_wallrun_probe", "profile": "exploration", "duration": 1.05, "side": 2.0, "yaw_bias_deg": 14},

        {"at": 10.80, "type": "teleport", "target": "sandbox_tower_approach"},
        {"at": 10.94, "type": "camera_profile", "profile": "exploration", "hold_seconds": 2.8},
        {"at": 11.10, "type": "hold", "action": "left", "duration": 0.84},
        {"at": 11.98, "type": "tap", "action": "crouch_toggle"},
        {"at": 12.56, "type": "tap", "action": "crouch_toggle"},
        {"at": 13.18, "type": "camera_shot", "name": "sandbox_tower_pan", "profile": "exploration", "duration": 1.10, "side": -2.1, "yaw_bias_deg": 18},

        {"at": 14.60, "type": "teleport", "target": "sandbox_pool_edge"},
        {"at": 14.76, "type": "hold", "action": "right", "duration": 0.76},
        {"at": 15.48, "type": "tap", "action": "jump"},
        {"at": 16.00, "type": "hold", "action": "left", "duration": 0.72},

        {"at": 16.92, "type": "teleport", "target": "sandbox_story_chest_approach"},
        {"at": 17.08, "type": "tap", "action": "interact"},
        {"at": 17.96, "type": "tap", "action": "attack_light"},
        {"at": 18.54, "type": "camera_shot", "name": "sandbox_story_chest", "profile": "exploration", "duration": 1.10, "side": 1.1, "yaw_bias_deg": 6},

        {"at": 19.90, "type": "teleport", "target": "sandbox_story_book_approach"},
        {"at": 20.08, "type": "hold", "action": "left", "duration": 0.68},
        {"at": 20.86, "type": "tap", "action": "interact"},
        {"at": 21.60, "type": "camera_profile", "profile": "exploration", "hold_seconds": 3.0},
        {"at": 21.76, "type": "camera_shot", "name": "sandbox_story_book", "profile": "exploration", "duration": 1.20, "side": 0.9, "yaw_bias_deg": 12},
        {"at": 23.10, "type": "tap", "action": "spell_1"},
        {"at": 23.40, "type": "tap", "action": "spell_cast"},
        {"at": 24.30, "type": "tap", "action": "attack_light"},
    ]


def _combat_marathon_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "training"},
        {"at": 0.12, "type": "force_aggro", "duration": 8.5, "teleport_to_enemy": True},
        {"at": 0.20, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 0.30, "type": "hold", "action": "run", "duration": 1.2},
        {"at": 0.72, "type": "tap", "action": "block", "duration": 0.34},
        {"at": 1.10, "type": "tap", "action": "attack_light"},
        {"at": 1.45, "type": "tap", "action": "attack_heavy"},
        {"at": 1.85, "type": "tap", "action": "spell_1"},
        {"at": 2.15, "type": "tap", "action": "attack_light"},
        {"at": 2.50, "type": "tap", "action": "spell_2"},
        {"at": 2.80, "type": "tap", "action": "attack_heavy"},
        {"at": 3.20, "type": "tap", "action": "attack_light"},
        {"at": 3.50, "type": "tap", "action": "spell_3"},
        {"at": 3.90, "type": "tap", "action": "attack_light"},
        {"at": 8.95, "type": "teleport", "target": "dragon_arena"},
        {"at": 9.07, "type": "force_aggro", "duration": 9.0, "teleport_to_enemy": True},
        {"at": 9.10, "type": "hold", "action": "forward", "duration": 1.6},
        {"at": 9.70, "type": "tap", "action": "jump"},
        {"at": 10.05, "type": "tap", "action": "attack_heavy"},
        {"at": 10.40, "type": "tap", "action": "spell_1"},
        {"at": 10.70, "type": "tap", "action": "attack_light"},
        {"at": 11.10, "type": "tap", "action": "attack_heavy"},
        {"at": 11.50, "type": "tap", "action": "spell_2"},
        {"at": 11.90, "type": "tap", "action": "attack_light"},
        {"at": 12.25, "type": "tap", "action": "attack_heavy"},
        {"at": 12.70, "type": "tap", "action": "spell_4"},
        {"at": 13.00, "type": "tap", "action": "attack_light"},
        {"at": 13.17, "type": "tap", "action": "block", "duration": 0.30},
        {"at": 18.55, "type": "teleport", "target": "docks"},
        {"at": 18.75, "type": "hold", "action": "left", "duration": 1.0},
        {"at": 19.05, "type": "hold", "action": "forward", "duration": 1.4},
        {"at": 19.75, "type": "tap", "action": "attack_light"},
        {"at": 20.05, "type": "tap", "action": "attack_heavy"},
        {"at": 20.40, "type": "tap", "action": "spell_1"},
        {"at": 20.70, "type": "tap", "action": "attack_light"},
        {"at": 21.15, "type": "tap", "action": "jump"},
        {"at": 21.45, "type": "tap", "action": "attack_heavy"},
        {"at": 21.80, "type": "tap", "action": "spell_3"},
        {"at": 22.15, "type": "tap", "action": "attack_light"},
    ]
    return base + _shift_events(base, 24.0) + _shift_events(base, 48.0)


def _arena_boss_probe_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "dragon_arena"},
        {"at": 0.08, "type": "set_time", "preset": "dusk"},
        {"at": 0.14, "type": "set_weather", "preset": "clear"},
        {"at": 0.20, "type": "camera_profile", "profile": "boss", "hold_seconds": 3.6},
        {"at": 0.62, "type": "camera_shot", "name": "boss_intro", "profile": "boss", "duration": 1.12, "side": 4.6, "yaw_bias_deg": 14},
        {"at": 0.18, "type": "equip_item", "item_id": "chainmail_armor"},
        {"at": 0.24, "type": "equip_item", "item_id": "training_shield"},
        {"at": 0.30, "type": "equip_item", "item_id": "rune_charm"},
        {"at": 0.40, "type": "force_aggro", "duration": 10.0, "teleport_to_enemy": True},
        {"at": 0.56, "type": "tap", "action": "target_lock"},
        {"at": 0.72, "type": "hold", "action": "forward", "duration": 2.0},
        {"at": 0.84, "type": "hold", "action": "run", "duration": 1.2},
        {"at": 1.26, "type": "tap", "action": "block", "duration": 0.34},
        {"at": 1.60, "type": "tap", "action": "attack_light"},
        {"at": 1.96, "type": "tap", "action": "attack_heavy"},
        {"at": 2.28, "type": "tap", "action": "spell_1"},
        {"at": 2.58, "type": "tap", "action": "spell_cast"},
        {"at": 2.92, "type": "tap", "action": "attack_light"},
        {"at": 3.28, "type": "tap", "action": "spell_2"},
        {"at": 3.58, "type": "tap", "action": "spell_cast"},
        {"at": 3.90, "type": "tap", "action": "attack_heavy"},
        {"at": 4.28, "type": "tap", "action": "attack_light"},
        {"at": 4.62, "type": "camera_impact", "kind": "heavy", "intensity": 0.32, "direction_deg": -12},
        {"at": 4.95, "type": "tap", "action": "block", "duration": 0.30},
        {"at": 5.35, "type": "tap", "action": "spell_3"},
        {"at": 5.64, "type": "tap", "action": "spell_cast"},
        {"at": 5.98, "type": "hold", "action": "left", "duration": 0.88},
        {"at": 6.86, "type": "hold", "action": "right", "duration": 0.82},
        {"at": 7.52, "type": "tap", "action": "jump"},
        {"at": 7.92, "type": "force_aggro", "duration": 10.0, "teleport_to_enemy": True},
        {"at": 8.16, "type": "tap", "action": "target_lock"},
        {"at": 8.36, "type": "tap", "action": "attack_light"},
        {"at": 8.70, "type": "tap", "action": "attack_heavy"},
        {"at": 9.04, "type": "tap", "action": "spell_4"},
        {"at": 9.34, "type": "tap", "action": "spell_cast"},
        {"at": 9.66, "type": "tap", "action": "attack_light"},
        {"at": 10.02, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 10.42, "type": "hold", "action": "forward", "duration": 1.8},
        {"at": 10.54, "type": "hold", "action": "run", "duration": 1.0},
        {"at": 11.58, "type": "camera_shot", "name": "boss_close", "profile": "combat", "duration": 0.98, "side": -2.1, "yaw_bias_deg": 9},
        {"at": 12.10, "type": "tap", "action": "attack_light"},
    ]
    return base + _shift_events(base, 13.2) + _shift_events(base, 26.4)


def _combat_magic_probe_events():
    base = [
        {"at": 0.02, "type": "equip_item", "item_id": "chainmail_armor"},
        {"at": 0.08, "type": "equip_item", "item_id": "training_shield"},
        {"at": 0.14, "type": "equip_item", "item_id": "rune_charm"},
        {"at": 0.20, "type": "force_aggro", "duration": 8.0, "teleport_to_enemy": True},
        {"at": 0.24, "type": "hold", "action": "forward", "duration": 1.9},
        {"at": 0.32, "type": "hold", "action": "run", "duration": 1.2},
        {"at": 0.92, "type": "tap", "action": "attack_light"},
        {"at": 1.28, "type": "tap", "action": "attack_heavy"},
        {"at": 1.62, "type": "tap", "action": "spell_1"},
        {"at": 1.94, "type": "tap", "action": "spell_cast"},
        {"at": 2.30, "type": "tap", "action": "attack_light"},
        {"at": 2.70, "type": "tap", "action": "spell_2"},
        {"at": 3.02, "type": "tap", "action": "spell_cast"},
        {"at": 3.36, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 3.82, "type": "tap", "action": "crouch_toggle"},
        {"at": 4.38, "type": "tap", "action": "crouch_toggle"},
        {"at": 4.88, "type": "tap", "action": "jump"},
        {"at": 5.30, "type": "tap", "action": "attack_heavy"},
        {"at": 5.66, "type": "tap", "action": "spell_3"},
        {"at": 5.98, "type": "tap", "action": "spell_cast"},
        {"at": 6.34, "type": "tap", "action": "attack_light"},
        {"at": 6.72, "type": "tap", "action": "spell_4"},
        {"at": 7.04, "type": "tap", "action": "spell_cast"},
        {"at": 7.36, "type": "tap", "action": "attack_light"},
        {"at": 7.92, "type": "hold", "action": "left", "duration": 0.85},
        {"at": 8.96, "type": "hold", "action": "right", "duration": 0.92},
    ]
    return base + _shift_events(base, 10.2) + _shift_events(base, 20.4)


def _anim_melee_core_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "dragon_arena"},
        {"at": 0.08, "type": "set_time", "preset": "dusk"},
        {"at": 0.14, "type": "set_weather", "preset": "clear"},
        {"at": 0.20, "type": "camera_profile", "profile": "combat", "hold_seconds": 3.2},
        {"at": 0.28, "type": "force_aggro", "duration": 9.5, "teleport_to_enemy": True},
        {"at": 0.46, "type": "tap", "action": "target_lock"},
        {"at": 0.64, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 1.02, "type": "tap", "action": "attack_light"},
        {"at": 1.36, "type": "tap", "action": "attack_heavy"},
        {"at": 1.76, "type": "tap", "action": "attack_light"},
        {"at": 2.14, "type": "tap", "action": "block", "duration": 0.32},
        {"at": 2.52, "type": "hold", "action": "forward", "duration": 1.3},
        {"at": 2.66, "type": "hold", "action": "run", "duration": 0.9},
        {"at": 3.10, "type": "tap", "action": "attack_light"},
        {"at": 3.44, "type": "tap", "action": "attack_heavy"},
        {"at": 3.82, "type": "tap", "action": "attack_light"},
        {"at": 4.10, "type": "camera_shot", "name": "melee_pass", "profile": "combat", "duration": 0.98, "side": -1.6, "yaw_bias_deg": 10},
        {"at": 4.58, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 4.96, "type": "tap", "action": "attack_heavy"},
        {"at": 5.34, "type": "tap", "action": "attack_light"},
    ]
    return base + _shift_events(base, 6.2) + _shift_events(base, 12.4)


def _anim_combo_chain_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "dragon_arena"},
        {"at": 0.12, "type": "force_aggro", "duration": 11.5, "teleport_to_enemy": True},
        {"at": 0.30, "type": "tap", "action": "target_lock"},
        {"at": 0.48, "type": "hold", "action": "forward", "duration": 1.4},
        {"at": 0.64, "type": "hold", "action": "run", "duration": 0.9},
        {"at": 1.04, "type": "tap", "action": "attack_light"},
        {"at": 1.16, "type": "hold", "action": "left", "duration": 0.34},
        {"at": 1.24, "type": "tap", "action": "attack_light"},
        {"at": 1.34, "type": "hold", "action": "right", "duration": 0.32},
        {"at": 1.44, "type": "tap", "action": "attack_heavy"},
        {"at": 1.58, "type": "hold", "action": "forward", "duration": 0.38},
        {"at": 1.70, "type": "tap", "action": "attack_light"},
        {"at": 1.82, "type": "tap", "action": "attack_thrust"},
        {"at": 1.92, "type": "tap", "action": "attack_heavy"},
        {"at": 2.18, "type": "tap", "action": "attack_light"},
        {"at": 2.42, "type": "tap", "action": "attack_light"},
        {"at": 2.68, "type": "tap", "action": "attack_heavy"},
        {"at": 2.92, "type": "tap", "action": "attack_light"},
        {"at": 3.18, "type": "tap", "action": "block", "duration": 0.28},
        {"at": 3.54, "type": "tap", "action": "attack_heavy"},
        {"at": 3.82, "type": "tap", "action": "attack_light"},
        {"at": 4.10, "type": "camera_shot", "name": "combo_chain", "profile": "combat", "duration": 0.92, "side": 1.8, "yaw_bias_deg": -11},
    ]
    return base + _shift_events(base, 4.9) + _shift_events(base, 9.8)


def _anim_weapon_modes_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "castle_interior"},
        {"at": 0.06, "type": "equip_item", "item_id": "chainmail_armor"},
        {"at": 0.12, "type": "equip_item", "item_id": "training_shield"},
        {"at": 0.18, "type": "equip_item", "item_id": "rune_charm"},
        {"at": 0.20, "type": "weapon_ready", "drawn": True},
        {"at": 0.24, "type": "hold", "action": "forward", "duration": 0.82},
        {"at": 0.28, "type": "hold", "action": "right", "duration": 0.48},
        {"at": 0.70, "type": "tap", "action": "attack_light"},
        {"at": 1.08, "type": "tap", "action": "attack_heavy"},
        {"at": 1.46, "type": "tap", "action": "block", "duration": 0.42},
        {"at": 1.78, "type": "weapon_ready", "drawn": False},
        {"at": 1.94, "type": "tap", "action": "spell_1"},
        {"at": 2.22, "type": "tap", "action": "spell_cast"},
        {"at": 2.46, "type": "weapon_ready", "drawn": True},
        {"at": 2.58, "type": "tap", "action": "spell_2"},
        {"at": 2.86, "type": "tap", "action": "spell_cast"},
        {"at": 3.24, "type": "tap", "action": "spell_3"},
        {"at": 3.50, "type": "tap", "action": "spell_cast"},
        {"at": 3.88, "type": "tap", "action": "spell_4"},
        {"at": 4.14, "type": "tap", "action": "spell_cast"},
        {"at": 4.56, "type": "tap", "action": "attack_light"},
        {"at": 4.92, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 5.04, "type": "weapon_ready", "drawn": False},
        {"at": 5.30, "type": "tap", "action": "attack_heavy"},
    ]
    return base + _shift_events(base, 6.0) + _shift_events(base, 12.0)


def _anim_defense_stealth_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "stealth_climb"},
        {"at": 0.06, "type": "equip_item", "item_id": "chainmail_armor"},
        {"at": 0.12, "type": "equip_item", "item_id": "training_shield"},
        {"at": 0.18, "type": "equip_item", "item_id": "rune_charm"},
        {"at": 0.24, "type": "force_aggro", "duration": 12.0, "teleport_to_enemy": True},
        {"at": 0.38, "type": "tap", "action": "crouch_toggle"},
        {"at": 0.50, "type": "hold", "action": "forward", "duration": 1.6},
        {"at": 0.64, "type": "hold", "action": "left", "duration": 0.56},
        {"at": 2.26, "type": "tap", "action": "interact", "duration": 0.20},
        {"at": 2.58, "type": "tap", "action": "crouch_toggle"},
        {"at": 2.72, "type": "hold", "action": "forward", "duration": 0.90},
        {"at": 3.12, "type": "tap", "action": "roll"},
        {"at": 3.36, "type": "tap", "action": "dash"},
        {"at": 3.54, "type": "tap", "action": "block", "duration": 0.42},
        {"at": 3.98, "type": "hold", "action": "left", "duration": 0.70},
        {"at": 4.34, "type": "tap", "action": "roll"},
        {"at": 4.62, "type": "tap", "action": "dash"},
        {"at": 4.86, "type": "hold", "action": "backward", "duration": 0.64},
        {"at": 5.10, "type": "tap", "action": "roll"},
        {"at": 5.54, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 5.96, "type": "tap", "action": "attack_light"},
        {"at": 6.32, "type": "tap", "action": "spell_2"},
        {"at": 6.58, "type": "tap", "action": "spell_cast"},
        {"at": 6.92, "type": "tap", "action": "crouch_toggle"},
        {"at": 7.04, "type": "hold", "action": "forward", "duration": 1.15},
        {"at": 7.18, "type": "hold", "action": "run", "duration": 0.78},
        {"at": 8.46, "type": "tap", "action": "crouch_toggle"},
    ]
    return base + _shift_events(base, 9.0)


def _anim_locomotion_transitions_events():
    return [
        {"at": 0.00, "type": "teleport", "target": "castle_interior"},
        {"at": 0.12, "type": "hold", "action": "forward", "duration": 2.8},
        {"at": 0.26, "type": "hold", "action": "run", "duration": 1.9},
        {"at": 0.56, "type": "hold", "action": "right", "duration": 1.30},
        {"at": 1.08, "type": "hold", "action": "left", "duration": 1.15},
        {"at": 1.62, "type": "hold", "action": "backward", "duration": 0.90},
        {"at": 2.44, "type": "tap", "action": "jump"},
        {"at": 3.24, "type": "hold", "action": "forward", "duration": 2.2},
        {"at": 3.36, "type": "hold", "action": "run", "duration": 1.4},
        {"at": 4.18, "type": "tap", "action": "crouch_toggle"},
        {"at": 4.30, "type": "hold", "action": "forward", "duration": 1.20},
        {"at": 4.36, "type": "hold", "action": "left", "duration": 0.85},
        {"at": 5.72, "type": "tap", "action": "crouch_toggle"},
        {"at": 6.40, "type": "hold", "action": "right", "duration": 1.10},
        {"at": 7.90, "type": "teleport", "target": "training_pool"},
        {"at": 8.02, "type": "set_flag", "flag": "in_water", "value": True, "duration": 8.6},
        {"at": 8.18, "type": "hold", "action": "forward", "duration": 3.6},
        {"at": 9.16, "type": "hold", "action": "right", "duration": 1.55},
        {"at": 10.56, "type": "hold", "action": "left", "duration": 1.30},
        {"at": 11.92, "type": "tap", "action": "jump"},
        {"at": 12.74, "type": "hold", "action": "backward", "duration": 1.20},
        {"at": 14.10, "type": "hold", "action": "forward", "duration": 2.0},
        {"at": 15.96, "type": "set_flag", "flag": "in_water", "value": False},
        {"at": 17.10, "type": "teleport", "target": "stealth_climb"},
        {"at": 17.24, "type": "hold", "action": "forward", "duration": 3.0},
        {"at": 17.36, "type": "hold", "action": "run", "duration": 2.1},
        {"at": 18.06, "type": "hold", "action": "right", "duration": 1.05},
        {"at": 19.12, "type": "tap", "action": "jump"},
        {"at": 20.32, "type": "tap", "action": "jump"},
        {"at": 21.28, "type": "hold", "action": "left", "duration": 1.10},
        {"at": 22.56, "type": "hold", "action": "backward", "duration": 0.84},
        {"at": 23.86, "type": "hold", "action": "forward", "duration": 2.1},
        {"at": 24.02, "type": "hold", "action": "run", "duration": 1.45},
        {"at": 26.80, "type": "teleport", "target": "flight"},
        {"at": 26.94, "type": "set_flag", "flag": "is_flying", "value": True, "duration": 14.2},
        {"at": 27.16, "type": "hold", "action": "forward", "duration": 4.2},
        {"at": 27.34, "type": "hold", "action": "run", "duration": 2.6},
        {"at": 28.18, "type": "hold", "action": "right", "duration": 1.55},
        {"at": 29.96, "type": "hold", "action": "left", "duration": 1.42},
        {"at": 31.12, "type": "hold", "action": "flight_up", "duration": 1.85},
        {"at": 33.30, "type": "hold", "action": "flight_down", "duration": 1.45},
        {"at": 34.98, "type": "hold", "action": "backward", "duration": 1.10},
        {"at": 36.42, "type": "hold", "action": "forward", "duration": 2.6},
        {"at": 39.34, "type": "set_flag", "flag": "is_flying", "value": False},
        {"at": 40.28, "type": "hold", "action": "forward", "duration": 2.0},
        {"at": 40.42, "type": "hold", "action": "run", "duration": 1.25},
        {"at": 42.96, "type": "teleport", "target": "castle_interior"},
        {"at": 43.10, "type": "hold", "action": "forward", "duration": 3.2},
        {"at": 43.24, "type": "hold", "action": "run", "duration": 2.3},
        {"at": 44.18, "type": "hold", "action": "right", "duration": 1.10},
        {"at": 45.44, "type": "hold", "action": "left", "duration": 0.96},
        {"at": 46.68, "type": "tap", "action": "jump"},
        {"at": 47.52, "type": "tap", "action": "crouch_toggle"},
        {"at": 47.62, "type": "hold", "action": "forward", "duration": 1.10},
        {"at": 48.68, "type": "tap", "action": "crouch_toggle"},
        {"at": 49.30, "type": "hold", "action": "backward", "duration": 0.92},
        {"at": 50.42, "type": "hold", "action": "forward", "duration": 3.4},
        {"at": 50.56, "type": "hold", "action": "run", "duration": 2.2},
        {"at": 54.40, "type": "hold", "action": "right", "duration": 0.95},
    ]


def _anim_enemy_visibility_aggro_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "dragon_arena"},
        {"at": 0.08, "type": "camera_profile", "profile": "boss", "hold_seconds": 3.8},
        {"at": 0.16, "type": "camera_shot", "name": "enemy_intro", "profile": "boss", "duration": 1.10, "side": 4.8, "yaw_bias_deg": 16},
        {"at": 0.24, "type": "force_aggro", "duration": 10.0, "teleport_to_enemy": True},
        {"at": 0.42, "type": "tap", "action": "target_lock"},
        {"at": 0.76, "type": "hold", "action": "forward", "duration": 1.6},
        {"at": 1.08, "type": "tap", "action": "attack_light"},
        {"at": 1.42, "type": "tap", "action": "block", "duration": 0.34},
        {"at": 1.78, "type": "tap", "action": "attack_heavy"},
        {"at": 2.12, "type": "camera_shot", "name": "enemy_side", "profile": "combat", "duration": 0.94, "side": -2.2, "yaw_bias_deg": -8},
        {"at": 2.52, "type": "hold", "action": "right", "duration": 0.82},
        {"at": 3.06, "type": "force_aggro", "duration": 9.0, "teleport_to_enemy": True},
        {"at": 3.34, "type": "tap", "action": "attack_light"},
        {"at": 3.70, "type": "tap", "action": "attack_heavy"},
        {"at": 4.04, "type": "tap", "action": "spell_1"},
        {"at": 4.28, "type": "tap", "action": "spell_cast"},
        {"at": 4.64, "type": "tap", "action": "block", "duration": 0.34},
        {"at": 5.06, "type": "camera_shot", "name": "enemy_contact", "profile": "combat", "duration": 0.90, "side": 1.9, "yaw_bias_deg": 7},
    ]
    return base + _shift_events(base, 5.8) + _shift_events(base, 11.6)


def _anim_camera_variation_events():
    return [
        {"at": 0.00, "type": "teleport", "target": "dragon_arena"},
        {"at": 0.08, "type": "force_aggro", "duration": 10.0, "teleport_to_enemy": True},
        {"at": 0.18, "type": "tap", "action": "target_lock"},
        {"at": 0.24, "type": "camera_profile", "profile": "exploration", "hold_seconds": 1.2},
        {"at": 0.28, "type": "camera_profile", "profile": "shoulder_right", "hold_seconds": 2.8},
        {"at": 0.38, "type": "camera_sequence", "name": "portal_arrival", "priority": 78},
        {"at": 1.50, "type": "hold", "action": "forward", "duration": 1.4},
        {"at": 1.82, "type": "tap", "action": "attack_light"},
        {"at": 2.20, "type": "camera_profile", "profile": "combat", "hold_seconds": 3.0},
        {"at": 2.34, "type": "camera_shot", "name": "combat_mid", "profile": "combat", "duration": 1.00, "side": 2.2, "yaw_bias_deg": -11},
        {"at": 3.38, "type": "tap", "action": "attack_heavy"},
        {"at": 3.76, "type": "tap", "action": "block", "duration": 0.32},
        {"at": 4.24, "type": "camera_profile", "profile": "boss", "hold_seconds": 3.2},
        {"at": 4.38, "type": "camera_shot", "name": "boss_close", "profile": "boss", "duration": 1.10, "side": 5.2, "yaw_bias_deg": 14},
        {"at": 5.56, "type": "tap", "action": "spell_2"},
        {"at": 5.82, "type": "tap", "action": "spell_cast"},
        {"at": 6.30, "type": "camera_shot", "name": "rear_track", "profile": "combat", "duration": 0.95, "side": -1.8, "yaw_bias_deg": -22},
        {"at": 7.20, "type": "hold", "action": "left", "duration": 0.88},
        {"at": 7.84, "type": "tap", "action": "attack_light"},
    ]


def _camera_context_modes_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "castle_interior"},
        {"at": 0.06, "type": "equip_item", "item_id": "hunter_bow"},
        {"at": 0.12, "type": "weapon_ready", "drawn": True},
        {"at": 0.20, "type": "hold", "action": "aim", "duration": 4.80},
        {"at": 0.36, "type": "hold", "action": "forward", "duration": 1.40},
        {"at": 0.52, "type": "hold", "action": "right", "duration": 0.70},
        {"at": 5.40, "type": "weapon_ready", "drawn": False},
        {"at": 5.62, "type": "tap", "action": "spell_1"},
        {"at": 5.90, "type": "hold", "action": "aim", "duration": 4.40},
        {"at": 6.24, "type": "tap", "action": "spell_cast"},
        {"at": 11.20, "type": "tap", "action": "crouch_toggle"},
        {"at": 11.36, "type": "hold", "action": "forward", "duration": 2.40},
        {"at": 11.56, "type": "hold", "action": "left", "duration": 0.80},
        {"at": 14.24, "type": "tap", "action": "crouch_toggle"},
    ]
    return (
        base
        + _shift_events(base, 16.8)
        + _shift_events(base, 33.6)
    )


def _hud_combat_feedback_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "dragon_arena"},
        {"at": 0.08, "type": "force_aggro", "duration": 12.0, "teleport_to_enemy": True},
        {"at": 0.22, "type": "tap", "action": "target_lock"},
        {"at": 0.42, "type": "camera_profile", "profile": "boss", "hold_seconds": 3.4},
        {"at": 0.78, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 1.18, "type": "damage_player", "ratio": 0.08},
        {"at": 1.64, "type": "tap", "action": "attack_light"},
        {"at": 1.96, "type": "damage_player", "ratio": 0.11},
        {"at": 2.44, "type": "tap", "action": "attack_heavy"},
        {"at": 2.80, "type": "damage_player", "ratio": 0.14},
        {"at": 3.26, "type": "tap", "action": "spell_1"},
        {"at": 3.52, "type": "tap", "action": "spell_cast"},
        {"at": 3.88, "type": "tap", "action": "block", "duration": 0.30},
        {"at": 4.22, "type": "tap", "action": "attack_light"},
        {"at": 4.54, "type": "damage_player", "ratio": 0.17},
        {"at": 4.90, "type": "camera_impact", "kind": "heavy", "intensity": 0.36, "direction_deg": -18},
        {"at": 5.30, "type": "tap", "action": "spell_3"},
        {"at": 5.56, "type": "tap", "action": "spell_cast"},
        {"at": 5.94, "type": "tap", "action": "attack_heavy"},
    ]
    return base + _shift_events(base, 6.4)


def _perf_animation_stability_events():
    base = [
        {"at": 0.00, "type": "teleport", "target": "dragon_arena"},
        {"at": 0.08, "type": "set_weather", "preset": "clear"},
        {"at": 0.14, "type": "force_aggro", "duration": 14.0, "teleport_to_enemy": True},
        {"at": 0.32, "type": "tap", "action": "target_lock"},
        {"at": 0.58, "type": "hold", "action": "forward", "duration": 1.5},
        {"at": 0.92, "type": "tap", "action": "attack_light"},
        {"at": 1.22, "type": "tap", "action": "attack_heavy"},
        {"at": 1.56, "type": "tap", "action": "spell_1"},
        {"at": 1.82, "type": "tap", "action": "spell_cast"},
        {"at": 2.22, "type": "tap", "action": "block", "duration": 0.30},
        {"at": 2.60, "type": "hold", "action": "left", "duration": 0.86},
        {"at": 3.04, "type": "tap", "action": "attack_light"},
        {"at": 3.34, "type": "tap", "action": "spell_2"},
        {"at": 3.60, "type": "tap", "action": "spell_cast"},
        {"at": 3.98, "type": "tap", "action": "attack_heavy"},
        {"at": 4.36, "type": "camera_shot", "name": "stability", "profile": "combat", "duration": 0.90, "side": 1.4, "yaw_bias_deg": -7},
        {"at": 4.86, "type": "tap", "action": "jump"},
        {"at": 5.30, "type": "tap", "action": "crouch_toggle"},
        {"at": 5.78, "type": "tap", "action": "crouch_toggle"},
        {"at": 6.16, "type": "force_aggro", "duration": 12.0, "teleport_to_enemy": True},
        {"at": 6.48, "type": "tap", "action": "attack_light"},
        {"at": 6.78, "type": "tap", "action": "attack_heavy"},
        {"at": 7.08, "type": "tap", "action": "spell_4"},
        {"at": 7.34, "type": "tap", "action": "spell_cast"},
        {"at": 7.74, "type": "tap", "action": "block", "duration": 0.36},
        {"at": 8.14, "type": "tap", "action": "attack_light"},
    ]
    return base + _shift_events(base, 8.8) + _shift_events(base, 17.6) + _shift_events(base, 26.4)


def _location_dialogue_probe_events():
    return (
        _dialogue_stop_events(
            0.0,
            "castle_interior",
            move_to=(4.6, 43.2, 0.0),
            profile="shoulder_right",
            shot_name="dialogue_castle_miner",
            shot_duration=1.16,
            side=0.92,
            yaw_bias_deg=8.0,
            hold_seconds=3.0,
            interact_offsets=(3.10,),
            close_offsets=(10.35,),
        )
        + _dialogue_stop_events(
            11.2,
            "dwarven_caves_gate",
            move_to=(92.2, -7.9, 4.0),
            profile="shoulder_left",
            shot_name="dialogue_gate_sentry",
            shot_duration=1.10,
            side=-1.05,
            yaw_bias_deg=10.0,
            hold_seconds=2.8,
            interact_offsets=(3.15,),
            close_offsets=(10.10,),
        )
        + _dialogue_stop_events(
            22.6,
            "port_market_memory",
            profile="exploration",
            shot_name="dialogue_memory_reveal",
            shot_duration=1.22,
            side=-1.55,
            yaw_bias_deg=12.0,
            hold_seconds=2.6,
            interact_offsets=(),
        )
    )


def _all_locations_grand_tour_events():
    bundle = {
        "route": [
            {"teleport": "town"},
            {"move": ["forward", "run"], "duration": 2.4},
            {"interact": True},
            {"ui": "inventory"},
            {"ui": "map"},
            {"ui": "skills"},
            {"ui": "journal"},
            {"ui": "close_inventory"},
            {"ui": "pause"},
            {"ui": "settings"},
            {"ui": "resume"},

            {"teleport": "castle_hill"},
            {"move": ["forward", "run"], "duration": 2.2},
            {"jump": True},
            {"teleport": "castle"},
            {"move": ["forward", "run"], "duration": 1.8},
            {"interact": True},
            {"teleport": "castle_interior"},
            {"move": "forward", "duration": 1.6},
            {"interact": True},
            {"teleport": "world_map_gallery"},
            {"move": "right", "duration": 0.9},
            {"teleport": "prince_chamber"},
            {"move": "left", "duration": 0.9},
            {"teleport": "royal_laundry"},
            {"move": "backward", "duration": 0.8},
            {"teleport": "throne_hall"},
            {"move": "forward", "duration": 1.1},
            {"interact": True},
            {"teleport": "castle_flight_edge"},
            {"move": ["forward", "run"], "duration": 1.5},

            {"teleport": "river_road"},
            {"move": ["forward", "run"], "duration": 2.3},
            {"teleport": "docks"},
            {"move": ["forward", "run"], "duration": 2.2},
            {"interact": True},
            {"teleport": "port_market_walk"},
            {"move": "forward", "duration": 1.5},
            {"teleport": "port_market_memory"},
            {"move": "right", "duration": 1.0},
            {"interact": True},
            {"teleport": "coastline"},
            {"move": ["forward", "run"], "duration": 2.0},

            {"teleport": "training"},
            {"move": ["forward", "run"], "duration": 2.2},
            {"jump": True},
            {"tap": "attack_light"},
            {"tap": "spell_1"},
            {"tap": "spell_cast"},
            {"teleport": "parkour"},
            {"move": ["forward", "run"], "duration": 2.4},
            {"tap": "jump"},
            {"tap": "jump"},
            {"teleport": "stealth_climb"},
            {"tap": "crouch_toggle"},
            {"move": "forward", "duration": 1.8},
            {"interact": True},
            {"tap": "crouch_toggle"},
            {"teleport": "flight"},
            {"tap": "flight_toggle"},
            {"hold": "flight_up", "duration": 1.3},
            {"hold": "forward", "duration": 1.5},
            {"hold": "flight_down", "duration": 0.8},
            {"tap": "flight_toggle"},

            {"teleport": "old_forest"},
            {"move": ["forward", "run"], "duration": 2.0},
            {"teleport": "sharuan_forest_bridge"},
            {"move": ["forward", "run"], "duration": 1.6},
            {"interact": True},
            {"teleport": "paradise_vision"},
            {"move": "forward", "duration": 1.3},

            {"teleport": "kremor_forest"},
            {"move": ["forward", "run"], "duration": 2.0},
            {"tap": "attack_light"},
            {"tap": "spell_2"},
            {"tap": "spell_cast"},
            {"teleport": "kremor_forest_cage"},
            {"move": "right", "duration": 1.1},
            {"interact": True},

            {"teleport": "dwarven_caves_gate"},
            {"move": ["forward", "run"], "duration": 1.8},
            {"interact": True},
            {"teleport": "dwarven_caves_halls"},
            {"move": "forward", "duration": 1.8},
            {"tap": "attack_heavy"},
            {"tap": "attack_light"},
            {"teleport": "dwarven_caves_throne"},
            {"move": "left", "duration": 1.0},
            {"interact": True}
        ]
    }
    parsed = parse_video_bot_plan_json(json.dumps(bundle))
    return list(parsed.get("events", [])) if isinstance(parsed, dict) else []


def _world_story_showcase_events():
    prelude = [
        {"at": 0.00, "type": "teleport", "target": "town"},
        {"at": 0.14, "type": "quest_action", "action": "bootstrap_all"},
        {"at": 0.90, "type": "ui_action", "action": "open_inventory", "cursor": {"x": 0.0, "y": 0.25, "click": True}},
        {"at": 1.45, "type": "ui_action", "action": "inventory_tab", "tab": "journal", "cursor": {"x": 0.58, "y": 0.46, "click": True}},
        {"at": 2.10, "type": "ui_action", "action": "inventory_tab", "tab": "inventory", "cursor": {"x": -0.58, "y": 0.46, "click": True}},
        {"at": 2.75, "type": "equip_item", "item_id": "chainmail_armor"},
        {"at": 3.10, "type": "equip_item", "item_id": "training_shield"},
        {"at": 3.50, "type": "tap", "action": "block", "duration": 0.34},
        {"at": 4.20, "type": "ui_action", "action": "close_inventory", "cursor": {"x": 0.0, "y": -0.66, "click": True}},
        {"at": 4.70, "type": "portal_jump", "target": "docks", "kind": "arcane"},
    ]
    return (
        prelude
        + _shift_events(_dialogue_events(), 6.0)
        + _shift_events(_ui_inventory_events(), 17.5)
        + _shift_events(_ui_pause_events(), 33.0)
        + _shift_events(_loot_chest_events(), 49.5)
        + _shift_events(_crouch_stealth_events(), 61.0)
        + [
            {"at": 72.45, "type": "quest_action", "action": "complete_tutorial"},
            {"at": 72.85, "type": "portal_jump", "target": "castle", "kind": "quest_gate"},
        ]
        + _shift_events(_dialogue_events(), 73.4)
    )


def _showcase_extended_events():
    narrative_setup = [
        {"at": 44.60, "type": "quest_action", "action": "bootstrap_all"},
        {"at": 44.95, "type": "equip_item", "item_id": "chainmail_armor"},
        {"at": 45.20, "type": "equip_item", "item_id": "royal_armor"},
        {"at": 45.45, "type": "equip_item", "item_id": "training_shield"},
        {"at": 45.85, "type": "tap", "action": "block", "duration": 0.38},
        {"at": 46.18, "type": "tap", "action": "spell_2"},
        {"at": 46.52, "type": "tap", "action": "spell_3"},
        {"at": 46.86, "type": "portal_jump", "target": "parkour", "kind": "arcane"},
    ]
    cinematic_tail = [
        {"at": 156.30, "type": "damage_player", "ratio": 0.34},
        {"at": 156.70, "type": "camera_impact", "kind": "heavy", "intensity": 1.20, "direction_deg": -20},
        {"at": 157.10, "type": "portal_jump", "target": "boats", "kind": "fire"},
        {"at": 157.40, "type": "tap", "action": "spell_4"},
        {"at": 157.72, "type": "tap", "action": "block", "duration": 0.30},
        {"at": 158.20, "type": "quest_action", "action": "complete_tutorial"},
    ]
    return (
        _shift_events(_excursion_events(), 0.0)
        + _shift_events(_ui_inventory_events(), 32.8)
        + narrative_setup
        + _shift_events(_parkour_events(), 48.6)
        + _shift_events(_wallcrawl_events(), 80.8)
        + _shift_events(_stealth_climb_events(), 113.2)
        + _shift_events(_loot_chest_events(), 126.0)
        + _shift_events(_dialogue_events(), 136.0)
        + _shift_events(_storm_quake_events(), 147.8)
        + cinematic_tail
        + _shift_events(_ui_pause_events(), 159.2)
        + _shift_events(_ui_inventory_events(), 175.6)
    )


def build_video_bot_events(raw_plan_name):
    plan = resolve_video_bot_plan_name(raw_plan_name)
    if plan == "idle":
        events = []
    elif plan == "swim":
        events = _swim_events()
    elif plan == "flight":
        events = _flight_events()
    elif plan == "parkour":
        events = _parkour_events()
    elif plan == "excursion":
        events = _excursion_events()
    elif plan == "environment_visual_probe":
        events = _environment_visual_probe_events()
    elif plan == "caves_visual_probe":
        events = _caves_visual_probe_events()
    elif plan == "ui_inventory":
        events = _ui_inventory_events()
    elif plan == "ui_pause":
        events = _ui_pause_events()
    elif plan == "ui_full":
        events = _ui_full_events()
    elif plan == "dialogue":
        events = _dialogue_events()
    elif plan == "loot_chest":
        events = _loot_chest_events()
    elif plan == "crouch_stealth":
        events = _crouch_stealth_events()
    elif plan == "stealth_climb":
        events = _stealth_climb_events()
    elif plan == "storm_quake":
        events = _storm_quake_events()
    elif plan == "quake_escape":
        events = _quake_escape_events()
    elif plan == "wallcrawl":
        events = _wallcrawl_events()
    elif plan == "ultimate_sandbox_probe":
        events = _ultimate_sandbox_probe_events()
    elif plan == "combat_marathon":
        events = _combat_marathon_events()
    elif plan == "arena_boss_probe":
        events = _arena_boss_probe_events()
    elif plan == "combat_magic_probe":
        events = _combat_magic_probe_events()
    elif plan == "anim_melee_core":
        events = _anim_melee_core_events()
    elif plan == "anim_combo_chain":
        events = _anim_combo_chain_events()
    elif plan == "anim_weapon_modes":
        events = _anim_weapon_modes_events()
    elif plan == "anim_defense_stealth":
        events = _anim_defense_stealth_events()
    elif plan == "anim_locomotion_transitions":
        events = _anim_locomotion_transitions_events()
    elif plan == "anim_enemy_visibility_aggro":
        events = _anim_enemy_visibility_aggro_events()
    elif plan == "anim_camera_variation":
        events = _anim_camera_variation_events()
    elif plan == "camera_context_modes":
        events = _camera_context_modes_events()
    elif plan == "hud_combat_feedback":
        events = _hud_combat_feedback_events()
    elif plan == "perf_animation_stability":
        events = _perf_animation_stability_events()
    elif plan == "location_dialogue_probe":
        events = _location_dialogue_probe_events()
    elif plan == "all_locations_grand_tour":
        events = _all_locations_grand_tour_events()
    elif plan == "world_story_showcase":
        events = _world_story_showcase_events()
    elif plan == "showcase_extended":
        events = _showcase_extended_events()
    elif plan == "mixed":
        events = (
            _shift_events(_ground_events(), 0.0)
            + _shift_events(_parkour_events(), 14.5)
            + _shift_events(_swim_events(), 31.0)
            + _shift_events(_flight_events(), 46.0)
            + _shift_events(_ui_full_events(), 60.0)
        )
    elif plan == "bot_nav_test":
        events = _bot_nav_test_events()
    else:
        events = _ground_events()
    return sorted(events, key=lambda row: float(row.get("at", 0.0) or 0.0))
