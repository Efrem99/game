"""Standard regular launcher for King Wizard RPG."""
import sys
import os

# Append src to path just in case, though bootstrap usually handles it
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from launchers.bootstrap import run_app, show_messagebox_error

def main():
    return run_app(
        startup_tag="--- Starting King Wizard [Regular Mode] ---",
        error_handler=show_messagebox_error
    )

if __name__ == "__main__":
    main()
