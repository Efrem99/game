# BAM And Animation Pipeline

## Why BAM

`*.bam` is Panda3D-native and usually gives:

- faster runtime loading,
- fewer importer edge-cases than raw `fbx/gltf`,
- stable deployment path for production builds.

## BAM conversion (targeted, not global scan)

The converter does **not** scan the whole repo by default. It reads only core runtime configs.

### Dry run

```powershell
python scripts/convert_assets_to_bam.py --dry-run
```

### Convert config-referenced assets

```powershell
python scripts/convert_assets_to_bam.py --verify
```

### Convert config + selected roots

```powershell
python scripts/convert_assets_to_bam.py --include-roots --verify --root assets/models --root assets/anims
```

Notes:

- Existing BAM files are not overwritten unless `--overwrite` is used.
- Runtime code now prefers `*.bam` automatically when a same-stem BAM exists.

## Blender animation library (all clips in one place)

Build an animation library blend around XBot rig:

```powershell
blender -b -P tools/blender/build_xbot_animation_library.py
```

Optional combined export:

```powershell
blender -b -P tools/blender/build_xbot_animation_library.py -- --export-glb
```

Outputs:

- `assets/models/xbot/xbot_animation_library.blend`
- `logs/xbot_animation_library_report.json`

This gives a single Animator/NLA workspace to review and refine all imported clips.
