import json
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
PLAYER_STATES_PATH = ROOT / "data" / "states" / "player_states.json"


def _load_transitions():
    payload = json.loads(PLAYER_STATES_PATH.read_text(encoding="utf-8-sig"))
    rows = payload.get("transitions", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _load_states():
    payload = json.loads(PLAYER_STATES_PATH.read_text(encoding="utf-8-sig"))
    rows = payload.get("states", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _state_names():
    names = set()
    for row in _load_states():
        name = str(row.get("name", "") or "").strip().lower()
        if name:
            names.add(name)
    return names


def _transition_sources(row):
    raw = row.get("from", [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return set()
    return {str(token or "").strip().lower() for token in raw if str(token or "").strip()}


def _has_recovery_safe_trigger(trigger_name):
    target_trigger = str(trigger_name or "").strip().lower()
    for row in _load_transitions():
        trigger = str(row.get("trigger", "") or "").strip().lower()
        if trigger != target_trigger:
            continue
        sources = _transition_sources(row)
        if "*" in sources or "recovering" in sources:
            return True
    return False


def _has_transition(source_state, target_state, *, trigger=None):
    source_token = str(source_state or "").strip().lower()
    target_token = str(target_state or "").strip().lower()
    trigger_token = str(trigger or "").strip().lower()
    for row in _load_transitions():
        target = str(row.get("to", "") or "").strip().lower()
        if target != target_token:
            continue
        if trigger_token:
            row_trigger = str(row.get("trigger", "") or "").strip().lower()
            if row_trigger != trigger_token:
                continue
        sources = _transition_sources(row)
        if source_token in sources or "*" in sources:
            return True
    return False


def _find_transition(source_state, target_state):
    source_token = str(source_state or "").strip().lower()
    target_token = str(target_state or "").strip().lower()
    for row in _load_transitions():
        target = str(row.get("to", "") or "").strip().lower()
        if target != target_token:
            continue
        sources = _transition_sources(row)
        if source_token in sources or "*" in sources:
            return row
    return None


def test_attack_trigger_can_start_from_recovering():
    assert _has_recovery_safe_trigger("attack")


def test_cast_trigger_can_start_from_recovering():
    assert _has_recovery_safe_trigger("cast_spell")


def test_cast_phase_states_are_declared_for_runtime_preflight():
    names = _state_names()
    assert "cast_prepare" in names
    assert "cast_channel" in names
    assert "cast_release" in names


def test_flight_phase_states_are_declared_for_runtime_preflight():
    names = _state_names()
    assert "flight_takeoff" in names
    assert "flight_hover" in names
    assert "flight_glide" in names
    assert "flight_dive" in names
    assert "flight_land" in names


def test_wallrun_has_explicit_exit_paths_back_to_runtime_locomotion():
    assert _has_transition("wallrun", "falling", trigger="exit_wallrun")
    assert _has_transition("wallrun", "running", trigger="exit_wallrun")
    assert _has_transition("wallrun", "walking", trigger="exit_wallrun")
    assert _has_transition("wallrun", "idle", trigger="exit_wallrun")


def test_climbing_and_vaulting_can_return_to_ground_locomotion_without_waiting_for_loop_end():
    assert _has_transition("climbing", "falling")
    assert _has_transition("climbing", "running")
    assert _has_transition("climbing", "walking")
    assert _has_transition("climbing", "idle")
    assert _has_transition("vaulting", "running")
    assert _has_transition("vaulting", "walking")
    assert _has_transition("vaulting", "idle")


def test_jump_to_fall_transition_waits_for_real_descent():
    row = _find_transition("jumping", "falling")
    assert row is not None
    condition = str(row.get("condition", "") or "").strip().lower()
    assert condition == "!on_ground && vertical_speed < -0.12"
