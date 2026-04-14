import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "dev" / "custom_debugger.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("custom_debugger", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CustomDebuggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_bug_classifier_maps_ui_failure_to_ui_bug(self):
        step = self.mod.ScenarioStep(name="open_inventory", action=self.mod.ActionType.OPEN_MENU)
        bug = self.mod.BugClassifier.classify(step, self.mod.WorldState(), self.mod.WorldState(), {"ui_failed": True})
        self.assertEqual(bug, self.mod.BugType.UI_BUG)

    def test_runner_treats_perf_only_failure_as_warning(self):
        mod = self.mod

        class LowPerfAdapter(mod.MockGameAdapter):
            def get_perf_metrics(self):
                return mod.PerfMetrics(
                    fps=12.0,
                    frame_time_ms=83.0,
                    draw_calls=320,
                    triangles=180000,
                    instances=450,
                )

        scenario = mod.Scenario(
            name="perf_warn_only",
            steps=[mod.ScenarioStep(name="wait", action=mod.ActionType.WAIT)],
        )
        runner = mod.AutonomousQARunner(
            adapter=LowPerfAdapter(),
            scenarios=[scenario],
            output_dir=str(ROOT / "tmp" / "custom_debugger_perf_warn"),
            hours=None,
            random_edge_case_chance=0.0,
            stop_on_fail=False,
        )

        summary = runner.run()
        self.assertEqual(summary["failed_steps"], 0)
        self.assertEqual(summary["warned_steps"], 1)

    def test_retry_uses_last_successful_attempt_evidence(self):
        mod = self.mod

        class RetryAdapter(mod.MockGameAdapter):
            def __init__(self):
                super().__init__()
                self.interact_calls = 0

            def interact(self, target_id: str) -> bool:
                self.interact_calls += 1
                if self.interact_calls == 1:
                    return False
                self.state.current_animation = "open_door"
                self.state.object_states[target_id] = "opened"
                return True

        scenario = mod.Scenario(
            name="retry_success",
            steps=[
                mod.ScenarioStep(
                    name="open_door",
                    action=mod.ActionType.INTERACT,
                    target="door_main",
                    retries=2,
                )
            ],
        )
        runner = mod.AutonomousQARunner(
            adapter=RetryAdapter(),
            scenarios=[scenario],
            output_dir=str(ROOT / "tmp" / "custom_debugger_retry_success"),
            hours=None,
            random_edge_case_chance=0.0,
            stop_on_fail=False,
        )

        summary = runner.run()
        self.assertEqual(summary["failed_steps"], 0)
        self.assertEqual(summary["warned_steps"], 0)

    def test_storage_sanitizes_step_name_for_blob_filename(self):
        mod = self.mod
        storage = mod.Storage(str(ROOT / "tmp" / "custom_debugger_storage"))
        try:
            result = mod.StepResult(
                scenario_name="storage_test",
                step_index=1,
                step_name="open/door:main?",
                action=mod.ActionType.INTERACT.value,
                verdict=mod.Verdict.PASS,
                started_at=0.0,
                finished_at=1.0,
                duration_sec=1.0,
            )
            storage.save_step_result(result)
            blob_paths = list((ROOT / "tmp" / "custom_debugger_storage" / "blobs").glob("storage_test_0001_*"))
            self.assertTrue(blob_paths)
        finally:
            storage.close()

    def test_runner_writes_markdown_report_alongside_html(self):
        mod = self.mod
        scenario = mod.Scenario(
            name="report_outputs",
            steps=[mod.ScenarioStep(name="wait", action=mod.ActionType.WAIT)],
        )
        out_dir = ROOT / "tmp" / "custom_debugger_reports"
        runner = mod.AutonomousQARunner(
            adapter=mod.MockGameAdapter(),
            scenarios=[scenario],
            output_dir=str(out_dir),
            hours=None,
            random_edge_case_chance=0.0,
            stop_on_fail=False,
        )

        summary = runner.run()
        self.assertTrue((out_dir / "report.html").exists())
        self.assertTrue((out_dir / "report.md").exists())
        self.assertIn("report_path", summary)
        self.assertIn("report_md_path", summary)

    def test_repo_video_loader_wraps_legacy_video_bot_scenario(self):
        mod = self.mod
        scenarios = mod.load_repo_video_scenarios(
            str(ROOT / "test" / "tests" / "video_scenarios" / "scenarios.json"),
            scenario_names=["loc-parkour-vault-route"],
        )

        self.assertEqual(1, len(scenarios))
        scenario = scenarios[0]
        self.assertEqual("loc-parkour-vault-route", scenario.name)
        self.assertEqual(1, len(scenario.steps))
        step = scenario.steps[0]
        self.assertEqual(mod.ActionType.RUN_VIDEO_SCENARIO, step.action)
        self.assertEqual("loc-parkour-vault-route", step.params["scenario_name"])
        self.assertEqual("parkour", step.params["launcher_test"])
        self.assertEqual("parkour", step.params["legacy_plan"])
        self.assertEqual("1", step.params["game_env"]["XBOT_VIDEO_BOT"])

    def test_step_executor_runs_repo_video_scenario_through_adapter(self):
        mod = self.mod

        class VideoScenarioAdapter(mod.MockGameAdapter):
            def __init__(self):
                super().__init__()
                self.calls = []

            def run_video_scenario(self, scenario_name: str, scenario_file: str, params):
                self.calls.append(
                    {
                        "scenario_name": scenario_name,
                        "scenario_file": scenario_file,
                        "params": dict(params),
                    }
                )
                self.state.misc["last_video_scenario"] = scenario_name
                return True

        adapter = VideoScenarioAdapter()
        executor = mod.StepExecutor(adapter)
        step = mod.ScenarioStep(
            name="repo_video_plan",
            action=mod.ActionType.RUN_VIDEO_SCENARIO,
            params={
                "scenario_name": "loc-parkour-vault-route",
                "scenario_file": str(ROOT / "test" / "tests" / "video_scenarios" / "scenarios.json"),
                "launcher_test": "parkour",
                "legacy_plan": "parkour",
            },
        )

        ok, evidence = executor.execute(step)
        self.assertTrue(ok)
        self.assertEqual("loc-parkour-vault-route", adapter.calls[0]["scenario_name"])
        self.assertEqual("parkour", adapter.calls[0]["params"]["legacy_plan"])
        self.assertEqual("loc-parkour-vault-route", evidence["video_scenario_name"])


if __name__ == "__main__":
    unittest.main()
