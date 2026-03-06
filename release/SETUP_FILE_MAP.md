# Setup File Map

## Included From Dev Machine (Build Inputs)

`release/build_player_exe.ps1` packs these directories into the player bundle:

- `assets/`
- `assets_raw/`
- `data/`
- `docs/`
- `launchers/`
- `models/`
- `scripts/`
- `shaders/`
- `src/`
- `tools/`
- `world/`

Optional file:

- `game_core.pyd` (if present in project root)

Entry point:

- `launcher.pyw` -> produces `KingWizardRPG.exe`

Also copied into bundle:

- `start_game.bat` (if present)

## Generated On Dev Machine During Build

- `release/build/` (PyInstaller temp/build files)
- `release/dist/KingWizardRPG/` (ready-to-install game bundle)
- `release/out/KingWizardRPG_Setup_<version>.exe` (installer output)

## Created On Player PC (Installed App)

Install location (default):

- `C:\Program Files\King Wizard RPG\`

Created by installer:

- all files from `release/dist/KingWizardRPG/`
- Start Menu shortcut
- optional Desktop shortcut

Runtime data (created on first run):

- `%LOCALAPPDATA%\KingWizardRPG\logs\`
- `%LOCALAPPDATA%\KingWizardRPG\saves\`
- `%LOCALAPPDATA%\KingWizardRPG\cache\`

## Update Flow

If you release an update:

1. Build new installer.
2. Keep same `AppId` in `KingWizardRPG.iss`.
3. Increase app version (script already passes a timestamp version).
4. User runs new installer over old install.

Result: in-place upgrade without losing saves/logs (they are in `%LOCALAPPDATA%`).
