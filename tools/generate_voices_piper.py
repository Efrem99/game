import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to sys.path to access PiperTTSManager if needed, 
# but we'll just implement a standalone version here for tool usage.

ROOT = Path(__file__).parent.parent
PIPER_EXE = ROOT / "tools" / "piper" / "piper.exe"
MODELS_DIR = ROOT / "tools" / "piper" / "models"
VOICES_DIR = ROOT / "data" / "audio" / "voices"
DIALOGUES_DIR = ROOT / "data" / "dialogues"
PROFILES_PATH = ROOT / "data" / "audio" / "piper_voices.json"

async def run_piper(text, model_path, output_path):
    import subprocess
    cmd = [
        str(PIPER_EXE),
        "-m", str(model_path),
        "-f", str(output_path)
    ]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        creationflags=0x08000000 # CREATE_NO_WINDOW
    )
    _, stderr = process.communicate(input=text)
    if process.returncode != 0:
        print(f"Error: {stderr}")

async def process_dialogue(filepath, profiles):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    
    npc_id = data.get("npc_id", filepath.stem)
    tree = data.get("dialogue_tree", {})
    
    profile = profiles.get(npc_id, profiles.get("default", {}))
    model_name = profile.get("model")
    model_path = MODELS_DIR / model_name
    
    if not model_path.exists():
        print(f"Warning: Model {model_name} for {npc_id} not found.")
        return

    npc_voice_dir = VOICES_DIR / npc_id
    npc_voice_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing NPC: {npc_id}")
    for node_id, node in tree.items():
        text = node.get("text", "").strip()
        if not text: continue
        
        out_path = npc_voice_dir / f"{node_id}.wav"
        if out_path.exists():
            print(f"  [SKIP] {node_id}")
            continue
            
        print(f"  [GEN ] {node_id}")
        await run_piper(text, model_path, out_path)

async def main():
    if not PIPER_EXE.exists():
        print(f"Error: Piper execution not found at {PIPER_EXE}")
        return

    with open(PROFILES_PATH, "r") as f:
        profiles = json.load(f)

    for f in DIALOGUES_DIR.glob("*.json"):
        if f.name.startswith("_") or f.name == "dialogue_schema.json":
            continue
        await process_dialogue(f, profiles)

if __name__ == "__main__":
    asyncio.run(main())
