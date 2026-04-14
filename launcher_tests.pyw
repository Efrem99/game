"""GUI-friendly entry point for the unified test hub."""

from launchers.pyw_bootstrap import run_launcher_script


if __name__ == "__main__":
    raise SystemExit(
        run_launcher_script(
            "launcher_test_hub.py",
            window_title="XBot Test Launcher Error",
        )
    )
