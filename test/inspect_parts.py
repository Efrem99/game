
import sys
from pathlib import Path

ROOT = Path(r'C:/xampp/htdocs/king-wizard')
sys.path.append(str(ROOT / 'src'))

from panda3d.core import loadPrcFileData, getModelPath, Filename
loadPrcFileData("", "window-type none")
from direct.showbase.ShowBase import ShowBase
base = ShowBase()

# Add ROOT and assets to model path
getModelPath().appendDirectory(Filename.from_os_specific(str(ROOT)))
getModelPath().appendDirectory(Filename.from_os_specific(str(ROOT / "assets")))

from direct.actor.Actor import Actor

model_path = "models/xbot/Xbot.glb"
print(f"Loading {model_path}...")
try:
    a = Actor(model_path)
    print(f"Parts: {a.getPartNames()}")
except Exception as e:
    print(f"Error: {e}")

base.destroy()
