"""Pyw wrapper for launcher_test_manifest.py."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from launchers.pyw_bootstrap import run_launcher_script


if __name__ == "__main__":
    raise SystemExit(run_launcher_script("launchers/tests/launcher_test_manifest.py"))
