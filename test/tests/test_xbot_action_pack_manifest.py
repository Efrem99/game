import json
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


def test_runtime_critical_combat_states_use_single_clip_runtime_glbs():
    sources = _manifest_sources_map()
    runtime_dir = "assets/models/xbot/runtime_clips"

    assert sources.get("attacking") == f"{runtime_dir}/attacking.glb"
    assert sources.get("attack_light_right") == f"{runtime_dir}/attack_light_right.glb"
    assert sources.get("attack_thrust_right") == f"{runtime_dir}/attack_thrust_right.glb"
    assert sources.get("blocking") == f"{runtime_dir}/blocking.glb"

    assert sources.get("casting") == f"{runtime_dir}/casting.glb"
    assert sources.get("cast_prepare") == f"{runtime_dir}/cast_prepare.glb"
    assert sources.get("cast_channel") == f"{runtime_dir}/cast_channel.glb"
    assert sources.get("cast_release") == f"{runtime_dir}/cast_release.glb"

    assert sources.get("recovering") == f"{runtime_dir}/recovering.glb"
    assert sources.get("weapon_unsheathe") == f"{runtime_dir}/weapon_unsheathe.glb"
    assert sources.get("weapon_sheathe") == f"{runtime_dir}/weapon_sheathe.glb"


def test_action_pack_remains_only_for_optional_cast_variants():
    sources = _manifest_sources_map()
    expected = "assets/models/xbot/xbot_action_pack.glb"

    assert sources.get("cast_fast") == expected
    assert sources.get("cast_arcane") == expected
    assert sources.get("cast_fire") == expected
    assert sources.get("cast_heal") == expected
    assert sources.get("cast_holy") == expected
    assert sources.get("cast_ice") == expected
    assert sources.get("cast_lightning") == expected
    assert sources.get("cast_ward") == expected
