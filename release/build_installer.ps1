param(
    [string]$PythonExe = "python",
    [string]$InnoCompiler = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    [switch]$SkipExeBuild
)

$ErrorActionPreference = "Stop"

$ReleaseRoot = (Resolve-Path $PSScriptRoot).Path
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if (-not $SkipExeBuild) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $ReleaseRoot "build_player_exe.ps1") -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "EXE build failed."
    }
}

if (-not (Test-Path $InnoCompiler)) {
    throw "Inno Setup compiler not found: $InnoCompiler"
}

$AppVersion = (Get-Date -Format "yyyy.MM.dd.HHmm")
$IssPath = Join-Path $ReleaseRoot "installer\KingWizardRPG.iss"

if (-not (Test-Path $IssPath)) {
    throw "Installer script not found: $IssPath"
}

& $InnoCompiler "/DAppVersion=$AppVersion" $IssPath
if ($LASTEXITCODE -ne 0) {
    throw "Installer build failed."
}

Write-Host "Installer build completed. Check: release\\out"
