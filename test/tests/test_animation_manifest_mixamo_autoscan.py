import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.animation_manifest import (
    alias_animation_key,
    load_player_manifest_sources,
    validate_player_manifest,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test")


def test_alias_animation_key_supports_mixamo_style_stealth_and_cast_variants():
    assert alias_animation_key("Stealth Idle") == "crouch_idle"
    assert alias_animation_key("Sneak Walk Forward") == "crouch_move"
    assert alias_animation_key("Spell Prepare") == "cast_prepare"
    assert alias_animation_key("Magic Channel Loop") == "cast_channel"
    assert alias_animation_key("Cast Release") == "cast_release"


def test_load_manifest_sources_merges_auto_source_dirs_without_overriding_manifest_entries(tmp_path):
    project_root = Path(tmp_path)
    manifest_path = project_root / "data" / "actors" / "player_animations.json"

    explicit_cast = project_root / "assets" / "anims" / "cast_manual.fbx"
    mixamo_dir = project_root / "assets" / "anims" / "mixamo" / "player"
    mixamo_cast = mixamo_dir / "Spell Cast.fbx"
    mixamo_crouch = mixamo_dir / "Sneak Walk Forward.fbx"

    _touch(explicit_cast)
    _touch(mixamo_cast)
    _touch(mixamo_crouch)

    payload = {
        "manifest": {
            "strict_runtime_sources": True,
            "sources": [
                {
                    "key": "casting",
                    "path": explicit_cast.as_posix(),
                    "loop": False,
                }
            ],
            "auto_source_dirs": [
                mixamo_dir.as_posix(),
            ],
        }
    }
    _write_json(manifest_path, payload)

    mapping, strict_mode, diagnostics = load_player_manifest_sources(
        manifest_path=manifest_path,
        require_existing_files=True,
    )

    assert strict_mode is True
    assert mapping.get("casting") == explicit_cast.as_posix()
    assert mapping.get("crouch_move") == mixamo_crouch.as_posix()
    assert all("failed" not in str(item).lower() for item in diagnostics)


def test_validate_player_manifest_flags_missing_weapon_transition_keys(tmp_path):
    project_root = Path(tmp_path)
    manifest_path = project_root / "data" / "actors" / "player_animations.json"
    state_path = project_root / "data" / "states" / "player_states.json"

    idle_path = project_root / "assets" / "models" / "xbot" / "idle.glb"
    _touch(idle_path)

    payload = {
        "manifest": {
            "sources": [
                {
                    "key": "idle",
                    "path": idle_path.as_posix(),
                    "loop": True,
                }
            ]
        },
        "player": {
            "idle": ["idle"],
            "weapon_unsheathe": ["weapon_unsheathe", "draw_sword"],
            "weapon_sheathe": ["weapon_sheathe", "sheath_sword_1"],
        },
    }
    _write_json(manifest_path, payload)
    _write_json(
        state_path,
        {
            "states": [
                {"name": "idle", "animation": "idle"},
                {"name": "weapon_unsheathe", "animation": "weapon_unsheathe"},
                {"name": "weapon_sheathe", "animation": "weapon_sheathe"},
            ]
        },
    )

    result = validate_player_manifest(
        manifest_path=manifest_path,
        state_path=state_path,
    )

    assert result["ok"] is False
    errors = "\n".join(result.get("errors", []))
    assert "'player.weapon_unsheathe' references missing manifest key 'weapon_unsheathe'." in errors
    assert "'player.weapon_unsheathe' references missing manifest key 'draw_sword'." in errors
    assert "'player.weapon_sheathe' references missing manifest key 'weapon_sheathe'." in errors
    assert "'player.weapon_sheathe' references missing manifest key 'sheath_sword_1'." in errors


def test_load_manifest_sources_accepts_backend_payload_without_manifest_file(tmp_path):
    project_root = Path(tmp_path)
    mixamo_dir = project_root / "assets" / "anims" / "mixamo" / "player"
    mixamo_cast = mixamo_dir / "Spell Cast.fbx"
    _touch(mixamo_cast)

    payload = {
        "manifest": {
            "strict_runtime_sources": True,
            "sources": [
                {
                    "key": "cast_fast",
                    "path": mixamo_cast.as_posix(),
                    "loop": False,
                }
            ],
        }
    }

    mapping, strict_mode, diagnostics = load_player_manifest_sources(
        manifest_payload=payload,
        project_root=project_root,
        require_existing_files=True,
    )

    assert strict_mode is True
    assert mapping["cast_fast"] == mixamo_cast.as_posix()
    assert diagnostics == []
