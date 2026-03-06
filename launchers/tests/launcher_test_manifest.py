"""Launcher for validating animation manifest/state coverage."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import subprocess


if __name__ == "__main__":
    root = ROOT
    script = root / "scripts" / "validate_player_manifest.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(root))
    raise SystemExit(result.returncode)


