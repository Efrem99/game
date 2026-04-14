---
name: ultimate-game-qa
description: Use this skill for gameplay recordings, scripted QA scenarios, smart autopilot runs, video-debug-driven fixing, and TDD-first validation of rendering, UI, movement, interactions, combat, animation, loading, cutscenes, companions, and performance.
metadata:
  short-description: Gameplay QA, video debug, autopilot, and TDD fixes
---

# Ultimate Game QA

Use this skill to turn gameplay recordings and automated runs into verified bugs, failing tests, concrete fixes, and repeatable validation.

Core principle:

- Analysis without fixing is failure.
- Fix without a failing test first is invalid.
- If logs say success but visuals, physics, animation, or world state disagree, the system is broken.

Use this skill when:

- reviewing `.mp4` gameplay recordings
- debugging non-web game scenarios
- validating bot or autopilot runs
- checking routes, interactions, menus, transitions, cutscenes, or loading screens
- verifying combat, magic, equipment, particles, or animations
- enforcing TDD for gameplay regressions
- validating render/performance work such as batching, instancing, LOD, HLOD, visibility, and impostors

Do not use this skill for report-only work. The expected flow is evidence -> diagnosis -> failing test -> minimal fix -> recheck.

## Validation Philosophy

Always validate across the layers that matter to the action:

- Internal truth: logic, flags, state, cooldowns, timers, metrics
- Visual truth: what is actually visible in frames
- Physical truth: position, collision, passability, motion, hit results
- Animation truth: correct pose, progression, timing, and completion
- Effect truth: particles, VFX, SFX, prompts, UI confirmation

If any required layer disagrees with the claimed result, classify that as a bug.

## Primary Workflow

1. Gather evidence.
   Prefer the latest gameplay video, `.metadata.json`, screenshots, and `logs/game.log`.
2. Generate or inspect visual proof.
   Use screenshots for all major segments. Never debug from logs alone.
3. Interpret findings.
   Classify by severity and subsystem.
4. Pick the top issue.
   Choose the highest-severity validated bug, or the most representative medium issue if there are no blockers.
5. Write the failing test first.
   Verify that the test fails for the correct reason.
6. Implement the smallest fix that proves the hypothesis.
7. Re-run focused tests.
8. Re-run the relevant gameplay scenario when the change touches runtime behavior.
9. Confirm the fix visually, not just by logs.
10. Refactor only while staying green.

## Required Output Artifacts

For video-debug work, prefer generating or preserving:

- `.debug.json`
- `.debug.md`
- targeted screenshots for important segments
- scenario metadata
- relevant session log excerpts

If the repo already has an analyzer, use it. If it does not, still preserve the same evidence structure.

## Smart Autopilot

Gameplay QA must support a smart autopilot. It is not a blind macro runner.

The autopilot must be able to:

- follow defined routes through locations
- move to world targets
- rotate or aim toward targets
- recover if stuck
- open and close menus
- scroll, switch tabs, and press buttons
- navigate settings, inventory, map, journal, and skill tree
- approach and interact with doors, books, chests, portals, obstacles, NPCs, mounts, and teleporters
- handle dialogue and dialogue progression
- swim
- fly
- mount and dismount
- transition between locations
- validate full locomotion and animation coverage

### Autopilot Step Contract

Each step must define:

- preconditions
- action
- expected result
- validation
- timeout
- retry or recovery policy
- explicit failure criteria

Supported step types should include at minimum:

- `move_to`
- `move_route`
- `rotate_to`
- `aim_at`
- `interact`
- `interact_until`
- `open_menu`
- `close_menu`
- `click_button`
- `scroll_menu`
- `select_entry`
- `talk_to_npc`
- `advance_dialogue`
- `mount`
- `dismount`
- `swim_to`
- `fly_to`
- `teleport`
- `transition_location`
- `wait_for_state`
- `wait_for_animation`
- `assert_state`
- `assert_visible`
- `assert_distance`
- `assert_ui`
- `assert_animation`
- `assert_route_progress`

### Autopilot Recovery Rules

If the run gets stuck or desynced, the autopilot should try bounded recovery before failing:

- stop movement
- step back
- re-align camera
- reacquire target
- reopen menu
- retrigger interaction
- repath to target
- retry from the last valid checkpoint

All recovery attempts must be logged. If recovery fails, preserve visual proof and mark the run failed.

### Route Rules

A route is only valid if:

- the player actually moved through world space
- checkpoints were reached in order
- route progress is measurable
- distance to intended checkpoints decreased appropriately
- no meaningful checkpoint was silently skipped
- movement was not replaced by teleport unless teleport was the intended action

## Mandatory System Validation

### Animation Validation

Every meaningful action must validate animation truth:

- correct animation triggered
- visible pose or motion changed appropriately
- timing is plausible
- progression reached the intended marker or completion point
- no wrong clip was substituted
- no interrupted or silent failure was accepted as success

At minimum validate:

- idle
- walk
- run
- sprint
- strafe
- turn
- jump
- fall
- land
- roll or dodge
- stealth locomotion
- interact
- door open
- chest open
- book read
- talk start, loop, and end
- swim enter, loop, and exit
- flight start, hover, glide, fast flight, and landing
- mount, mounted idle, mounted move, and dismount
- teleport start, transition, and end
- hit reacts where applicable

### Movement And Traversal Validation

Validate:

- forward, backward, left, right
- diagonals
- locomotion starts and stops
- turn-in-place
- run transitions
- jump and landing transitions
- stealth motion
- roll or dodge
- climbing, vaulting, wall interactions if supported
- swim
- flight
- mount traversal
- door and obstacle passability

### Interaction Validation

For doors, books, chests, NPCs, and interactables, success is valid only if:

- the prompt or eligible interaction state existed
- the action triggered
- the correct animation played when required
- the object or world state changed correctly
- the result remained consistent after the interaction

### UI Validation

Menus are not valid just because they opened.

Validate:

- inventory
- map
- skill tree
- journal
- pause
- settings
- save or load surfaces if present

For UI, verify:

- focus is correct
- navigation works
- tabs switch correctly
- scrolling works
- closing restores gameplay control
- screens do not overlap incorrectly
- claimed button presses result in real visible change

### Combat Validation

Validate the full chain:

- input
- animation
- effect or trail
- hit timing
- hit detection
- damage or gameplay result
- visual confirmation

#### Melee

Validate:

- sword attacks
- directional attacks
- combo chains from different sides
- shield interactions
- block and block reactions
- roll or dodge into combat
- hit only on valid frames
- no phantom damage

#### Ranged

Validate:

- bow draw
- release timing
- projectile spawn position
- projectile direction
- trajectory plausibility
- hit detection

#### Magic

Validate:

- cast animation
- cast timing
- effect location
- target or world result
- cooldown or resource rules if the game uses them
- no invisible or fake spell success

#### Equipment

Validate:

- clothing or armor visual swap
- equipped weapon visuals
- shield visuals
- no missing mesh or material
- no unacceptable clipping
- correct deformation during animation
- no placeholder fallback presented as a real result

#### Particles And Effects

Validate:

- spawn timing
- spawn position and orientation
- lifetime
- cleanup
- sync with the triggering animation or event
- no silent failure
- no runaway overdraw or obvious performance spike

### Companion Validation

If the game has companions or a pet, validate:

- following behavior
- navigation and unstuck behavior
- animation state
- combat participation if intended
- location transitions
- no desync or disappearance after transitions

### Cutscene Validation

Validate:

- trigger condition
- camera behavior
- involved character animations
- dialogue timing if present
- clean exit back to gameplay
- no stuck control state

### Loading Validation

Validate:

- no infinite loading
- scene fully initializes before reveal
- no missing assets during or after reveal
- correct transition state before gameplay resumes
- loading screens do not claim readiness too early

### Input Consistency Validation

Validate:

- button hold behavior
- double-click or double-input timing
- rapid input switching
- input buffering
- input during loading
- input during cutscenes
- input restoration after modal screens

If the same input produces inconsistent results under the same conditions, classify that as `input_bug`.

### State Persistence Validation

Validate state continuity across:

- save and load
- death and respawn
- teleport
- location transition

Compare intended persistent state before and after:

- position if applicable
- stats
- equipment
- active effects
- animation or movement mode when relevant
- UI state if intended

### Edge-Case Mode

Include stress scenarios such as:

- rapid button spam
- interrupted actions
- overlapping inputs
- rapid state switching
- interaction spam
- UI spam

If the system enters an invalid state, loses input, or desyncs state and animation, classify that as `edge_case_bug`.

## Bug Classification

Use clear, specific labels such as:

- `visual_desync`
- `physics_desync`
- `false_positive_state`
- `animation_bug`
- `ui_bug`
- `distance_error`
- `route_bug`
- `interaction_bug`
- `transition_bug`
- `menu_navigation_bug`
- `combat_bug`
- `melee_desync`
- `ranged_desync`
- `magic_bug`
- `projectile_bug`
- `equipment_bug`
- `particle_bug`
- `companion_bug`
- `cutscene_bug`
- `loading_bug`
- `input_bug`
- `persistence_bug`
- `edge_case_bug`
- `performance_issue`

## TDD Contract

Iron law:

- No production fix without a failing test first.

Required cycle:

- RED
- GREEN
- REFACTOR

RED:

- write one minimal failing test for the validated bug
- use a real behavior contract, not a fake placeholder
- verify that it fails for the correct reason

GREEN:

- implement the smallest safe fix
- do not bundle speculative features
- rerun the focused tests

REFACTOR:

- clean structure only while preserving green behavior
- remove temporary diagnostics that are no longer needed

If a gameplay fix cannot be cleanly unit-tested, add the tightest focused test possible and require a scenario re-run.

## Performance And Render Validation

Every serious gameplay run should track, when available:

- FPS
- frame time
- draw calls
- triangles
- instance counts
- LOD distribution

Performance must be checked during:

- walking routes
- interaction-heavy scenarios
- menu traversal
- combat
- transition-heavy runs
- swim, flight, and mount paths

A scene that is only healthy while standing still is not healthy.

### Optimization Order

When performance work is required, prioritize in this order:

1. material cleanup
2. instancing for repeated objects
3. LOD
4. static batching
5. HLOD
6. impostors

Visibility systems should account for:

- frustum culling
- distance culling
- optional occlusion

Do not fake LOD or instancing results with random local patches. If the architecture is missing, introduce the minimal architecture layer first.

## Debug Overlay And Replay Expectations

When a debug overlay exists, it should expose the truth needed for diagnosis:

- FPS
- draw calls
- current step
- route progress
- target
- distance
- current animation
- current state
- interaction state
- UI stack

When replay support exists, preserve actions and route progression well enough to reproduce the bug.

## Anti-Patterns

Forbidden:

- analysis without fix
- fix without test
- tests written only after code
- trusting logs over visuals
- skipping screenshots
- skipping performance checks when the issue is performance-related
- blind macro playback without conditions
- claiming an interaction worked without route, distance, and world confirmation
- claiming a menu works without navigating it
- claiming locomotion works without validating transitions
- claiming a transition works without validating pre-state and post-state

## Completion Criteria

Do not call the issue fixed unless all relevant checks pass:

- failing test written first
- failing test verified red
- minimal fix implemented
- tests verified green
- visual result confirmed
- physical or world result confirmed
- required animation confirmed
- required effect confirmed
- route, interaction, or transition confirmed
- performance checked when relevant

Final rule:

- If you did not see it, test it, break it, fix it, and verify it, it is not fixed.
