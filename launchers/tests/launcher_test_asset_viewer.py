"""Launcher for interactive asset + animation viewer utility."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import subprocess


if __name__ == "__main__":
    root = ROOT
    script = root / "scripts" / "asset_animation_viewer.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(root))
    raise SystemExit(result.returncode)
