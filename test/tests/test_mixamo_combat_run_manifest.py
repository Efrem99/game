import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "actors" / "player_animations.json"


def _load_payload():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))


def _manifest_sources_map(payload):
    rows = payload.get("manifest", {}).get("sources", [])
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or row.get("state") or row.get("id") or "").strip().lower()
        path = str(row.get("path") or row.get("file") or row.get("src") or "").strip().replace("\\", "/")
        if key and path:
            out[key] = path
    return out


def test_running_prefers_mixamo_blade_run_clip():
    payload = _load_payload()
    running = payload.get("player", {}).get("running", [])
    if isinstance(running, str):
        running = [running]
    assert isinstance(running, list)
    assert running and str(running[0]).strip().lower() == "run_blade"


def test_combat_run_and_block_sources_follow_current_runtime_layout():
    """Canonical Mixamo + shared FBX paths (strict_runtime_sources)."""
    payload = _load_payload()
    sources = _manifest_sources_map(payload)
    expected = {
        "run_blade": "assets/anims/mixamo/player/run_blade.fbx",
        "attack_light_right": "assets/anims/mixamo/player/attack_light_right.fbx",
        "blocking": "assets/anims/mixamo/player/blocking.fbx",
        "falling_hard": "assets/anims/dismounting_horse.fbx",
        "flight_takeoff": "assets/anims/jump_takeoff.fbx",
        "flight_land": "assets/anims/land_recover.fbx",
    }
    for key, path in expected.items():
        assert sources.get(key) == path


def test_xbot_runtime_auxiliary_clips_are_explicitly_loaded_from_manifest():
    """XBot candidate tokens must match loaded clip names (aliases share FBX paths)."""
    payload = _load_payload()
    sources = _manifest_sources_map(payload)
    expected = {
        "dodge_roll": "assets/anims/dodge_roll.fbx",
        "block_guard": "assets/anims/mixamo/player/blocking.fbx",
        "flying_loop": "assets/anims/flying_loop.fbx",
        "swim_loop": "assets/anims/swim_loop.fbx",
        "vault_over": "assets/anims/vault_over.fbx",
        "wallrun_side": "assets/anims/wallrun_side.fbx",
    }
    for key, path in expected.items():
        assert sources.get(key) == path


def test_flight_phase_clips_have_manifest_entries():
    payload = _load_payload()
    sources = _manifest_sources_map(payload)
    for key in (
        "flight_airdash",
        "flight_glide",
        "flight_hover",
        "flight_dive",
    ):
        assert key in sources, f"missing manifest key {key}"
