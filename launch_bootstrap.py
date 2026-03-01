"""Shared startup helpers for XBot RPG launchers."""

import ctypes
import os
import sys
import traceback

_ERROR_ALREADY_EXISTS = 183
_INSTANCE_MUTEX_NAME = "Global\\AntiGravity.XBotRPG.SingleInstance"
_INSTANCE_MUTEX_HANDLE = None


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
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def run_app(startup_tag, error_handler=None, pause_on_error=False):
    if not _acquire_single_instance():
        # Temporarily ignoring the mutex lock so we can recover from crashes
        # that leave orphaned mutexes behind.
        pass

    root = os.path.dirname(os.path.abspath(__file__))
    try:
        _prepare_runtime(root)

        logger = None
        try:
            from utils.logger import logger as app_logger

            logger = app_logger
            logger.info(startup_tag)
            logger.info(f"Working Directory: {os.getcwd()}")
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
            error_text = f"FATAL ERROR during startup:\n{exc}\n\nSee logs/game.log for details."
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
