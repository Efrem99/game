"""Launcher for mount/vehicle feature testing."""

import os

from launch_bootstrap import run_app


def main():
    os.environ["XBOT_TEST_PROFILE"] = "mounts"
    os.environ.setdefault("XBOT_TEST_LOCATION", "9,6,0")
    return run_app(
        startup_tag="--- Starting XBot RPG [MOUNTS TEST] ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())

