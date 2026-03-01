"""Launcher for journal UI and quest log testing."""

import os

from launch_bootstrap import run_app


def main():
    os.environ["XBOT_TEST_PROFILE"] = "journal"
    os.environ.setdefault("XBOT_TEST_LOCATION", "town")
    return run_app(
        startup_tag="--- Starting XBot RPG [JOURNAL TEST] ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())

