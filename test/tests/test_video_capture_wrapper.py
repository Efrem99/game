import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).absolute().parents[2]
TEST_ROOT = REPO_ROOT / "test"
WRAPPER_SCRIPT = TEST_ROOT / "tests" / "video_scenarios" / "run_game_tests_with_video.ps1"


def _run_wrapper_helper(expression: str) -> str:
    script_path = str(WRAPPER_SCRIPT).replace("'", "''")
    helper_loader = textwrap.dedent(
        f"""
        $source = Get-Content -LiteralPath '{script_path}' -Raw
        $start = $source.IndexOf('Set-StrictMode -Version Latest')
        $end = $source.IndexOf('$resolvedScenarioFile =')
        if ($start -lt 0 -or $end -le $start) {{
          throw 'Failed to isolate wrapper helper block.'
        }}
        $helpers = $source.Substring($start, $end - $start)
        Invoke-Expression $helpers
        {expression}
        """
    ).strip()
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", helper_loader],
        cwd=TEST_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "PowerShell helper invocation failed:\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )
    return completed.stdout.strip()


class VideoCaptureWrapperTests(unittest.TestCase):
    def test_wrapper_sets_safe_blas_thread_defaults_for_child_recorders(self):
        raw = _run_wrapper_helper(
            """
            foreach ($name in @(
              'OPENBLAS_NUM_THREADS',
              'OMP_NUM_THREADS',
              'MKL_NUM_THREADS',
              'NUMEXPR_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS',
              'GOTO_NUM_THREADS'
            )) {
              Remove-Item "Env:$name" -ErrorAction SilentlyContinue
            }
            $env:MKL_NUM_THREADS = '4'
            Set-DefaultBlasThreadEnv
            @{
              OPENBLAS_NUM_THREADS = $env:OPENBLAS_NUM_THREADS
              OMP_NUM_THREADS = $env:OMP_NUM_THREADS
              MKL_NUM_THREADS = $env:MKL_NUM_THREADS
              NUMEXPR_NUM_THREADS = $env:NUMEXPR_NUM_THREADS
              VECLIB_MAXIMUM_THREADS = $env:VECLIB_MAXIMUM_THREADS
              GOTO_NUM_THREADS = $env:GOTO_NUM_THREADS
            } | ConvertTo-Json -Compress
            """
        )
        self.assertEqual(
            {
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "4",
                "NUMEXPR_NUM_THREADS": "1",
                "VECLIB_MAXIMUM_THREADS": "1",
                "GOTO_NUM_THREADS": "1",
            },
            json.loads(raw),
        )

    def test_wrapper_does_not_force_default_cli_overrides_when_not_explicitly_bound(self):
        raw = _run_wrapper_helper(
            """
            $resultArgs = Get-ScenarioRecorderOverrideArgs `
              -BoundParameters @{} `
              -WindowTitle 'King Wizard' `
              -CaptureAudio $false `
              -Fps 24 `
              -VideoBackend 'internal' `
              -AudioMode 'loopback' `
              -OutputDirOverride ''
            $resultArgs | ConvertTo-Json -Compress
            """
        )
        self.assertEqual(["--video-backend", "internal"], [] if not raw else json.loads(raw))

    def test_wrapper_emits_only_user_bound_cli_overrides(self):
        raw = _run_wrapper_helper(
            """
            $resultArgs = Get-ScenarioRecorderOverrideArgs `
              -BoundParameters @{
                CaptureAudio = $true
                Fps = 48
                AudioMode = 'dshow'
                OutputDirOverride = 'C:\\review-out'
              } `
              -WindowTitle 'King Wizard' `
              -CaptureAudio $true `
              -Fps 48 `
              -VideoBackend 'internal' `
              -AudioMode 'dshow' `
              -OutputDirOverride 'C:\\review-out'
            $resultArgs | ConvertTo-Json -Compress
            """
        )
        self.assertEqual(
            [
                "--capture-audio",
                "true",
                "--video-backend",
                "internal",
                "--audio-mode",
                "dshow",
                "--fps",
                "48",
                "--output-dir",
                "C:\\review-out",
            ],
            json.loads(raw),
        )

    def test_wrapper_emits_debug_game_env_args_only_when_bound(self):
        raw = _run_wrapper_helper(
            """
            $resultArgs = Get-DebugGameEnvArgs `
              -BoundParameters @{
                DebugOverlay = $true
                DebugColliders = $true
              } `
              -DebugOverlay:$true `
              -DebugColliders:$true
            $resultArgs | ConvertTo-Json -Compress
            """
        )
        self.assertEqual(
            [
                "--game-env",
                "XBOT_DEBUG_OVERLAY=1",
                "--game-env",
                "XBOT_DEBUG_COLLIDERS=1",
            ],
            json.loads(raw),
        )

    def test_wrapper_does_not_emit_debug_game_env_args_when_not_bound(self):
        raw = _run_wrapper_helper(
            """
            $resultArgs = Get-DebugGameEnvArgs `
              -BoundParameters @{} `
              -DebugOverlay:$false `
              -DebugColliders:$false
            $resultArgs | ConvertTo-Json -Compress
            """
        )
        self.assertEqual([], [] if not raw else json.loads(raw))

    def test_wrapper_recovers_video_path_from_metadata_sidecar_when_metadata_path_is_broken(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            metadata_path = tmp_path / "20260315-225942-ultimate-sandbox-mechanics.metadata.json"
            video_path = tmp_path / "20260315-225942-ultimate-sandbox-mechanics.mp4"
            metadata_path.write_text("{}", encoding="utf-8")
            video_path.write_bytes(b"fake-mp4")

            metadata_literal = str(metadata_path).replace("'", "''")
            bad_video_path = "C:\\xampp\\htdocs\\ÐšÐ¾Ñ€Ð¾Ð»ÑŒ\\broken.mp4".replace("'", "''")

            resolved = _run_wrapper_helper(
                f"""
                $meta = [pscustomobject]@{{ video_path = '{bad_video_path}' }}
                Resolve-RecordedVideoPath -Metadata $meta -MetadataPath '{metadata_literal}'
                """
            )
        self.assertEqual(str(video_path), resolved)


class RepoHygieneTests(unittest.TestCase):
    def test_gitignore_excludes_non_web_mechanics_review_outputs(self):
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("output/non-web-mechanics-review/", content)
        self.assertIn("src/output/non-web-mechanics-review/", content)


class ScenarioCatalogParsingTests(unittest.TestCase):
    def test_wrapper_loads_real_game_scenario_catalog(self):
        scenario_path = str(WRAPPER_SCRIPT.parent / "scenarios.json").replace("'", "''")
        raw = _run_wrapper_helper(
            f"""
            $catalog = Get-GameScenarioCatalog -ScenarioPath '{scenario_path}'
            [pscustomobject]@{{
              count = [int]$catalog.Count
              has_probe = [bool]$catalog.Contains('ultimate-sandbox-collider-probe')
            }} | ConvertTo-Json -Compress
            """
        )

        payload = json.loads(raw)
        self.assertGreaterEqual(payload["count"], 10)
        self.assertTrue(payload["has_probe"])


if __name__ == "__main__":
    unittest.main()
