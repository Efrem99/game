param(
  [string]$Scenario = "all",
  [string]$ScenarioFile = "$PSScriptRoot\scenarios.json",
  [string]$BookDocx = "",
  [string]$NodePath = "node",
  [string]$RecorderScript = "",
  [string]$FfmpegPath = "",
  [string]$WindowTitle = "King Wizard",
  [bool]$CaptureAudio = $false,
  [int]$Fps = 24,
  [ValidateSet("external", "internal")]
  [string]$VideoBackend = "internal",
  [ValidateSet("auto", "loopback", "dshow")]
  [string]$AudioMode = "loopback",
  [string]$OutputDirOverride = "",
  [int]$MaxRetries = 1,
  [double]$MinDurationCoverage = 0.65,
  [int]$MinDurationSec = 12,
  [switch]$DebugOverlay,
  [switch]$DebugColliders,
  [switch]$List
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RecorderScript {
  param([string]$ExplicitPath)

  if ($ExplicitPath -and (Test-Path -LiteralPath $ExplicitPath)) {
    return (Resolve-Path -LiteralPath $ExplicitPath).Path
  }

  $codeHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
  $candidate = Join-Path $codeHome "skills\record-gameplay-test-video\scripts\record_gameplay_test_video.js"
  if (Test-Path -LiteralPath $candidate) {
    return (Resolve-Path -LiteralPath $candidate).Path
  }

  throw "Recorder script not found. Pass -RecorderScript explicitly."
}

function Resolve-FfmpegPath {
  param([string]$ExplicitPath)

  if ($ExplicitPath -and (Test-Path -LiteralPath $ExplicitPath)) {
    return (Resolve-Path -LiteralPath $ExplicitPath).Path
  }

  $ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
  if ($ffmpegCmd) {
    return $ffmpegCmd.Source
  }

  $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
  if (Test-Path -LiteralPath $wingetRoot) {
    $found = Get-ChildItem -Path $wingetRoot -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue |
      Select-Object -First 1 -ExpandProperty FullName
    if ($found) {
      return $found
    }
  }

  throw "ffmpeg.exe not found. Install FFmpeg or pass -FfmpegPath."
}

function Resolve-FfprobePath {
  param([string]$ResolvedFfmpegPath)

  if (-not $ResolvedFfmpegPath) {
    throw "Resolved ffmpeg path is required."
  }

  $ffprobeCandidate = Join-Path (Split-Path -Parent $ResolvedFfmpegPath) "ffprobe.exe"
  if (Test-Path -LiteralPath $ffprobeCandidate) {
    return (Resolve-Path -LiteralPath $ffprobeCandidate).Path
  }

  $ffprobeCmd = Get-Command ffprobe -ErrorAction SilentlyContinue
  if ($ffprobeCmd -and (Test-Path -LiteralPath $ffprobeCmd.Source)) {
    return $ffprobeCmd.Source
  }

  throw "ffprobe.exe not found near ffmpeg or in PATH."
}

function Resolve-PythonExe {
  try {
    $resolved = & python -c "import sys; print(sys.executable)"
    if ($LASTEXITCODE -eq 0 -and $resolved) {
      $candidate = $resolved.Trim()
      if (Test-Path -LiteralPath $candidate) {
        return $candidate
      }
    }
  } catch {}

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd -and (Test-Path -LiteralPath $pythonCmd.Source)) {
    return $pythonCmd.Source
  }
  throw "python executable not found in PATH."
}

function Resolve-ScenarioOutputDir {
  param(
    [object]$ScenarioCfg,
    [string]$ProjectRootPath,
    [string]$OutputDirOverridePath
  )

  if ($OutputDirOverridePath) {
    return (Resolve-Path -LiteralPath $OutputDirOverridePath).Path
  }

  $raw = "output/non-web-mechanics-review"
  if (
    $ScenarioCfg -and
    $ScenarioCfg.PSObject.Properties["output_dir"] -and
    $ScenarioCfg.output_dir
  ) {
    $raw = [string]$ScenarioCfg.output_dir
  }

  if ([System.IO.Path]::IsPathRooted($raw)) {
    if (Test-Path -LiteralPath $raw) {
      return (Resolve-Path -LiteralPath $raw).Path
    }
    return $raw
  }

  $combined = Join-Path $ProjectRootPath $raw
  if (Test-Path -LiteralPath $combined) {
    return (Resolve-Path -LiteralPath $combined).Path
  }
  return $combined
}

function Find-LatestScenarioMetadata {
  param(
    [string]$OutputDir,
    [string]$ScenarioName,
    [datetime]$StartedAt
  )

  if (-not (Test-Path -LiteralPath $OutputDir)) {
    return $null
  }

  $pattern = "*-$ScenarioName.metadata.json"
  $rows = Get-ChildItem -LiteralPath $OutputDir -Filter $pattern -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -ge $StartedAt.AddSeconds(-2) } |
    Sort-Object LastWriteTime -Descending

  return ($rows | Select-Object -First 1)
}

function Get-RecordedVideoDurationSec {
  param(
    [string]$FfprobePath,
    [string]$VideoPath
  )

  if (-not $VideoPath) {
    return $null
  }
  if (-not (Test-Path -LiteralPath $VideoPath)) {
    return $null
  }

  $probeArgs = @(
    "-v", "error",
    "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1",
    $VideoPath
  )
  try {
    $raw = & $FfprobePath @probeArgs 2>$null
    if ($LASTEXITCODE -ne 0) {
      return $null
    }
    $text = [string]::Join("", @($raw)).Trim()
    if (-not $text) {
      return $null
    }
    return [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
  } catch {
    return $null
  }
}

function Resolve-RecordedVideoPath {
  param(
    [object]$Metadata,
    [string]$MetadataPath
  )

  $candidates = @()
  if (
    $Metadata -and
    $Metadata.PSObject.Properties["video_path"] -and
    $Metadata.video_path
  ) {
    $candidates += [string]$Metadata.video_path
  }

  if ($MetadataPath) {
    $sidecarBase = $MetadataPath -replace '\.metadata\.json$', ''
    if ($sidecarBase -and ($sidecarBase -ne $MetadataPath)) {
      $candidates += "$sidecarBase.mp4"
      $candidates += "$sidecarBase.video-only.mp4"
    }
  }

  foreach ($candidate in @($candidates)) {
    if (-not $candidate) {
      continue
    }
    if (Test-Path -LiteralPath $candidate) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }

  return $null
}

function Get-ScenarioRecorderOverrideArgs {
  param(
    [hashtable]$BoundParameters,
    [string]$WindowTitle,
    [bool]$CaptureAudio,
    [int]$Fps,
    [string]$VideoBackend,
    [string]$AudioMode,
    [string]$OutputDirOverride
  )

  $scenarioArgs = @()
  if ($BoundParameters -and $BoundParameters.ContainsKey("WindowTitle") -and $WindowTitle) {
    $scenarioArgs += @("--window-title", $WindowTitle)
  }
  if ($BoundParameters -and $BoundParameters.ContainsKey("CaptureAudio")) {
    $scenarioArgs += @("--capture-audio", ($(if ($CaptureAudio) { "true" } else { "false" })))
  }
  if ($VideoBackend) {
    $scenarioArgs += @("--video-backend", $VideoBackend)
  }
  if ($BoundParameters -and $BoundParameters.ContainsKey("AudioMode") -and $AudioMode) {
    $scenarioArgs += @("--audio-mode", $AudioMode)
  }
  if ($BoundParameters -and $BoundParameters.ContainsKey("Fps")) {
    $scenarioArgs += @("--fps", ([string]([Math]::Max(8, $Fps))))
  }
  if ($BoundParameters -and $BoundParameters.ContainsKey("OutputDirOverride") -and $OutputDirOverride) {
    $scenarioArgs += @("--output-dir", $OutputDirOverride)
  }
  return @($scenarioArgs)
}

function Get-DebugGameEnvArgs {
  param(
    [hashtable]$BoundParameters,
    [bool]$DebugOverlay,
    [bool]$DebugColliders
  )

  $scenarioArgs = @()
  if ($BoundParameters -and $BoundParameters.ContainsKey("DebugOverlay") -and $DebugOverlay) {
    $scenarioArgs += @("--game-env", "XBOT_DEBUG_OVERLAY=1")
  }
  if ($BoundParameters -and $BoundParameters.ContainsKey("DebugColliders") -and $DebugColliders) {
    $scenarioArgs += @("--game-env", "XBOT_DEBUG_COLLIDERS=1")
  }
  return @($scenarioArgs)
}

function Test-IsVideoRunnerProcess {
  param([object]$Row)

  if (-not $Row) {
    return $false
  }
  $name = [string]$Row.Name
  $cmd = [string]$Row.CommandLine
  return ( ($name -match '^(powershell|pwsh)(\.exe)?$') -and ($cmd -match 'run_game_tests_with_video\.ps1') )
}

function Test-IsCaptureRelatedProcess {
  param([object]$Row)

  if (-not $Row) {
    return $false
  }
  $name = [string]$Row.Name
  $cmd = [string]$Row.CommandLine

  if ($name -match '^python(\.exe)?$') {
    return (($cmd -match 'launcher_test_hub\.py') -or ($cmd -match '\bmain\.py\b'))
  }
  if ($name -match '^node(\.exe)?$') {
    return ($cmd -match 'record_gameplay_test_video\.js')
  }
  return $false
}

function New-ProcessLookup {
  param([object[]]$Rows)

  $lookup = @{}
  foreach ($row in @($Rows)) {
    $procId = 0
    try {
      $procId = [int]$row.ProcessId
    } catch {
      $procId = 0
    }
    if ($procId -gt 0) {
      $lookup[$procId] = $row
    }
  }
  return $lookup
}

function New-ActiveRunnerLookup {
  param([object[]]$Rows)

  $lookup = @{}
  foreach ($row in @($Rows)) {
    if (-not (Test-IsVideoRunnerProcess -Row $row)) {
      continue
    }
    $procId = 0
    try {
      $procId = [int]$row.ProcessId
    } catch {
      $procId = 0
    }
    if ($procId -gt 0) {
      $lookup[$procId] = $true
    }
  }
  return $lookup
}

function Get-RunnerAncestorPid {
  param(
    [object]$ProcessRow,
    [hashtable]$ProcessLookup,
    [hashtable]$ActiveRunnerLookup
  )

  if (-not $ProcessRow) {
    return 0
  }

  $seen = @{}
  $cursor = $ProcessRow
  for ($depth = 0; $depth -lt 16; $depth++) {
    $parentId = 0
    try {
      $parentId = [int]$cursor.ParentProcessId
    } catch {
      $parentId = 0
    }
    if ($parentId -le 0) {
      break
    }
    if ($seen.ContainsKey($parentId)) {
      break
    }
    $seen[$parentId] = $true
    if ($ActiveRunnerLookup.ContainsKey($parentId)) {
      return $parentId
    }
    if (-not $ProcessLookup.ContainsKey($parentId)) {
      break
    }
    $cursor = $ProcessLookup[$parentId]
  }

  return 0
}

function Get-StaleCaptureProcessesFromRows {
  param(
    [object[]]$Rows,
    [int]$CurrentRunnerPid,
    [int[]]$ExcludeProcessIds = @()
  )

  $excludeLookup = @{}
  foreach ($pidValue in @($ExcludeProcessIds)) {
    if ($pidValue -and $pidValue -gt 0) {
      $excludeLookup[[int]$pidValue] = $true
    }
  }

  $processLookup = New-ProcessLookup -Rows $Rows
  $activeRunnerLookup = New-ActiveRunnerLookup -Rows $Rows
  $results = New-Object System.Collections.Generic.List[object]

  foreach ($row in @($Rows)) {
    $procId = 0
    try {
      $procId = [int]$row.ProcessId
    } catch {
      $procId = 0
    }
    if ($procId -le 0) {
      continue
    }
    if ($excludeLookup.ContainsKey($procId)) {
      continue
    }
    if (-not (Test-IsCaptureRelatedProcess -Row $row)) {
      continue
    }

    $ownerRunnerPid = Get-RunnerAncestorPid `
      -ProcessRow $row `
      -ProcessLookup $processLookup `
      -ActiveRunnerLookup $activeRunnerLookup
    if ($ownerRunnerPid -gt 0 -and $ownerRunnerPid -ne $CurrentRunnerPid) {
      continue
    }

    [void]$results.Add($row)
  }

  return @($results.ToArray())
}

function Set-DefaultBlasThreadEnv {
  foreach ($envName in @(
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "GOTO_NUM_THREADS"
  )) {
    if (-not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($envName))) {
      continue
    }
    [Environment]::SetEnvironmentVariable($envName, "1")
  }
}

function Get-StaleCaptureProcesses {
  param([int[]]$ExcludeProcessIds = @())

  $rows = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
  return @(Get-StaleCaptureProcessesFromRows -Rows $rows -CurrentRunnerPid ([int]$PID) -ExcludeProcessIds $ExcludeProcessIds)
}

function Stop-StaleCaptureProcesses {
  param([int]$WaitTimeoutSec = 20)

  $selfProc = Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction SilentlyContinue
  $exclude = @([int]$PID)
  if ($selfProc -and $selfProc.ParentProcessId) {
    $exclude += [int]$selfProc.ParentProcessId
  }

  $deadline = (Get-Date).AddSeconds([Math]::Max(4, [int]$WaitTimeoutSec))
  while ($true) {
    $stale = Get-StaleCaptureProcesses -ExcludeProcessIds $exclude
    if (@($stale).Count -eq 0) {
      return $true
    }

    foreach ($row in @($stale)) {
      try {
        Stop-Process -Id $row.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped stale process PID=$($row.ProcessId) [$($row.Name)]"
      } catch {
        Write-Host "Failed to stop stale process PID=$($row.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
      }
    }

    if ((Get-Date) -ge $deadline) {
      break
    }
    Start-Sleep -Milliseconds 650
  }

  $remaining = Get-StaleCaptureProcesses -ExcludeProcessIds $exclude
  if (@($remaining).Count -gt 0) {
    $pids = (@($remaining) | Select-Object -ExpandProperty ProcessId) -join ", "
    Write-Host "Warning: stale capture-related processes still running: $pids" -ForegroundColor Yellow
    return $false
  }

  return $true
}

function Stop-StaleGameProcesses {
  [void](Stop-StaleCaptureProcesses -WaitTimeoutSec 20)
}

function New-ScenarioRunIsolationContext {
  param(
    [string]$ProjectRootPath,
    [string]$ScenarioName,
    [string]$WindowTitleBase,
    [int]$AttemptNo,
    [datetime]$StartedAt = (Get-Date)
  )

  $safeScenario = [regex]::Replace(([string]$ScenarioName).ToLowerInvariant(), '[^a-z0-9]+', '-').Trim('-')
  if (-not $safeScenario) {
    $safeScenario = "scenario"
  }

  $safeTitle = [string]$WindowTitleBase
  if ([string]::IsNullOrWhiteSpace($safeTitle)) {
    $safeTitle = "King Wizard"
  }

  $runToken = "{0}-{1}-a{2}-p{3}" -f $StartedAt.ToString("yyyyMMdd-HHmmss"), $safeScenario, ([Math]::Max(1, [int]$AttemptNo)), $PID
  $runtimeUserDir = Join-Path $ProjectRootPath (Join-Path "tmp\video-run-sessions" $runToken)
  [void](New-Item -ItemType Directory -Force -Path $runtimeUserDir)

  return [pscustomobject]@{
    run_token = $runToken
    window_title = "$safeTitle [$runToken]"
    user_data_dir = $runtimeUserDir
    ready_log_path = Join-Path $runtimeUserDir "logs\game.log"
  }
}

function Get-GameScenarioCatalog {
  param([string]$ScenarioPath)

  if (-not (Test-Path -LiteralPath $ScenarioPath)) {
    throw "Scenario file not found: $ScenarioPath"
  }

  $pythonExe = Resolve-PythonExe
  $pythonScript = @'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8-sig"))
scenarios = payload.get("scenarios")
if not isinstance(scenarios, dict):
    raise SystemExit("Scenario file must contain 'scenarios' object map.")

rows = []
for name, cfg in scenarios.items():
    if isinstance(cfg, dict) and str(cfg.get("kind", "")).strip().lower() == "game":
        rows.append({"name": name, "cfg": cfg})

print(json.dumps(rows))
'@
  $rowsJson = $pythonScript | & $pythonExe - $ScenarioPath
  if ($LASTEXITCODE -ne 0) {
    throw "Scenario catalog normalization failed for $ScenarioPath"
  }
  $rows = @()
  $rowsPayload = [string]::Join("", @($rowsJson))
  if ($rowsPayload) {
    $rows = $rowsPayload | ConvertFrom-Json
  }

  $result = [ordered]@{}
  foreach ($entry in @($rows)) {
    if (-not $entry) {
      continue
    }
    $name = [string]$entry.name
    $cfg = $entry.cfg
    if ($cfg) {
      $result[$name] = $cfg
    }
  }

  if ($result.Keys.Count -eq 0) {
    throw "No game scenarios found (kind=game) in $ScenarioPath"
  }

  return $result
}

$resolvedScenarioFile = (Resolve-Path -LiteralPath $ScenarioFile).Path
$resolvedRecorderScript = Resolve-RecorderScript -ExplicitPath $RecorderScript
$resolvedFfmpegPath = Resolve-FfmpegPath -ExplicitPath $FfmpegPath
$resolvedFfprobePath = Resolve-FfprobePath -ResolvedFfmpegPath $resolvedFfmpegPath
$resolvedPythonExe = Resolve-PythonExe
$projectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $resolvedScenarioFile)))
$bookConformanceScript = Join-Path $projectRoot "scripts\book_visual_conformance_report.py"
$verdictCheckScript = Join-Path $projectRoot "test\tests\video_scenarios\check_video_bot_verdict.py"
if (-not (Test-Path -LiteralPath $bookConformanceScript)) {
  throw "Book conformance script not found: $bookConformanceScript"
}
if (-not (Test-Path -LiteralPath $verdictCheckScript)) {
  throw "Video bot verdict checker not found: $verdictCheckScript"
}

$gameScenarioCatalog = Get-GameScenarioCatalog -ScenarioPath $resolvedScenarioFile
$gameScenarios = @($gameScenarioCatalog.Keys)

if ($List) {
  Write-Host "Game scenarios in $resolvedScenarioFile"
  foreach ($name in $gameScenarios) {
    Write-Host "- $name"
  }
  exit 0
}

$selected = @()
if ($Scenario -eq "all") {
  $selected = $gameScenarios
} else {
  if ($gameScenarios -notcontains $Scenario) {
    throw "Scenario '$Scenario' is not game-kind or missing. Available: $($gameScenarios -join ', ')"
  }
  $selected = @($Scenario)
}

$hadFailure = $false
$retryCount = [Math]::Max(0, [int]$MaxRetries)
$minCoverage = [Math]::Max(0.20, [Math]::Min(1.00, [double]$MinDurationCoverage))
$minDurationFloorSec = [Math]::Max(8, [int]$MinDurationSec)

foreach ($scenarioName in $selected) {
  $scenarioCfg = $gameScenarioCatalog[$scenarioName]
  $launcherTest = "movement"
  if (
    $scenarioCfg -and
    $scenarioCfg.PSObject.Properties["launcher_test"] -and
    $scenarioCfg.launcher_test
  ) {
    $launcherTest = [string]$scenarioCfg.launcher_test
  }
  $launcherLocation = ""
  if (
    $scenarioCfg -and
    $scenarioCfg.PSObject.Properties["launcher_location"] -and
    $scenarioCfg.launcher_location
  ) {
    $launcherLocation = [string]$scenarioCfg.launcher_location
  }
  $skipBookConformance = $false
  if (
    $scenarioCfg -and
    $scenarioCfg.PSObject.Properties["skip_book_conformance"]
  ) {
    try {
      $skipBookConformance = [bool]$scenarioCfg.skip_book_conformance
    } catch {
      $skipBookConformance = $false
    }
  }

  $expectedDurationSec = 0.0
  if (
    $scenarioCfg -and
    $scenarioCfg.PSObject.Properties["duration_sec"] -and
    $scenarioCfg.duration_sec
  ) {
    try {
      $expectedDurationSec = [double]$scenarioCfg.duration_sec
    } catch {
      $expectedDurationSec = 0.0
    }
  }
  $requiredVideoSec = [Math]::Max([double]$minDurationFloorSec, $expectedDurationSec * $minCoverage)
  $scenarioOutputDir = Resolve-ScenarioOutputDir `
    -ScenarioCfg $scenarioCfg `
    -ProjectRootPath $projectRoot `
    -OutputDirOverridePath $OutputDirOverride

  $scenarioArgs = @(
    $resolvedRecorderScript,
    "--scenario-file", $resolvedScenarioFile,
    "--scenario", $scenarioName,
    "--ffmpeg-path", $resolvedFfmpegPath,
    "--game-exe", $resolvedPythonExe,
    "--game-arg", "launcher_test_hub.py",
    "--game-arg", "--test",
    "--game-arg", $launcherTest,
    "--game-arg", "--auto-start",
    "--game-arg", "--video-bot",
    "--game-cwd", $projectRoot
  )
  $scenarioArgs += Get-ScenarioRecorderOverrideArgs `
    -BoundParameters $PSBoundParameters `
    -WindowTitle $WindowTitle `
    -CaptureAudio $CaptureAudio `
    -Fps $Fps `
    -VideoBackend $VideoBackend `
    -AudioMode $AudioMode `
    -OutputDirOverride $OutputDirOverride
  $scenarioArgs += Get-DebugGameEnvArgs `
    -BoundParameters $PSBoundParameters `
    -DebugOverlay:$DebugOverlay `
    -DebugColliders:$DebugColliders
  if ($launcherLocation) {
    $scenarioArgs += @("--game-arg", "--location", "--game-arg", $launcherLocation)
  }

  $scenarioSucceeded = $false
  for ($attempt = 0; $attempt -le $retryCount -and -not $scenarioSucceeded; $attempt++) {
    $attemptNo = $attempt + 1
    $attemptTotal = $retryCount + 1
    Write-Host "Running game scenario with video: $scenarioName (attempt $attemptNo/$attemptTotal)"
    Set-DefaultBlasThreadEnv
    Stop-StaleGameProcesses
    $attemptStartedAt = Get-Date
    $runIsolation = New-ScenarioRunIsolationContext `
      -ProjectRootPath $projectRoot `
      -ScenarioName $scenarioName `
      -WindowTitleBase $WindowTitle `
      -AttemptNo $attemptNo `
      -StartedAt $attemptStartedAt

    $scenarioArgsForAttempt = @($scenarioArgs)
    $scenarioArgsForAttempt += @(
      "--window-title", $runIsolation.window_title,
      "--ready-log-path", $runIsolation.ready_log_path,
      "--game-env", "XBOT_WINDOW_TITLE=$($runIsolation.window_title)",
      "--game-env", "XBOT_USER_DATA_DIR=$($runIsolation.user_data_dir)",
      "--game-env", "XBOT_RUN_TOKEN=$($runIsolation.run_token)"
    )
    $scenarioHasVideoBot = $false
    $scenarioDefinesVideoBotLoop = $false
    if ($scenarioCfg -and $scenarioCfg.PSObject.Properties["game_env"] -and $scenarioCfg.game_env) {
      $scenarioEnv = $scenarioCfg.game_env
      foreach ($prop in $scenarioEnv.PSObject.Properties) {
        if (-not $prop) {
          continue
        }
        $envKey = [string]$prop.Name
        if ([string]::IsNullOrWhiteSpace($envKey)) {
          continue
        }
        $envValue = ""
        if ($null -ne $prop.Value) {
          $envValue = [string]$prop.Value
        }
        if ($envKey -eq "XBOT_VIDEO_BOT" -and $envValue -match '^(?i:1|true|yes|on)$') {
          $scenarioHasVideoBot = $true
        }
        if ($envKey -eq "XBOT_VIDEO_BOT_LOOP_PLAN") {
          $scenarioDefinesVideoBotLoop = $true
        }
        $scenarioArgsForAttempt += @("--game-env", "$envKey=$envValue")
      }
    }
    if ($scenarioHasVideoBot -and -not $scenarioDefinesVideoBotLoop) {
      $scenarioArgsForAttempt += @("--game-env", "XBOT_VIDEO_BOT_LOOP_PLAN=0")
    }

    & $NodePath @scenarioArgsForAttempt
    $runExitCode = $LASTEXITCODE
    if ($runExitCode -ne 0) {
      if ($attempt -lt $retryCount) {
        Write-Host "Scenario run failed (exit=$runExitCode), retrying..." -ForegroundColor Yellow
        continue
      }
      $hadFailure = $true
      Write-Host "Scenario failed: $scenarioName (exit=$runExitCode)" -ForegroundColor Red
      break
    }

    $metaFile = Find-LatestScenarioMetadata `
      -OutputDir $scenarioOutputDir `
      -ScenarioName $scenarioName `
      -StartedAt $attemptStartedAt
    if (-not $metaFile) {
      if ($attempt -lt $retryCount) {
        Write-Host "Metadata not found for '$scenarioName' in '$scenarioOutputDir', retrying..." -ForegroundColor Yellow
        continue
      }
      $hadFailure = $true
      Write-Host "Scenario failed: $scenarioName (metadata missing)" -ForegroundColor Red
      break
    }

    try {
      $meta = Get-Content -LiteralPath $metaFile.FullName -Raw | ConvertFrom-Json
    } catch {
      if ($attempt -lt $retryCount) {
        Write-Host "Metadata parse failed for '$scenarioName', retrying..." -ForegroundColor Yellow
        continue
      }
      $hadFailure = $true
      Write-Host "Scenario failed: $scenarioName (metadata parse error)" -ForegroundColor Red
      break
    }

    $readyOk = $true
    if ($meta -and $meta.PSObject.Properties["wait_ready_found"]) {
      $readyOk = [bool]$meta.wait_ready_found
    }
    if (-not $readyOk) {
      if ($attempt -lt $retryCount) {
        Write-Host "Ready marker was not found for '$scenarioName', retrying..." -ForegroundColor Yellow
        continue
      }
      $hadFailure = $true
      Write-Host "Scenario failed: $scenarioName (ready marker missing)" -ForegroundColor Red
      break
    }

    $videoPath = Resolve-RecordedVideoPath -Metadata $meta -MetadataPath $metaFile.FullName
    $videoDurationSec = Get-RecordedVideoDurationSec -FfprobePath $resolvedFfprobePath -VideoPath $videoPath
    if ($null -eq $videoDurationSec) {
      if ($attempt -lt $retryCount) {
        Write-Host "Video duration probe failed for '$scenarioName', retrying..." -ForegroundColor Yellow
        continue
      }
      $hadFailure = $true
      Write-Host "Scenario failed: $scenarioName (video duration probe failed)" -ForegroundColor Red
      break
    }

    if ([double]$videoDurationSec + 0.001 -lt [double]$requiredVideoSec) {
      $msg = "Scenario '$scenarioName' too short: recorded $([Math]::Round($videoDurationSec,1))s, required >= $([Math]::Round($requiredVideoSec,1))s."
      if ($attempt -lt $retryCount) {
        Write-Host "$msg Retrying..." -ForegroundColor Yellow
        continue
      }
      $hadFailure = $true
      Write-Host "Scenario failed: $msg" -ForegroundColor Red
      break
    }

    if (-not $skipBookConformance) {
      $bookArgs = @(
        $bookConformanceScript,
        "--metadata", $metaFile.FullName,
        "--scenario-file", $resolvedScenarioFile,
        "--project-root", $projectRoot,
        "--strict-book"
      )
      if ($BookDocx) {
        $bookArgs += @("--book-docx", $BookDocx)
      }

      & $resolvedPythonExe @bookArgs
      $bookExitCode = $LASTEXITCODE
      if ($bookExitCode -ne 0) {
        if ($attempt -lt $retryCount) {
          Write-Host "Book conformance failed for '$scenarioName' (exit=$bookExitCode), retrying..." -ForegroundColor Yellow
          continue
        }
        $hadFailure = $true
        Write-Host "Scenario failed: $scenarioName (book conformance mismatch)" -ForegroundColor Red
        break
      }
    } else {
      Write-Host "Book conformance skipped for '$scenarioName' by scenario policy." -ForegroundColor DarkYellow
    }

    $verdictArgs = @(
      $verdictCheckScript,
      "--scenario", $scenarioName,
      "--scenario-file", $resolvedScenarioFile,
      "--project-root", $runIsolation.user_data_dir
    )
    & $resolvedPythonExe @verdictArgs
    $verdictExitCode = $LASTEXITCODE
    if ($verdictExitCode -ne 0) {
      if ($attempt -lt $retryCount) {
        Write-Host "Video bot verdict failed for '$scenarioName' (exit=$verdictExitCode), retrying..." -ForegroundColor Yellow
        continue
      }
      $hadFailure = $true
      Write-Host "Scenario failed: $scenarioName (video bot verdict mismatch)" -ForegroundColor Red
      break
    }

    $scenarioSucceeded = $true
    Write-Host "Scenario done: $scenarioName (video $([Math]::Round($videoDurationSec,1))s)" -ForegroundColor Green
  }

  if (-not $scenarioSucceeded) {
    $hadFailure = $true
  }
}

if ($hadFailure) {
  exit 1
}

exit 0
