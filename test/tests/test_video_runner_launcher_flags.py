from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]


def test_video_runner_passes_explicit_runtime_launcher_flags():
    source = (
        ROOT / "test" / "tests" / "video_scenarios" / "run_game_tests_with_video.ps1"
    ).read_text(encoding="utf-8")

    launcher_idx = source.index('"--game-arg", "launcher_test_hub.py"')
    test_idx = source.index('"--game-arg", "--test"', launcher_idx)
    auto_start_idx = source.index('"--game-arg", "--auto-start"', test_idx)
    video_bot_idx = source.index('"--game-arg", "--video-bot"', auto_start_idx)

    assert launcher_idx < test_idx < auto_start_idx < video_bot_idx


def test_video_runner_forwards_scenario_game_env_to_game_process():
    source = (
        ROOT / "test" / "tests" / "video_scenarios" / "run_game_tests_with_video.ps1"
    ).read_text(encoding="utf-8")

    assert '$scenarioCfg.PSObject.Properties["game_env"]' in source
    assert '$scenarioArgsForAttempt += @("--game-env", "$envKey=$envValue")' in source


def test_video_runner_checks_verdict_inside_isolated_runtime_user_dir():
    source = (
        ROOT / "test" / "tests" / "video_scenarios" / "run_game_tests_with_video.ps1"
    ).read_text(encoding="utf-8")

    assert '"--project-root", $runIsolation.user_data_dir' in source
