"""Generate voice files for all current game dialogues using edge-tts (Microsoft Neural TTS).

Voices chosen:
    guard_city (Guard Captain Marcus)  → en-GB-RyanNeural (authoritative male, British)
    dragon_boss (The Ashen Dragon)     → en-US-ChristopherNeural (deep, commanding)
    player (King Wizard)               → en-GB-LibbyNeural → actually male: en-IE-ConnorNeural
    player (King Wizard)               → en-US-DavisNeural (heroic, assertive)
"""

import asyncio
import os
import sys

try:
    import edge_tts
except ImportError:
    print("edge-tts not installed. Run: python -m pip install edge-tts")
    sys.exit(1)

BASE_DIR = os.path.join("data", "audio", "voices")

LINES = [
    # ── Guard Captain Marcus ─────────────────────────────────────────────
    {
        "path": "guard_city/start",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "pitch": "-4Hz",
        "text": "Halt! State your business, citizen.",
    },
    {
        "path": "guard_city/passing_through",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "pitch": "-4Hz",
        "text": "Very well. Stay out of trouble, and keep to the main roads after dark. "
                "Bandits have been spotted in the woods.",
    },
    {
        "path": "guard_city/directions",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "pitch": "-4Hz",
        "text": "Where are you headed? The market is to the east, the temple to the north, "
                "and the training grounds are south of here.",
    },
    {
        "path": "guard_city/castle_directions",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "pitch": "-4Hz",
        "text": "The castle? You will need clearance to enter. "
                "Head north past the temple, but the guards will not let you in without proper authorization.",
    },
    {
        "path": "guard_city/trouble",
        "voice": "en-GB-RyanNeural",
        "rate": "-4%",
        "pitch": "-4Hz",
        "text": "Aye, there has been increased monster activity near the forest. "
                "We are stretched thin as it is. If you are capable, we could use help clearing them out.",
    },
    {
        "path": "guard_city/accept_patrol",
        "voice": "en-GB-RyanNeural",
        "rate": "+4%",
        "pitch": "-4Hz",
        "text": "Excellent! Clear out at least five monsters from the forest perimeter, "
                "and I will make sure you are compensated. Report back when it is done.",
    },
    {
        "path": "guard_city/farewell",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "pitch": "-4Hz",
        "text": "Stay vigilant, citizen.",
    },

    # ── The Ashen Dragon ─────────────────────────────────────────────────
    {
        "path": "dragon_boss/start",
        "voice": "en-US-ChristopherNeural",
        "rate": "-12%",
        "pitch": "-10Hz",
        "text": "You dare enter my domain, little wizard? How… amusing.",
    },
    {
        "path": "dragon_boss/boss_laugh",
        "voice": "en-US-ChristopherNeural",
        "rate": "-10%",
        "pitch": "-10Hz",
        "text": "Ha! Centuries of slumber and this is the hero the kingdom sends? "
                "Very well — let the flames judge you.",
    },

    # ── King Wizard (player) ─────────────────────────────────────────────
    {
        "path": "player/boss_opener",
        "voice": "en-US-DavisNeural",
        "rate": "+2%",
        "pitch": "+2Hz",
        "text": "Your reign of fire ends today.",
    },
]


async def generate_one(entry: dict):
    out_path = os.path.join(BASE_DIR, entry["path"] + ".mp3")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if os.path.exists(out_path):
        print(f"  [SKIP already exists] {out_path}")
        return

    print(f"  [GEN] {entry['path']} -> {os.path.basename(out_path)}")
    try:
        communicate = edge_tts.Communicate(
            text=entry["text"],
            voice=entry["voice"],
            rate=entry.get("rate", "+0%"),
            pitch=entry.get("pitch", "+0Hz"),
        )
        await communicate.save(out_path)
        print(f"  [OK]  {out_path}")
    except Exception as exc:
        print(f"  [ERR] {entry['path']}: {exc}")


async def main():
    print(f"\nGenerating {len(LINES)} voice lines into '{BASE_DIR}/'...\n")
    # Generate sequentially to avoid overwhelming network
    for entry in LINES:
        await generate_one(entry)
        await asyncio.sleep(0.15)  # small pause between requests
    print("\nAll done!")


if __name__ == "__main__":
    asyncio.run(main())
