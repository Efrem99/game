"""Primary entry point for the King Wizard RPG."""

import os
import sys

# Ensure we're in the project root
root = os.path.dirname(os.path.abspath(__file__))
os.chdir(root)

# Use the shared bootstrap logic to launch the game
try:
    from launchers.bootstrap import run_app
    
    if __name__ == "__main__":
        # Process command line arguments and launch
        sys.exit(run_app(
            startup_tag="[KingWizard] Initializing from main.py",
            pause_on_error=True
        ))
except ImportError as exc:
    print(f"FATAL: Could not initialize bootstrap launcher: {exc}")
    sys.exit(1)
except Exception as exc:
    print(f"FATAL: Unexpected error during startup: {exc}")
    sys.exit(1)
