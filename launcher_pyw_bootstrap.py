"""Helpers for .pyw wrappers around launcher scripts."""

import os
import runpy
import sys
import traceback
from pathlib import Path

from launch_bootstrap import show_messagebox_error


def _normalize_exit_code(raw_code):
    if raw_code is None:
        return 0
    if isinstance(raw_code, bool):
        return int(raw_code)
    if isinstance(raw_code, int):
        return raw_code
    try:
        return int(raw_code)
    except Exception:
        return 1


def run_launcher_script(script_name, *, window_title="XBot Launcher Error"):
    root = Path(__file__).resolve().parent
    os.chdir(root)
    src_dir = root / "src"
    src_dir_str = str(src_dir)
    if src_dir_str not in sys.path:
        sys.path.insert(0, src_dir_str)

    script_path = root / str(script_name)
    if not script_path.exists():
        show_messagebox_error(window_title, f"Launcher script not found:\n{script_path}")
        return 1

    try:
        runpy.run_path(str(script_path), run_name="__main__")
        return 0
    except SystemExit as exc:
        return _normalize_exit_code(exc.code)
    except Exception as exc:
        show_messagebox_error(
            window_title,
            f"FATAL ERROR in {script_path.name}:\n{exc}\n\nSee logs/game.log for details.",
        )
        try:
            from utils.logger import logger

            logger.error(f"[LauncherPYW] {script_path.name} failed: {exc}")
            logger.error(traceback.format_exc())
        except Exception:
            pass
        return 1
