import logging
from logging.handlers import RotatingFileHandler
import sys
import os
from datetime import datetime
from utils.runtime_paths import runtime_dir

def setup_logger():
    # Create log directory if it doesn't exist
    log_dir = runtime_dir("logs")

    logger = logging.getLogger("XBotRPG")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Console logging — only if stdout is available (not .pyw windowless mode).
    if sys.stdout is not None:
        import io
        try:
            utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except Exception:
            utf8_stdout = sys.stdout
        stream_handler = logging.StreamHandler(utf8_stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    log_file = str(log_dir / "game.log")
    file_handler = None
    try:
        # Keep logs bounded to avoid multi-hundred-MB growth during long sessions.
        file_handler = RotatingFileHandler(
            log_file,
            mode="a",
            maxBytes=25 * 1024 * 1024,
            backupCount=6,
            encoding="utf-8",
        )
    except Exception:
        # Fallback for locked/invalid file states.
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = str(log_dir / f"game_{ts}_{os.getpid()}.log")
        try:
            file_handler = RotatingFileHandler(
                fallback,
                mode="a",
                maxBytes=25 * 1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
        except Exception:
            file_handler = None

    if file_handler:
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.info(f"Logger initialized. Outputting to console and {log_file}")
    return logger

# Global logger instance
logger = setup_logger()
