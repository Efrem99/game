import json
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).absolute().parents[1]
WRAPPER_SCRIPT = ROOT / "tests" / "video_scenarios" / "run_game_tests_with_video.ps1"


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
        cwd=ROOT,
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


def test_wrapper_skips_capture_processes_owned_by_other_live_runner():
    raw = _run_wrapper_helper(
        """
        $rows = @(
          [pscustomobject]@{ ProcessId = 100; ParentProcessId = 1; Name = 'powershell.exe'; CommandLine = 'powershell -File run_game_tests_with_video.ps1 -Scenario first' },
          [pscustomobject]@{ ProcessId = 110; ParentProcessId = 100; Name = 'node.exe'; CommandLine = 'node record_gameplay_test_video.js --scenario first' },
          [pscustomobject]@{ ProcessId = 120; ParentProcessId = 110; Name = 'python.exe'; CommandLine = 'python launcher_test_hub.py --test movement' },
          [pscustomobject]@{ ProcessId = 200; ParentProcessId = 1; Name = 'powershell.exe'; CommandLine = 'powershell -File run_game_tests_with_video.ps1 -Scenario second' },
          [pscustomobject]@{ ProcessId = 210; ParentProcessId = 200; Name = 'node.exe'; CommandLine = 'node record_gameplay_test_video.js --scenario second' },
          [pscustomobject]@{ ProcessId = 220; ParentProcessId = 210; Name = 'python.exe'; CommandLine = 'python launcher_test_hub.py --test movement' },
          [pscustomobject]@{ ProcessId = 310; ParentProcessId = 9999; Name = 'node.exe'; CommandLine = 'node record_gameplay_test_video.js --scenario orphaned' }
        )
        $result = Get-StaleCaptureProcessesFromRows -Rows $rows -CurrentRunnerPid 100 -ExcludeProcessIds @()
        ($result | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress
        """
    )

    assert json.loads(raw) == [110, 120, 310]


def test_wrapper_source_includes_per_run_window_and_runtime_isolation():
    content = WRAPPER_SCRIPT.read_text(encoding="utf-8")

    assert "XBOT_WINDOW_TITLE" in content
    assert "XBOT_USER_DATA_DIR" in content
    assert "--ready-log-path" in content
