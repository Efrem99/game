import json
import struct
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
MANIFEST_PATH = ROOT / "data" / "actors" / "player_animations.json"


def _manifest_sources_map():
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    out = {}
    for row in payload.get("manifest", {}).get("sources", []):
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or row.get("state") or row.get("id") or "").strip().lower()
        path = str(row.get("path") or row.get("file") or row.get("src") or "").strip().replace("\\", "/")
        if key and path:
            out[key] = path
    return out


def _built_transition_pack_states():
    report_path = ROOT / "logs" / "xbot_transition_pack_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    created = payload.get("created", []) if isinstance(payload, dict) else []
    states = set()
    for row in created:
        if not isinstance(row, dict):
            continue
        token = str(row.get("state") or "").strip().lower()
        if token:
            states.add(token)
    return states


def _built_runtime_exports_map():
    report_path = ROOT / "logs" / "xbot_transition_pack_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    created = payload.get("runtime_exports", []) if isinstance(payload, dict) else []
    exports = {}
    for row in created:
        if not isinstance(row, dict):
            continue
        token = str(row.get("state") or "").strip().lower()
        path = str(row.get("output_glb") or "").strip()
        if token and path:
            exports[token] = Path(path)
    return exports


def _glb_animation_names(path: Path):
    with path.open("rb") as handle:
        header = handle.read(12)
        _, _, _ = struct.unpack("<III", header)
        chunk_len, chunk_type = struct.unpack("<II", handle.read(8))
        assert chunk_type == 0x4E4F534A, "GLB missing JSON chunk"
        payload = json.loads(handle.read(chunk_len).decode("utf-8"))
    return {str(row.get("name") or "").strip() for row in payload.get("animations", []) if isinstance(row, dict)}


def test_transition_states_use_curated_runtime_sources():
    sources = _manifest_sources_map()
    runtime_dir = "assets/models/xbot/runtime_clips"
    bespoke = {
        "jumping": "assets/anims/jump_takeoff.fbx",
        "falling": "assets/anims/fall_air.fbx",
        "landing": "assets/anims/land_recover.fbx",
        "run_blade": "assets/anims/mixamo/player/run_blade.fbx",
        "vaulting": "assets/anims/mixamo/player/vault_low.fbx",
        "climbing": "assets/anims/mixamo/player/climb_fast.fbx",
    }
    for key, path in bespoke.items():
        assert sources.get(key) == path

    assert sources.get("dodging") == f"{runtime_dir}/dodging.glb"
    assert sources.get("flying") == f"{runtime_dir}/flying.glb"
    assert sources.get("flight_hover") == f"{runtime_dir}/flight_hover.glb"
    assert sources.get("flight_glide") == f"{runtime_dir}/flight_glide.glb"
    assert sources.get("flight_dive") == f"{runtime_dir}/flight_dive.glb"
    assert sources.get("sliding") == f"{runtime_dir}/sliding.glb"
    assert sources.get("swim") == f"{runtime_dir}/swim.glb"
    assert sources.get("wallrun") == f"{runtime_dir}/wallrun.glb"
    assert sources.get("weapon_unsheathe") == f"{runtime_dir}/weapon_unsheathe.glb"
    assert sources.get("weapon_sheathe") == f"{runtime_dir}/weapon_sheathe.glb"


def test_transition_pack_report_lists_core_runtime_mobility_states():
    states = _built_transition_pack_states()
    assert "run_blade" in states
    assert "climbing" in states
    assert "wallrun" in states
    assert "flight_takeoff" in states
    assert "flight_dive" in states
    assert "flight_land" in states


def test_transition_pack_contains_core_locomotion_animation_names():
    names = _glb_animation_names(ROOT / "assets" / "models" / "xbot" / "xbot_transition_pack.glb")
    assert "idle" in names
    assert "walk" in names
    assert "run" in names
    assert "flight_hover" in names
    assert "flight_glide" in names
    assert "flight_dive" in names


def test_runtime_clips_exist_for_core_states_and_keep_state_named_actions():
    exports = _built_runtime_exports_map()
    for state_key in (
        "idle",
        "walk",
        "run",
        "jumping",
        "flight_glide",
        "weapon_unsheathe",
        "weapon_sheathe",
    ):
        clip_path = exports.get(state_key)
        assert clip_path is not None, f"Missing runtime export entry for {state_key}"
        assert clip_path.exists(), f"Runtime clip file missing for {state_key}: {clip_path}"
        assert state_key in _glb_animation_names(clip_path)
