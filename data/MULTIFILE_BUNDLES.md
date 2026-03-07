# Multifile Bundles

The project now supports themed Panda3D `.mf` archives.

## Config
- File: `data/asset_multifiles.json`
- Defines:
  - `bundles`: archive name + source patterns + optional prewarm model list
  - `profiles`: runtime context presets (`startup`, `sharuan`, `combat`, `opening_memory`)
  - `location_profiles`: location token -> profile

## Build archives
```powershell
python scripts/build_multifiles.py
```

Build only startup bundles:
```powershell
python scripts/build_multifiles.py --profile startup
```

Build a single bundle:
```powershell
python scripts/build_multifiles.py --bundle core_characters
```

## Runtime behavior
- `AssetBundleManager` mounts bundle `.mf` files when profile/location is activated.
- Startup and location transitions activate corresponding bundle profiles.
- `PreloadManager` now checks Panda VFS, so prewarm targets inside mounted `.mf` are valid.
