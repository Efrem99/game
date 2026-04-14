from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]


def test_video_runner_disables_video_bot_loop_by_default_for_scenarios():
    source = (ROOT / "test" / "tests" / "video_scenarios" / "run_game_tests_with_video.ps1").read_text(encoding="utf-8")

    assert "XBOT_VIDEO_BOT_LOOP_PLAN" in source
    assert "scenarioHasVideoBot" in source
    assert "scenarioDefinesVideoBotLoop" in source
    assert "--game-env\", \"XBOT_VIDEO_BOT_LOOP_PLAN=0\"" in source
