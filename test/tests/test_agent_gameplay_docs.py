from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_agents_doc_points_to_current_video_runner_path():
    content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "test/tests/video_scenarios/run_game_tests_with_video.ps1" in content


def test_gameplay_playbook_points_to_current_video_runner_path():
    content = (ROOT / "docs" / "AGENT_GAMEPLAY_PLAYBOOK.md").read_text(encoding="utf-8")

    assert "test\\tests\\video_scenarios\\run_game_tests_with_video.ps1" in content
