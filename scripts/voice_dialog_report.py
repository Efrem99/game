"""Dialogue voice coverage audit + optional synthesis for missing clips."""

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path


EXTENSIONS = (".ogg", ".mp3", ".wav")
INLINE_TAG_RE = re.compile(r"\|([a-z_]+)\s*=\s*([^|]+)\|", re.IGNORECASE)


def _load_json(path):
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


def _voice_candidates(voices_root, voice_key):
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


def _parse_percent(token, default):
    text = str(token or "").strip()
    if text.endswith("%"):
        return _coerce_float(text[:-1], default)
    return _coerce_float(text, default)


def _parse_hz(token, default):
    text = str(token or "").strip().lower()
    if text.endswith("hz"):
        return _coerce_float(text[:-2], default)
    return _coerce_float(text, default)


def _stable_unit(row, salt):
    seed = f"{row.get('voice_key', '')}|{row.get('text', '')}|{salt}".encode("utf-8", errors="ignore")
    digest = hashlib.sha1(seed).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def _derive_delivery(row, profile):
    text, tags = _extract_dialog_text(row.get("text", ""))
    if not text:
        text = str(row.get("text", "") or "").strip()

    expressiveness = _clamp(_coerce_float(profile.get("expressiveness", 1.0), 1.0), 0.0, 1.7)
    base_rate_pct = _parse_percent(profile.get("rate", "+0%"), 0.0)
    base_pitch_hz = _parse_hz(profile.get("pitch", "+0Hz"), 0.0)
    base_pyttsx_rate = int(_coerce_float(profile.get("pyttsx3_rate", 178), 178))
    base_pyttsx_volume = _clamp(_coerce_float(profile.get("pyttsx3_volume", 0.94), 0.94), 0.55, 1.0)

    exclam = text.count("!")
    question = text.count("?")
    dots = text.count("...")
    comma = text.count(",")
    semicolon = text.count(";")

    pace_shift = 0.0
    pitch_shift = 0.0
    if exclam:
        pace_shift += min(9.0, 2.0 * exclam)
        pitch_shift += min(18.0, 4.0 * exclam)
    if question:
        pace_shift += min(4.0, 1.2 * question)
        pitch_shift += min(14.0, 3.0 * question)
    if dots:
        pace_shift -= min(9.0, 3.0 * dots)
    if comma or semicolon:
        pace_shift -= min(4.0, 0.6 * (comma + semicolon))
    if len(text) >= 140:
        pace_shift -= 3.0

    tagged_rate = _coerce_float(tags.get("rate", 0.0), 0.0)
    if tagged_rate > 0.0:
        pace_shift += ((tagged_rate / 170.0) - 1.0) * 100.0
    tagged_pitch = tags.get("pitch")
    if tagged_pitch is not None:
        pitch_shift += _coerce_float(tagged_pitch, 0.0)

    # Deterministic per-line jitter keeps takes varied without changing every run.
    jitter = (_stable_unit(row, "rate") - 0.5) * (10.0 * expressiveness)
    pitch_jitter = (_stable_unit(row, "pitch") - 0.5) * (12.0 * expressiveness)
    volume_jitter = (_stable_unit(row, "volume") - 0.5) * (0.10 * expressiveness)

    final_rate_pct = _clamp(base_rate_pct + pace_shift + jitter, -35.0, 35.0)
    final_pitch_hz = _clamp(base_pitch_hz + pitch_shift + pitch_jitter, -32.0, 32.0)
    edge_rate_int = int(round(final_rate_pct))
    edge_pitch_int = int(round(final_pitch_hz))
    py_rate = int(_clamp(base_pyttsx_rate + final_rate_pct * 0.7, 120, 235))
    py_volume = _clamp(base_pyttsx_volume + volume_jitter, 0.6, 1.0)
    return {
        "text": text,
        "edge_rate": f"{edge_rate_int:+d}%",
        "edge_pitch": f"{edge_pitch_int:+d}Hz",
        "pyttsx_rate": py_rate,
        "pyttsx_volume": py_volume,
    }


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


def _audit(dialogues_dir, voices_dir):
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
                    "preferred_output_wav": str(candidates[1]).replace("\\", "/"),
                    "preferred_output_mp3": str(candidates[2]).replace("\\", "/"),
                }
            )
    return entries


def _load_voice_profiles(root, rel_path):
    profile_path = (root / rel_path).resolve()
    payload = _load_json(profile_path)
    if not isinstance(payload, dict):
        return {}
    return payload


def _default_profile_for_row(row):
    npc_id = str(row.get("npc_id", "")).strip().lower()
    speaker = str(row.get("speaker", "")).strip().lower()
    voice = "en-US-AriaNeural"
    if any(token in npc_id for token in ("dragon", "golem", "boss")):
        voice = "en-US-GuyNeural"
    elif any(token in npc_id for token in ("guard", "captain", "knight")):
        voice = "en-US-ChristopherNeural"
    elif any(token in npc_id for token in ("merchant", "trader")):
        voice = "en-US-JennyNeural"
    elif "elder" in speaker:
        voice = "en-US-AnaNeural"
    elif "king wizard" in speaker or "player" in npc_id:
        voice = "en-US-EricNeural"
    return {
        "edge_voice": voice,
        "rate": "+0%",
        "pitch": "+0Hz",
        "pyttsx3_rate": 178,
        "pyttsx3_volume": 0.94,
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


async def _edge_render_one(delivery, out_path, profile):
    import edge_tts

    voice = str(profile.get("edge_voice", "en-US-AriaNeural"))
    communicator = edge_tts.Communicate(
        text=delivery["text"],
        voice=voice,
        rate=delivery["edge_rate"],
        pitch=delivery["edge_pitch"],
    )
    await communicator.save(str(out_path))


def _target_out_path(voices_dir, row, engine):
    suffix = ".mp3" if engine == "edge" else ".wav"
    return voices_dir / f"{row['voice_key']}{suffix}"


def _synthesize_with_edge_tts(rows, voices_dir, profiles, overwrite=False):
    try:
        import edge_tts  # noqa: F401
    except Exception as exc:
        return {"enabled": False, "generated": 0, "failed": len(rows), "error": str(exc), "engine": "edge", "skipped": 0}

    generated = 0
    failed = 0
    skipped = 0
    first_error = ""
    for row in rows:
        out_path = _target_out_path(voices_dir, row, "edge")
        if out_path.exists() and not overwrite:
            skipped += 1
            continue
        profile = _merge_voice_profile(row, profiles)
        delivery = _derive_delivery(row, profile)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            asyncio.run(_edge_render_one(delivery, out_path, profile))
            generated += 1
            row["exists"] = True
            row["resolved_path"] = str(out_path).replace("\\", "/")
        except Exception as exc:
            failed += 1
            if not first_error:
                first_error = str(exc)
    return {"enabled": True, "generated": generated, "failed": failed, "error": first_error, "engine": "edge", "skipped": skipped}


def _synthesize_with_pyttsx3(rows, voices_dir, profiles, overwrite=False):
    try:
        import pyttsx3
    except Exception as exc:
        return {
            "enabled": False,
            "generated": 0,
            "failed": len(rows),
            "error": str(exc),
            "engine": "pyttsx3",
            "skipped": 0,
        }

    engine = pyttsx3.init()
    generated = 0
    failed = 0
    skipped = 0
    first_error = ""
    for row in rows:
        out_path = _target_out_path(voices_dir, row, "pyttsx3")
        if out_path.exists() and not overwrite:
            skipped += 1
            continue
        profile = _merge_voice_profile(row, profiles)
        delivery = _derive_delivery(row, profile)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            engine.setProperty("rate", int(delivery["pyttsx_rate"]))
            engine.setProperty("volume", float(delivery["pyttsx_volume"]))
            engine.save_to_file(delivery["text"], str(out_path))
            engine.runAndWait()
            generated += 1
            row["exists"] = True
            row["resolved_path"] = str(out_path).replace("\\", "/")
        except Exception as exc:
            failed += 1
            if not first_error:
                first_error = str(exc)
    try:
        engine.stop()
    except Exception:
        pass
    return {"enabled": True, "generated": generated, "failed": failed, "error": first_error, "engine": "pyttsx3", "skipped": skipped}


def _synthesize_rows(rows, voices_dir, profiles, engine, overwrite):
    token = str(engine or "auto").strip().lower()
    if token in {"edge", "edge_tts"}:
        return _synthesize_with_edge_tts(rows, voices_dir, profiles, overwrite=overwrite)
    if token in {"pyttsx3", "offline"}:
        return _synthesize_with_pyttsx3(rows, voices_dir, profiles, overwrite=overwrite)

    # auto: prefer edge-tts for more natural cadence, fallback to pyttsx3.
    out = _synthesize_with_edge_tts(rows, voices_dir, profiles, overwrite=overwrite)
    if out.get("enabled", False) and int(out.get("generated", 0)) > 0:
        return out
    if out.get("enabled", False) and int(out.get("failed", 0)) == 0:
        return out
    return _synthesize_with_pyttsx3(rows, voices_dir, profiles, overwrite=overwrite)


def _write_reports(report, logs_dir):
    logs_dir.mkdir(parents=True, exist_ok=True)
    json_path = logs_dir / "voice_dialog_report.json"
    md_path = logs_dir / "voice_dialog_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = []
    lines.append("# Voice Dialogue Report")
    lines.append("")
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
    parser = argparse.ArgumentParser(description="Audit dialogue voice coverage.")
    parser.add_argument("--dialogues-dir", default="data/dialogues", help="Path to dialogue JSON files.")
    parser.add_argument("--voices-dir", default="data/audio/voices", help="Path to voice clips root.")
    parser.add_argument(
        "--voice-profiles",
        default="data/audio/voice_generation_profiles.json",
        help="Optional npc/speaker voice profile map.",
    )
    parser.add_argument("--synthesize-missing", action="store_true", help="Generate missing lines with TTS.")
    parser.add_argument("--synthesize-all", action="store_true", help="Generate voice clips for all dialogue lines.")
    parser.add_argument("--force-regenerate", action="store_true", help="Overwrite existing generated clips.")
    parser.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "edge", "pyttsx3"],
        help="TTS engine for synthesis mode.",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    dialogues_dir = (root / args.dialogues_dir).resolve()
    voices_dir = (root / args.voices_dir).resolve()
    logs_dir = (root / "logs").resolve()
    profiles = _load_voice_profiles(root, args.voice_profiles)

    rows = _audit(dialogues_dir, voices_dir)
    synthesis = {"enabled": False, "generated": 0, "failed": 0, "error": "", "engine": "none", "requested": 0, "skipped": 0}

    targets = []
    if args.synthesize_all:
        targets = list(rows)
    elif args.synthesize_missing:
        targets = [row for row in rows if not bool(row.get("exists", False))]

    if targets:
        synthesis = _synthesize_rows(
            targets,
            voices_dir,
            profiles,
            args.engine,
            overwrite=bool(args.force_regenerate),
        )
        synthesis["requested"] = len(targets)

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
    if synthesis.get("enabled", False):
        _safe_print(
            f"[VoiceReport] synth engine={synthesis.get('engine', 'none')} "
            f"requested={synthesis.get('requested', 0)} generated={synthesis.get('generated', 0)} "
            f"skipped={synthesis.get('skipped', 0)} failed={synthesis.get('failed', 0)}"
        )
        if synthesis.get("error"):
            _safe_print(f"[VoiceReport] synth_error={synthesis['error']}")
    _safe_print(f"[VoiceReport] JSON: {json_path}")
    _safe_print(f"[VoiceReport] MD: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
