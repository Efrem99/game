"""Dialogue voice coverage audit + synthesis via speech skill CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


EXTENSIONS = (".ogg", ".mp3", ".wav")
INLINE_TAG_RE = re.compile(r"\|([a-z_]+)\s*=\s*([^|]+)\|", re.IGNORECASE)
DEFAULT_MODEL = "gpt-4o-mini-tts-2025-12-15"
DEFAULT_VOICE = "cedar"
DEFAULT_RPM = 24
ALLOWED_OPENAI_VOICES = {
    "alloy",
    "ash",
    "ballad",
    "cedar",
    "coral",
    "echo",
    "fable",
    "marin",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
}


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _safe_print(text):
    payload = str(text)
    data = (payload + "\n").encode("utf-8", errors="replace")
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(data)
        stream.flush()
        return
    print(payload)


def _voice_candidates(voices_root: Path, voice_key: str):
    token = str(voice_key or "").strip().replace("\\", "/")
    out = []
    for ext in EXTENSIONS:
        out.append(voices_root / f"{token}{ext}")
    return out


def _pick_existing(candidates):
    for path in candidates:
        if path.exists():
            return path
    return None


def _coerce_float(value, default):
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _extract_dialog_text(raw_text):
    text = str(raw_text or "")
    tags = {}
    for match in INLINE_TAG_RE.finditer(text):
        key = str(match.group(1) or "").strip().lower()
        value = str(match.group(2) or "").strip()
        if key:
            tags[key] = value
    cleaned = INLINE_TAG_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, tags


def _iter_dialogue_nodes(dialog_payload, file_path):
    if not isinstance(dialog_payload, dict):
        return
    tree = dialog_payload.get("dialogue_tree", {})
    if not isinstance(tree, dict):
        return
    fallback_npc = str(Path(file_path).stem or "unknown_npc").strip().lower().replace(" ", "_")
    npc_id = str(dialog_payload.get("npc_id", "") or "").strip() or fallback_npc
    for node_id, node in tree.items():
        if not isinstance(node, dict):
            continue
        text = str(node.get("text", "") or "").strip()
        if not text:
            continue
        voice_key = str(node.get("voice") or f"{npc_id}/{node_id}")
        yield {
            "npc_id": npc_id,
            "node_id": str(node_id),
            "voice_key": voice_key.strip().replace("\\", "/"),
            "speaker": str(node.get("speaker", "") or ""),
            "text": text,
        }


def _audit(dialogues_dir: Path, voices_dir: Path):
    entries = []
    files = sorted(dialogues_dir.glob("*.json"))
    for file_path in files:
        payload = _load_json(file_path)
        if not isinstance(payload, dict):
            continue
        for row in _iter_dialogue_nodes(payload, file_path):
            candidates = _voice_candidates(voices_dir, row["voice_key"])
            existing = _pick_existing(candidates)
            entries.append(
                {
                    "dialogue_file": str(file_path).replace("\\", "/"),
                    "npc_id": row["npc_id"],
                    "node_id": row["node_id"],
                    "speaker": row["speaker"],
                    "voice_key": row["voice_key"],
                    "text": row["text"],
                    "exists": bool(existing),
                    "resolved_path": str(existing).replace("\\", "/") if existing else "",
                    "preferred_output_mp3": str(candidates[1]).replace("\\", "/"),
                }
            )
    return entries


def _load_voice_profiles(root: Path, rel_path: str):
    profile_path = (root / rel_path).resolve()
    payload = _load_json(profile_path)
    if not isinstance(payload, dict):
        return {}
    return payload


def _legacy_edge_to_openai(edge_voice: str) -> str:
    token = str(edge_voice or "").strip().lower()
    if "guy" in token:
        return "onyx"
    if "christopher" in token or "eric" in token:
        return "cedar"
    if "jenny" in token:
        return "marin"
    if "ana" in token or "aria" in token:
        return "coral"
    return DEFAULT_VOICE


def _normalize_openai_voice(value: str | None, fallback: str = DEFAULT_VOICE) -> str:
    token = str(value or "").strip().lower()
    if token in ALLOWED_OPENAI_VOICES:
        return token
    return fallback


def _default_profile_for_row(row):
    npc_id = str(row.get("npc_id", "")).strip().lower()
    speaker = str(row.get("speaker", "")).strip().lower()
    voice = "cedar"
    speed = 1.0
    style = (
        "Voice Affect: Natural grounded fantasy dialogue. "
        "Tone: cinematic but restrained. "
        "Pacing: steady and clear."
    )
    if any(token in npc_id for token in ("dragon", "golem", "boss")):
        voice = "onyx"
        speed = 0.96
        style = (
            "Voice Affect: Heavy and intimidating. "
            "Tone: menacing and controlled. "
            "Pacing: deliberate with short pauses."
        )
    elif any(token in npc_id for token in ("merchant", "trader")):
        voice = "marin"
        speed = 1.04
        style = (
            "Voice Affect: Lively and persuasive. "
            "Tone: friendly with subtle urgency. "
            "Pacing: brisk but articulate."
        )
    elif any(token in npc_id for token in ("guard", "captain", "knight")):
        voice = "ash"
        speed = 0.99
        style = (
            "Voice Affect: Firm and disciplined. "
            "Tone: authoritative and alert. "
            "Pacing: measured and clear."
        )
    elif "elder" in speaker:
        voice = "sage"
        speed = 0.97
        style = (
            "Voice Affect: Wise and calm. "
            "Tone: warm and thoughtful. "
            "Pacing: smooth with gentle pauses."
        )
    elif "player" in npc_id or "sherward" in speaker:
        voice = "cedar"
        speed = 1.0

    return {
        "openai_voice": voice,
        "openai_speed": speed,
        "openai_instructions": style,
        # Keep legacy keys for backward-compat in older profile files.
        "edge_voice": "",
        "expressiveness": 1.0,
    }


def _merge_voice_profile(row, profiles):
    base = _default_profile_for_row(row)
    if not isinstance(profiles, dict):
        return base
    npc_map = profiles.get("npc", {}) if isinstance(profiles.get("npc"), dict) else {}
    speaker_map = profiles.get("speaker", {}) if isinstance(profiles.get("speaker"), dict) else {}
    npc_key = str(row.get("npc_id", "")).strip().lower()
    speaker_key = str(row.get("speaker", "")).strip().lower()
    merged = dict(base)
    if npc_key in npc_map and isinstance(npc_map[npc_key], dict):
        merged.update(npc_map[npc_key])
    if speaker_key in speaker_map and isinstance(speaker_map[speaker_key], dict):
        merged.update(speaker_map[speaker_key])
    return merged


def _derive_openai_job(row, profile, fallback_voice):
    text, tags = _extract_dialog_text(row.get("text", ""))
    if not text:
        text = str(row.get("text", "") or "").strip()
    if not text:
        return None

    raw_voice = profile.get("openai_voice")
    if not raw_voice:
        raw_voice = _legacy_edge_to_openai(profile.get("edge_voice", ""))
    voice = _normalize_openai_voice(raw_voice, fallback=fallback_voice)

    speed = _coerce_float(profile.get("openai_speed", 1.0), 1.0)
    tagged_rate = _coerce_float(tags.get("rate", 0.0), 0.0)
    if tagged_rate > 0:
        speed *= tagged_rate / 170.0
    if text.count("...") > 0:
        speed -= 0.03
    if text.count("!") > 0:
        speed += 0.02
    speed = _clamp(speed, 0.8, 1.2)

    instructions = str(profile.get("openai_instructions", "") or "").strip()
    if not instructions:
        instructions = (
            "Voice Affect: Natural grounded fantasy dialogue. "
            "Tone: cinematic but restrained. "
            "Pacing: steady and clear."
        )

    # Keep each line self-sufficient for batch generation quality.
    instructions = (
        f"{instructions} "
        "Emotion: Match punctuation and scene tension naturally. "
        "Pronunciation: Keep names and places clear."
    )

    return {
        "input": text,
        "voice": voice,
        "speed": round(float(speed), 3),
        "instructions": instructions,
        "response_format": "mp3",
        "out": f"{row['voice_key']}.mp3",
    }


def _resolve_speech_cli(explicit_path: str | None):
    probes = []
    if explicit_path:
        probes.append(Path(explicit_path).expanduser())
    env_hint = os.getenv("XBOT_SPEECH_CLI", "").strip()
    if env_hint:
        probes.append(Path(env_hint).expanduser())
    codex_home = os.getenv("CODEX_HOME", "").strip()
    if codex_home:
        probes.append(Path(codex_home) / "skills" / "speech" / "scripts" / "text_to_speech.py")
    probes.append(Path.home() / ".codex" / "skills" / "speech" / "scripts" / "text_to_speech.py")

    for candidate in probes:
        if candidate and candidate.exists():
            return candidate.resolve()
    return None


def _write_jobs_jsonl(path: Path, jobs):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for row in jobs:
        lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _run_speech_batch(*, cli_path, jobs_path, out_dir, model, default_voice, rpm, force, dry_run):
    cmd = [
        sys.executable,
        str(cli_path),
        "speak-batch",
        "--input",
        str(jobs_path),
        "--out-dir",
        str(out_dir),
        "--model",
        str(model),
        "--voice",
        str(default_voice),
        "--response-format",
        "mp3",
        "--rpm",
        str(int(rpm)),
    ]
    if force:
        cmd.append("--force")
    if dry_run:
        cmd.append("--dry-run")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": int(result.returncode),
        "stdout": str(result.stdout or "").strip(),
        "stderr": str(result.stderr or "").strip(),
        "command": " ".join(cmd),
    }


def _synthesize_with_speech_skill(
    *,
    rows,
    root,
    voices_dir,
    profiles,
    overwrite,
    skill_cli_path,
    model,
    default_voice,
    rpm,
    dry_run,
    keep_tmp_jsonl,
):
    if not rows:
        return {
            "enabled": True,
            "engine": "speech",
            "generated": 0,
            "failed": 0,
            "error": "",
            "skipped": 0,
            "requested": 0,
            "cli_path": "",
            "command": "",
        }

    cli_path = _resolve_speech_cli(skill_cli_path)
    if not cli_path:
        return {
            "enabled": False,
            "engine": "speech",
            "generated": 0,
            "failed": len(rows),
            "error": "speech skill CLI not found (text_to_speech.py).",
            "skipped": 0,
            "requested": len(rows),
            "cli_path": "",
            "command": "",
        }
    if not dry_run and not os.getenv("OPENAI_API_KEY"):
        return {
            "enabled": False,
            "engine": "speech",
            "generated": 0,
            "failed": len(rows),
            "error": "OPENAI_API_KEY is not set.",
            "skipped": 0,
            "requested": len(rows),
            "cli_path": str(cli_path).replace("\\", "/"),
            "command": "",
        }

    default_voice = _normalize_openai_voice(default_voice, fallback=DEFAULT_VOICE)
    jobs = []
    targets = []
    skipped = 0

    for row in rows:
        out_path = voices_dir / f"{row['voice_key']}.mp3"
        if out_path.exists() and not overwrite:
            skipped += 1
            continue
        profile = _merge_voice_profile(row, profiles)
        job = _derive_openai_job(row, profile, default_voice)
        if not job:
            skipped += 1
            continue
        jobs.append(job)
        targets.append((row, out_path))

    if not jobs:
        return {
            "enabled": True,
            "engine": "speech",
            "generated": 0,
            "failed": 0,
            "error": "",
            "skipped": skipped,
            "requested": 0,
            "cli_path": str(cli_path).replace("\\", "/"),
            "command": "",
        }

    jobs_path = (root / "tmp" / "speech" / "dialogue_jobs.jsonl").resolve()
    _write_jobs_jsonl(jobs_path, jobs)

    run = _run_speech_batch(
        cli_path=cli_path,
        jobs_path=jobs_path,
        out_dir=voices_dir,
        model=model,
        default_voice=default_voice,
        rpm=max(1, min(50, int(rpm))),
        force=overwrite,
        dry_run=dry_run,
    )

    if not keep_tmp_jsonl:
        try:
            jobs_path.unlink(missing_ok=True)
        except Exception:
            pass

    if dry_run:
        return {
            "enabled": bool(run["ok"]),
            "engine": "speech",
            "generated": 0,
            "failed": 0 if run["ok"] else len(jobs),
            "error": "" if run["ok"] else (run["stderr"] or run["stdout"] or "speech batch dry-run failed"),
            "skipped": skipped,
            "requested": len(jobs),
            "cli_path": str(cli_path).replace("\\", "/"),
            "command": run["command"],
        }

    generated = 0
    failed = 0
    for row, out_path in targets:
        if out_path.exists():
            generated += 1
            row["exists"] = True
            row["resolved_path"] = str(out_path).replace("\\", "/")
        else:
            failed += 1

    err = ""
    if not run["ok"]:
        err = run["stderr"] or run["stdout"] or f"speech batch failed with code={run['returncode']}"

    return {
        "enabled": bool(run["ok"]),
        "engine": "speech",
        "generated": generated,
        "failed": failed if run["ok"] else max(failed, len(jobs) - generated),
        "error": err,
        "skipped": skipped,
        "requested": len(jobs),
        "cli_path": str(cli_path).replace("\\", "/"),
        "command": run["command"],
    }


def _write_reports(report, logs_dir):
    logs_dir.mkdir(parents=True, exist_ok=True)
    json_path = logs_dir / "voice_dialog_report.json"
    md_path = logs_dir / "voice_dialog_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = []
    lines.append("# Voice Dialogue Report")
    lines.append("")
    lines.append("- note: dialogue voice clips are AI-generated (OpenAI TTS).")
    lines.append(f"- total_lines: {report.get('total_lines', 0)}")
    lines.append(f"- voiced_lines: {report.get('voiced_lines', 0)}")
    lines.append(f"- missing_lines: {report.get('missing_lines', 0)}")
    synthesis = report.get("synthesis", {})
    if isinstance(synthesis, dict):
        lines.append(
            f"- synthesis: enabled={bool(synthesis.get('enabled', False))}, "
            f"engine={str(synthesis.get('engine', 'none'))}, "
            f"requested={int(synthesis.get('requested', 0))}, "
            f"generated={int(synthesis.get('generated', 0))}, "
            f"skipped={int(synthesis.get('skipped', 0))}, "
            f"failed={int(synthesis.get('failed', 0))}"
        )
        cli_path = str(synthesis.get("cli_path", "") or "").strip()
        if cli_path:
            lines.append(f"- speech_cli: `{cli_path}`")
    lines.append("")
    if report.get("missing_rows"):
        lines.append("## Missing Clips")
        lines.append("")
        for row in report["missing_rows"]:
            lines.append(
                f"- `{row.get('voice_key', '')}` "
                f"({row.get('dialogue_file', '')} :: {row.get('node_id', '')})"
            )
    else:
        lines.append("All dialogue lines have voice clips.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit dialogue voice coverage and synthesize missing lines.")
    parser.add_argument("--dialogues-dir", default="data/dialogues", help="Path to dialogue JSON files.")
    parser.add_argument("--voices-dir", default="data/audio/voices", help="Path to voice clips root.")
    parser.add_argument(
        "--voice-profiles",
        default="data/audio/voice_generation_profiles.json",
        help="Optional npc/speaker voice profile map.",
    )
    parser.add_argument("--synthesize-missing", action="store_true", help="Generate missing lines with speech skill.")
    parser.add_argument("--synthesize-all", action="store_true", help="Generate clips for all dialogue lines.")
    parser.add_argument("--force-regenerate", action="store_true", help="Overwrite existing generated clips.")
    parser.add_argument("--engine", default="speech", help="Compatibility flag; uses speech skill in all modes.")
    parser.add_argument("--skill-cli", default="", help="Optional explicit path to speech skill text_to_speech.py.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI TTS model (default: {DEFAULT_MODEL}).")
    parser.add_argument("--default-voice", default=DEFAULT_VOICE, help=f"Fallback voice (default: {DEFAULT_VOICE}).")
    parser.add_argument("--rpm", type=int, default=DEFAULT_RPM, help="Batch requests/min cap (1..50).")
    parser.add_argument("--dry-run-synthesis", action="store_true", help="Validate payloads without API calls.")
    parser.add_argument("--keep-temp-jsonl", action="store_true", help="Do not delete tmp/speech/dialogue_jobs.jsonl.")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    dialogues_dir = (root / args.dialogues_dir).resolve()
    voices_dir = (root / args.voices_dir).resolve()
    logs_dir = (root / "logs").resolve()
    profiles = _load_voice_profiles(root, args.voice_profiles)

    rows = _audit(dialogues_dir, voices_dir)
    synthesis = {
        "enabled": False,
        "generated": 0,
        "failed": 0,
        "error": "",
        "engine": "none",
        "requested": 0,
        "skipped": 0,
        "cli_path": "",
        "command": "",
    }

    targets = []
    if args.synthesize_all:
        targets = list(rows)
    elif args.synthesize_missing:
        targets = [row for row in rows if not bool(row.get("exists", False))]

    if targets:
        synthesis = _synthesize_with_speech_skill(
            rows=targets,
            root=root,
            voices_dir=voices_dir,
            profiles=profiles,
            overwrite=bool(args.force_regenerate),
            skill_cli_path=args.skill_cli,
            model=args.model,
            default_voice=args.default_voice,
            rpm=args.rpm,
            dry_run=bool(args.dry_run_synthesis),
            keep_tmp_jsonl=bool(args.keep_temp_jsonl),
        )
        synthesis["requested"] = int(synthesis.get("requested", len(targets)) or 0)

    missing = [row for row in rows if not bool(row.get("exists", False))]
    report = {
        "dialogues_dir": str(dialogues_dir).replace("\\", "/"),
        "voices_dir": str(voices_dir).replace("\\", "/"),
        "total_lines": len(rows),
        "voiced_lines": len(rows) - len(missing),
        "missing_lines": len(missing),
        "synthesis": synthesis,
        "missing_rows": missing,
    }
    json_path, md_path = _write_reports(report, logs_dir)

    _safe_print(f"[VoiceReport] total={report['total_lines']} voiced={report['voiced_lines']} missing={report['missing_lines']}")
    if synthesis.get("requested", 0):
        _safe_print(
            f"[VoiceReport] synth engine={synthesis.get('engine', 'none')} "
            f"requested={synthesis.get('requested', 0)} generated={synthesis.get('generated', 0)} "
            f"skipped={synthesis.get('skipped', 0)} failed={synthesis.get('failed', 0)} "
            f"enabled={bool(synthesis.get('enabled', False))}"
        )
        if synthesis.get("error"):
            _safe_print(f"[VoiceReport] synth_error={synthesis['error']}")
    _safe_print(f"[VoiceReport] JSON: {json_path}")
    _safe_print(f"[VoiceReport] MD: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
