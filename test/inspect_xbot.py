
import sys
from pathlib import Path

ROOT = Path(r'C:/xampp/htdocs/king-wizard')
sys.path.append(str(ROOT / 'src'))

from panda3d.core import loadPrcFileData
loadPrcFileData("", "window-type none")
from direct.showbase.ShowBase import ShowBase
base = ShowBase()

from direct.actor.Actor import Actor

model_path = str(ROOT / "assets/models/xbot/Xbot.glb")
print(f"Loading {model_path}...")
try:
    a = Actor(model_path)
    print("Hierarchy:")
    a.listJoints()
    
    print("\nAnimations listed in file (if any):")
    # In Panda3D gltf loader, tracks are usually available as anim parts
    # but let's see what getAnimNames returns for a fresh actor
    print(f"Anim Names: {a.getAnimNames()}")
    
except Exception as e:
    print(f"Error: {e}")

base.destroy()
