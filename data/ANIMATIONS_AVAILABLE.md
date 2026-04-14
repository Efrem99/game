# Animation Asset Guide

This is the canonical high-level animation status document for the repo.

Use it together with:

- `data/states/STATE_ARCHITECTURE_FULL.md` for the runtime state model
- `data/states/ANIMATION_COVERAGE.md` for the current resolved state-to-clip report
- `assets/anims/README.md` for runtime source folders and naming rules
- `docs/BAM_AND_ANIMATION_PIPELINE.md` for conversion and packaging workflow

## Runtime Source Of Truth

- State definitions and transition rules: `data/states/player_states.json`
- State-to-clip overrides: `data/actors/player_animations.json`
- Runtime resolution and coverage report generation: `src/entities/player.py`
- Folder-level animation source rules: `assets/anims/README.md`

## Current Runtime Status

Latest coverage snapshot from `data/states/ANIMATION_COVERAGE.md`:

- Generated: `2026-03-24 15:07:02`
- Total states: `31`
- OK: `31`
- Fallback: `0`
- Missing: `0`

That means the runtime state machine currently resolves every required player
state to a clip, even though some assets still come from different source sets.

## Asset Audit Snapshot

The old root-level inventory reports were merged into this file:

- `animation-inventory.md`
- `game-animation-inventory.md`
- `campfire-local-inventory.md`

Latest full-game snapshot that was worth keeping:

- Scope: `183` scanned game assets
- OK: `20`
- Unknown: `110`
- Warning: `53`

What those numbers mean:

- `OK`: asset container exposed usable animation clips
- `Unknown`: mostly binary FBX files that need DCC or converter inspection
- `Warning`: static assets or GLBs with no animation clips

The old campfire/local inventory was a narrow prop-only subset and did not add a
separate long-term source of truth, so it is folded into the summary here rather
than maintained as a standalone report.

## Gameplay-Ready Animation Assets

These assets are the curated set currently called out as directly useful for the
player runtime and combat feel.

### In `assets/anims/`

Combat:

- `attack_longsword_1.glb`
- `attack_longsword_2.glb`
- `attack_slashes.glb`
- `attack_thrust.glb`
- `block_idle.glb`
- `parry.glb`

Movement and parkour:

- `landing_run.glb`
- `midair.glb`

Magic:

- `sword_and_shield_casting.glb`
- `sword_and_shield_casting_2.glb`

Draw and sheath:

- `sheath_sword_1.glb`
- `sheath_sword_2.glb`

Death:

- `death.glb`

## Current Runtime Mapping Notes

States already backed by the curated set:

- `falling` -> `midair.glb`
- `landing` -> `landing_run.glb`
- `attacking` -> `attack_longsword_1.glb`
- `blocking` -> `block_idle.glb`
- `casting` -> `sword_and_shield_casting.glb`
- `dead` -> `death.glb`

States still commonly resolved through XBot or Mixamo-compatible fallback paths:

- `idle`
- `walking`
- `running`
- `jumping`
- `dodging`
- `vaulting`
- `climbing`
- `wallrun`

## External Libraries And Acquisition Paths

### Mixamo / manifest-driven runtime folders

See `assets/anims/README.md` for:

- strict runtime source behavior
- auto source directories
- mount naming conventions
- Mixamo fetch helpers

### Paragon archive

Known external library:

- Location: `assets/models/paragonanimationsretargetedtomanny/ParagonAnimationsRetargetedToManny/`
- Approximate count: `5,385` FBX files

Best candidate families called out previously:

- `FengMaoManny` for sword combat
- `gideonManny` for casting and mage motion
- `KallariManny` for dodge and stealth motion
- `minionsManny` for simple enemy coverage

## Remaining Gaps

Highest-value animation gaps to close next:

- vault-over obstacle clips
- ledge-climb up clips
- wall-run specific clips
- richer dodge variants
- more spell cast variants

## Maintenance Rule

Keep this file as the concise animation status guide.

Do not create new root-level inventory Markdown files for one-off audits.
If a new audit is needed, either:

- update this summary if it changes the canonical understanding, or
- store the raw output under a clearly scoped review/artifact location

