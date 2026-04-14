---
name: task-context-skill
description: >
  King Wizard agent workflow: canonical repo root, read AGENTS and playbook before gameplay changes,
  inspect logs and video-run metadata, verify with run_game_tests_with_video.ps1, build core via
  scripts/build_game_core.py, import game_core only through src/utils/core_runtime.py. Also defines
  how to create or extend Codex skills without duplicates (dedup, init_skill, quick_validate, mirror).
---

# Task Context Skill

## Canonical project root

Use ASCII path only: `C:\xampp\htdocs\king-wizard`. Do not rely on resolving the Cyrillic junction for tools or instructions.

## Before gameplay, rendering, animation, camera, UI, locations, NPCs, or test automation

1. Read `AGENTS.md` at repo root.
2. Read `docs/AGENT_GAMEPLAY_PLAYBOOK.md` for checklist, commands, scenario map.
3. Read latest `logs/game.log` and the newest `*.metadata.json` under `output/non-web-mechanics-review` (for video runs).

## Gameplay verification

- Primary: `test/tests/video_scenarios/run_game_tests_with_video.ps1` — by scenario name or `-Scenario all`.
- Store review artifacts under `output/non-web-mechanics-review`.
- Do not use `pytest` as the primary proof for gameplay regressions (pytest is for non-game or helper logic).

## Compiled core

- Build: `python scripts/build_game_core.py` from repo root.
- Confirm log line that `game_core.pyd` loaded successfully.
- Import `game_core` only via `src/utils/core_runtime.py` (do not import `game_core` directly in Panda-heavy modules).

## Creating or extending other Codex skills (no duplication)

1. Search for overlap: `%USERPROFILE%\.codex\skills` and `C:\xampp\htdocs\king-wizard\.codex\skills` (grep or open `SKILL.md` files). If the same workflow exists, extend that skill instead of adding a parallel folder.
2. New skill only if scope is distinct: run  
   `python "%USERPROFILE%\.codex\skills\.system\skill-creator\scripts\init_skill.py" name-kebab --path "%USERPROFILE%\.codex\skills"`  
   then edit `SKILL.md` and `agents/openai.yaml`.
3. Validate:  
   `python "%USERPROFILE%\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "%USERPROFILE%\.codex\skills\name-kebab"`
4. Mirror into the repo when the skill should live with the project: copy the skill directory to `C:\xampp\htdocs\king-wizard\.codex\skills\name-kebab\`.
5. Do not add new helper modules unless multiple skills will reuse them.

## Trigger phrases (for discovery)

- task-context-skill, King Wizard QA pipeline, run_game_tests_with_video, build_game_core, core_runtime game_core
- AGENTS.md playbook game.log metadata, non-web-mechanics-review
- init_skill, quick_validate, mirror .codex/skills, dedup skills

## Agent reply format when this skill was used to author or update a skill

Respond with: skill name (kebab-case), full path to the skill folder, trigger phrases for the YAML description, and whether the outcome was created new or extended existing.
