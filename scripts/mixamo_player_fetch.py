#!/usr/bin/env python3
"""
Fetch missing player gameplay animations from Mixamo and patch runtime manifest.

Usage:
  python scripts/mixamo_player_fetch.py --token-env MIXAMO_ACCESS_TOKEN
  python scripts/mixamo_player_fetch.py --dry-run --only crouch_idle,crouch_move
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List

import mixamo_mount_fetch as base


TARGET_QUERIES: Dict[str, List[str]] = {
    # Core locomotion transitions missing from the current XBot runtime set
    "jumping": [
        "jump",
        "jumping",
        "jump start",
    ],
    "falling": [
        "falling",
        "midair",
        "in air",
    ],
    "landing": [
        "landing",
        "land",
        "hard landing",
    ],
    # Fast magic cast (fireball-like)
    "cast_fast": [
        "spell cast",
        "magic spell cast",
        "throw",
    ],
    # Ranged bow handling
    "bow_aim": [
        "standing aiming",
        "archery aim",
        "aiming bow",
    ],
    "bow_shoot": [
        "standing shoot arrow",
        "archery shot",
        "firing bow",
    ],
    # Combat locomotion
    "run_blade": [
        "sword and shield run",
        "run with sword",
        "running",
    ],
    # Melee combat
    "attack_light_right": [
        "one handed sword attack",
        "sword slash",
        "sword attack",
    ],
    "attack_thrust_right": [
        "sword thrust",
        "sword stab",
        "one handed sword attack",
    ],
    "blocking": [
        "shield block",
        "block",
        "sword and shield idle",
    ],
    # Weapon ready-state transitions
    "weapon_unsheathe": [
        "draw sword",
        "unsheathe sword",
        "take out sword",
    ],
    "weapon_sheathe": [
        "sheath sword",
        "put away sword",
        "sword put away",
    ],
    # Stealth / crouch
    "crouch_idle": [
        "crouched idle",
        "crouch idle",
        "sneaking idle",
    ],
    "crouch_move": [
        "sneaking forward",
        "crouched walking",
        "sneak walk",
    ],
    # Magic phases
    "cast_prepare": [
        "spell prepare",
        "magic spell cast",
        "spell casting",
    ],
    "cast_channel": [
        "spellcasting loop",
        "magic channel",
        "spell channeling",
        "spell casting",
        "magic spell cast",
    ],
    "cast_release": [
        "spell cast",
        "magic attack",
        "cast release",
    ],
    # Parkour variants
    "climb_fast": [
        "climbing",
        "climb up",
        "ledge climb",
    ],
    "climb_slow": [
        "climbing ladder",
        "climb up",
        "ledge climb",
    ],
    "vault_low": [
        "vault",
        "hurdle jump",
        "jump over",
    ],
    "vault_high": [
        "vault",
        "hurdle jump",
        "jump over",
    ],
    "wallrun_start": [
        "parkour run",
        "running jump",
        "wall run",
    ],
    "wallrun_exit": [
        "jump down",
        "landing",
        "parkour roll",
    ],
    # Swim variant used by fallback tree
    "swim_surface": [
        "swimming",
        "swim forward",
        "treading water",
    ],
}


# Optional pin map. Keep empty by default so search fallback can adapt.
TARGET_PRODUCT_IDS: Dict[str, str] = {}


DEFAULT_LOOPS: Dict[str, bool] = {
    "jumping": False,
    "falling": True,
    "landing": False,
    "cast_fast": False,
    "bow_aim": True,
    "bow_shoot": False,
    "run_blade": True,
    "attack_light_right": False,
    "attack_thrust_right": False,
    "blocking": True,
    "weapon_unsheathe": False,
    "weapon_sheathe": False,
    "crouch_idle": True,
    "crouch_move": True,
    "cast_prepare": False,
    "cast_channel": True,
    "cast_release": False,
    "climb_fast": False,
    "climb_slow": False,
    "vault_low": False,
    "vault_high": False,
    "wallrun_start": False,
    "wallrun_exit": False,
    "swim_surface": True,
}


def _resolve_targets(only: str) -> List[str]:
    keys = list(TARGET_QUERIES.keys())
    if not only:
        return keys
    requested = [part.strip().lower() for part in only.split(",") if part.strip()]
    return [key for key in keys if key in requested]


def _apply_mixamo_overrides():
    base.TARGET_QUERIES = dict(TARGET_QUERIES)
    base.TARGET_PRODUCT_IDS = dict(TARGET_PRODUCT_IDS)
    merged_loops = dict(getattr(base, "DEFAULT_LOOPS", {}))
    merged_loops.update(DEFAULT_LOOPS)
    base.DEFAULT_LOOPS = merged_loops


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download missing gameplay animations from Mixamo."
    )
    parser.add_argument(
        "--token",
        default="",
        help="Mixamo bearer token. If omitted, --token-env is used.",
    )
    parser.add_argument(
        "--token-env",
        default="MIXAMO_ACCESS_TOKEN",
        help="Environment variable name for Mixamo bearer token.",
    )
    parser.add_argument(
        "--character-id",
        default=os.environ.get("MIXAMO_CHARACTER_ID", base.DEFAULT_CHARACTER_ID),
        help="Mixamo character id (defaults to XBot).",
    )
    parser.add_argument(
        "--manifest",
        default="data/actors/player_animations.json",
        help="Path to player animation manifest.",
    )
    parser.add_argument(
        "--out-dir",
        default="assets/anims/mixamo/player",
        help="Output folder for downloaded clips.",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated subset of keys to fetch.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=45.0,
        help="HTTP timeout for Mixamo requests.",
    )
    parser.add_argument(
        "--max-wait-sec",
        type=float,
        default=120.0,
        help="Maximum export wait time per clip.",
    )
    parser.add_argument(
        "--poll-sec",
        type=float,
        default=1.5,
        help="Polling interval for export monitor endpoint.",
    )
    parser.add_argument(
        "--request-delay-sec",
        type=float,
        default=1.2,
        help="Delay between target exports to reduce rate limiting.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Retry count for retryable HTTP statuses (429/5xx).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only resolve candidates, do not download or patch files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _apply_mixamo_overrides()

    token = str(args.token or "").strip()
    if not token:
        token = str(os.environ.get(str(args.token_env), "")).strip()
    if not token:
        print(
            f"[mixamo] token is missing. Set --token or environment variable {args.token_env}.",
            file=sys.stderr,
        )
        return 2

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[mixamo] manifest not found: {manifest_path.as_posix()}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    targets = _resolve_targets(args.only)
    if not targets:
        print("[mixamo] no valid targets selected", file=sys.stderr)
        return 2

    client = base.MixamoClient(
        token=token,
        timeout_sec=args.timeout_sec,
        max_retries=args.max_retries,
    )

    print(f"[mixamo] character_id={args.character_id}")
    print(f"[mixamo] targets={len(targets)} dry_run={bool(args.dry_run)}")
    fetched, failed = base.fetch_targets(
        client=client,
        character_id=str(args.character_id).strip(),
        targets=targets,
        out_dir=out_dir,
        dry_run=bool(args.dry_run),
        max_wait_sec=float(args.max_wait_sec),
        poll_sec=float(args.poll_sec),
        request_delay_sec=float(args.request_delay_sec),
    )

    changed = 0
    if not args.dry_run:
        changed = base.patch_manifest(manifest_path, fetched, dry_run=False)

    print("")
    print("[mixamo] summary")
    print(f"  resolved: {len(fetched)}")
    if not args.dry_run:
        print(f"  manifest updates: {changed}")
    print(f"  failed: {len(failed)}")
    for key, reason in failed.items():
        print(f"    - {key}: {reason}")

    return 0 if fetched else 1


if __name__ == "__main__":
    raise SystemExit(main())
