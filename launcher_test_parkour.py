"""Launcher for focused parkour traversal testing."""

import os

from launch_bootstrap import run_app


def main():
    os.environ["XBOT_TEST_PROFILE"] = "parkour"
    os.environ.setdefault("XBOT_TEST_LOCATION", "parkour")
    return run_app(
        startup_tag="--- Starting XBot RPG [PARKOUR TEST] ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
