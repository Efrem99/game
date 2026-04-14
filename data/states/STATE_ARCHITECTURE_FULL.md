# Character Animation Architecture

This is the canonical architecture document for the player animation and state
system.

Runtime implementation lives in:

- `data/states/player_states.json`
- `data/actors/player_animations.json`
- `src/entities/player_state_machine_mixin.py`
- `src/entities/player.py`

Use this document with:

- `data/states/ANIMATION_COVERAGE.md` for the current resolved clip report
- `data/ANIMATIONS_AVAILABLE.md` for the asset-level status guide

## Full State Tree

```text
Character
|
+-- LifeState
|   +-- Alive
|   +-- Downed
|   +-- Dead
|
+-- LocomotionLayer (primary)
|   +-- Grounded
|   |   +-- Idle
|   |   +-- Walk
|   |   +-- Run
|   |   +-- Sprint
|   |   +-- Crouch
|   |
|   +-- Airborne
|   |   +-- JumpStart
|   |   +-- InAir
|   |   +-- Falling
|   |   +-- Landing
|   |
|   +-- Water
|   |   +-- EnterWater
|   |   +-- SurfaceSwim
|   |   +-- Dive
|   |   +-- UnderwaterSwim
|   |   +-- ExitWater
|   |
|   +-- Flight
|       +-- TakeOff
|       +-- Glide
|       +-- Hover
|       +-- Dive
|       +-- Land
|
+-- StabilityLayer (modifier)
|   +-- Stable
|   +-- Unstable
|   +-- Sliding
|   +-- Staggered
|   +-- FallingHard
|   +-- Recovering
|
+-- ActionLayer (overlay)
|   +-- None
|   +-- Attack
|   |   +-- Light
|   |   +-- Heavy
|   |   +-- Combo
|   +-- Block
|   +-- Dash
|   +-- Cast
|   +-- Interact
|   +-- Parkour
|       +-- Vault
|       +-- GrabLedge
|       +-- ClimbUp
|       +-- WallRun
|       +-- WallJump
|
+-- DamageResponseLayer
|   +-- LightHit
|   +-- HeavyHit
|   +-- Knockback
|   +-- AirHit
|   +-- WallImpact
|   +-- GroundImpact
|
+-- ContextFlags (not states)
    +-- WallContact
    +-- DestructibleSurface
    +-- SlipperySurface
    +-- SoftSurface
    +-- SteepSlope
    +-- InMud
    +-- InWater
    +-- InAirCurrent
    +-- ObstacleAhead
    +-- LowCeiling
```

## Runtime Priority Bands

Lower number means stronger priority.

| Band | Range | Purpose |
|---|---:|---|
| Life | 0-9 | Dead/downed hard override |
| Stability | 10-29 | Loss of control, stagger, hard falls |
| Action | 30-39 | Attack, cast, dodge, parkour overlays |
| Locomotion | 40-59 | Idle, walk, run, jump, fall, swim, fly |
| Context tweaks | 60+ | Weak contextual corrections |

## Runtime-Implemented States

The active runtime currently implements and resolves these state families:

- `dead`
- `falling_hard`
- `staggered`
- `sliding`
- `recovering`
- `mounting`
- `mounted_idle`
- `mounted_move`
- `dismounting`
- `attacking`
- `dodging`
- `blocking`
- `casting`
- `cast_prepare`
- `cast_channel`
- `cast_release`
- `vaulting`
- `climbing`
- `wallrun`
- `swim`
- `flying`
- `jumping`
- `falling`
- `landing`
- `idle`
- `walking`
- `running`
- `crouch_idle`
- `crouch_move`

## Runtime Rules

- Death override (`hp <= 0`) always wins.
- Hard landing can promote to `falling_hard`.
- Mount context drives mount idle and move states.
- Flight and water context override ordinary grounded locomotion.
- Parkour conditions can promote to `vaulting`, `climbing`, or `wallrun`.
- State changes are expected to drive clip selection through the runtime player
  animation system rather than ad-hoc hardcoded animation switches.

## Validation

When changing state logic, verify all three layers:

1. Architecture integrity
- `data/states/player_states.json`
- `data/actors/player_animations.json`

2. Coverage integrity
- `data/states/ANIMATION_COVERAGE.md`

3. Live behavior
- relevant gameplay video scenario

Recommended live checks:

- locomotion transition routes
- melee core route
- weapon mode route
- HUD/combat feedback route
- water and flight routes

## Historical Note

The old `EXTENDED_STATES.md` planning document was folded into this file once the
state machine and coverage reporting became runtime-backed rather than speculative.
