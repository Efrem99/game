"""Runtime-oriented player animation coverage report.

Loads the current player model + base anims, attaches optional clips from
`data/actors/player_animations.json`, resolves clip mapping per state, and
reports missing/fallback/shared coverage.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from direct.actor.Actor import Actor
from panda3d.core import Filename, getModelPath


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.animation_manifest import (  # noqa: E402
    alias_animation_key,
    load_player_manifest_sources,
)
from entities.player_animation_config import (  # noqa: E402
    ANIM_TOKEN_ALIASES,
    STATE_ANIM_FALLBACK,
)


def _safe_print(message):
    text = str(message)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalize_anim_key(token):
    return "".join(ch for ch in str(token or "").lower() if ch.isalnum())


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rel(path: Path):
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def _player_cfg():
    path = ROOT / "data" / "actors" / "player.json"
    if not path.exists():
        return {}
    payload = _read_json(path)
    nested = payload.get("player", payload) if isinstance(payload, dict) else {}
    return nested if isinstance(nested, dict) else {}


def _resolve_model_candidates(cfg):
    candidates = []

    def _add(token):
        value = str(token or "").strip().replace("\\", "/")
        if value and value not in candidates:
            candidates.append(value)

    raw_candidates = cfg.get("model_candidates")
    if isinstance(raw_candidates, list):
        for item in raw_candidates:
            _add(item)

    raw_model = str(cfg.get("model", "") or "").strip()
    raw_fallback = str(cfg.get("fallback_model", "") or "").strip()

    for raw in (raw_model, raw_fallback):
        if not raw:
            continue
        _add(raw)
        if raw.startswith("./"):
            _add(raw[2:])
        if raw.startswith("models/"):
            _add(f"assets/{raw}")
        if not raw.startswith("assets/"):
            _add(f"assets/{raw}")

    _add("assets/models/xbot/Xbot.glb")
    existing = [token for token in candidates if (ROOT / token).exists()]
    return existing if existing else candidates


def _resolve_base_anims(cfg):
    defaults = {
        "idle": "assets/models/xbot/idle.glb",
        "walk": "assets/models/xbot/walk.glb",
        "run": "assets/models/xbot/run.glb",
    }
    raw = cfg.get("base_anims")
    if not isinstance(raw, dict):
        return defaults
    resolved = {}
    for key, value in raw.items():
        clip_key = str(key or "").strip().lower()
        clip_path = str(value or "").strip().replace("\\", "/")
        if clip_key and clip_path:
            resolved[clip_key] = clip_path
    return resolved if resolved else defaults


def _load_actor_animation_overrides():
    path = ROOT / "data" / "actors" / "player_animations.json"
    if not path.exists():
        return {}

    payload = _read_json(path)
    player_map = payload.get("player", {}) if isinstance(payload, dict) else {}
    if not isinstance(player_map, dict):
        return {}

    generic_tags = {
        "combat",
        "parkour",
        "magic",
        "shield",
        "social",
        "enemy",
        "character",
        "player",
    }

    mapping = {}
    for state_name, raw_value in player_map.items():
        state_key = str(state_name or "").strip().lower()
        if not state_key:
            continue

        candidates = []
        if isinstance(raw_value, str):
            candidates.append(raw_value)
        elif isinstance(raw_value, list):
            for item in raw_value:
                if isinstance(item, str):
                    candidates.append(item)
        elif isinstance(raw_value, dict):
            for field in ("animation", "clip", "name", "id"):
                value = raw_value.get(field)
                if isinstance(value, str):
                    candidates.append(value)
            aliases = raw_value.get("aliases")
            if isinstance(aliases, list):
                for item in aliases:
                    if isinstance(item, str):
                        candidates.append(item)

        cleaned = []
        seen = set()
        for candidate in candidates:
            token = str(candidate or "").strip()
            if not token:
                continue
            marker = token.lower()
            if marker in seen:
                continue
            seen.add(marker)
            cleaned.append(token)

        filtered = []
        for token in cleaned:
            compact = _normalize_anim_key(token)
            if compact in generic_tags:
                continue
            filtered.append(token)

        usable = filtered if filtered else cleaned
        if usable:
            mapping[state_key] = usable
    return mapping


def _load_state_anim_tokens():
    path = ROOT / "data" / "states" / "player_states.json"
    if not path.exists():
        return {}, []
    payload = _read_json(path)
    states = payload.get("states", []) if isinstance(payload, dict) else []
    mapping = {}
    ordered_states = []
    for entry in states:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip().lower()
        anim = str(entry.get("animation", "")).strip()
        if not name:
            continue
        ordered_states.append(name)
        if anim:
            mapping[name] = anim
    return mapping, ordered_states


def _collect_optional_sources():
    mapping, strict_mode, diagnostics = load_player_manifest_sources(
        str(ROOT / "data" / "actors" / "player_animations.json"),
        require_existing_files=True,
    )
    errors = [d for d in diagnostics if "Missing animation file" in d or "Failed" in d]
    warnings = [d for d in diagnostics if d not in errors]

    candidates = dict(mapping)
    if not strict_mode:
        for root in (
            ROOT / "assets" / "anims",
            ROOT / "assets" / "models" / "xbot",
        ):
            if not root.exists():
                continue
            for path in root.glob("*"):
                if path.suffix.lower() not in {".glb", ".gltf", ".bam", ".fbx"}:
                    continue
                if path.stem.lower() in {"xbot", "character"}:
                    continue
                key = alias_animation_key(path.stem)
                if not key or key in {"idle", "walk", "run"}:
                    continue
                candidates.setdefault(key, _rel(path))

    return candidates, strict_mode, warnings, errors


def _configure_model_path():
    model_path = getModelPath()
    roots = [
        ROOT,
        ROOT / "assets",
        ROOT / "assets" / "models",
        ROOT / "assets" / "anims",
    ]
    for path in roots:
        try:
            model_path.appendDirectory(Filename.from_os_specific(str(path)))
        except Exception:
            continue


def _to_panda_filename(token):
    raw = str(token or "").strip().replace("\\", "/")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / raw
    return Filename.from_os_specific(str(path))


def _iter_anim_candidates(state_name, state_overrides, state_tokens):
    state = str(state_name or "idle").strip()
    state_key = state.lower()
    candidates = []

    for token in state_overrides.get(state_key, []):
        candidates.append((token, "player_animations"))

    state_token = state_tokens.get(state_key)
    if state_token:
        candidates.append((state_token, "player_states"))

    candidates.append((state, "state_name"))
    for token in STATE_ANIM_FALLBACK.get(state_key, []):
        candidates.append((token, "state_fallback"))

    expanded = []
    for token, source in candidates:
        expanded.append((token, source))
        alias_list = ANIM_TOKEN_ALIASES.get(_normalize_anim_key(token), [])
        for alias_token in alias_list:
            expanded.append((alias_token, f"alias:{source}"))

    expanded.extend([("idle", "global_fallback"), ("walk", "global_fallback"), ("run", "global_fallback")])

    dedup = []
    seen = set()
    for token, source in expanded:
        key = str(token or "").strip()
        if not key:
            continue
        marker = key.lower()
        if marker in seen:
            continue
        seen.add(marker)
        dedup.append((key, source))
    return dedup


def _resolve_clip_for_state(state_name, available_anims, state_overrides, state_tokens):
    available = list(available_anims)
    available_lower = {name.lower(): name for name in available}
    available_norm = {_normalize_anim_key(name): name for name in available}

    for candidate, source in _iter_anim_candidates(state_name, state_overrides, state_tokens):
        if candidate in available_anims:
            return candidate, source, candidate

        lower = candidate.lower()
        if lower in available_lower:
            return available_lower[lower], source, candidate

        normalized = _normalize_anim_key(candidate)
        if normalized in available_norm:
            return available_norm[normalized], source, candidate

    return None, None, None


def _write_reports(report):
    out_json = ROOT / "logs" / "player_anim_runtime_report.json"
    out_md = ROOT / "logs" / "player_anim_runtime_report.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Player Animation Runtime Report",
        "",
        f"- Generated: `{report.get('generated_at_utc', '-')}`",
        f"- Strict manifest mode: `{report.get('strict_manifest_mode', False)}`",
        f"- Model used: `{report.get('model_used', '-')}`",
        f"- Optional animations loaded: `{report.get('optional_loaded', 0)}`",
        f"- States total: `{report.get('summary', {}).get('states_total', 0)}`",
        f"- OK: `{report.get('summary', {}).get('ok', 0)}`",
        f"- Fallback: `{report.get('summary', {}).get('fallback', 0)}`",
        f"- Missing: `{report.get('summary', {}).get('missing', 0)}`",
        f"- Unplayable: `{report.get('summary', {}).get('unplayable', 0)}`",
        "",
        "## State Coverage",
        "",
        "| State | Status | Clip | Source | Candidate | Playable |",
        "|---|---|---|---|---|---|",
    ]
    for row in report.get("states", []):
        lines.append(
            f"| {row.get('state', '-')} | {row.get('status', '-')} | "
            f"{row.get('clip', '-')} | {row.get('source', '-')} | "
            f"{row.get('candidate', '-')} | {row.get('playable', '-')} |"
        )

    shared = report.get("shared_clips", {})
    if shared:
        lines.extend(["", "## Shared Clips"])
        for clip, states in sorted(shared.items()):
            lines.append(f"- `{clip}`: {', '.join(states)}")

    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        for item in report["warnings"]:
            lines.append(f"- {item}")
    if report.get("errors"):
        lines.extend(["", "## Errors"])
        for item in report["errors"]:
            lines.append(f"- {item}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    _configure_model_path()
    cfg = _player_cfg()
    base_anims = _resolve_base_anims(cfg)
    base_anims_runtime = {key: _to_panda_filename(value) for key, value in base_anims.items()}
    model_candidates = _resolve_model_candidates(cfg)

    if not model_candidates:
        print("[AnimRuntime] ERROR: no player model candidates found.")
        return 1

    model_used = ""
    actor = None
    load_errors = []
    for token in model_candidates:
        try:
            actor = Actor(_to_panda_filename(token), base_anims_runtime)
            model_used = token
            break
        except Exception as exc:
            load_errors.append(f"{token}: {exc}")

    if actor is None:
        _safe_print("[AnimRuntime] ERROR: failed to load actor model.")
        for item in load_errors:
            _safe_print(f"[AnimRuntime] {item}")
        return 1

    optional_sources, strict_mode, warnings, errors = _collect_optional_sources()
    loaded_count = 0
    for key, rel_path in optional_sources.items():
        try:
            actor.loadAnims({key: _to_panda_filename(rel_path)})
            loaded_count += 1
        except Exception as exc:
            warnings.append(f"Failed to load optional anim '{key}' ({rel_path}): {exc}")

    state_tokens, state_order = _load_state_anim_tokens()
    state_overrides = _load_actor_animation_overrides()
    available = {str(name) for name in actor.getAnimNames()}
    _safe_print(f"[AnimRuntime] AVAILABLE TRACKS: {sorted(available)}")

    rows = []
    clip_usage = defaultdict(list)
    counts = {"ok": 0, "fallback": 0, "missing": 0, "unplayable": 0}

    for state in state_order:
        clip, source, candidate = _resolve_clip_for_state(state, available, state_overrides, state_tokens)
        playable = False
        if clip:
            try:
                actor.getDuration(clip)
                actor.pose(clip, 0)
                playable = True
            except Exception:
                playable = False

        if not clip:
            status = "MISSING"
            counts["missing"] += 1
        elif (source or "").startswith("state_fallback") or (source or "").startswith("global_fallback"):
            status = "FALLBACK"
            counts["fallback"] += 1
        elif (source or "").startswith("alias:state_fallback") or (source or "").startswith("alias:global_fallback"):
            status = "FALLBACK"
            counts["fallback"] += 1
        else:
            status = "OK"
            counts["ok"] += 1

        if clip and not playable:
            counts["unplayable"] += 1
            status = "UNPLAYABLE"

        if clip:
            clip_usage[clip].append(state)

        rows.append(
            {
                "state": state,
                "status": status,
                "clip": clip or "-",
                "source": source or "-",
                "candidate": candidate or "-",
                "playable": playable,
            }
        )

    shared_clips = {clip: states for clip, states in clip_usage.items() if len(states) > 1}

    report = {
        "generated_at_utc": _utc_now(),
        "strict_manifest_mode": strict_mode,
        "model_used": model_used,
        "optional_loaded": loaded_count,
        "base_anim_count": len(base_anims),
        "available_anim_count": len(available),
        "summary": {
            "states_total": len(state_order),
            "ok": counts["ok"],
            "fallback": counts["fallback"],
            "missing": counts["missing"],
            "unplayable": counts["unplayable"],
            "shared_clips": len(shared_clips),
        },
        "states": rows,
        "shared_clips": shared_clips,
        "warnings": warnings,
        "errors": errors,
    }
    _write_reports(report)

    _safe_print(
        "[AnimRuntime] states={total} ok={ok} fallback={fb} missing={miss} unplayable={un}".format(
            total=report["summary"]["states_total"],
            ok=counts["ok"],
            fb=counts["fallback"],
            miss=counts["missing"],
            un=counts["unplayable"],
        )
    )
    _safe_print(f"[AnimRuntime] model={model_used} available={len(available)} optional_loaded={loaded_count}")
    _safe_print("[AnimRuntime] Report: logs/player_anim_runtime_report.md")

    if counts["missing"] > 0 or counts["unplayable"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
