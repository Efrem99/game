#!/usr/bin/env python3
"""Generate book-vs-visual conformance report for one recorded gameplay run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.book_visual_conformance import (
    BOOK_LOCATION_PROFILES,
    evaluate_location_conformance,
    infer_canonical_locations_for_run,
    load_world_snapshot,
    read_docx_text,
)


def _safe_print(line: str, stream: str = "stdout") -> None:
    target = sys.stdout if stream == "stdout" else sys.stderr
    text = str(line)
    try:
        target.write(text + "\n")
    except UnicodeEncodeError:
        raw = (text + "\n").encode("utf-8", errors="replace")
        if stream == "stdout":
            sys.stdout.buffer.write(raw)
            sys.stdout.flush()
        else:
            sys.stderr.buffer.write(raw)
            sys.stderr.flush()


def _safe_load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _detect_default_book_docx() -> Optional[Path]:
    home = Path.home()
    candidates = [
        home / "OneDrive" / "Рабочий стол" / "все о Короле Волшебнике" / "текст" / "книга 1" / "Король Волшебник.docx",
        home / "Desktop" / "все о Короле Волшебнике" / "текст" / "книга 1" / "Король Волшебник.docx",
        home / "OneDrive" / "Desktop" / "all about king wizard" / "text" / "book 1" / "King Wizard.docx",
    ]
    for row in candidates:
        if row.exists():
            return row.resolve()
    return None


def _load_fallback_book_text(project_root: Path) -> str:
    chunks: List[str] = []
    opening = project_root / "data" / "story" / "opening_memory_package.json"
    bible = project_root / "data" / "story" / "STORY_BIBLE_V0_1.md"
    if opening.exists():
        try:
            payload = _safe_load_json(opening)
            for row in payload.get("voice_keys", []) if isinstance(payload.get("voice_keys"), list) else []:
                if isinstance(row, dict):
                    text = str(row.get("text", "") or "").strip()
                    if text:
                        chunks.append(text)
            for row in payload.get("story_beats", []) if isinstance(payload.get("story_beats"), list) else []:
                if isinstance(row, dict):
                    text = str(row.get("label", "") or "").strip()
                    if text:
                        chunks.append(text)
        except Exception:
            pass
    if bible.exists():
        try:
            chunks.append(bible.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass
    return "\n".join(chunks).strip()


def _resolve_report_paths(metadata_path: Path) -> Dict[str, Path]:
    name = metadata_path.name
    if name.endswith(".metadata.json"):
        base = name[: -len(".metadata.json")]
    else:
        base = metadata_path.stem
    return {
        "json": metadata_path.with_name(f"{base}.book.json"),
        "md": metadata_path.with_name(f"{base}.book.md"),
    }


def _render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Book Visual Conformance Report",
        "",
        "## Run",
        f"- Metadata: `{report.get('metadata_path', '')}`",
        f"- Scenario: `{report.get('scenario_name', '')}`",
        f"- Bot plan: `{report.get('plan_name', '')}`",
        f"- Launcher location: `{report.get('launcher_location', '') or '-'}`",
        f"- Book source: `{report.get('book_docx_path', '') or 'none'}`",
        f"- Strict book mode: `{str(bool(report.get('strict_book', False))).lower()}`",
        f"- Overall status: `{report.get('status', '')}`",
        f"- Reason: `{report.get('reason', '')}`",
        "",
        "## Canonical Locations In Run",
    ]

    canonical_locations = report.get("canonical_locations", [])
    if not canonical_locations:
        lines.append("- none")
    else:
        for row in canonical_locations:
            lines.append(f"- `{row}`")

    lines.extend(["", "## Findings"])
    findings = report.get("location_results", [])
    if not findings:
        lines.append("- No canonical location checks were required for this run.")
    else:
        for item in findings:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", item.get("canonical_location", "")))
            status = str(item.get("status", "unknown")).upper()
            lines.append(f"- [{status}] {title}")
            book = item.get("book", {}) if isinstance(item.get("book"), dict) else {}
            lines.append(
                f"  book: aliases={book.get('alias_total', 0)} cues={book.get('cue_present', 0)}/{book.get('min_cues', 0)}"
            )
            excerpt = str(book.get("excerpt", "") or "").strip()
            if excerpt:
                lines.append(f"  excerpt: `{excerpt}`")
            world_checks = item.get("world_checks", [])
            failed_checks = [row for row in world_checks if isinstance(row, dict) and not bool(row.get("ok", False))]
            if not failed_checks:
                lines.append("  world: all checks passed")
            else:
                for row in failed_checks:
                    lines.append(f"  world fail: `{row.get('id', '')}` - {row.get('details', '')}")

    lines.extend(["", "## Notes"])
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build book-vs-visual conformance report for one metadata run.")
    parser.add_argument("--metadata", required=True, help="Path to scenario metadata JSON.")
    parser.add_argument("--scenario-file", default="", help="Path to scenarios.json (optional).")
    parser.add_argument("--book-docx", default="", help="Path to main book .docx.")
    parser.add_argument("--project-root", default="", help="Project root. Defaults to script root parent.")
    parser.add_argument("--strict-book", action="store_true", help="Fail when .docx source is not available.")
    parser.add_argument("--output-json", default="", help="Custom output json path.")
    parser.add_argument("--output-md", default="", help="Custom output markdown path.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    metadata_path = Path(args.metadata).expanduser().resolve()
    if not metadata_path.exists():
        _safe_print(f"[BookConformance] metadata not found: {metadata_path}", stream="stderr")
        return 2

    project_root = Path(args.project_root).expanduser().resolve() if str(args.project_root or "").strip() else ROOT
    metadata = _safe_load_json(metadata_path)
    scenario_name = str(metadata.get("scenario_name", "") or "").strip()

    scenario_file = (
        Path(args.scenario_file).expanduser().resolve()
        if str(args.scenario_file or "").strip()
        else Path(str(metadata.get("scenario_file", "") or "")).expanduser().resolve()
    )
    scenario_row: Dict[str, Any] = {}
    if scenario_file.exists():
        try:
            payload = _safe_load_json(scenario_file)
            scenarios = payload.get("scenarios", {}) if isinstance(payload, dict) else {}
            if isinstance(scenarios, dict):
                scenario_row = scenarios.get(scenario_name, {}) if isinstance(scenarios.get(scenario_name, {}), dict) else {}
        except Exception:
            scenario_row = {}

    game_env = metadata.get("game_env", {}) if isinstance(metadata.get("game_env"), dict) else {}
    if not game_env and isinstance(scenario_row.get("game_env"), dict):
        game_env = scenario_row.get("game_env", {})

    plan_name = str(game_env.get("XBOT_VIDEO_BOT_PLAN", "") or "").strip()
    launcher_location = str(scenario_row.get("launcher_location", "") or "").strip()
    canonical_locations = infer_canonical_locations_for_run(plan_name, launcher_location)

    requested_book = str(args.book_docx or "").strip()
    resolved_book_docx = Path(requested_book).expanduser().resolve() if requested_book else _detect_default_book_docx()

    notes: List[str] = []
    book_text = ""
    if resolved_book_docx and resolved_book_docx.exists():
        try:
            book_text = read_docx_text(resolved_book_docx)
        except Exception as exc:
            notes.append(f"book read failed: {exc}")
            book_text = ""
    elif args.strict_book:
        notes.append("strict mode: main .docx was not found")
    else:
        notes.append("main .docx not provided; using fallback story sources")
        book_text = _load_fallback_book_text(project_root)

    snapshot = load_world_snapshot(project_root)
    location_results = [
        evaluate_location_conformance(location_id, book_text, snapshot)
        for location_id in canonical_locations
        if location_id in BOOK_LOCATION_PROFILES
    ]

    status = "pass"
    reason = "ok"
    if args.strict_book and (not book_text.strip()):
        status = "fail"
        reason = "book_docx_missing_or_unreadable"
    elif location_results and any(str(row.get("status", "")).lower() != "pass" for row in location_results):
        status = "fail"
        reason = "location_mismatches_detected"
    elif not location_results:
        reason = "no_book_locations_in_run"

    report = {
        "metadata_path": str(metadata_path),
        "scenario_name": scenario_name,
        "plan_name": plan_name,
        "launcher_location": launcher_location,
        "canonical_locations": canonical_locations,
        "book_docx_path": str(resolved_book_docx) if resolved_book_docx else "",
        "book_text_length": len(book_text),
        "strict_book": bool(args.strict_book),
        "status": status,
        "reason": reason,
        "notes": notes,
        "location_results": location_results,
    }

    default_paths = _resolve_report_paths(metadata_path)
    out_json = Path(args.output_json).expanduser().resolve() if str(args.output_json or "").strip() else default_paths["json"]
    out_md = Path(args.output_md).expanduser().resolve() if str(args.output_md or "").strip() else default_paths["md"]
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(report), encoding="utf-8")

    _safe_print(f"[BookConformance] JSON: {out_json}")
    _safe_print(f"[BookConformance] Markdown: {out_md}")
    _safe_print(f"[BookConformance] Status: {status} ({reason})")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
