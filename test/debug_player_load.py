
import sys
import os
from pathlib import Path
import json

ROOT = Path(r'C:/xampp/htdocs/king-wizard')
sys.path.append(str(ROOT / 'src'))

from panda3d.core import loadPrcFileData
loadPrcFileData("", "window-type none")
from direct.showbase.ShowBase import ShowBase
base = ShowBase()

from entities.player import Player
from managers.data_manager import DataManager

# Mock DataManager
class MockDM:
    def get_player_config(self):
        p = ROOT / "data/actors/player.json"
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8-sig'))
        return {}

dm = MockDM()
p = Player(dm)

print("--- Player Model Debug ---")
cfg = p._player_model_config()
print(f"Config: {cfg}")
candidates = p._resolve_player_model_candidates()
print(f"Candidates: {candidates}")

for c in candidates:
    exists = (ROOT / c).exists()
    print(f"Candidate {c} exists: {exists}")
    if exists:
        try:
            from direct.actor.Actor import Actor
            # Set model path to include ROOT
            from panda3d.core import getModelPath, Filename
            getModelPath().appendDirectory(Filename.from_os_specific(str(ROOT)))
            getModelPath().appendDirectory(Filename.from_os_specific(str(ROOT / "assets")))
            
            base_anims = p._resolve_base_anims()
            print(f"Base Anims: {base_anims}")
            
            # Use base_anims with ROOT prepended
            resolved_anims = {}
            for k, v in base_anims.items():
                resolved_anims[k] = v
            
            a = Actor(c, resolved_anims)
            metrics = p._actor_bounds_metrics(a)
            playable = p._is_actor_bounds_playable(c, a)
            print(f"Actor {c} load success. Metrics: {metrics}, Playable: {playable}")
        except Exception as e:
            print(f"Actor {c} load FAILED: {e}")

print("--- End Debug ---")
base.destroy()
