#!/usr/bin/env python3
"""Sync workspace files to a target game folder.

Usage examples:
  python scripts/sync_to_target.py --target "D:\\Games\\KingWizard"
  python scripts/sync_to_target.py --watch --interval 1.5 --target "D:\\Games\\KingWizard"
  python scripts/sync_to_target.py --mirror --target "D:\\Games\\KingWizard"
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path


SYNC_TARGET_ENV = "GAME_SYNC_TARGET"
EXCLUDE_DIRS = {
    ".git",
    ".codex",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "tmp",
    "logs",
}
EXCLUDE_FILE_NAMES = {
    "Thumbs.db",
    ".DS_Store",
}
EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".tmp",
    ".log",
}


@dataclass
class SyncStats:
    copied: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    errors: int = 0

    @property
    def changed(self) -> int:
        return self.copied + self.updated + self.removed


def _norm(path: Path) -> str:
    return str(path).replace("\\", "/").lower()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _skip_relative(rel_path: Path) -> bool:
    for part in rel_path.parts[:-1]:
        if part in EXCLUDE_DIRS:
            return True
    if rel_path.name in EXCLUDE_FILE_NAMES:
        return True
    if rel_path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return False


def _iter_source_files(source: Path):
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        if _skip_relative(rel):
            continue
        yield rel, path


def _files_differ(src: Path, dst: Path) -> bool:
    try:
        src_stat = src.stat()
        dst_stat = dst.stat()
    except Exception:
        return True
    if src_stat.st_size != dst_stat.st_size:
        return True
    # Use second precision tolerance for cross-volume writes.
    return int(src_stat.st_mtime) != int(dst_stat.st_mtime)


def _log(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        # Some Windows consoles use legacy encodings (e.g. cp1252) and fail
        # on Cyrillic paths; degrade gracefully instead of crashing watch mode.
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe)


def sync_once(source: Path, target: Path, mirror: bool = False) -> SyncStats:
    stats = SyncStats()
    expected_targets = set()

    for rel, src in _iter_source_files(source):
        dst = target / rel
        expected_targets.add(_norm(dst))
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
                stats.copied += 1
            elif _files_differ(src, dst):
                shutil.copy2(src, dst)
                stats.updated += 1
            else:
                stats.unchanged += 1
        except Exception:
            stats.errors += 1

    if mirror:
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(target)
            if _skip_relative(rel):
                continue
            if _norm(path) in expected_targets:
                continue
            try:
                path.unlink()
                stats.removed += 1
            except Exception:
                stats.errors += 1

    return stats


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync current project to a target folder.")
    parser.add_argument("--source", default=".", help="Project root to sync (default: current directory).")
    parser.add_argument(
        "--target",
        default=os.environ.get(SYNC_TARGET_ENV, ""),
        help=f"Destination folder (or set {SYNC_TARGET_ENV}).",
    )
    parser.add_argument("--watch", action="store_true", help="Repeat sync in a loop.")
    parser.add_argument("--interval", type=float, default=1.5, help="Watch interval in seconds.")
    parser.add_argument("--mirror", action="store_true", help="Delete files in target that do not exist in source.")
    parser.add_argument("--quiet-unchanged", action="store_true", help="Suppress unchanged cycle logs in watch mode.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    source = Path(args.source).resolve()
    target_arg = str(args.target or "").strip()

    if not target_arg:
        _log(f"[sync] Missing target. Pass --target <path> or set {SYNC_TARGET_ENV}.")
        return 2

    target = Path(target_arg).resolve()

    if not source.exists() or not source.is_dir():
        _log(f"[sync] Source is invalid: {source}")
        return 2

    if _is_relative_to(target, source):
        _log("[sync] Refusing to sync: target is inside source tree.")
        return 2

    target.mkdir(parents=True, exist_ok=True)

    def _run_once() -> SyncStats:
        started = time.time()
        stats = sync_once(source, target, mirror=bool(args.mirror))
        elapsed = (time.time() - started) * 1000.0
        if stats.changed or stats.errors or not args.quiet_unchanged:
            _log(
                "[sync] copied={0} updated={1} removed={2} unchanged={3} errors={4} "
                "elapsed_ms={5:.1f}".format(
                    stats.copied,
                    stats.updated,
                    stats.removed,
                    stats.unchanged,
                    stats.errors,
                    elapsed,
                )
            )
        return stats

    if not args.watch:
        stats = _run_once()
        return 1 if stats.errors else 0

    interval = max(0.25, float(args.interval or 1.5))
    _log(f"[sync] Watching {source} -> {target} (interval={interval:.2f}s, mirror={bool(args.mirror)})")
    try:
        while True:
            _run_once()
            time.sleep(interval)
    except KeyboardInterrupt:
        _log("[sync] Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
