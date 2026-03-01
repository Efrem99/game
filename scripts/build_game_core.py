#!/usr/bin/env python3
"""Build helper for game_core.pyd on Windows."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build-cpp"


def emit(message: str):
    text = str(message)
    try:
        print(text)
    except UnicodeEncodeError:
        enc = (getattr(sys.stdout, "encoding", None) or "utf-8")
        safe = text.encode(enc, errors="backslashreplace").decode(enc, errors="replace")
        print(safe)


def run(cmd, cwd=None):
    emit("> " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def ensure_module(module_name: str, package_name: str | None = None):
    package = package_name or module_name
    try:
        __import__(module_name)
    except Exception:
        run([sys.executable, "-m", "pip", "install", package])


def main() -> int:
    if sys.platform != "win32":
        emit("[build_game_core] This helper currently supports Windows only.")
        return 2

    ensure_module("pybind11")
    ensure_module("cmake")

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)

    cmake_cmd = [sys.executable, "-m", "cmake"]
    generators = [
        ("vs2022", ["-G", "Visual Studio 17 2022", "-A", "x64"]),
        ("vs2019", ["-G", "Visual Studio 16 2019", "-A", "x64"]),
    ]

    configured = False
    configured_build_dir = None
    last_error = ""
    for tag, gen in generators:
        build_dir = BUILD_ROOT / tag
        build_dir.mkdir(parents=True, exist_ok=True)
        try:
            run(cmake_cmd + ["-S", str(ROOT), "-B", str(build_dir)] + gen)
            configured = True
            configured_build_dir = build_dir
            break
        except Exception as exc:
            last_error = str(exc)
            continue

    if not configured:
        emit("")
        emit("[build_game_core] Could not configure CMake with Visual Studio generator.")
        emit("[build_game_core] Install Visual Studio Build Tools with 'Desktop development with C++'.")
        emit("[build_game_core] Last error:")
        emit(last_error)
        return 3

    run(cmake_cmd + ["--build", str(configured_build_dir), "--config", "Release"])

    out_file = ROOT / "game_core.pyd"
    if out_file.exists():
        emit(f"[build_game_core] Success: {out_file}")
        return 0

    # Fallback search in build tree and copy to root.
    built_candidates = list((configured_build_dir or BUILD_ROOT).rglob("game_core.pyd"))
    if built_candidates:
        src = built_candidates[0]
        shutil.copy2(src, out_file)
        emit(f"[build_game_core] Copied: {src} -> {out_file}")
        return 0

    emit("[build_game_core] Build finished but game_core.pyd was not found.")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
