# Blender Art Pass Guide

## Goal
Create unique-looking characters, mobs, and bosses by upgrading heads/faces, silhouette details, and materials while keeping the existing gameplay rig and animation pipeline stable.

## 1) Head Swap Strategy
Yes, replacing the old head with a generated/sculpted one is a valid production workflow.

Use `models/blender_head_swap.py` to automate:
- importing a new head mesh,
- aligning it to the head bone,
- transferring skin weights from body mesh,
- binding to the same armature,
- optional join back into body mesh,
- exporting final GLB/FBX.

Example:
```bash
blender --background models/character.blend --python models/blender_head_swap.py -- \
  --armature XBot_Armature \
  --body Character_Body \
  --head-bone mixamorig:Head \
  --new-head "C:/art/new_head.glb" \
  --new-head-name HeroHeadA \
  --old-head Character_Head \
  --scale 1.0 \
  --join-body \
  --output models/character_headswap.blend \
  --export-glb assets/models/character_headswap.glb
```

## 2) Face and Character Uniqueness
- Keep one rig, vary identity with:
- head shape and jawline,
- nose/lips/brow proportions,
- scars/tattoos/paint masks,
- hairstyle, beard, brows, accessories,
- skin roughness/normal map variation.

## 3) Boss/Mob Uniqueness Pass
- Bosses:
- custom horn/crest/spine shapes,
- emissive accents and unique silhouette,
- large readable attack pose keyframes.
- Mobs:
- 2-4 visual variants per type (color + attachments + minor mesh edits),
- maintain same collision/scale class where gameplay requires.

## 4) Material and Lighting Rules
- Author PBR maps consistently:
- albedo (no baked lighting),
- normal (tangent-space),
- roughness (high variation for readability),
- metallic only for true metal parts.
- Avoid very dark albedo values to prevent black-looking assets in runtime.

## 5) Animation Safety Checklist
- Armature name unchanged.
- Core bones unchanged (`mixamorig:*` if used).
- Root transform clean (`scale = 1`, no hidden pre-rotation).
- No negative scale on exported meshes.
- Verify clips:
- `idle`, `move/run`, `telegraph`, `attack`, `recover`, `hit`, `death`.

## 6) World Art Pass (Global Graphics)
- Terrain:
- improve texture tiling breakup (macro/micro variation).
- Water:
- transparency, specular highlights, shoreline foam.
- Biomes:
- distinct fog tint + ambient color per biome.
- Post:
- quality presets must control AA, bloom, screenspace pass, and light intensity consistently.

## 7) Integration Order
1. Head swap on hero + one boss + one mob.
2. Re-export GLB and hook into runtime config.
3. Validate animation state-map names.
4. Run visual sanity pass in test launchers.
5. Repeat for full roster.
