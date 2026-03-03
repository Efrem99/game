"""Static readiness checks for Shervard hero asset package."""

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = ROOT / "assets" / "models" / "hero" / "sherward"
MODEL_PATH = MODEL_ROOT / "sherward.glb"
TEXTURE_ROOT = MODEL_ROOT / "textures"
PLAYER_CFG = ROOT / "data" / "actors" / "player.json"
PROFILE_JSON = ROOT / "data" / "characters" / "sherward_profile.json"
PROFILE_MD = ROOT / "data" / "characters" / "SHERWARD_REALISM_SPEC.md"
PIPELINE_MD = ROOT / "models" / "SHERWARD_BLENDER_PIPELINE.md"


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _check_player_config():
    report = {"ok": False, "errors": [], "warnings": [], "resolved_model_candidates": []}
    data = _read_json(PLAYER_CFG)
    player = data.get("player", data) if isinstance(data, dict) else {}
    if not isinstance(player, dict):
        report["errors"].append("Invalid player config payload.")
        return report

    model = str(player.get("model", "") or "").strip()
    model_candidates = player.get("model_candidates")
    fallback_model = str(player.get("fallback_model", "") or "").strip()

    candidates = []
    if isinstance(model_candidates, list):
        for item in model_candidates:
            token = str(item or "").strip()
            if token and token not in candidates:
                candidates.append(token)
    if model and model not in candidates:
        candidates.insert(0, model)
    if fallback_model and fallback_model not in candidates:
        candidates.append(fallback_model)

    report["resolved_model_candidates"] = list(candidates)
    has_sherward = any("hero/sherward/sherward.glb" in c.replace("\\", "/").lower() for c in candidates)
    has_fallback = any("xbot/xbot.glb" in c.replace("\\", "/").lower() for c in candidates)
    if not has_sherward:
        report["errors"].append("Player config has no Shervard model candidate.")
    if not has_fallback:
        report["warnings"].append("Player config has no explicit Xbot fallback candidate.")

    report["ok"] = len(report["errors"]) == 0
    return report


def _check_model_files():
    report = {
        "ok": False,
        "errors": [],
        "warnings": [],
        "model_exists": MODEL_PATH.exists(),
        "model_size_bytes": 0,
        "texture_files_found": [],
        "texture_recommendations_missing": [],
    }

    if MODEL_PATH.exists():
        try:
            report["model_size_bytes"] = int(MODEL_PATH.stat().st_size)
        except Exception:
            report["model_size_bytes"] = 0
        if report["model_size_bytes"] <= 0:
            report["errors"].append(f"Model is zero-byte: {MODEL_PATH.relative_to(ROOT).as_posix()}")
    else:
        report["errors"].append(f"Missing model: {MODEL_PATH.relative_to(ROOT).as_posix()}")

    recommended = [
        "sherward_albedo.png",
        "sherward_normal.png",
        "sherward_roughness.png",
        "sherward_metallic.png",
        "sherward_ao.png",
    ]
    for name in recommended:
        p = TEXTURE_ROOT / name
        if p.exists():
            report["texture_files_found"].append(p.relative_to(ROOT).as_posix())
        else:
            report["texture_recommendations_missing"].append(p.relative_to(ROOT).as_posix())

    if report["texture_recommendations_missing"]:
        report["warnings"].append(
            "Recommended textures missing: " + ", ".join(report["texture_recommendations_missing"][:5])
        )

    report["ok"] = len(report["errors"]) == 0
    return report


def _check_docs():
    report = {"ok": False, "errors": [], "warnings": []}
    for path in (PROFILE_JSON, PROFILE_MD, PIPELINE_MD):
        if not path.exists():
            report["errors"].append(f"Missing doc/profile file: {path.relative_to(ROOT).as_posix()}")
    report["ok"] = len(report["errors"]) == 0
    return report


def _write_reports(payload):
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    json_path = logs_dir / "sherward_asset_report.json"
    md_path = logs_dir / "sherward_asset_report.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Shervard Asset Report",
        "",
        f"- Generated: `{payload.get('generated_at_utc', '-')}`",
        f"- Overall OK: `{payload.get('ok', False)}`",
        "",
        "## Player Config",
        f"- OK: `{payload.get('player_config', {}).get('ok', False)}`",
        f"- Candidates: `{len(payload.get('player_config', {}).get('resolved_model_candidates', []))}`",
        "",
        "## Model Slot",
        f"- OK: `{payload.get('model_files', {}).get('ok', False)}`",
        f"- Model exists: `{payload.get('model_files', {}).get('model_exists', False)}`",
        f"- Model size bytes: `{payload.get('model_files', {}).get('model_size_bytes', 0)}`",
        "",
        "## Docs/Profile",
        f"- OK: `{payload.get('docs', {}).get('ok', False)}`",
    ]

    for section in ("player_config", "model_files", "docs"):
        block = payload.get(section, {})
        errors = block.get("errors", [])
        warnings = block.get("warnings", [])
        if errors:
            md.extend(["", f"### {section} errors"])
            md.extend([f"- {item}" for item in errors[:80]])
        if warnings:
            md.extend(["", f"### {section} warnings"])
            md.extend([f"- {item}" for item in warnings[:80]])

    md_path.write_text("\n".join(md), encoding="utf-8")


def main():
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "player_config": _check_player_config(),
        "model_files": _check_model_files(),
        "docs": _check_docs(),
    }
    payload["ok"] = (
        bool(payload["player_config"].get("ok"))
        and bool(payload["model_files"].get("ok"))
        and bool(payload["docs"].get("ok"))
    )

    _write_reports(payload)
    print(f"[Sherward] OK={payload['ok']}")
    print(
        "[Sherward] player_config_ok=%s model_ok=%s docs_ok=%s"
        % (
            payload["player_config"].get("ok"),
            payload["model_files"].get("ok"),
            payload["docs"].get("ok"),
        )
    )
    print("[Sherward] Report: logs/sherward_asset_report.md")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
