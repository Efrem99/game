"""Unified launcher with menu-driven test profile selection."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from launchers.bootstrap import run_app


RUNTIME_TESTS = {
    "prototype_v1": {
        "profile": "prototype_v1",
        "location": "parkour",
        "tag": "--- Starting XBot RPG [PROTOTYPE V1 TEST] ---",
    },
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
    "mechanics": {
        "profile": "mechanics",
        "location": "training",
        "tag": "--- Starting XBot RPG [MECHANICS SANDBOX TEST] ---",
    },
    "parkour": {
        "profile": "parkour",
        "location": "parkour",
        "tag": "--- Starting XBot RPG [PARKOUR TEST] ---",
    },
    "stealth_climb": {
        "profile": "stealth_climb",
        "location": "stealth_climb",
        "tag": "--- Starting XBot RPG [STEALTH + CLIMB TEST] ---",
    },
    "flight": {
        "profile": "flight",
        "location": "flight",
        "tag": "--- Starting XBot RPG [FLIGHT TEST] ---",
    },
    "ultimate_sandbox": {
        "profile": "ultimate_sandbox",
        "location": "ultimate_sandbox",
        "tag": "--- Starting King Wizard [ULTIMATE SANDBOX] ---",
    },
    "castle_courtyard": {
        "profile": "movement",
        "location": "inner_castle",
        "tag": "--- Starting King Wizard [CASTLE COURTYARD] ---",
    },
    "castle_interior": {
        "profile": "movement",
        "location": "castle_interior",
        "tag": "--- Starting King Wizard [CASTLE INTERIOR] ---",
    },
    "prince_chamber": {
        "profile": "movement",
        "location": "prince_chamber",
        "tag": "--- Starting King Wizard [PRINCE CHAMBER] ---",
    },
    "throne_hall": {
        "profile": "movement",
        "location": "throne_hall",
        "tag": "--- Starting King Wizard [THRONE HALL] ---",
    },
    "old_forest": {
        "profile": "movement",
        "location": "old_forest",
        "tag": "--- Starting King Wizard [OLD FOREST] ---",
    },
    "port_market": {
        "profile": "movement",
        "location": "port_town",
        "tag": "--- Starting King Wizard [PORT MARKET] ---",
    },
    "krimora_forest": {
        "profile": "movement",
        "location": "krimora_forest",
        "tag": "--- Starting King Wizard [KRIMORA FOREST] ---",
    },
    "krimora_cage": {
        "profile": "movement",
        "location": "krimora_forest_cage",
        "tag": "--- Starting King Wizard [KRIMORA CAGE] ---",
    },
    "dwarven_gate": {
        "profile": "movement",
        "location": "dwarven_caves_gate",
        "tag": "--- Starting King Wizard [DWARVEN GATE] ---",
    },
    "dwarven_halls": {
        "profile": "movement",
        "location": "dwarven_caves_halls",
        "tag": "--- Starting King Wizard [DWARVEN HALLS] ---",
    },
    "dwarven_throne": {
        "profile": "movement",
        "location": "dwarven_caves_throne",
        "tag": "--- Starting King Wizard [DWARVEN THRONE] ---",
    },
}

SCRIPT_TESTS = {
    "manifest": ["scripts/validate_player_manifest.py"],
    "anim_runtime": ["scripts/player_anim_runtime_report.py"],
    "asset_viewer": ["scripts/asset_animation_viewer.py", "--parkour-debug", "--start-anim", "vault_low"],
    "smoke": ["scripts/smoke_report.py"],
    "baseline": ["scripts/baseline_report.py"],
    "voice_report": ["scripts/voice_dialog_report.py"],
    "voice_build": ["scripts/voice_dialog_report.py", "--synthesize-all", "--force-regenerate", "--engine", "auto"],
}

RUNTIME_TEST_LABELS = {
    "prototype_v1": ("Prototype Legacy", "Old experimental sandbox."),
    "dragon": ("Dragon Boss Arena", "Boss fight and dragon behavior."),
    "music": ("Music & Ambience", "Audio mix by location."),
    "journal": ("Journal UI", "Codex/journal/map interaction checks."),
    "mounts": ("Mounts & Vehicles", "Horse, wolf, stag, carriage, boat controls."),
    "skills": ("Skills & Spells", "Skill tree and spell casting showcase."),
    "movement": ("Movement Core", "Run/jump/crouch/combat baseline."),
    "mechanics": ("Mechanics Sandbox", "Broad combined mechanics test."),
    "parkour": ("Parkour Route", "Vault, wallrun, traversal flow."),
    "stealth_climb": ("Stealth + Climb Grounds", "Dedicated stealth route with climb towers."),
    "flight": ("Flight Route", "Air movement and camera behavior."),
    "ultimate_sandbox": ("Ultimate Sandbox", "Cubes, walls, water, and enemies for full mechanics testing."),
    "castle_courtyard": ("Castle Courtyard", "The main open area outside the castle halls."),
    "castle_interior": ("Castle Interior", "The standard interior environment (rooms, corridors)."),
    "prince_chamber": ("Prince's Chamber", "Personal quarters of the prince."),
    "throne_hall": ("Imperial Throne Hall", "The grand ceremonial chamber."),
    "old_forest": ("The Old Forest", "Dense temperate woods near the river."),
    "port_market": ("Port Market", "The bustling trade area in the southern docks."),
    "krimora_forest": ("Krimora Forest", "Cursed, dry environment with reddish atmosphere."),
    "krimora_cage": ("Krimora Cage", "The clearing containing the central cage landmark."),
    "dwarven_gate": ("Dwarven Gate", "The massive entrance to the underground kingdom."),
    "dwarven_halls": ("Dwarven Forge Halls", "The main industrial and social sectors of the caves."),
    "dwarven_throne": ("Dwarven Grand Throne", "The seat of power deep within the mountains."),
}

SCRIPT_TEST_LABELS = {
    "manifest": ("Manifest Validator", "Checks animation/model manifests."),
    "anim_runtime": ("Animation Runtime Report", "Animation load/runtime diagnostics."),
    "asset_viewer": ("Asset Animation Viewer", "Interactive asset viewer with minimalist parkour debug course and IK preview."),
    "smoke": ("Smoke Report", "Quick regression snapshot."),
    "baseline": ("Baseline Report", "Reference metrics and deltas."),
    "voice_report": ("Voice Report", "Voice/dialog coverage diagnostics."),
    "voice_build": ("Voice Rebuild", "Regenerate all synthesized voices."),
}

RUNTIME_AUTOMATION_ENV_KEYS = (
    "XBOT_AUTO_START",
    "XBOT_VIDEO_BOT",
    "XBOT_VIDEO_BOT_PLAN",
    "XBOT_VIDEO_BOT_PLAN_JSON",
    "XBOT_VIDEO_BOT_LOOP_PLAN",
    "XBOT_VIDEO_BOT_LOOP_GAP_SEC",
    "XBOT_VIDEO_BOT_TRACE",
    "XBOT_VIDEO_VISIBILITY_BOOST",
    "XBOT_VIDEO_BOT_CAPTURE_INPUT",
    "XBOT_VIDEO_BOT_CONTEXT_RULES",
    "XBOT_VIDEO_BOT_SUCCESS_IF",
    "XBOT_VIDEO_BOT_FAIL_IF",
    "XBOT_FORCE_AGGRO_MOBS",
    "XBOT_TEST_SCENARIO",
)


def _describe_test(key):
    if key in RUNTIME_TESTS:
        return RUNTIME_TEST_LABELS.get(key, (key.replace("_", " ").title(), ""))
    if key in SCRIPT_TESTS:
        return SCRIPT_TEST_LABELS.get(key, (key.replace("_", " ").title(), ""))
    return (key.replace("_", " ").title(), "")


def _stdin_is_tty_safe():
    stream = getattr(sys, "stdin", None)
    if stream is None:
        return False
    probe = getattr(stream, "isatty", None)
    if not callable(probe):
        return False
    try:
        return bool(probe())
    except Exception:
        return False


def _run_script(script_args):
    root = Path(__file__).resolve().parent
    if isinstance(script_args, (list, tuple)):
        args = [str(item) for item in script_args if str(item)]
    else:
        args = [str(script_args)]
    script = root / args[0]
    result = subprocess.run([sys.executable, str(script), *args[1:]], cwd=str(root))
    return int(result.returncode)


def _clear_runtime_automation_env():
    for key in RUNTIME_AUTOMATION_ENV_KEYS:
        os.environ.pop(key, None)


def _run_runtime(test_key, location_override, *, auto_start=False, video_bot=False):
    row = RUNTIME_TESTS[test_key]
    preserved = {}
    if video_bot:
        for key in (
            "XBOT_VIDEO_BOT_PLAN",
            "XBOT_VIDEO_BOT_PLAN_JSON",
            "XBOT_VIDEO_BOT_LOOP_PLAN",
            "XBOT_VIDEO_BOT_LOOP_GAP_SEC",
            "XBOT_VIDEO_BOT_TRACE",
            "XBOT_VIDEO_VISIBILITY_BOOST",
            "XBOT_VIDEO_BOT_CAPTURE_INPUT",
            "XBOT_VIDEO_BOT_CONTEXT_RULES",
            "XBOT_VIDEO_BOT_SUCCESS_IF",
            "XBOT_VIDEO_BOT_FAIL_IF",
            "XBOT_FORCE_AGGRO_MOBS",
            "XBOT_TEST_SCENARIO",
        ):
            value = os.environ.get(key)
            if value is not None:
                preserved[key] = value
    _clear_runtime_automation_env()
    for key, value in preserved.items():
        os.environ[key] = value
    os.environ["XBOT_TEST_PROFILE"] = str(row["profile"])
    if location_override:
        os.environ["XBOT_TEST_LOCATION"] = str(location_override)
    else:
        os.environ["XBOT_TEST_LOCATION"] = str(row["location"])
    if auto_start:
        os.environ["XBOT_AUTO_START"] = "1"
    if video_bot:
        os.environ["XBOT_VIDEO_BOT"] = "1"
    return run_app(startup_tag=str(row["tag"]), pause_on_error=True)


def _menu_choice():
    options = list(RUNTIME_TESTS.keys()) + list(SCRIPT_TESTS.keys())
    print("=== XBot Test Hub ===")
    for idx, key in enumerate(options, start=1):
        kind = "runtime" if key in RUNTIME_TESTS else "script"
        title, desc = _describe_test(key)
        print(f"{idx}. {key} - {title} ({kind})")
        if desc:
            print(f"    {desc}")
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
        return {"key": "", "auto_start": False, "video_bot": False}
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return ""

    chosen = {"key": "", "auto_start": False, "video_bot": False}
    root = tk.Tk()
    root.title("XBot Test Hub")
    root.resizable(False, False)
    root.geometry("440x250")
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
    auto_start_var = tk.BooleanVar(value=False)
    video_bot_var = tk.BooleanVar(value=False)
    combo = ttk.Combobox(root, textvariable=value, values=options, state="readonly", width=44)
    combo.pack(padx=12, pady=6)
    combo.focus_set()

    first_title, first_desc = _describe_test(options[0])
    kind_var = tk.StringVar(value=f"kind: {'runtime' if options[0] in RUNTIME_TESTS else 'script'} | {first_title}")
    kind_label = tk.Label(root, textvariable=kind_var, bg="#121212", fg="#B8B8B8", font=("Segoe UI", 9))
    kind_label.pack(padx=12, pady=2)
    desc_var = tk.StringVar(value=first_desc)
    desc_label = tk.Label(root, textvariable=desc_var, bg="#121212", fg="#9CA3AF", font=("Segoe UI", 8), wraplength=390, justify="left")
    desc_label.pack(padx=12, pady=1)

    toggle_wrap = tk.Frame(root, bg="#121212")
    toggle_wrap.pack(padx=12, pady=6, anchor="w")

    auto_start_chk = tk.Checkbutton(
        toggle_wrap,
        text="Auto-start after intro",
        variable=auto_start_var,
        bg="#121212",
        fg="#E7D39B",
        activebackground="#121212",
        activeforeground="#E7D39B",
        selectcolor="#1E1E1E",
        highlightthickness=0,
    )
    auto_start_chk.pack(anchor="w")

    video_bot_chk = tk.Checkbutton(
        toggle_wrap,
        text="Enable Video Bot automation",
        variable=video_bot_var,
        bg="#121212",
        fg="#E7D39B",
        activebackground="#121212",
        activeforeground="#E7D39B",
        selectcolor="#1E1E1E",
        highlightthickness=0,
    )
    video_bot_chk.pack(anchor="w")

    def _update_kind(*_):
        key = str(value.get() or "")
        title, desc = _describe_test(key)
        kind_var.set(f"kind: {'runtime' if key in RUNTIME_TESTS else 'script'} | {title}")
        desc_var.set(desc)
        is_runtime = key in RUNTIME_TESTS
        state = tk.NORMAL if is_runtime else tk.DISABLED
        auto_start_chk.configure(state=state)
        video_bot_chk.configure(state=state)
        if not is_runtime:
            auto_start_var.set(False)
            video_bot_var.set(False)

    value.trace_add("write", _update_kind)

    btn_wrap = tk.Frame(root, bg="#121212")
    btn_wrap.pack(padx=12, pady=10)

    def _run():
        chosen["key"] = str(value.get() or "").strip().lower()
        chosen["auto_start"] = bool(auto_start_var.get()) if chosen["key"] in RUNTIME_TESTS else False
        chosen["video_bot"] = bool(video_bot_var.get()) if chosen["key"] in RUNTIME_TESTS else False
        root.destroy()

    def _cancel():
        chosen["key"] = ""
        chosen["auto_start"] = False
        chosen["video_bot"] = False
        root.destroy()

    tk.Button(btn_wrap, text="Run", width=12, command=_run).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_wrap, text="Cancel", width=12, command=_cancel).pack(side=tk.LEFT, padx=5)
    _update_kind()
    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.mainloop()
    return chosen


def main():
    parser = argparse.ArgumentParser(description="Unified test launcher for XBot RPG.")
    parser.add_argument("--test", default="", help="Test key (runtime or script).")
    parser.add_argument("--location", default="", help="Optional location override for runtime tests.")
    parser.add_argument("--auto-start", action="store_true", help="Auto-start runtime profile after intro.")
    parser.add_argument("--video-bot", action="store_true", help="Enable Video Bot automation for runtime profiles.")
    parser.add_argument("--list", action="store_true", help="Print available tests and exit.")
    args = parser.parse_args()

    if args.list:
        print("Runtime tests:")
        for key in RUNTIME_TESTS.keys():
            title, desc = _describe_test(key)
            print(f"- {key}: {title}")
            if desc:
                print(f"  {desc}")
        print("Script tests:")
        for key in SCRIPT_TESTS.keys():
            title, desc = _describe_test(key)
            print(f"- {key}: {title}")
            if desc:
                print(f"  {desc}")
        return 0

    key = str(args.test or "").strip().lower()
    auto_start = bool(args.auto_start)
    video_bot = bool(args.video_bot)
    if not key:
        stdin_is_tty = _stdin_is_tty_safe()
        if stdin_is_tty:
            key = _menu_choice()
        else:
            selection = _menu_choice_gui()
            if isinstance(selection, dict):
                key = str(selection.get("key", "") or "").strip().lower()
                auto_start = bool(selection.get("auto_start", False))
                video_bot = bool(selection.get("video_bot", False))
            else:
                key = str(selection or "").strip().lower()
        if not key:
            return 0

    if key in RUNTIME_TESTS:
        return _run_runtime(key, args.location, auto_start=auto_start, video_bot=video_bot)
    if key in SCRIPT_TESTS:
        return _run_script(SCRIPT_TESTS[key])

    print(f"Unknown test key: {key}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

