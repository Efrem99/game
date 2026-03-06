"""Launcher for music routing and ambient transitions testing."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import os

from launchers.bootstrap import run_app


def main():
    os.environ["XBOT_TEST_PROFILE"] = "music"
    os.environ.setdefault("XBOT_TEST_LOCATION", "docks")
    return run_app(
        startup_tag="--- Starting XBot RPG [MUSIC TEST] ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())


