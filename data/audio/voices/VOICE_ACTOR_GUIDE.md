# Voice Acting / Voiceover Guide

## File Placement

Voice files go in `data/audio/voices/`. The path corresponds directly to the `voice` field in dialogue JSON.

**Example:**
```
data/audio/voices/
├── guard_city/
│   ├── start.ogg
│   ├── passing_through.ogg
│   ├── directions.ogg
│   ├── farewell.ogg
│   └── ...
├── dragon_boss/
│   ├── start.ogg
│   ├── boss_laugh.ogg
│   └── ...
└── player/
    ├── boss_opener.ogg
    └── ...
```

## Supported Formats

The engine tries `.ogg` → `.wav` → `.mp3` in order.
**Recommended**: `.ogg` (Vorbis, stereo, 44.1 kHz, ~160 kbps)

## Dialogue JSON Fields

Each node in a dialogue tree can include:

| Field | Type | Description |
|---|---|---|
| `voice` | `string` | Relative path under `voices/` without extension |
| `camera` | `string` | `npc`, `player`, `wide`, `side`, `auto` |
| `duration` | `float` | Override auto-duration (seconds). If omitted, derived from text length (~18 chars/sec, min 2s, max 9s) |

## Camera Modes

| Value | Behaviour |
|---|---|
| `npc` | Over-shoulder facing NPC — used when NPC is speaking |
| `player` | Over-shoulder facing player — used when player replies |
| `wide` | Cinematic wide shot (both in frame) |
| `auto` | Alternates npc/player with each line |

## Boss Cinematic Dialogues (No Choices)

For pure cinematic sequences (boss confrontations, cutscenes), use empty `choices: []` or single-element choices with no `text` field.
The system auto-advances to the next node after `duration` seconds (or text reading time).

```json
{
  "speaker": "The Ashen Dragon",
  "text": "You dare enter my domain...",
  "camera": "wide",
  "voice": "dragon_boss/start",
  "choices": [
    { "next_node": "player_reply" }
  ]
}
```

## Player Input During Dialog

- **Space / E** — advance to next line early (skips remaining duration)
- **Click** on a choice button — for branching dialogue nodes

## Audio Ducking During Dialogue

While a dialogue cinematic is active:
- Background music ducks to **30%** volume
- Ambient sounds duck to **28%** volume

If a voiceover is playing, these are automatically managed by the `AudioDirector`.

## Adding Voiceovers (Placeholder Workflow)

Until real voice actors are recorded, you can:
1. Use **ElevenLabs** or **Murf AI** to generate placeholder TTS voices.
2. Export as `.ogg` and place in the correct subfolder.
3. Name files exactly matching the JSON `voice` field path.

The engine silently skips missing voice files — text subtitles always display.
