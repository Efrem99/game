# King Wizard

King Wizard is the main development workspace for the Panda3D action-RPG prototype.
This repository is the source of truth for gameplay, rendering, UI, data, assets,
and the optional compiled `game_core.pyd` runtime module.

## Workspace Rules

- This repo is the mandatory dev workspace.
- Player-facing Windows builds are produced from `release/`.
- Do not treat the release bundle as the editable source of truth.

## Quick Start

Run the game from project root:

```powershell
python main.py
```

Build the optional compiled core:

```powershell
python scripts/build_game_core.py
```

After a successful build, `game_core.pyd` should appear in project root and
`logs/game.log` should contain `Successfully loaded game_core.pyd`.

## Testing

Gameplay and rendering checks:

- Use `tests/video_scenarios/run_game_tests_with_video.ps1`
- Store review artifacts in `output/non-web-mechanics-review`
- Treat short or broken video runs as failures

Non-game checks:

- Use focused `pytest` runs

## Primary Docs

- Agent rules: `AGENTS.md`
- Gameplay debug workflow: `docs/AGENT_GAMEPLAY_PLAYBOOK.md`
- Visual audit and known world-system risks: `docs/VISUAL_SYSTEMS_AUDIT.md`
- Animation pipeline: `docs/BAM_AND_ANIMATION_PIPELINE.md`
- Animation asset status: `data/ANIMATIONS_AVAILABLE.md`
- Animation state architecture: `data/states/STATE_ARCHITECTURE_FULL.md`
- Windows build notes for `game_core`: `data/BUILD_GAME_CORE_WINDOWS.md`
- Release packaging: `release/README.md`
- Installer payload map: `release/SETUP_FILE_MAP.md`

## Release Output

Player build output paths:

- EXE bundle: `release/dist/KingWizardRPG/`
- Installer: `release/out/`

Use these scripts:

```powershell
powershell -ExecutionPolicy Bypass -File release/build_player_exe.ps1
powershell -ExecutionPolicy Bypass -File release/build_installer.ps1
```
