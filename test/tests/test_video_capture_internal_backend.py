from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
WRAPPER = ROOT / "test" / "tests" / "video_scenarios" / "run_game_tests_with_video.ps1"
RECORDER = Path.home() / ".codex" / "skills" / "record-gameplay-test-video" / "scripts" / "record_gameplay_test_video.js"


def test_recorder_source_supports_internal_backend():
    content = RECORDER.read_text(encoding="utf-8")

    assert "--video-backend <mode>" in content
    assert 'normalizeVideoBackend' in content
    assert 'XBOT_INTERNAL_VIDEO_CAPTURE' in content
    assert 'video_backend_used' in content
    assert 'internal_capture_status_path' in content


def test_wrapper_defaults_repo_video_runs_to_internal_backend():
    content = WRAPPER.read_text(encoding="utf-8")

    assert '[string]$VideoBackend = "internal"' in content
    assert '--video-backend' in content
