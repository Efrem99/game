#!/usr/bin/env python3
"""Build helper for game_core.pyd on Windows."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def project_root_from_script(script_file: str | Path) -> Path:
    # Preserve the invoked Windows path instead of resolving junctions/symlinks
    # into a potentially non-ASCII real path that MSBuild handles poorly.
    return Path(script_file).absolute().parents[1]


ROOT = project_root_from_script(__file__)
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


def _vswhere_path() -> Path:
    return Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")


def visual_studio_installations() -> list[dict]:
    vswhere = _vswhere_path()
    if not vswhere.exists():
        return []
    result = subprocess.run(
        [str(vswhere), "-all", "-products", "*", "-format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout or "[]")
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _generator_info_for_major(version_major: int) -> tuple[str, str] | None:
    if version_major == 18:
        return ("vs2026", "Visual Studio 18 2026")
    if version_major == 17:
        return ("vs2022", "Visual Studio 17 2022")
    if version_major == 16:
        return ("vs2019", "Visual Studio 16 2019")
    return None


def visual_studio_generators(instances: list[dict] | None = None) -> list[tuple[str, list[str]]]:
    payload = instances if instances is not None else visual_studio_installations()
    detected: list[tuple[int, str, list[str]]] = []
    seen_majors: set[int] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        version_text = str(item.get("installationVersion", "") or "").strip()
        instance_path = str(item.get("installationPath", "") or "").strip()
        try:
            version_major = int(version_text.split(".", 1)[0])
        except Exception:
            continue
        if version_major in seen_majors:
            continue
        info = _generator_info_for_major(version_major)
        if not info:
            continue
        tag, name = info
        args = ["-G", name, "-A", "x64"]
        if instance_path:
            args.append(f"-DCMAKE_GENERATOR_INSTANCE:PATH={instance_path}")
        detected.append((version_major, tag, args))
        seen_majors.add(version_major)

    detected.sort(key=lambda item: item[0], reverse=True)
    generators = [(tag, args) for _, tag, args in detected]

    for version_major in (18, 17, 16):
        if version_major in seen_majors:
            continue
        info = _generator_info_for_major(version_major)
        if not info:
            continue
        tag, name = info
        generators.append((tag, ["-G", name, "-A", "x64"]))
    return generators


def built_module_source(root: Path, configured_build_dir: Path | None) -> Path | None:
    out_file = root / "game_core.pyd"
    search_roots: list[Path] = []
    if configured_build_dir:
        search_roots.append(configured_build_dir)
    search_roots.extend([root / "Release", root / "build-cpp", root])

    candidates: list[Path] = []
    seen: set[Path] = set()
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for candidate in search_root.rglob("game_core.pyd"):
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: (
            candidate.stat().st_mtime,
            candidate == out_file,
            candidate.stat().st_size,
        ),
        reverse=True,
    )
    return candidates[0]


def main() -> int:
    if sys.platform != "win32":
        emit("[build_game_core] This helper currently supports Windows only.")
        return 2

    ensure_module("pybind11")
    ensure_module("cmake")

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)

    cmake_cmd = [sys.executable, "-m", "cmake"]
    generators = visual_studio_generators()

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
    best_candidate = built_module_source(ROOT, configured_build_dir)
    if best_candidate is None:
        emit("[build_game_core] Build finished but game_core.pyd was not found.")
        return 4

    if best_candidate != out_file:
        shutil.copy2(best_candidate, out_file)
        emit(f"[build_game_core] Copied: {best_candidate} -> {out_file}")

    emit(f"[build_game_core] Success: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
