"""Validate player animation manifest integrity."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.animation_manifest import validate_player_manifest  # noqa: E402


def main():
    result = validate_player_manifest(
        manifest_path=str(ROOT / "data" / "actors" / "player_animations.json"),
        state_path=str(ROOT / "data" / "states" / "player_states.json"),
    )
    print(
        "[Manifest] sources={sources} player_states={states}".format(
            sources=result.get("manifest_source_count", 0),
            states=result.get("player_state_count", 0),
        )
    )

    for warning in result.get("warnings", []):
        print(f"[WARN] {warning}")
    for error in result.get("errors", []):
        print(f"[ERROR] {error}")

    if result.get("ok"):
        print("[Manifest] OK")
        return 0
    print("[Manifest] FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
