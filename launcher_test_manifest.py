"""Launcher for validating animation manifest/state coverage."""

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "validate_player_manifest.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(root))
    raise SystemExit(result.returncode)
