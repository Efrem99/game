"""Manifest parsing and validation helpers for actor animation sources."""

import json
from pathlib import Path


BASE_RUNTIME_KEYS = {"idle", "walk", "run"}
AUTO_SOURCE_EXTS = {".bam", ".glb", ".gltf", ".fbx", ".egg"}
AUTO_SOURCE_EXT_PRIORITY = {
    ".bam": 0,
    ".glb": 1,
    ".gltf": 2,
    ".fbx": 3,
    ".egg": 4,
}
DEFAULT_MIXAMO_AUTO_SOURCE_DIRS = (
    "assets/anims/mixamo",
    "assets/anims/mixamo/player",
    "assets/anims/mixamo/hero",
)


def normalize_anim_key(value):
    token = str(value or "").strip().lower()
    token = token.replace("-", "_").replace(" ", "_")
    return token


def alias_animation_key(stem):
    token = normalize_anim_key(stem)
    if not token:
        return ""
    is_bow = (
        "bow" in token
        or "archer" in token
        or "archery" in token
        or "arrow" in token
    )
    if is_bow and ("aim" in token or "draw" in token or "ready" in token):
        return "bow_aim"
    if is_bow and ("shoot" in token or "shot" in token or "release" in token or "fire" in token):
        return "bow_shoot"
    is_stealth = (
        "crouch" in token
        or "crouched" in token
        or "stealth" in token
        or "sneak" in token
    )
    if is_stealth:
        if (
            "walk" in token
            or "move" in token
            or "run" in token
            or "strafe" in token
            or "step" in token
        ):
            return "crouch_move"
        return "crouch_idle"
    is_spell = (
        "cast" in token
        or "spell" in token
        or "magic" in token
        or "wizard" in token
        or "sorcery" in token
    )
    if is_spell and (
        "prepare" in token or "charge" in token or "windup" in token or "ready" in token
    ):
        return "cast_prepare"
    if is_spell and ("channel" in token or "chant" in token):
        return "cast_channel"
    if is_spell and ("release" in token or "unleash" in token):
        return "cast_release"
    if is_spell and ("fast" in token or "quick" in token or "instant" in token):
        return "cast_fast"
    if "idle" in token:
        return "idle"
    if "sprint" in token or "run" in token or "jog" in token:
        return "run"
    if "walk" in token:
        return "walk"
    if "jump" in token or "takeoff" in token or "hop" in token:
        return "jumping"
    if "fall" in token or "air" in token:
        return "falling"
    if "land" in token:
        return "landing"
    if "attack" in token or "slash" in token or "swing" in token or "strike" in token:
        return "attacking"
    if "dodge" in token or "roll" in token:
        return "dodging"
    if "block" in token or "guard" in token:
        return "blocking"
    if "cast" in token or "spell" in token:
        return "casting"
    if "vault" in token:
        return "vaulting"
    if "climb" in token:
        return "climbing"
    if "wallrun" in token or ("wall" in token and "run" in token):
        return "wallrun"
    if "swim" in token:
        return "swim"
    if "fly" in token or "flight" in token or "hover" in token or "glide" in token:
        return "flying"
    if "death" in token or token == "die":
        return "dead"
    return token


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _project_root_for_manifest(path=None, project_root=None):
    if project_root is not None:
        return Path(project_root)
    probe = Path(path or "data/actors/player_animations.json")
    folder = probe.parent
    if folder.name.lower() == "actors" and folder.parent.name.lower() == "data":
        return folder.parent.parent
    return Path.cwd()


def _resolve_existing_path(token, project_root):
    value = str(token or "").strip().replace("\\", "/")
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    rooted = Path(project_root) / candidate
    if rooted.exists():
        return rooted
    return candidate if candidate.exists() else None


def _collect_auto_source_dir_specs(manifest):
    specs = []
    seen = set()

    def _push(token, *, explicit):
        normalized = str(token or "").strip().replace("\\", "/")
        if not normalized:
            return
        marker = normalized.lower()
        if marker in seen:
            return
        seen.add(marker)
        specs.append((normalized, explicit))

    include_defaults = bool(manifest.get("include_default_mixamo_dirs", True))
    if include_defaults:
        for token in DEFAULT_MIXAMO_AUTO_SOURCE_DIRS:
            _push(token, explicit=False)

    for field_name in ("auto_source_dirs", "mixamo_source_dirs"):
        raw = manifest.get(field_name)
        if isinstance(raw, str):
            _push(raw, explicit=True)
        elif isinstance(raw, list):
            for token in raw:
                _push(token, explicit=True)
    return specs


def _scan_auto_source_dirs(dir_specs, project_root, diagnostics):
    discovered = {}
    used_stems = set()
    for directory_token, explicit in dir_specs:
        directory_path = Path(directory_token)
        if not directory_path.is_absolute():
            directory_path = Path(project_root) / directory_path
        if not directory_path.exists():
            if explicit:
                diagnostics.append(f"Auto source dir not found: {directory_token}")
            continue
        if not directory_path.is_dir():
            if explicit:
                diagnostics.append(f"Auto source path is not a directory: {directory_token}")
            continue

        clip_paths = [
            path
            for path in directory_path.rglob("*")
            if path.is_file() and path.suffix.lower() in AUTO_SOURCE_EXTS
        ]
        clip_paths.sort(
            key=lambda p: (
                p.stem.lower(),
                AUTO_SOURCE_EXT_PRIORITY.get(p.suffix.lower(), 99),
                p.as_posix().lower(),
            )
        )

        for path in clip_paths:
            key = alias_animation_key(path.stem)
            if not key or key in BASE_RUNTIME_KEYS:
                continue
            marker = key.lower()
            if marker in used_stems:
                continue
            used_stems.add(marker)
            discovered[key] = path.as_posix()
    return discovered


def load_player_manifest_sources(
    manifest_path="data/actors/player_animations.json",
    *,
    manifest_payload=None,
    project_root=None,
    require_existing_files=True,
):
    strict_mode = False
    mapping = {}
    diagnostics = []
    used_keys = set()

    path = Path(manifest_path)
    project_root = _project_root_for_manifest(path, project_root=project_root)
    if isinstance(manifest_payload, dict):
        payload = manifest_payload
    else:
        if not path.exists():
            return mapping, strict_mode, diagnostics
        try:
            payload = _read_json(path)
        except Exception as exc:
            diagnostics.append(f"Failed to read animation manifest: {exc}")
            return mapping, strict_mode, diagnostics

    manifest = payload.get("manifest", {}) if isinstance(payload, dict) else {}
    if not isinstance(manifest, dict):
        diagnostics.append("Manifest root must contain object 'manifest'.")
        return mapping, strict_mode, diagnostics

    strict_mode = bool(manifest.get("strict_runtime_sources", False))
    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        diagnostics.append("Manifest field 'manifest.sources' must be an array.")
        return mapping, strict_mode, diagnostics

    for idx, entry in enumerate(sources):
        key = ""
        clip_path = ""
        if isinstance(entry, str):
            clip_path = entry.strip().replace("\\", "/")
            key = alias_animation_key(Path(clip_path).stem)
        elif isinstance(entry, dict):
            key = normalize_anim_key(
                entry.get("key") or entry.get("state") or entry.get("id") or ""
            )
            clip_path = str(
                entry.get("path") or entry.get("file") or entry.get("src") or ""
            ).strip().replace("\\", "/")
            if not key and clip_path:
                key = alias_animation_key(Path(clip_path).stem)

        if not key or not clip_path:
            diagnostics.append(f"Skipped source[{idx}]: missing key/path.")
            continue
        if key in BASE_RUNTIME_KEYS:
            continue
        if key in used_keys:
            diagnostics.append(f"Duplicate key in manifest.sources: '{key}'")
            continue
        if require_existing_files and _resolve_existing_path(clip_path, project_root) is None:
            diagnostics.append(f"Missing animation file for key '{key}': {clip_path}")
            continue

        used_keys.add(key)
        mapping[key] = clip_path

    auto_specs = _collect_auto_source_dir_specs(manifest)
    auto_sources = _scan_auto_source_dirs(auto_specs, project_root, diagnostics)
    for key, clip_path in auto_sources.items():
        if key in used_keys:
            continue
        if require_existing_files and _resolve_existing_path(clip_path, project_root) is None:
            diagnostics.append(f"Missing animation file for key '{key}': {clip_path}")
            continue
        used_keys.add(key)
        mapping[key] = clip_path

    return mapping, strict_mode, diagnostics


def validate_player_manifest(
    manifest_path="data/actors/player_animations.json",
    state_path="data/states/player_states.json",
):
    errors = []
    warnings = []

    path = Path(manifest_path)
    if not path.exists():
        errors.append(f"Manifest file not found: {manifest_path}")
        return {"ok": False, "errors": errors, "warnings": warnings}

    try:
        payload = _read_json(path)
    except Exception as exc:
        errors.append(f"Manifest read failed: {exc}")
        return {"ok": False, "errors": errors, "warnings": warnings}

    manifest = payload.get("manifest", {}) if isinstance(payload, dict) else {}
    if not isinstance(manifest, dict):
        errors.append("Top-level 'manifest' object is missing or invalid.")
        return {"ok": False, "errors": errors, "warnings": warnings}

    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        errors.append("'manifest.sources' must be an array.")
        return {"ok": False, "errors": errors, "warnings": warnings}

    key_to_path = {}
    for idx, entry in enumerate(sources):
        key = ""
        clip_path = ""
        loop_value = None
        if isinstance(entry, str):
            clip_path = entry.strip().replace("\\", "/")
            key = alias_animation_key(Path(clip_path).stem)
        elif isinstance(entry, dict):
            key = normalize_anim_key(
                entry.get("key") or entry.get("state") or entry.get("id") or ""
            )
            clip_path = str(
                entry.get("path") or entry.get("file") or entry.get("src") or ""
            ).strip().replace("\\", "/")
            loop_value = entry.get("loop", None)
            if not key and clip_path:
                key = alias_animation_key(Path(clip_path).stem)
        else:
            warnings.append(f"sources[{idx}] ignored: unsupported entry type.")
            continue

        if not key:
            errors.append(f"sources[{idx}] missing key.")
            continue
        if not clip_path:
            errors.append(f"sources[{idx}] missing path for key '{key}'.")
            continue
        if key in key_to_path:
            errors.append(
                f"Duplicate source key '{key}' -> '{clip_path}' and '{key_to_path[key]}'"
            )
            continue
        key_to_path[key] = clip_path
        if not Path(clip_path).exists():
            errors.append(f"Missing file for key '{key}': {clip_path}")
        if loop_value is not None and not isinstance(loop_value, bool):
            warnings.append(f"Key '{key}' has non-boolean loop value: {loop_value!r}")

    player_map = payload.get("player", {}) if isinstance(payload, dict) else {}
    if not isinstance(player_map, dict):
        errors.append("Top-level 'player' mapping must be an object.")
        player_map = {}

    state_names = set()
    state_file = Path(state_path)
    if state_file.exists():
        try:
            states_payload = _read_json(state_file)
            states = states_payload.get("states", []) if isinstance(states_payload, dict) else []
            for st in states:
                if isinstance(st, dict):
                    name = normalize_anim_key(st.get("name"))
                    if name:
                        state_names.add(name)
        except Exception as exc:
            warnings.append(f"Could not parse state definitions '{state_path}': {exc}")
    else:
        warnings.append(f"State file not found: {state_path}")

    for state, clips in player_map.items():
        state_key = normalize_anim_key(state)
        if state_names and state_key not in state_names:
            warnings.append(f"'player.{state_key}' has no matching state in '{state_path}'.")
        if not isinstance(clips, list) or not clips:
            errors.append(f"'player.{state_key}' must be a non-empty list.")
            continue
        for clip_key in clips:
            token = normalize_anim_key(clip_key)
            if not token:
                errors.append(f"'player.{state_key}' contains empty clip token.")
                continue
            if token in BASE_RUNTIME_KEYS:
                continue
            if token not in key_to_path:
                errors.append(
                    f"'player.{state_key}' references missing manifest key '{token}'."
                )

    ok = len(errors) == 0
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "manifest_source_count": len(key_to_path),
        "player_state_count": len(player_map),
    }
