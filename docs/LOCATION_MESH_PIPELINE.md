# Location Mesh Pipeline (Blender Python -> Game)

This project now supports handcrafted location meshes loaded at runtime.

## 1) Generate base location meshes in Blender

Run from project root:

```powershell
blender -b -P tools/blender/generate_location_blockouts.py
```

Optional target:

```powershell
blender -b -P tools/blender/generate_location_blockouts.py -- --target sherward_room
blender -b -P tools/blender/generate_location_blockouts.py -- --target castle_keep
```

Generated exports:

- `assets/models/locations/sherward_room.glb`
- `assets/models/locations/sherward_room.fbx`
- `assets/models/locations/castle_keep_block.glb`
- `assets/models/locations/castle_keep_block.fbx`

## 2) Enable meshes in world config

Edit `data/world/location_meshes.json` and set `"enabled": true` for the entries you want.

Example:

```json
{
  "id": "sherward_room_shell",
  "enabled": true,
  "model": "assets/models/locations/sherward_room.glb",
  "pos": [6.0, 74.0, 24.0],
  "hpr": [180.0, 0.0, 0.0],
  "scale": 1.0,
  "is_platform": true
}
```

## 3) Runtime behavior

- Meshes are loaded during world generation (`SharuanWorld._build_location_meshes`).
- If `is_platform` is `true`, bounds are registered into physics/collider fallback.
- Missing files are skipped safely with a warning.

## 4) Recommended production flow

1. Blockout with the generator script.
2. Polish in Blender manually (UV, materials, trims, collisions).
3. Export final `GLB` (preferred) and optional `FBX`.
4. Keep transforms applied (`Ctrl+A`) before export.
