# Agent Gameplay Playbook

Use this file after reading `AGENTS.md`.

## Purpose

- Give agents a stable workflow for game changes.
- Reduce random regressions in visuals, animation, camera, UI, and test automation.
- Keep investigation focused instead of scanning the whole repository.

## Read Order

- `AGENTS.md`
- `docs/AGENT_GAMEPLAY_PLAYBOOK.md`
- latest `logs/game.log`
- latest relevant `output/non-web-mechanics-review/*.metadata.json`

## Focused Search Rule

- Search only the subsystem you are touching first.
- Prefer targeted `rg` commands such as:
- `rg -n "has_mat|SceneValidate|Camera transform" src/app.py src/render tests`
- `rg -n "set_shadow_mode|shadow_mode|shadow_aura" src/entities`
- `rg -n "game_core|HAS_CORE|core_runtime" src scripts tests`
- Do not start with whole-repo scans unless the issue is truly cross-cutting.
- Avoid broad scans of:
- `assets_raw`
- `output`
- `cache`
- `build`
- `build-cpp`
- `tools`
- generated inventory files

## Documentation Hygiene

- Do not leave raw audit Markdown files in project root after a task is done.
- Promote only stable, reusable guidance into `README.md`, `docs/`, or `data/`.
- If an audit is temporary, keep it in `output/` or another artifact folder.
- If an existing canonical doc already covers the topic, update it instead of creating a new parallel Markdown file.

## TODO Checklist Rule

- Do not check off a TODO item until it has been verified in the real system that the task targets.
- Code changed is not the same thing as task completed.
- For gameplay and visual tasks, verify with the relevant video scenario, logs, and observed behavior.
- For non-game tasks, verify with the relevant focused test, command output, or artifact.
- If any verification step is still missing, keep the checkbox open and add a short note about what is still unconfirmed.

## Change Scope Rule

- Prefer minimal, surgical edits.
- Keep a debug fix inside one subsystem whenever possible.
- Do not edit unrelated files as part of a focused runtime fix.
- Do not mix speculative refactors with active regression debugging.
- Read the minimum context needed before editing.

## Startup Checklist

- Confirm working directory is `C:\xampp\htdocs\king-wizard`.
- Check whether `game_core.pyd` exists in project root.
- If missing or stale, run `python scripts/build_game_core.py`.
- Confirm import success with:
- `python - <<'PY'`
- `import game_core`
- `print(game_core.__file__)`
- `PY`
- Confirm the app log contains `Successfully loaded game_core.pyd` before concluding anything about runtime mode.

## Known Good Commands

- Build C++ core:
- `python scripts/build_game_core.py`
- Focused build/runtime tests:
- `python -m pytest tests/test_build_game_core.py tests/test_core_runtime_import_order.py -q`
- Standard gameplay video run:
- `powershell -ExecutionPolicy Bypass -File .\test\tests\video_scenarios\run_game_tests_with_video.ps1 -Scenario ultimate-sandbox-collider-probe -MaxRetries 0`
- Tail the game log:
- `Get-Content logs\game.log -Tail 200`
- Search fatal markers:
- `rg -n "FATAL|has_mat|Playback failed|Detached invalid node|Successfully loaded game_core" logs/game.log`

## Scenario Map

- Use `ultimate-sandbox-collider-probe` for startup, collision, and early gameplay health.
- Use `ultimate-sandbox-mechanics` for broader sandbox behavior.
- Use `world-excursion-tour` for world traversal and general coverage.
- Use `loc-parkour-vault-route` for parkour movement.
- Use `loc-training-swim-route` for swim and water checks.
- Use `loc-coast-flight-route` for flight checks.
- Use `ui-inventory-map-tour` for inventory and map UI.
- Use `ui-pause-menu-tour` for pause UI.
- Use `ui-full-showcase-tour` for broad HUD and UI coverage.
- Use `loc-dialogue-npc-tour` for NPC dialogue and interaction prompts.
- Use `loc-environment-sky-trees-water` for environment visuals.
- Use `loc-all-locations-dialogue-check` for multi-stop dialogue-scene smoke coverage: verified castle dialogue, guard-hub framing at the gate, and the port memory reveal.
- Use `loc-anim-melee-core`, `loc-anim-combo-chain`, `loc-anim-weapon-modes`, and `loc-anim-locomotion-transitions` for animation-specific work.
- Use `loc-hud-combat-feedback` for combat HUD feedback.
- Use `loc-perf-animation-stability` when a change risks animation or performance instability.

## Crash Triage Order

- Read the latest scenario `.metadata.json`.
- Read the latest scenario `.report.md`.
- Read `logs/game.log`.
- Read `logs/video_bot_verdict.json` if verdict rules are in play.
- Only after that, inspect code.

## Debug Mode

- Treat "nothing happens" as a failure signal.
- If the scene renders but expected objects, motion, VFX, UI, or interactions are absent, assume the system is broken.
- During debug, prefer instrumentation and logging over behavioral changes.
- Do not enable broad fallback behavior unless the task explicitly asks for it.
- If a temporary guard or fallback is unavoidable, make it loud, scoped, and removable.

## Failure Signals

The following conditions are critical failures and must not be treated as acceptable temporary states:

- Scene renders but expected objects are missing
- Player exists but is invisible or stuck in T-pose
- Movement input produces no visible result
- Camera moves but the scene does not update correctly
- Only debug geometry, fallback shaders, or black output is visible
- Animations do not play when state changes
- Objects exist but appear in invalid positions
- Interaction prompts, HUD, or core location cues disappear unexpectedly

## Fallback Policy

- Fallbacks are for crash prevention, not for masking bugs.
- Never apply a fallback silently.
- Log the original failure loudly before any fallback path is used.
- Fallback behavior must be reversible.
- If fallback logic persists across frames, treat it as a bug unless the design explicitly requires it.
- Do not let a fallback become the de facto runtime mode without an explicit decision.

## Debug Pipeline

1. Detect
- Identify what is missing, frozen, invisible, invalid, or inactive.
- "Nothing happens" means failure, not success.

2. Log
- Add or inspect logs for inputs, state transitions, object validity, transforms, and animation resolution.
- Do not change behavior yet unless necessary to keep the app observable.

3. Isolate
- Reduce the problem to the smallest reproducible subsystem, location, scenario, or object.
- Disable unrelated noise rather than patching multiple systems.

4. Verify
- Check NodePath validity, finite transforms, actor state, animation clip resolution, visibility state, and relevant config inputs.

5. Fix
- Apply the smallest safe change to the failing subsystem.
- Avoid speculative refactors.

6. Recheck
- Confirm the fix in logs and in behavior.
- Verify that no guard or fallback is hiding the original bug.

7. Cleanup
- Remove temporary diagnostics when they are no longer needed.
- Keep durable diagnostics only when they materially improve future debugging.

## Unsafe Shortcuts

- Do not force Python-only mode as a fake fix.
- Do not globally disable player animation as a fake fix.
- Do not bypass `src/utils/core_runtime.py` for `game_core` imports in Panda-heavy modules.
- Do not replace lexical project paths with `.resolve()` in build helpers or runtime path selection without checking the junction impact.
- Do not declare a fix from a boot-only or menu-only launch.

## Visual Acceptance Checklist

- Sky is visible and not black unless the scenario explicitly demands darkness.
- Ground is not replaced by the black-purple debug grid unless a debug surface is intentional.
- Player is not in T-pose.
- HUD is visible and readable when expected.
- Interaction prompts appear when expected.
- Particle effects show up without obvious leaks or broken cleanup.
- Target location reads correctly in motion, not just from a still frame.

## Sherward Checklist

- Verify Sherward normal mode.
- Verify Sherward dark or shadow mode.
- Verify aura spawn and cleanup when toggling.
- Verify no stale color scale remains after returning to normal mode.

## Current Known Trap

- `game_core.pyd` can now be built and loaded on this machine.
- There is still an unresolved live blocker where gameplay can crash shortly after `Final Vis - Playing: True, Loading: False` with `has_mat()` during render.
- Treat short video captures as failures even if the game window opened and the log reached the ready marker.
