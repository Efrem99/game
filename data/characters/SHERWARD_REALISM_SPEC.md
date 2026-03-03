# SHERWARD Realism Spec

## Identity
- Name: `Shervard`
- Visual target: realistic dark-fantasy hero, Mortensen-type energy, but younger and less exhausted.
- Emotional baseline: controlled and internal tension, not permanently angry.

## Body Proportions
- Height: `185 cm`
- Head-to-body ratio: `1:7.5`
- Shoulders: slightly above average width, non-superhero.
- Neck: athletic/solid but not massive.
- Build: survival-trained, functional strength, not bodybuilder.

## Face
- Shape: moderately elongated.
- Cheekbones: visible but not razor-sharp.
- Jaw: clear line, not square block.
- Nose: straight, slightly longer than average, mild natural asymmetry.
- Eyes: deep-set, calm alert gaze.
- Iris color target: dark green or gray-brown.
- Eyebrows: neutral by default, no permanent frown.

## Hair And Facial Hair
- Hair color: dark chestnut.
- Hair length: medium.
- Style: practical, pushed/swept back or partially tied.
- Facial hair: 2-4 day stubble, slightly darker than hair.

## Outfit (Peaceful Version)
- Base layers:
  - linen shirt
  - matte leather doublet
  - lightweight steel inserts
  - knee-length cloak
- Material direction:
  - leather: matte, worn edges
  - steel: low gloss, non-mirror
  - visible wear on elbows and garment edges
- Weapon:
  - practical sword
  - minimal ornament
  - readability and function over gold/decor

## Animation Character Notes
- Idle:
  - balanced center of mass
  - low amplitude breathing/shoulder movement
  - periodic subtle look scanning
- Combat idle:
  - slight forward lean
  - lower center of gravity
  - no nervous bouncing

## Technical Requirements (Blender)
- PBR skin with subtle subsurface scattering.
- Micro-normal detail for pores (non-noisy).
- Face asymmetry required (do not mirror final sculpt).
- Head as separate mesh during production is allowed.
- Rig controls required:
  - jaw bone
  - eye bones
  - brow controls
  - lip corner controls

## Runtime Constraints
- Keep gameplay rig compatibility with existing animation/state pipeline.
- Preserve Mixamo-style bone naming where possible.
- Export scale must remain clean (`1.0`), no negative scales.
- Runtime fallback remains `assets/models/xbot/Xbot.glb` until hero asset is ready.
