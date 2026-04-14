from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_app_wires_video_bot_verdicts_to_msgpack_runtime_artifact():
    source = (ROOT / "src" / "app.py").read_text(encoding="utf-8")

    assert 'runtime_file("logs", "video_bot_verdict.msgpack")' in source


def test_app_parses_success_and_failure_rules_before_constructing_tracker():
    source = (ROOT / "src" / "app.py").read_text(encoding="utf-8")

    assert 'success_if=parse_video_bot_rule(os.environ.get("XBOT_VIDEO_BOT_SUCCESS_IF", ""))' in source
    assert 'fail_if=parse_video_bot_rule(os.environ.get("XBOT_VIDEO_BOT_FAIL_IF", ""))' in source
