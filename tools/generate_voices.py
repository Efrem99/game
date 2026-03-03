"""Voice generation tool for King Wizard NPC/boss dialogues.

Usage:
    python tools/generate_voices.py

Reads all dialogue JSONs from data/dialogues/ and generates .mp3 files
in data/audio/voices/ using Microsoft Edge Neural TTS (free, no API key).

Voice profiles (edit as needed):
    - NPC voices keyed by npc_id → voice name, rate, pitch
    - Player voice for player lines
    - Falls back to DEFAULT_VOICE if npc_id not in VOICE_PROFILES

Requires:  pip install edge-tts
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

try:
    import edge_tts
except ImportError:
    print("ERROR: edge-tts not installed. Run: python -m pip install edge-tts")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────

DIALOGUES_DIR = os.path.join("data", "dialogues")
VOICES_DIR    = os.path.join("data", "audio", "voices")

DEFAULT_VOICE = {"voice": "en-GB-RyanNeural", "rate": "+0%", "pitch": "-2Hz"}

VOICE_PROFILES: dict[str, dict] = {
    # key = npc_id or speaker name (lowercased, spaces → _)
    "guard_city":     {"voice": "en-GB-RyanNeural",         "rate": "+0%",  "pitch": "-4Hz"},
    "guard_captain_marcus": {"voice": "en-GB-RyanNeural",   "rate": "+0%",  "pitch": "-4Hz"},
    "dragon_boss":    {"voice": "en-US-ChristopherNeural",  "rate": "-12%", "pitch": "-10Hz"},
    "the_ashen_dragon": {"voice": "en-US-ChristopherNeural","rate": "-12%", "pitch": "-10Hz"},
    "player":         {"voice": "en-US-GuyNeural",          "rate": "+4%",  "pitch": "+2Hz"},
    "king_wizard":    {"voice": "en-US-GuyNeural",          "rate": "+4%",  "pitch": "+2Hz"},
    "merchant":       {"voice": "en-US-AriaNeural",         "rate": "+2%",  "pitch": "+4Hz"},
    "quest_giver":    {"voice": "en-GB-SoniaNeural",        "rate": "-2%",  "pitch": "+0Hz"},
}


def _speaker_key(npc_id: str, speaker: str) -> str:
    for key in (
        npc_id.lower().replace(" ", "_"),
        speaker.lower().replace(" ", "_"),
    ):
        if key in VOICE_PROFILES:
            return key
    return ""


async def generate_line(npc_id: str, node_id: str, text: str, voice_key: str):
    """Generate one voice file.  voice_key may be overridden by 'voice' JSON field."""
    out_path = os.path.join(VOICES_DIR, npc_id, node_id + ".mp3")
    if os.path.exists(out_path):
        print(f"  [SKIP] {out_path}")
        return

    profile = VOICE_PROFILES.get(voice_key, DEFAULT_VOICE)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    print(f"  [GEN ] {out_path}  ({profile['voice']})")
    try:
        c = edge_tts.Communicate(
            text=text,
            voice=profile["voice"],
            rate=profile.get("rate", "+0%"),
            pitch=profile.get("pitch", "+0Hz"),
        )
        await c.save(out_path)
        print(f"  [OK  ] {out_path}")
    except Exception as exc:
        # Try fallback voice
        try:
            c = edge_tts.Communicate(text=text, voice=DEFAULT_VOICE["voice"])
            await c.save(out_path)
            print(f"  [FALLBACK OK] {out_path}")
        except Exception as exc2:
            print(f"  [ERR ] {out_path}: {exc} | fallback: {exc2}")


async def process_dialogue(filepath: str):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    npc_id = str(data.get("npc_id", os.path.splitext(os.path.basename(filepath))[0]))
    npc_name = str(data.get("npc_name", npc_id))
    tree = data.get("dialogue_tree", {})

    print(f"\n[Dialogue] {npc_id} ({npc_name})  [{len(tree)} nodes]")

    for node_id, node in tree.items():
        if not isinstance(node, dict):
            continue
        text = str(node.get("text", "") or "").strip()
        if not text:
            continue  # skip empty nodes (e.g. combat_start)

        # Determine voice: JSON 'voice' field overrides, else resolve from speaker
        json_voice = str(node.get("voice", "") or "")
        speaker = str(node.get("speaker", npc_id) or npc_id)

        if json_voice and "/" in json_voice:
            # voice field like "guard_city/start" → use npc portion as key
            vk = json_voice.split("/")[0].lower()
        else:
            vk = _speaker_key(npc_id, speaker)

        await generate_line(npc_id, node_id, text, vk)
        await asyncio.sleep(0.12)


async def main():
    if not os.path.isdir(DIALOGUES_DIR):
        print(f"ERROR: dialogues dir not found: {DIALOGUES_DIR}")
        sys.exit(1)

    files = [
        os.path.join(DIALOGUES_DIR, f)
        for f in os.listdir(DIALOGUES_DIR)
        if f.endswith(".json") and not f.startswith("_") and f != "dialogue_schema.json"
    ]
    print(f"Found {len(files)} dialogue files.")

    for filepath in sorted(files):
        try:
            await process_dialogue(filepath)
        except Exception as exc:
            print(f"  [ERR] {filepath}: {exc}")

    print("\n=== Voice generation complete. ===")


if __name__ == "__main__":
    asyncio.run(main())
