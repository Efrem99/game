"""Launcher for full mechanics sandbox testing (combat, magic, parkour, mounts, flight)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import os

from launchers.bootstrap import run_app


def main():
    os.environ["XBOT_TEST_PROFILE"] = "mechanics"
    os.environ.setdefault("XBOT_TEST_LOCATION", "training")
    os.environ.setdefault("XBOT_TEST_FALLBACK_UI", "1")
    return run_app(
        startup_tag="--- Starting XBot RPG [MECHANICS SANDBOX TEST] ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
