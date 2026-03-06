"""Prepare first-pass Shervard asset (Blender build or placeholder copy)."""

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "prepare_sherward_first_pass.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(root))
    raise SystemExit(result.returncode)
