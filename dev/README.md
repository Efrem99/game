# Dev Workspace (Mandatory)

This repository is the development workspace and must remain intact as the source of truth.

## Rule

- `dev` workflow and source directories stay in the repo.
- Player distribution is built separately via `release/`.

## Player Build Path

- EXE bundle: `release/dist/KingWizardRPG/`
- Installer: `release/out/`

This keeps developer tooling and player-facing delivery cleanly separated.
