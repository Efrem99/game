"""Launcher for runtime-oriented player animation coverage report."""

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "player_anim_runtime_report.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(root))
    raise SystemExit(result.returncode)
