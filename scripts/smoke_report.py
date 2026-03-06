"""Static smoke checks for core content/config integrity (no game boot)."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.animation_manifest import validate_player_manifest  # noqa: E402
from utils.preflight_checks import run_startup_preflight  # noqa: E402


INCLUDE_EXT = {".py", ".json", ".md", ".h", ".hpp", ".cpp", ".c", ".glsl", ".vert", ".frag"}
EXCLUDE_DIRS = {".git", "__pycache__", "build", "build-cpp", "logs", "saves", ".venv", "venv"}


def _iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if {p.lower() for p in rel.parts}.intersection(EXCLUDE_DIRS):
            continue
        if path.suffix.lower() not in INCLUDE_EXT:
            continue
        yield path


def _count_lines(path):
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return 0
    return len(text.splitlines())


def _baseline_metrics():
    files = list(_iter_files())
    total_lines = 0
    for path in files:
        total_lines += _count_lines(path)
    return {"file_count": len(files), "total_lines": int(total_lines)}


def _validate_json_files(paths):
    errors = []
    for rel in paths:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"Missing JSON file: {rel}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            errors.append(f"JSON parse failed: {rel} -> {exc}")
    return errors


def _check_required_files(paths):
    missing = []
    for rel in paths:
        if not (ROOT / rel).exists():
            missing.append(rel)
    return missing


def _write_reports(report):
    report_json = ROOT / "logs" / "smoke_report.json"
    report_md = ROOT / "logs" / "smoke_report.md"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Smoke Report",
        "",
        f"- Generated: `{report.get('generated_at_utc', '-')}`",
        f"- Overall OK: `{report.get('ok', False)}`",
        "",
        "## Baseline",
        f"- Files: `{report.get('baseline', {}).get('file_count', 0)}`",
        f"- Total lines: `{report.get('baseline', {}).get('total_lines', 0)}`",
        "",
        "## Preflight",
        f"- Animation OK: `{report.get('preflight', {}).get('animation', {}).get('ok', False)}`",
        f"- Visual Assets OK: `{report.get('preflight', {}).get('visuals', {}).get('ok', False)}`",
        f"- Preflight errors: `{report.get('preflight', {}).get('error_count', 0)}`",
        f"- Preflight warnings: `{report.get('preflight', {}).get('warning_count', 0)}`",
        "",
        "## Manifest",
        f"- Manifest OK: `{report.get('manifest', {}).get('ok', False)}`",
        f"- Manifest errors: `{len(report.get('manifest', {}).get('errors', []))}`",
        "",
        "## JSON Integrity",
        f"- JSON errors: `{len(report.get('json_errors', []))}`",
        "",
        "## Required Files",
        f"- Missing required files: `{len(report.get('missing_required_files', []))}`",
    ]
    if report.get("json_errors"):
        md.extend(["", "### JSON Errors"])
        md.extend([f"- {item}" for item in report["json_errors"][:80]])
    if report.get("missing_required_files"):
        md.extend(["", "### Missing Files"])
        md.extend([f"- `{item}`" for item in report["missing_required_files"][:80]])
    if report.get("manifest", {}).get("errors"):
        md.extend(["", "### Manifest Errors"])
        md.extend([f"- {item}" for item in report["manifest"]["errors"][:80]])
    if report.get("manifest", {}).get("warnings"):
        md.extend(["", "### Manifest Warnings"])
        md.extend([f"- {item}" for item in report["manifest"]["warnings"][:80]])

    report_md.write_text("\n".join(md), encoding="utf-8")


def main():
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    baseline = _baseline_metrics()

    preflight = run_startup_preflight(ROOT, logger=None, strict=False)
    manifest = validate_player_manifest(
        manifest_path=str(ROOT / "data" / "actors" / "player_animations.json"),
        state_path=str(ROOT / "data" / "states" / "player_states.json"),
    )

    json_errors = _validate_json_files(
        [
            "data/camera_profiles.json",
            "data/cutscene_triggers.json",
            "data/audio/sound_config.json",
            "data/world_config.json",
            "data/world/layout.json",
            "data/logic/character_brain.json",
            "data/combat/styles.json",
            "data/vehicles/default.json",
            "data/vehicles/horse.json",
            "data/vehicles/carriage.json",
            "data/vehicles/ship.json",
            "data/sky_config.json",
            "data/actors/player_animations.json",
            "data/states/player_states.json",
        ]
    )
    missing_required_files = _check_required_files(
        [
            "launchers/tests/launcher_test_dragon.py",
            "launcher_test_hub.py",
            "launchers/tests/launcher_test_music.py",
            "launchers/tests/launcher_test_journal.py",
            "launchers/tests/launcher_test_mounts.py",
            "launchers/tests/launcher_test_skills.py",
            "launchers/tests/launcher_test_movement.py",
            "launchers/tests/launcher_test_parkour.py",
            "launchers/tests/launcher_test_flight.py",
            "launchers/tests/launcher_test_manifest.py",
            "launchers/tests/launcher_test_player_anim_runtime.py",
            "launchers/tests/launcher_test_baseline.py",
            "launchers/tests/launcher_test_smoke.py",
            "scripts/validate_player_manifest.py",
            "scripts/player_anim_runtime_report.py",
            "scripts/voice_dialog_report.py",
            "scripts/smoke_report.py",
            "scripts/baseline_report.py",
            "src/entities/character_brain.py",
            "src/managers/sky_manager.py",
            "src/managers/time_fx_manager.py",
            "data/world/layout.json",
            "data/logic/character_brain.json",
            "data/combat/styles.json",
            "data/vehicles/default.json",
            "data/vehicles/horse.json",
            "data/vehicles/carriage.json",
            "data/vehicles/ship.json",
        ]
    )

    ok = bool(preflight.get("ok", False)) and bool(manifest.get("ok", False))
    ok = ok and (len(json_errors) == 0) and (len(missing_required_files) == 0)
    report = {
        "generated_at_utc": generated,
        "ok": ok,
        "baseline": baseline,
        "preflight": preflight,
        "manifest": manifest,
        "json_errors": json_errors,
        "missing_required_files": missing_required_files,
    }
    _write_reports(report)

    print(f"[Smoke] OK={ok}")
    print(f"[Smoke] Baseline files={baseline['file_count']} lines={baseline['total_lines']}")
    print(
        f"[Smoke] preflight_errors={preflight.get('error_count', 0)} "
        f"manifest_errors={len(manifest.get('errors', []))} json_errors={len(json_errors)} "
        f"missing_files={len(missing_required_files)}"
    )
    print("[Smoke] Report: logs/smoke_report.md")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

