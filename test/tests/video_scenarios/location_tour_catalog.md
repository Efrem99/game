# Video Tour Catalog

This file documents the expanded non-web gameplay video scenarios used by the recorder.

## Routes

| Scenario | Launcher Test | Test Scenario | Bot Plan | Route Focus |
|---|---|---|---|---|
| `ultimate-sandbox-mechanics` | `ultimate_sandbox` | `ultimate_sandbox_01` | `idle` | Full mechanics sandbox spawn for broad launcher/bootstrap verification |
| `ultimate-sandbox-collider-probe` | `ultimate_sandbox` | `ultimate_sandbox_01` | `ultimate_sandbox_probe` | Deterministic sandbox collider pass over stairs, cube lane, wallrun wall, tower, and pool edge |
| `world-excursion-tour` | `movement` | `movement_04` | `excursion` | Town -> Castle -> Docks -> Parkour -> Swim Pool -> Flight Grounds (+ transitions) |
| `loc-town-ground-marathon` | `movement` | `movement_04` | `ground` | Ground mechanics loop in town zone |
| `loc-parkour-vault-route` | `parkour` | `parkour_01` | `parkour` | Parkour route with repeated jump/vault rhythm |
| `loc-training-swim-route` | `movement` | `movement_01` | `swim` | Swim-focused route with water entry and combat actions |
| `loc-coast-flight-route` | `flight` | `flight_01` | `flight` | Flight route with ascent/descent and combat/spell checks |
| `loc-docks-ground-route` | `movement` | `movement_05` | `ground` | Docks traversal and ground mechanics |
| `loc-parkour-excursion-scout` | `parkour` | `parkour_06` | `excursion` | Excursion variant starting from parkour context |
| `ui-inventory-map-tour` | `movement` | `movement_04` | `ui_inventory` | In-game inventory walkthrough: inventory -> map -> skills -> journal |
| `ui-pause-menu-tour` | `movement` | `movement_04` | `ui_pause` | Pause menu walkthrough: settings/load panels + return to gameplay |
| `ui-full-showcase-tour` | `movement` | `movement_04` | `ui_full` | Combined UI + gameplay showcase route |
| `loc-dialogue-npc-tour` | `movement` | `movement_04` | `dialogue` | Clean-room NPC dialogue pass in `castle_interior`: prompt acquisition, subtitle/HUD visibility, and repeated interact beats without combat or parkour noise |
| `loc-loot-chest-run` | `movement` | `movement_01` | `loot_chest` | Chest approach, interact/loot passes in training route |
| `loc-stealth-crouch-run` | `movement` | `movement_04` | `crouch_stealth` | Crouch/stealth route with shield+rune equip, spell cast, and forced mob aggro |
| `loc-storm-quake-survival` | `movement` | `movement_05` | `storm_quake` | Storm weather + quake-style camera impact stress test |
| `loc-wallcrawl-parkour-run` | `parkour` | `parkour_02` | `wallcrawl` | Wallrun/wall-crawl-like parkour route on cube lane |
| `loc-parkour-minimalist-lane` | `parkour` | `parkour_07` | `parkour` | Minimalist parkour route in dedicated clean lane |
| `loc-stealth-climb-course` | `stealth_climb` | `stealth_climb_01` | `stealth_climb` | Dedicated stealth + climb pass with block/heavy/spell animation cadence and forced mob aggro |
| `loc-catastrophe-earthquake-escape` | `stealth_climb` | `catastrophe_02` | `quake_escape` | Earthquake/catastrophe escape route with impact bursts |
| `loc-showcase-extended-marathon` | `mechanics` | `mechanics_01` | `showcase_extended` | Long cinematic mechanics pass: armor swap, shield block, quest/journal, portal jumps, loot, climb, catastrophes, fire magic, damage vignette |
| `loc-combat-marathon-arena` | `dragon` | `dragon_03` | `arena_boss_probe` | Arena-only combat pass with lock-on, shield blocks, melee+magic cadence, and forced boss aggro |
| `loc-world-story-cinematic` | `movement` | `movement_04` | `world_story_showcase` | Story-focused route: dialogue, quests, journal reading, loot, pause/menu checks, portal transitions |
| `loc-dragon-boss-marathon` | `dragon` | `dragon_06` | `arena_boss_probe` | Dedicated boss arena run with persistent lock-on and readable boss HP showcase |
| `loc-arena-boss-healthbar` | `dragon` | `dragon_06` | `arena_boss_probe` | Focused verification pass for boss health bar visibility under real combat |
| `loc-castle-interior-debug` | `movement` | `movement_04` | `combat_magic_probe` | Direct launch into castle interior with armor/shield equip, spell loop, and forced mob aggro |
| `loc-krimora-forest-debug` | `movement` | `movement_05` | `combat_magic_probe` | Krimora forest pass with explicit combat+magic cadence, crouch/jump checks, and forced aggro |
| `loc-dwarven-caves-debug` | `movement` | `movement_05` | `caves_visual_probe` | Dwarven caves visual pass (stone cavern shell + torches), no mandatory combat focus |
| `loc-environment-sky-trees-water` | `movement` | `movement_05` | `environment_visual_probe` | Environment quality pass for sky, trees, trails, docks water, and training pool water readability |
| `loc-all-locations-dialogue-check` | `movement` | `movement_04` | `location_dialogue_probe` | Multi-stop dialogue-scene route: verified castle dialogue in `castle_interior`, guard-hub framing at `dwarven_caves_gate`, and the `port_market_memory` reveal without combat or parkour noise |
| `loc-all-locations-grand-tour` | `movement` | `movement_04` | `all_locations_grand_tour` | Grand world tour across all current location clusters: town, castle, port, training, forest, Kremor, and dwarven halls, with walking inside clusters and teleports only between far sectors |

## Notes

- All scenarios are defined in `tests/video_scenarios/scenarios.json`.
- Test-launcher runtime entry is `launcher_test_hub.py --test ...` (not `main.py`).
- Video bot plans are defined in `src/utils/video_bot_plan.py`.
- Scenarios are configured to capture only game window `King Wizard` with audio enabled in `loopback` mode.
- Readiness marker now waits for full world load: `Final Vis - Playing: True, Loading: False`.

