# Release Pipeline (Player Build)

This folder is for player-facing artifacts only.

## Goal

- Keep this repository as the mandatory `dev` workspace.
- Build a separate Windows player package (`.exe` + installer) from this workspace.

## Quick Start (Windows)

1. Build executable bundle:
   - `powershell -ExecutionPolicy Bypass -File release/build_player_exe.ps1`
2. Build installer (requires Inno Setup 6):
   - `powershell -ExecutionPolicy Bypass -File release/build_installer.ps1`

## Output

- EXE bundle: `release/dist/KingWizardRPG/`
- Installer: `release/out/`

## Notes

- This is a production scaffold and may need tuning for final art/audio payload.
- `game_core.pyd` is included automatically when present in project root.
- Exact file map: `release/SETUP_FILE_MAP.md`.
