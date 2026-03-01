"""Launcher for skill wheel and combat spell testing."""

import os

from launch_bootstrap import run_app


def main():
    os.environ["XBOT_TEST_PROFILE"] = "skills"
    os.environ.setdefault("XBOT_TEST_LOCATION", "0,0,0")
    return run_app(
        startup_tag="--- Starting XBot RPG [SKILLS TEST] ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())

