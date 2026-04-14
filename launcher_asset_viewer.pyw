"""GUI-friendly entry point for the asset animation viewer."""

from launchers.pyw_bootstrap import run_launcher_script


if __name__ == "__main__":
    raise SystemExit(
        run_launcher_script(
            "launchers/tests/launcher_test_asset_viewer.py",
            window_title="XBot Asset Viewer Launcher Error",
        )
    )
