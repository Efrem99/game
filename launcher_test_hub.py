"""Unified launcher with menu-driven test profile selection."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from launchers.bootstrap import run_app


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


def _menu_choice_gui():
    options = list(RUNTIME_TESTS.keys()) + list(SCRIPT_TESTS.keys())
    if not options:
        return ""
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return ""

    chosen = {"key": ""}
    root = tk.Tk()
    root.title("XBot Test Hub")
    root.resizable(False, False)
    root.geometry("420x170")
    root.configure(bg="#121212")

    pad = {"padx": 12, "pady": 8}
    label = tk.Label(
        root,
        text="Select test profile",
        bg="#121212",
        fg="#E7D39B",
        font=("Segoe UI", 11, "bold"),
    )
    label.pack(**pad)

    value = tk.StringVar(value=options[0])
    combo = ttk.Combobox(root, textvariable=value, values=options, state="readonly", width=44)
    combo.pack(padx=12, pady=6)
    combo.focus_set()

    kind_var = tk.StringVar(value=f"kind: {'runtime' if options[0] in RUNTIME_TESTS else 'script'}")
    kind_label = tk.Label(root, textvariable=kind_var, bg="#121212", fg="#B8B8B8", font=("Segoe UI", 9))
    kind_label.pack(padx=12, pady=2)

    def _update_kind(*_):
        key = str(value.get() or "")
        kind_var.set(f"kind: {'runtime' if key in RUNTIME_TESTS else 'script'}")

    value.trace_add("write", _update_kind)

    btn_wrap = tk.Frame(root, bg="#121212")
    btn_wrap.pack(padx=12, pady=10)

    def _run():
        chosen["key"] = str(value.get() or "").strip().lower()
        root.destroy()

    def _cancel():
        chosen["key"] = ""
        root.destroy()

    tk.Button(btn_wrap, text="Run", width=12, command=_run).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_wrap, text="Cancel", width=12, command=_cancel).pack(side=tk.LEFT, padx=5)
    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.mainloop()
    return chosen["key"]


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
        stdin_is_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
        if stdin_is_tty:
            key = _menu_choice()
        else:
            key = _menu_choice_gui()
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

