# King Wizard Agent Rules

Read this file first before changing gameplay, rendering, animation, camera, UI, locations, NPCs, or test automation.
For detailed checklist, commands, and scenario map, read `docs/AGENT_GAMEPLAY_PLAYBOOK.md`.

## Read Order

- Read `AGENTS.md` first.
- Read `docs/AGENT_GAMEPLAY_PLAYBOOK.md` before deeper gameplay or rendering work.
- Inspect latest `logs/game.log` and latest video-run `.metadata.json` before proposing fixes.

## Game Test Policy

- Use video capture for gameplay-related tests.
- Prefer `test/tests/video_scenarios/run_game_tests_with_video.ps1`.
- Run by scenario name or `-Scenario all`.
- Launch real game process and record that session.
- Do not use `pytest` as primary verification for gameplay regressions.
- Store artifacts in `output/non-web-mechanics-review`.

## Non-Game Test Policy

- Use normal test commands such as `pytest`.
- Keep tests focused and fast.

## Optimization And Indexing Rule

- Think before acting. Read existing files before writing code.
- Do not modify code unless the full data flow is understood.
- Be concise in output but thorough in reasoning.
- Keep solutions simple and direct.
- Prefer editing over rewriting whole files.
- Do not re-read files unless they may have changed.
- Test code before declaring done.

- Do not introduce parallel systems or duplicate sources of truth.
- One system = one responsibility unless tightly related in the same data flow.

- Avoid overhead in hot paths (per-frame, per-entity logic).

- Index and search only what is needed for the task.
- Prefer targeted `rg` queries over broad scans.
- Do not bulk-scan the repository by default.
- Avoid scanning `assets_raw`, `output`, `cache`, `build`, `build-cpp`, `tools` unless necessary.
- Reuse existing logs and artifacts before generating new scans.
- Start debugging from the affected subsystem, not the whole project.

- User instructions always override this file.

## Token Efficiency Rule

- Minimize unnecessary file reads and repeated context loading.
- Avoid scanning large directories unless directly required.
- Prefer narrow, targeted queries over wide exploration.
- Reuse already gathered context instead of reloading it.
- Do not generate large outputs unless explicitly needed.
- Avoid repeating explanations or re-analyzing unchanged data.
- Focus only on files relevant to the current bug or feature.
- Treat token usage as a limited resource and optimize for precision.

## Documentation Hygiene

- Do not create one-off Markdown files in project root.
- Keep canonical docs in `README.md`, `AGENTS.md`, `docs/`, or `data/`.
- Put temporary output in `output/` or `tmp/`.
- Merge duplicate documentation instead of creating new files.

## TODO Checklist Rule

- Do not mark TODO as done until verified.
- Do not rely on assumptions.
- Verify via scenarios, logs, or real behavior.
- Leave unchecked if verification is incomplete.

## Change Scope Rule

- Prefer minimal, surgical changes.
- Do not modify unrelated files.
- Fix one root cause at a time.
- Do not bundle refactors into bug fixes.
- Read minimum required context.

## Compiled Core First

- Do not assume Python-only runtime.
- Ensure `game_core.pyd` exists and is up to date.
- Build via `python scripts/build_game_core.py` if needed.
- Confirm log: `Successfully loaded game_core.pyd`.
- Do not silently fallback to Python runtime.

## game_core Import Rule

- Do not import `game_core` directly in Panda-heavy modules.
- Use `src/utils/core_runtime.py` (`gc`, `HAS_CORE`).
- Prevent crash due to import order.

## Windows Path Rule

- Use `C:\xampp\htdocs\king-wizard`.
- Do not resolve junction to Cyrillic path.
- Preserve ASCII path for build tools.

## Animation And Model Safety

- Do not disable animation to fix T-pose.
- Prefer stable XBot fallback over unsafe Sherward forcing.
- Use explicit env flags for experiments.

## Debug Mode Rule

- "Nothing happens" = critical failure.
- Missing visuals or interactions = blocking issue.
- Prefer diagnostics before behavior changes.
- Do not apply auto-fixes during debugging.
- Avoid refactors until root cause is confirmed.

## Camera And Transform Safety

- Treat `has_mat()` as transform corruption.
- Inspect logs before assuming capture issues.
- Validate NodePaths, transforms, animation data.
- Avoid global scene mutations during debugging.

Check logs for:
- `FATAL ERROR`
- `has_mat()`
- `Playback failed`
- `Camera transform commit failed`
- `Detached invalid node`

## Visual Regression Safety

- "Launches" is not enough.
- Verify visuals via video run.
- Missing terrain, player, sky, UI = critical failure.
- Preserve HUD and interactions during debugging.

## Fallback Policy

- No silent fallbacks.
- Fallbacks must log original issue.
- Must be reversible.
- Persistent fallback = bug.

## Diagnosis First

- Confirm failure mode before changes.
- Prefer logging over guessing.
- Assume system is broken until proven otherwise.

## Logging Rule

- Use human-readable logs.
- Avoid cryptic messages without explanation.

## Sherward Dark Toggle

- Verify normal and shadow modes.
- Check aura spawn/cleanup.
- Avoid partial state leaks.

## Required Verification After Gameplay Changes

- Run relevant video scenario.
- Inspect `.metadata.json` and `logs/game.log`.
- Short video = failure.
- Add pytest only for helper logic if needed.

## Startup Checklist

- Confirm project root path.
- Confirm `game_core.pyd` status.
- Confirm log state.
- Identify scenario for subsystem.

## Definition Of Done

- No short video runs.
- No remaining fatal log markers.
- Visuals fully correct.
- Player modes verified.

## Current Known Trap

- `game_core.pyd` may load but rendering still unstable.
- Known crash after `Final Vis - Playing: True, Loading: False` with `has_mat()`.
- Do not claim stability without full scenario pass.

## Agent Workflow

- Identify change type before editing:
  - runtime/build
  - animation/model
  - transform/camera
  - shaders/materials
  - test/scenario

- Make smallest change that proves hypothesis.
- Add regression tests when practical.
- After fix, rerun scenario.

- During debugging:
  - avoid refactors until root cause is confirmed
  - refactor only if it does not interfere with diagnosis

- Always verify new features and changes,
  especially interactions and system boundaries.

- Do not assume behavior works.
- Treat interaction changes as high-risk.

- Validate via logs, scenarios, video runs.
- Fix iteratively until no unexplained errors remain.

- After debugging is complete, clear logs.
