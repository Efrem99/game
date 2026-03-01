"""Launcher for dragon feature testing."""

import os

from launch_bootstrap import run_app


def main():
    os.environ["XBOT_TEST_PROFILE"] = "dragon"
    os.environ.setdefault("XBOT_TEST_LOCATION", "dragon_arena")
    return run_app(
        startup_tag="--- Starting XBot RPG [DRAGON TEST] ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())

