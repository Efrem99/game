"""Single .pyw entry point for all test profiles."""

from launchers.pyw_bootstrap import run_launcher_script


if __name__ == "__main__":
    raise SystemExit(run_launcher_script("launcher_test_hub.py"))
