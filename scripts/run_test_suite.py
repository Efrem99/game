"""Run the project's Python unittest suite with a stable entrypoint.

Usage:
  python scripts/run_test_suite.py
  python scripts/run_test_suite.py -k adaptive
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _build_command(name_filter: str = "") -> list[str]:
    pattern = "test_*.py" if not name_filter else f"test_*{name_filter}*.py"
    return [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        pattern,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run project unittest suite.")
    parser.add_argument(
        "-k",
        "--filter",
        default="",
        help="Optional substring filter for test filenames.",
    )
    args = parser.parse_args()

    cmd = _build_command(str(args.filter or "").strip())
    print(f"[TestSuite] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0:
        print("[TestSuite] OK")
    else:
        print(f"[TestSuite] FAILED (exit={result.returncode})")
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
