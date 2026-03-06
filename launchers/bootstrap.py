"""Shared startup helpers for XBot RPG launchers."""

import ctypes
import os
import sys
import traceback

_ERROR_ALREADY_EXISTS = 183
_INSTANCE_MUTEX_NAME = "Global\\AntiGravity.XBotRPG.SingleInstance"
_INSTANCE_MUTEX_HANDLE = None


def _runtime_log_hint():
    user_root = str(os.environ.get("XBOT_USER_DATA_DIR", "") or "").strip()
    if user_root:
        return os.path.join(user_root, "logs", "game.log")
    return "logs/game.log"


def show_messagebox_error(title, message):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass


def _acquire_single_instance():
    global _INSTANCE_MUTEX_HANDLE
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, _INSTANCE_MUTEX_NAME)
        if not handle:
            return True
        if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        _INSTANCE_MUTEX_HANDLE = handle
        return True
    except Exception:
        return True


def _release_single_instance():
    global _INSTANCE_MUTEX_HANDLE
    if not _INSTANCE_MUTEX_HANDLE:
        return
    try:
        ctypes.windll.kernel32.CloseHandle(_INSTANCE_MUTEX_HANDLE)
    except Exception:
        pass
    _INSTANCE_MUTEX_HANDLE = None


def _prepare_runtime(root):
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault("XBOT_PROJECT_ROOT", root)

    # Player installs (frozen exe) should never write runtime artifacts into Program Files.
    if getattr(sys, "frozen", False):
        user_root = str(os.environ.get("XBOT_USER_DATA_DIR", "") or "").strip()
        if not user_root:
            local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
            if local_app_data:
                user_root = os.path.join(local_app_data, "KingWizardRPG")
            else:
                user_root = os.path.join(os.path.expanduser("~"), "KingWizardRPG")
            os.environ["XBOT_USER_DATA_DIR"] = user_root
        try:
            for folder in ("logs", "saves", "cache"):
                os.makedirs(os.path.join(user_root, folder), exist_ok=True)
        except Exception:
            pass


def run_app(startup_tag, error_handler=None, pause_on_error=False):
    if not _acquire_single_instance():
        # Temporarily ignoring the mutex lock so we can recover from crashes
        # that leave orphaned mutexes behind.
        pass

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        _prepare_runtime(root)

        logger = None
        try:
            from utils.logger import logger as app_logger

            logger = app_logger
            logger.info(startup_tag)
            logger.info(f"Working Directory: {os.getcwd()}")

            skip_preflight = str(os.environ.get("XBOT_SKIP_PREFLIGHT", "")).strip().lower() in {"1", "true", "yes"}
            strict_preflight = str(os.environ.get("XBOT_STRICT_PREFLIGHT", "")).strip().lower() in {"1", "true", "yes"}
            if not skip_preflight:
                try:
                    from utils.preflight_checks import run_startup_preflight

                    preflight = run_startup_preflight(root, logger=logger, strict=strict_preflight)
                    if strict_preflight and not bool(preflight.get("ok", False)):
                        logger.error("[Preflight] Strict mode enabled; aborting startup due to preflight errors.")
                        if pause_on_error:
                            input("Preflight failed. Press Enter to close...")
                        return 1
                except Exception as exc:
                    logger.warning(f"[Preflight] Startup preflight failed unexpectedly: {exc}")
        except Exception as exc:
            message = f"Logger initialization failed:\n{exc}"
            if error_handler:
                error_handler("Logger Init Failed", message)
            else:
                print(message)
                traceback.print_exc()
            if pause_on_error:
                input("Press Enter to close...")
            return 1

        try:
            from app import XBotApp

            logger.info("Initializing XBotApp...")
            app = XBotApp()
            logger.info("Starting Main Loop (app.run)...")
            app.run()
            return 0
        except Exception as exc:
            details = traceback.format_exc()
            error_text = f"FATAL ERROR during startup:\n{exc}\n\nSee {_runtime_log_hint()} for details."
            try:
                logger.error(error_text)
                logger.error(details)
            except Exception:
                pass

            if error_handler:
                error_handler("XBot RPG Error", error_text)
            else:
                print(error_text)
                print(details)

            if pause_on_error:
                input("Press Enter to close...")
            return 1
    finally:
        _release_single_instance()

