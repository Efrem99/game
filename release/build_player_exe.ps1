param(
    [string]$PythonExe = "python",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Invoke-Python {
    param([string[]]$Args)
    & $PythonExe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $PythonExe $($Args -join ' ')"
    }
}

$DistPath = Join-Path $ProjectRoot "release\dist"
$WorkPath = Join-Path $ProjectRoot "release\build"
$SpecPath = Join-Path $ProjectRoot "release"

if ($Clean) {
    if (Test-Path $DistPath) { Remove-Item -Recurse -Force $DistPath }
    if (Test-Path $WorkPath) { Remove-Item -Recurse -Force $WorkPath }
}

New-Item -ItemType Directory -Path $DistPath -Force | Out-Null
New-Item -ItemType Directory -Path $WorkPath -Force | Out-Null

Invoke-Python @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Python @("-m", "pip", "install", "-r", "requirements.txt", "pyinstaller")

$addData = @(
    "assets;assets",
    "assets_raw;assets_raw",
    "data;data",
    "docs;docs",
    "launchers;launchers",
    "models;models",
    "scripts;scripts",
    "shaders;shaders",
    "src;src",
    "tools;tools",
    "world;world"
)

if (Test-Path (Join-Path $ProjectRoot "game_core.pyd")) {
    $addData += "game_core.pyd;."
}

$args = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "KingWizardRPG",
    "--paths", "src",
    "--distpath", $DistPath,
    "--workpath", $WorkPath,
    "--specpath", $SpecPath,
    "launcher.pyw"
)

foreach ($pair in $addData) {
    $args += @("--add-data", $pair)
}

Invoke-Python $args

$BundleRoot = Join-Path $DistPath "KingWizardRPG"
if (-not (Test-Path $BundleRoot)) {
    throw "Expected bundle was not created: $BundleRoot"
}

if (Test-Path (Join-Path $ProjectRoot "start_game.bat")) {
    Copy-Item -Path (Join-Path $ProjectRoot "start_game.bat") -Destination (Join-Path $BundleRoot "start_game.bat") -Force
}

Write-Host "Player EXE bundle ready: $BundleRoot"
