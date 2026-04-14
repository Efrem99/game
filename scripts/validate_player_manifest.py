"""Compatibility wrapper for the themed player manifest validator entry point."""

from scripts.animation.validate_player_manifest import main


if __name__ == "__main__":
    raise SystemExit(main())
