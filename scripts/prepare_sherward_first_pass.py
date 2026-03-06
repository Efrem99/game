"""Prepare first-pass Shervard asset.

Behavior:
1) If Blender is available, run the Shervard builder script.
2) Otherwise, create a temporary runtime-ready `sherward.glb` by copying Xbot.

This keeps gameplay wiring stable while art is iterated.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
ASSET_OUT = ROOT / "assets" / "models" / "hero" / "sherward" / "sherward.glb"
ASSET_META = ROOT / "assets" / "models" / "hero" / "sherward" / "sherward.asset.json"
XBOT_SRC = ROOT / "assets" / "models" / "xbot" / "Xbot.glb"
BUILD_SCRIPT = MODELS_DIR / "build_sherward_base.py"


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _find_blender():
    env_path = str(os.environ.get("BLENDER_EXE", "") or "").strip()
    if env_path and Path(env_path).exists():
        return Path(env_path)

    candidates = []
    pf = Path(r"C:\Program Files\Blender Foundation")
    if pf.exists():
        # Prefer newest installed Blender version first (e.g. Blender 5.0).
        for folder in sorted(pf.glob("Blender*"), reverse=True):
            candidates.append(folder / "blender.exe")

    # Common explicit fallbacks.
    candidates.extend(
        [
            Path(r"C:\Program Files\Blender Foundation\Blender\blender.exe"),
            Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"),
            Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"),
            Path(r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"),
            Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
        ]
    )

    # Portable Blender on OneDrive Desktop (localized names included).
    one_drive = Path(os.environ.get("OneDrive", ""))
    if one_drive.exists():
        for desktop_name in ("Desktop", "Työpöytä", "Рабочий стол"):
            desk = one_drive / desktop_name
            if not desk.exists():
                continue
            candidates.append(desk / "blender.exe")
            for folder in sorted(desk.glob("Blender*"), reverse=True):
                candidates.append(folder / "blender.exe")
            for path in desk.glob("**/blender.exe"):
                candidates.append(path)

    for path in candidates:
        if path.exists():
            return path
    return None


def _write_meta(payload):
    ASSET_META.parent.mkdir(parents=True, exist_ok=True)
    ASSET_META.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _copy_xbot_placeholder():
    if not XBOT_SRC.exists():
        raise RuntimeError(f"Missing source fallback model: {XBOT_SRC}")
    ASSET_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(XBOT_SRC, ASSET_OUT)
    payload = {
        "id": "sherward_first_pass_placeholder",
        "generated_at_utc": _utc_now(),
        "pipeline": "placeholder_copy",
        "source_model": _rel(XBOT_SRC),
        "output_model": _rel(ASSET_OUT),
        "notes": [
            "Temporary first-pass asset copied from Xbot.",
            "Replace with Blender export using models/build_sherward_base.py.",
        ],
    }
    _write_meta(payload)
    print(f"[SherwardPrep] Placeholder copied: {_rel(ASSET_OUT)}")
    return 0


def _run_blender_build(blender_exe):
    ASSET_OUT.parent.mkdir(parents=True, exist_ok=True)
    out_blend = ROOT / "models" / "sherward_character.blend"
    cmd = [
        str(blender_exe),
        "--background",
        "--python",
        str(BUILD_SCRIPT),
        "--",
        "--base-model",
        str(XBOT_SRC),
        "--target-height",
        "1.85",
        "--output-blend",
        str(out_blend),
        "--export-glb",
        str(ASSET_OUT),
        "--add-facial-control-hooks",
    ]
    shown_cmd = [str(blender_exe), "--background", "--python", _rel(BUILD_SCRIPT), "--", "..."]
    print(f"[SherwardPrep] Running Blender build: {' '.join(shown_cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"Blender build failed with code {result.returncode}")

    payload = {
        "id": "sherward_first_pass_blender",
        "generated_at_utc": _utc_now(),
        "pipeline": "blender_build_sherward_base",
        "blender_exe": str(blender_exe),
        "build_script": _rel(BUILD_SCRIPT),
        "output_model": _rel(ASSET_OUT),
    }
    _write_meta(payload)
    print(f"[SherwardPrep] Blender first-pass ready: {_rel(ASSET_OUT)}")
    return 0


def main():
    blender = _find_blender()
    try:
        if blender and BUILD_SCRIPT.exists():
            return _run_blender_build(blender)
        print("[SherwardPrep] Blender not found. Falling back to placeholder copy.")
        return _copy_xbot_placeholder()
    except Exception as exc:
        print(f"[SherwardPrep] ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
