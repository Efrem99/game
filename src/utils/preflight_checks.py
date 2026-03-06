"""Startup preflight checks: animation integrity + visual asset health."""

import json
from datetime import datetime, timezone
from pathlib import Path

from entities.animation_manifest import (
    BASE_RUNTIME_KEYS,
    normalize_anim_key,
    validate_player_manifest,
)
from entities.player_animation_config import STATE_ANIM_FALLBACK
from utils.runtime_paths import is_user_data_mode, runtime_file


def _safe_read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _safe_write_text(path, content):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(str(content), encoding="utf-8")
    except Exception:
        pass


def _runtime_log_path(project_root, filename):
    if is_user_data_mode():
        return runtime_file("logs", str(filename))
    return Path(project_root) / "logs" / str(filename)


def run_animation_preflight(project_root):
    root = Path(project_root)
    manifest_path = root / "data" / "actors" / "player_animations.json"
    states_path = root / "data" / "states" / "player_states.json"

    result = validate_player_manifest(
        manifest_path=str(manifest_path),
        state_path=str(states_path),
    )
    errors = list(result.get("errors", []) or [])
    warnings = list(result.get("warnings", []) or [])

    manifest_payload = _safe_read_json(manifest_path)
    states_payload = _safe_read_json(states_path)

    sources = (
        manifest_payload.get("manifest", {}).get("sources", [])
        if isinstance(manifest_payload, dict)
        else []
    )
    source_keys = set(BASE_RUNTIME_KEYS)
    if isinstance(sources, list):
        for entry in sources:
            if isinstance(entry, dict):
                key = normalize_anim_key(entry.get("key") or entry.get("state") or entry.get("id") or "")
                if key:
                    source_keys.add(key)

    player_map = manifest_payload.get("player", {}) if isinstance(manifest_payload, dict) else {}
    if not isinstance(player_map, dict):
        player_map = {}

    state_names = []
    states = states_payload.get("states", []) if isinstance(states_payload, dict) else []
    if isinstance(states, list):
        for st in states:
            if not isinstance(st, dict):
                continue
            name = normalize_anim_key(st.get("name"))
            if name:
                state_names.append(name)

    unresolved_states = []
    missing_mapping_states = []
    for state in state_names:
        mapped = player_map.get(state, [])
        mapped_ok = False
        if isinstance(mapped, list) and mapped:
            for token in mapped:
                norm = normalize_anim_key(token)
                if norm in source_keys:
                    mapped_ok = True
                    break
        else:
            missing_mapping_states.append(state)

        fallback_tokens = STATE_ANIM_FALLBACK.get(state, [])
        fallback_ok = False
        if isinstance(fallback_tokens, list):
            for token in fallback_tokens:
                norm = normalize_anim_key(token)
                if norm in source_keys:
                    fallback_ok = True
                    break

        if not mapped_ok and not fallback_ok:
            unresolved_states.append(state)

    if missing_mapping_states:
        warnings.append(
            "States without direct manifest mapping: "
            + ", ".join(sorted(missing_mapping_states))
        )
    if unresolved_states:
        errors.append(
            "States with no resolvable direct/fallback animation source: "
            + ", ".join(sorted(unresolved_states))
        )

    report = {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "state_count": len(state_names),
        "manifest_source_count": int(result.get("manifest_source_count", 0) or 0),
        "unresolved_state_count": len(unresolved_states),
    }

    report_md = [
        "# Animation Preflight",
        "",
        f"- OK: `{report['ok']}`",
        f"- States: `{report['state_count']}`",
        f"- Sources: `{report['manifest_source_count']}`",
        f"- Unresolved states: `{report['unresolved_state_count']}`",
        "",
        "## Errors",
    ]
    if errors:
        report_md.extend([f"- {item}" for item in errors])
    else:
        report_md.append("- None")
    report_md.extend(["", "## Warnings"])
    if warnings:
        report_md.extend([f"- {item}" for item in warnings])
    else:
        report_md.append("- None")

    _safe_write_text(_runtime_log_path(root, "animation_preflight.json"), json.dumps(report, ensure_ascii=False, indent=2))
    _safe_write_text(_runtime_log_path(root, "animation_preflight.md"), "\n".join(report_md))
    return report


def run_visual_asset_preflight(project_root):
    root = Path(project_root)
    scan_roots = [root / "assets" / "models", root / "models"]
    model_ext = {".gltf", ".glb", ".fbx", ".obj", ".bam"}

    model_files = []
    zero_byte = []
    missing_texture_refs = []
    gltf_parse_fail = []

    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in model_ext:
                continue
            model_files.append(path)
            try:
                if path.stat().st_size <= 0:
                    zero_byte.append(path.relative_to(root).as_posix())
            except Exception:
                continue

            if path.suffix.lower() != ".gltf":
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                gltf_parse_fail.append(f"{path.relative_to(root).as_posix()}: {exc}")
                continue

            images = payload.get("images", [])
            if not isinstance(images, list):
                continue
            for img in images:
                if not isinstance(img, dict):
                    continue
                uri = str(img.get("uri", "") or "").strip().replace("\\", "/")
                if not uri or uri.startswith("data:"):
                    continue
                tex_path = (path.parent / uri).resolve()
                if not tex_path.exists():
                    missing_texture_refs.append(
                        f"{path.relative_to(root).as_posix()} -> {uri}"
                    )

    errors = []
    warnings = []
    if zero_byte:
        errors.append(f"Zero-byte model files: {len(zero_byte)}")
    if gltf_parse_fail:
        warnings.append(f"GLTF parse issues: {len(gltf_parse_fail)}")
    if missing_texture_refs:
        warnings.append(f"Missing GLTF texture references: {len(missing_texture_refs)}")

    report = {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "model_file_count": len(model_files),
        "zero_byte_files": zero_byte[:200],
        "gltf_parse_issues": gltf_parse_fail[:200],
        "missing_texture_refs": missing_texture_refs[:400],
    }

    report_md = [
        "# Visual Asset Preflight",
        "",
        f"- OK: `{report['ok']}`",
        f"- Model files scanned: `{report['model_file_count']}`",
        f"- Zero-byte files: `{len(zero_byte)}`",
        f"- GLTF parse issues: `{len(gltf_parse_fail)}`",
        f"- Missing texture refs: `{len(missing_texture_refs)}`",
        "",
        "## Errors",
    ]
    if errors:
        report_md.extend([f"- {item}" for item in errors])
    else:
        report_md.append("- None")
    report_md.extend(["", "## Warnings"])
    if warnings:
        report_md.extend([f"- {item}" for item in warnings])
    else:
        report_md.append("- None")

    if zero_byte:
        report_md.extend(["", "## Zero-byte Files"])
        report_md.extend([f"- `{item}`" for item in zero_byte[:40]])
    if missing_texture_refs:
        report_md.extend(["", "## Missing Texture References"])
        report_md.extend([f"- `{item}`" for item in missing_texture_refs[:80]])

    _safe_write_text(_runtime_log_path(root, "visual_asset_preflight.json"), json.dumps(report, ensure_ascii=False, indent=2))
    _safe_write_text(_runtime_log_path(root, "visual_asset_preflight.md"), "\n".join(report_md))
    return report


def run_player_model_preflight(project_root):
    root = Path(project_root)
    cfg_path = root / "data" / "actors" / "player.json"
    payload = _safe_read_json(cfg_path)
    player = payload.get("player", payload) if isinstance(payload, dict) else {}
    if not isinstance(player, dict):
        player = {}

    def _norm(token):
        return str(token or "").strip().replace("\\", "/")

    def _as_path(token):
        raw = _norm(token)
        if not raw:
            return None
        p = Path(raw)
        if p.is_absolute():
            return p
        return (root / raw).resolve()

    primary = _norm(player.get("model"))
    fallback = _norm(player.get("fallback_model"))
    raw_candidates = player.get("model_candidates")

    candidates = []

    def _push(item):
        tok = _norm(item)
        if tok and tok not in candidates:
            candidates.append(tok)

    if isinstance(raw_candidates, list):
        for item in raw_candidates:
            _push(item)
    if primary:
        if primary in candidates:
            candidates.remove(primary)
        candidates.insert(0, primary)
    if fallback:
        _push(fallback)

    existing = []
    missing = []
    for token in candidates:
        p = _as_path(token)
        if p is not None and p.exists():
            existing.append(token)
        else:
            missing.append(token)

    errors = []
    warnings = []
    if not candidates:
        errors.append("Player model config has no candidates (model/model_candidates are empty).")
    if primary and primary in missing:
        warnings.append(f"Primary player model is missing: {primary}. Runtime will use fallback candidate.")
    if fallback and fallback in missing:
        warnings.append(f"Fallback player model is missing: {fallback}.")
    if candidates and not existing:
        errors.append("No existing player model candidate found on disk.")

    report = {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "primary_model": primary,
        "fallback_model": fallback,
        "candidate_count": len(candidates),
        "existing_candidates": existing,
        "missing_candidates": missing,
    }

    report_md = [
        "# Player Model Preflight",
        "",
        f"- OK: `{report['ok']}`",
        f"- Candidate count: `{report['candidate_count']}`",
        f"- Existing candidates: `{len(existing)}`",
        f"- Missing candidates: `{len(missing)}`",
        f"- Primary: `{primary or '-'}`",
        f"- Fallback: `{fallback or '-'}`",
        "",
        "## Errors",
    ]
    if errors:
        report_md.extend([f"- {item}" for item in errors])
    else:
        report_md.append("- None")
    report_md.extend(["", "## Warnings"])
    if warnings:
        report_md.extend([f"- {item}" for item in warnings])
    else:
        report_md.append("- None")
    if existing:
        report_md.extend(["", "## Existing Candidates"])
        report_md.extend([f"- `{item}`" for item in existing[:40]])
    if missing:
        report_md.extend(["", "## Missing Candidates"])
        report_md.extend([f"- `{item}`" for item in missing[:40]])

    _safe_write_text(_runtime_log_path(root, "player_model_preflight.json"), json.dumps(report, ensure_ascii=False, indent=2))
    _safe_write_text(_runtime_log_path(root, "player_model_preflight.md"), "\n".join(report_md))
    return report


def run_startup_preflight(project_root, logger=None, strict=False):
    root = Path(project_root)
    started = datetime.now(timezone.utc).isoformat()
    animation = run_animation_preflight(root)
    visuals = run_visual_asset_preflight(root)
    player_model = run_player_model_preflight(root)

    errors = []
    errors.extend(animation.get("errors", []))
    errors.extend(visuals.get("errors", []))
    errors.extend(player_model.get("errors", []))
    warnings = []
    warnings.extend(animation.get("warnings", []))
    warnings.extend(visuals.get("warnings", []))
    warnings.extend(player_model.get("warnings", []))

    report = {
        "ok": len(errors) == 0,
        "strict": bool(strict),
        "started_at_utc": started,
        "animation": animation,
        "visuals": visuals,
        "player_model": player_model,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }

    _safe_write_text(_runtime_log_path(root, "startup_preflight.json"), json.dumps(report, ensure_ascii=False, indent=2))

    if logger:
        logger.info(
            f"[Preflight] animation_ok={animation.get('ok')} visuals_ok={visuals.get('ok')} "
            f"player_model_ok={player_model.get('ok')} "
            f"errors={len(errors)} warnings={len(warnings)}"
        )
        if warnings:
            logger.warning(f"[Preflight] Warnings detected: {len(warnings)} (see logs/*preflight*.md)")
        if errors:
            logger.error(f"[Preflight] Errors detected: {len(errors)} (see logs/*preflight*.md)")

    return report
