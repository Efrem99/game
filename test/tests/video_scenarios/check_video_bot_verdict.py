"""Validate repo-local video bot verdict artifacts after a recorded run."""

from __future__ import annotations

import argparse
import json
import msgpack
from pathlib import Path


SUCCESS_KEY = "XBOT_VIDEO_BOT_SUCCESS_IF"
FAIL_KEY = "XBOT_VIDEO_BOT_FAIL_IF"


def _load_registry(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    scenarios = payload.get("scenarios", {})
    return scenarios if isinstance(scenarios, dict) else {}


def validate_video_bot_verdict(scenario_name, scenario_cfg, project_root):
    row = scenario_cfg if isinstance(scenario_cfg, dict) else {}
    game_env = row.get("game_env", {}) if isinstance(row, dict) else {}
    if not isinstance(game_env, dict):
        game_env = {}
    has_success = bool(str(game_env.get(SUCCESS_KEY, "") or "").strip())
    has_fail = bool(str(game_env.get(FAIL_KEY, "") or "").strip())
    if not has_success and not has_fail:
        return (True, f"Scenario '{scenario_name}' has no verdict rules.")

    verdict_path = Path(project_root) / "logs" / "video_bot_verdict.msgpack"
    if not verdict_path.exists():
        return (False, f"Video bot verdict file is missing: {verdict_path}")

    try:
        payload = msgpack.unpackb(verdict_path.read_bytes(), raw=False)
    except Exception as exc:
        return (False, f"Video bot verdict file is unreadable: {exc}")

    status = str(payload.get("status", "pending") or "pending").strip().lower()
    reason = str(payload.get("reason", "") or "").strip().lower()
    if status == "failure":
        return (False, f"Scenario '{scenario_name}' reported failure via {reason or 'fail_if'}.")
    if has_success and status != "success":
        return (False, f"Scenario '{scenario_name}' expected success but verdict status is '{status}'.")
    return (True, f"Scenario '{scenario_name}' verdict ok: {status or 'pending'}.")


def main():
    parser = argparse.ArgumentParser(description="Check project-local video bot verdict artifact.")
    parser.add_argument("--scenario", required=True, help="Scenario key from tests/video_scenarios/scenarios.json")
    parser.add_argument("--scenario-file", required=True, help="Scenario registry JSON path")
    parser.add_argument("--project-root", required=True, help="Project root containing logs/video_bot_verdict.msgpack")
    args = parser.parse_args()

    scenarios = _load_registry(args.scenario_file)
    row = scenarios.get(args.scenario)
    if not isinstance(row, dict):
        raise SystemExit(f"Scenario '{args.scenario}' not found in {args.scenario_file}")

    ok, message = validate_video_bot_verdict(
        scenario_name=args.scenario,
        scenario_cfg=row,
        project_root=Path(args.project_root),
    )
    print(message)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
