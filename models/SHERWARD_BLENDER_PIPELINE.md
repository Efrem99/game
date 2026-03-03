# Shervard Blender Pipeline

## Goal
Produce a game-ready Shervard hero model with realistic face/body, existing gameplay animation compatibility, and clean runtime export.

## Source of Truth
- Visual spec: `data/characters/SHERWARD_REALISM_SPEC.md`
- Machine-readable profile: `data/characters/sherward_profile.json`
- Runtime player config: `data/actors/player.json`

## Output Paths
- Main model: `assets/models/hero/sherward/sherward.glb`
- Optional source blend: `models/sherward_character.blend`
- Optional textures:
  - `assets/models/hero/sherward/textures/sherward_albedo.png`
  - `assets/models/hero/sherward/textures/sherward_normal.png`
  - `assets/models/hero/sherward/textures/sherward_roughness.png`
  - `assets/models/hero/sherward/textures/sherward_metallic.png`
  - `assets/models/hero/sherward/textures/sherward_ao.png`

## Production Steps
1. Duplicate baseline character rig scene.
2. Sculpt/proportion pass:
   - enforce 185 cm, 1:7.5 ratio
   - refine shoulders/neck to realistic athletic profile
3. Face pass:
   - asymmetry first, then details
   - deep-set eyes, neutral brow baseline, mild nose asymmetry
4. Hair/stubble pass:
   - medium dark chestnut hairstyle
   - 2-4 day stubble mask
5. Outfit pass:
   - linen + leather + steel inserts + cloak
   - edge wear/micro roughness breakup
6. Rig compatibility pass:
   - preserve main gameplay skeleton compatibility
   - add facial controls (jaw/eyes/brows/lip corners)
7. Animation sanity pass:
   - idle, walk, run, jump, land, attack
   - combat idle posture matches design notes
8. Export GLB with clean transforms.

## Fast Auto-Base Build Script
You can generate a first-pass Shervard baseline from existing Xbot rig with:

```bash
blender --background --python models/build_sherward_base.py -- \
  --base-model assets/models/xbot/Xbot.glb \
  --target-height 1.85 \
  --output-blend models/sherward_character.blend \
  --export-glb assets/models/hero/sherward/sherward.glb \
  --add-facial-control-hooks
```

Optional head replacement in the same run:

```bash
blender --background --python models/build_sherward_base.py -- \
  --base-model assets/models/xbot/Xbot.glb \
  --head-model C:/art/sherward_head.glb \
  --head-bone mixamorig:Head \
  --head-scale 1.0 \
  --target-height 1.85 \
  --output-blend models/sherward_character.blend \
  --export-glb assets/models/hero/sherward/sherward.glb
```

## Likeness Refinement Script (Second Pass)
After first-pass mesh/outfit, run precise likeness pass with references:

```bash
blender --background --python models/refine_sherward_likeness.py -- \
  --scene-blend models/sherward_character.blend \
  --references-dir data/characters/sherward_refs \
  --output-blend models/sherward_character_likeness.blend \
  --export-glb assets/models/hero/sherward/sherward.glb \
  --eye-color dark_green \
  --asymmetry 0.35 \
  --stubble-strength 0.45 \
  --create-review-cameras \
  --create-neutral-lights
```

Optional explicit references:

```bash
blender --background --python models/refine_sherward_likeness.py -- \
  --scene-blend models/sherward_character.blend \
  --front-ref C:/art/sherward_front.png \
  --side-ref C:/art/sherward_side.png \
  --threeq-ref C:/art/sherward_3q.png \
  --output-blend models/sherward_character_likeness.blend
```

## Existing Head-Swap Utility
Use when replacing only the head while preserving current body/rig:
`models/blender_head_swap.py`

Example:
```bash
blender --background models/character.blend --python models/blender_head_swap.py -- \
  --armature XBot_Armature \
  --body Character_Body \
  --head-bone mixamorig:Head \
  --new-head "C:/art/sherward_head.glb" \
  --new-head-name SherwardHead \
  --old-head Character_Head \
  --scale 1.0 \
  --join-body \
  --output models/sherward_character.blend \
  --export-glb assets/models/hero/sherward/sherward.glb
```

## Validation
Run:
```bash
python launcher_test_sherward.py
python launcher_test_manifest.py
python launcher_test_smoke.py
```

`launcher_test_sherward.py` validates expected files and runtime config wiring before game launch.
