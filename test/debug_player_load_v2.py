
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

# Mock objects
class Mock:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __getattr__(self, name):
        return Mock()
    def __call__(self, *args, **kwargs):
        return Mock()

mock_app = Mock(data_mgr=Mock())
mock_render = base.render
mock_loader = base.loader
mock_char_state = Mock(velocity=Mock(x=0.0, y=0.0, z=0.0), grounded=True)
mock_phys = Mock()
mock_combat = Mock()
mock_parkour = Mock()
mock_magic = Mock()
mock_particles = Mock()
mock_parkour_state = Mock()

# Pre-configure model paths
from panda3d.core import getModelPath, Filename
getModelPath().appendDirectory(Filename.from_os_specific(str(ROOT)))
getModelPath().appendDirectory(Filename.from_os_specific(str(ROOT / "assets")))

try:
    p = Player(
        mock_app, mock_render, mock_loader, mock_char_state,
        mock_phys, mock_combat, mock_parkour, mock_magic,
        mock_particles, mock_parkour_state
    )
except Exception as e:
    print(f"Player init error: {e}")
    sys.exit(1)

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
            base_anims = p._resolve_base_anims()
            print(f"Base Anims: {base_anims}")
            
            candidate = Actor(c, base_anims)
            metrics = p._actor_bounds_metrics(candidate)
            playable = p._is_actor_bounds_playable(c, candidate)
            print(f"Actor {c} load success. Metrics: {metrics}, Playable: {playable}")
        except Exception as e:
            print(f"Actor {c} load FAILED: {e}")

print("--- End Debug ---")
base.destroy()
