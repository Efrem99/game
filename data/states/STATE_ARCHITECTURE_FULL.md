# Character Animation Architecture (Full)

This document is the canonical "full tree" for the player animation/state design.
Runtime implementation lives in:

- `data/states/player_states.json` (state definitions, transitions, runtime rules)
- `src/entities/player_state_machine_mixin.py` (rule processor, priorities, transition gating)

## Full Tree

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
| Action | 30-39 | Attack, cast, dash, parkour overlays |
| Locomotion | 40-59 | Idle/walk/run/jump/fall/swim/fly |
| Context tweaks | 60+ | Weak contextual corrections |

## Current Runtime-Implemented States

Implemented in `player_states.json` now:

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

## Runtime Rules (Implemented)

- Death override (`hp <= 0`) always wins.
- Hard landing trigger promotes to `falling_hard`.
- Mount context drives `mounted_idle`/`mounted_move`.
- Flight and water context override locomotion when active.
- Wallrun exit at high speed can promote to `staggered`.

