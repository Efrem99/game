# Story Bible v0.1

Updated: 2026-03-06
Scope: working canon for current prototype and narrative-aligned gameplay systems.

## 1. Canon Anchor

- Main playable story starts from Sherward.
- Entry point is a pre-game memory cutscene in the morning.
- The key opening beat is Sherward's argument with his father Sebastian.
- Full player control starts after this opening recollection.

## 2. Priority Narrative Lines

- Adalin is a mandatory primary line in the main arc.
- Darius is a knowledge-bearing guide figure and historical witness.
- Krimora is a high-impact source of corruption, long-range consequence, and political-spiritual pressure.
- Sebastian is both ruler and father figure, so his choices shape both state and family conflict.

## 3. World Thesis

- Core axis is Light vs Darkness, expressed as choice and moral agency, not raw power alone.
- Historical collapses are tied to curiosity without ethical limits.
- Personal relationships and political decisions are both used to escalate world-scale fallout.

## 4. Structure Snapshot

- Opening: Sherward morning memory (argument with father).
- Early progression: immediate personal tension, court pressure, and instability signals.
- Context layer: Darius/Krimora backstory explains how current crisis became possible.
- Ongoing arc: civil strain, trust fractures, shifting alliances, and social cost visible through daily life.

## 5. Non-Negotiables

- Do not replace the opening memory with any other scene.
- Do not downgrade Adalin to background flavor.
- Do not move Darius/Krimora context ahead of the Sherward opening beat.
- Keep lore and gameplay-facing codex entries aligned with this document.

## 6. Current Engine Hooks

- Cutscene trigger event: `opening_memory_started`
- Canon trigger id: `opening_memory_sherward_morning`
- Runtime codex event token: `opening_memory_sherward_morning`
- Static codex section source: `data/journal_entries.json` ("Opening Canon")

