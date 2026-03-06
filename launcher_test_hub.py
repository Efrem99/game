"""Unified launcher with menu-driven test profile selection."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from launch_bootstrap import run_app


RUNTIME_TESTS = {
    "dragon": {
        "profile": "dragon",
        "location": "dragon_arena",
        "tag": "--- Starting XBot RPG [DRAGON TEST] ---",
    },
    "music": {
        "profile": "music",
        "location": "docks",
        "tag": "--- Starting XBot RPG [MUSIC TEST] ---",
    },
    "journal": {
        "profile": "journal",
        "location": "town",
        "tag": "--- Starting XBot RPG [JOURNAL TEST] ---",
    },
    "mounts": {
        "profile": "mounts",
        "location": "9,6,0",
        "tag": "--- Starting XBot RPG [MOUNTS TEST] ---",
    },
    "skills": {
        "profile": "skills",
        "location": "0,0,0",
        "tag": "--- Starting XBot RPG [SKILLS TEST] ---",
    },
    "movement": {
        "profile": "movement",
        "location": "training",
        "tag": "--- Starting XBot RPG [MOVEMENT TEST] ---",
    },
    "parkour": {
        "profile": "parkour",
        "location": "parkour",
        "tag": "--- Starting XBot RPG [PARKOUR TEST] ---",
    },
    "flight": {
        "profile": "flight",
        "location": "flight",
        "tag": "--- Starting XBot RPG [FLIGHT TEST] ---",
    },
}

SCRIPT_TESTS = {
    "manifest": ["scripts/validate_player_manifest.py"],
    "anim_runtime": ["scripts/player_anim_runtime_report.py"],
    "smoke": ["scripts/smoke_report.py"],
    "baseline": ["scripts/baseline_report.py"],
    "voice_report": ["scripts/voice_dialog_report.py"],
    "voice_build": ["scripts/voice_dialog_report.py", "--synthesize-all", "--force-regenerate", "--engine", "auto"],
}


def _run_script(script_args):
    root = Path(__file__).resolve().parent
    if isinstance(script_args, (list, tuple)):
        args = [str(item) for item in script_args if str(item)]
    else:
        args = [str(script_args)]
    script = root / args[0]
    result = subprocess.run([sys.executable, str(script), *args[1:]], cwd=str(root))
    return int(result.returncode)


def _run_runtime(test_key, location_override):
    row = RUNTIME_TESTS[test_key]
    os.environ["XBOT_TEST_PROFILE"] = str(row["profile"])
    if location_override:
        os.environ["XBOT_TEST_LOCATION"] = str(location_override)
    else:
        os.environ.setdefault("XBOT_TEST_LOCATION", str(row["location"]))
    return run_app(startup_tag=str(row["tag"]), pause_on_error=True)


def _menu_choice():
    options = list(RUNTIME_TESTS.keys()) + list(SCRIPT_TESTS.keys())
    print("=== XBot Test Hub ===")
    for idx, key in enumerate(options, start=1):
        kind = "runtime" if key in RUNTIME_TESTS else "script"
        print(f"{idx}. {key} ({kind})")
    print("0. exit")
    while True:
        raw = input("Select test: ").strip()
        if raw == "0":
            return ""
        try:
            num = int(raw)
        except Exception:
            print("Please enter a number.")
            continue
        if 1 <= num <= len(options):
            return options[num - 1]
        print("Invalid choice.")


def main():
    parser = argparse.ArgumentParser(description="Unified test launcher for XBot RPG.")
    parser.add_argument("--test", default="", help="Test key (runtime or script).")
    parser.add_argument("--location", default="", help="Optional location override for runtime tests.")
    parser.add_argument("--list", action="store_true", help="Print available tests and exit.")
    args = parser.parse_args()

    if args.list:
        print("Runtime tests:")
        for key in RUNTIME_TESTS.keys():
            print(f"- {key}")
        print("Script tests:")
        for key in SCRIPT_TESTS.keys():
            print(f"- {key}")
        return 0

    key = str(args.test or "").strip().lower()
    if not key:
        key = _menu_choice()
        if not key:
            return 0

    if key in RUNTIME_TESTS:
        return _run_runtime(key, args.location)
    if key in SCRIPT_TESTS:
        return _run_script(SCRIPT_TESTS[key])

    print(f"Unknown test key: {key}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
