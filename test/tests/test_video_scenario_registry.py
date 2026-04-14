import json
import unittest
from pathlib import Path

import launcher_test_hub as hub


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_REGISTRY = ROOT / "tests" / "video_scenarios" / "scenarios.json"


class VideoScenarioRegistryTests(unittest.TestCase):
    def test_game_scenarios_use_runtime_test_launcher_keys(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        self.assertIsInstance(scenarios, dict)
        self.assertGreaterEqual(len(scenarios), 6)

        runtime_keys = set(hub.RUNTIME_TESTS.keys())
        for name, row in scenarios.items():
            self.assertIsInstance(row, dict, msg=f"{name} must be object")
            self.assertEqual("game", str(row.get("kind", "")).strip().lower())
            launcher_test = str(row.get("launcher_test", "")).strip().lower()
            self.assertIn(launcher_test, runtime_keys, msg=f"{name} launcher_test must be runtime key")
            self.assertTrue(
                str(row.get("window_title", "")).strip(),
                msg=f"{name} must define window_title for window-only capture",
            )
            self.assertTrue(
                bool(row.get("capture_audio", False)),
                msg=f"{name} must enable capture_audio",
            )
            self.assertEqual(
                "loopback",
                str(row.get("audio_mode", "")).strip().lower(),
                msg=f"{name} must use loopback audio_mode for game-audio capture",
            )
            marker = str(row.get("wait_ready_marker", "")).strip()
            self.assertIn(
                "Loading: False",
                marker,
                msg=f"{name} wait_ready_marker must require fully loaded world",
            )

    def test_game_scenarios_define_video_bot_env(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        plan_tokens = set()
        for name, row in scenarios.items():
            env = row.get("game_env", {})
            self.assertIsInstance(env, dict, msg=f"{name} game_env must be object")
            self.assertEqual("1", str(env.get("XBOT_VIDEO_BOT", "")).strip(), msg=f"{name} must enable XBOT_VIDEO_BOT")
            self.assertEqual(
                "1",
                str(env.get("XBOT_VIDEO_VISIBILITY_BOOST", "")).strip(),
                msg=f"{name} must enable XBOT_VIDEO_VISIBILITY_BOOST",
            )
            plan = str(env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower()
            self.assertTrue(plan, msg=f"{name} must define XBOT_VIDEO_BOT_PLAN")
            plan_tokens.add(plan)
            self.assertTrue(
                str(env.get("XBOT_TEST_SCENARIO", "")).strip(),
                msg=f"{name} must define XBOT_TEST_SCENARIO",
            )
        for required in {
            "ground",
            "parkour",
            "swim",
            "flight",
            "excursion",
            "ui_inventory",
            "ui_pause",
            "storm_quake",
            "quake_escape",
            "stealth_climb",
            "showcase_extended",
            "arena_boss_probe",
            "combat_magic_probe",
            "caves_visual_probe",
            "environment_visual_probe",
            "world_story_showcase",
            "location_dialogue_probe",
            "all_locations_grand_tour",
            "ultimate_sandbox_probe",
            "anim_melee_core",
            "anim_combo_chain",
            "anim_weapon_modes",
            "anim_defense_stealth",
            "anim_locomotion_transitions",
            "anim_enemy_visibility_aggro",
            "anim_camera_variation",
            "hud_combat_feedback",
            "perf_animation_stability",
        }:
            self.assertIn(required, plan_tokens)

    def test_registry_contains_new_mobility_and_catastrophe_scenarios(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        self.assertIn("ultimate-sandbox-collider-probe", scenarios)
        self.assertIn("loc-parkour-minimalist-lane", scenarios)
        self.assertIn("loc-stealth-climb-course", scenarios)
        self.assertIn("loc-catastrophe-earthquake-escape", scenarios)
        self.assertIn("loc-showcase-extended-marathon", scenarios)
        self.assertIn("loc-combat-marathon-arena", scenarios)
        self.assertIn("loc-arena-boss-healthbar", scenarios)
        self.assertIn("loc-world-story-cinematic", scenarios)
        self.assertIn("loc-dragon-boss-marathon", scenarios)
        self.assertIn("loc-castle-interior-debug", scenarios)
        self.assertIn("loc-krimora-forest-debug", scenarios)
        self.assertIn("loc-dwarven-caves-debug", scenarios)
        self.assertIn("loc-environment-sky-trees-water", scenarios)
        self.assertIn("loc-all-locations-dialogue-check", scenarios)
        self.assertIn("loc-all-locations-grand-tour", scenarios)
        self.assertIn("loc-anim-melee-core", scenarios)
        self.assertIn("loc-anim-combo-chain", scenarios)
        self.assertIn("loc-anim-weapon-modes", scenarios)
        self.assertIn("loc-anim-defense-stealth", scenarios)
        self.assertIn("loc-anim-locomotion-transitions", scenarios)
        self.assertIn("loc-anim-enemy-aggro-visibility", scenarios)
        self.assertIn("loc-anim-camera-variation", scenarios)
        self.assertIn("loc-hud-combat-feedback", scenarios)
        self.assertIn("loc-perf-animation-stability", scenarios)

    def test_registry_keeps_dedicated_dragon_runtime_scenario(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        self.assertTrue(
            any(str(row.get("launcher_test", "")).strip().lower() == "dragon" for row in scenarios.values() if isinstance(row, dict))
        )

    def test_registry_exposes_castle_interior_as_direct_launch_location(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        row = scenarios.get("loc-castle-interior-debug", {})
        self.assertIsInstance(row, dict)
        self.assertEqual("movement", str(row.get("launcher_test", "")).strip().lower())
        self.assertEqual("castle_interior", str(row.get("launcher_location", "")).strip().lower())
        env = row.get("game_env", {}) if isinstance(row, dict) else {}
        self.assertEqual("combat_magic_probe", str(env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())

    def test_registry_exposes_krimora_and_dwarven_debug_locations(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        krimora = scenarios.get("loc-krimora-forest-debug", {})
        dwarven = scenarios.get("loc-dwarven-caves-debug", {})
        self.assertIsInstance(krimora, dict)
        self.assertIsInstance(dwarven, dict)
        self.assertEqual("krimora_forest", str(krimora.get("launcher_location", "")).strip().lower())
        self.assertEqual("dwarven_caves", str(dwarven.get("launcher_location", "")).strip().lower())
        krimora_env = krimora.get("game_env", {}) if isinstance(krimora, dict) else {}
        dwarven_env = dwarven.get("game_env", {}) if isinstance(dwarven, dict) else {}
        self.assertEqual("combat_magic_probe", str(krimora_env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())
        self.assertEqual("caves_visual_probe", str(dwarven_env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())

    def test_registry_marks_combat_and_stealth_runs_with_force_aggro(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        for key in {
            "loc-combat-marathon-arena",
            "loc-dragon-boss-marathon",
            "loc-arena-boss-healthbar",
            "loc-castle-interior-debug",
            "loc-krimora-forest-debug",
            "loc-stealth-climb-course",
            "loc-stealth-crouch-run",
        }:
            row = scenarios.get(key, {})
            self.assertIsInstance(row, dict, msg=f"{key} must exist")
            env = row.get("game_env", {}) if isinstance(row, dict) else {}
            self.assertEqual("1", str(env.get("XBOT_FORCE_AGGRO_MOBS", "")).strip(), msg=f"{key} must force aggro")

    def test_registry_exposes_environment_probe_scenario(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        row = scenarios.get("loc-environment-sky-trees-water", {})
        self.assertIsInstance(row, dict)
        self.assertEqual("krimora_forest", str(row.get("launcher_location", "")).strip().lower())
        env = row.get("game_env", {}) if isinstance(row, dict) else {}
        self.assertEqual("environment_visual_probe", str(env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())

    def test_registry_marks_grand_location_tour_as_non_blocking_for_book_conformance(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        row = scenarios.get("loc-all-locations-grand-tour", {})
        self.assertIsInstance(row, dict)
        self.assertEqual("town", str(row.get("launcher_location", "")).strip().lower())
        self.assertTrue(bool(row.get("skip_book_conformance", False)))
        env = row.get("game_env", {}) if isinstance(row, dict) else {}
        self.assertEqual("all_locations_grand_tour", str(env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())

    def test_registry_keeps_dialogue_scenarios_in_clean_room_mode(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})

        npc_tour = scenarios.get("loc-dialogue-npc-tour", {})
        self.assertIsInstance(npc_tour, dict)
        self.assertEqual("castle_interior", str(npc_tour.get("launcher_location", "")).strip().lower())
        self.assertLessEqual(float(npc_tour.get("duration_sec", 0.0) or 0.0), 24.0)
        npc_env = npc_tour.get("game_env", {}) if isinstance(npc_tour, dict) else {}
        self.assertEqual("dialogue", str(npc_env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())
        self.assertEqual("1", str(npc_env.get("XBOT_DEBUG_DISABLE_CUTSCENE_TRIGGERS", "")).strip())
        self.assertEqual("1", str(npc_env.get("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO", "")).strip())
        self.assertEqual("1", str(npc_env.get("XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES", "")).strip())
        self.assertEqual("1", str(npc_env.get("XBOT_DEBUG_SKIP_RUNTIME_ENEMY_ROSTER", "")).strip())
        self.assertNotEqual("1", str(npc_env.get("XBOT_DEBUG_SKIP_RUNTIME_NPC_SPAWNS", "")).strip())
        self.assertNotEqual("1", str(npc_env.get("XBOT_FORCE_AGGRO_MOBS", "")).strip())

        dialogue_probe = scenarios.get("loc-all-locations-dialogue-check", {})
        self.assertIsInstance(dialogue_probe, dict)
        self.assertEqual("castle_interior", str(dialogue_probe.get("launcher_location", "")).strip().lower())
        self.assertLessEqual(float(dialogue_probe.get("duration_sec", 0.0) or 0.0), 40.0)
        probe_env = dialogue_probe.get("game_env", {}) if isinstance(dialogue_probe, dict) else {}
        self.assertEqual("location_dialogue_probe", str(probe_env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())
        self.assertEqual("1", str(probe_env.get("XBOT_DEBUG_DISABLE_CUTSCENE_TRIGGERS", "")).strip())
        self.assertEqual("1", str(probe_env.get("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO", "")).strip())
        self.assertEqual("1", str(probe_env.get("XBOT_DEBUG_DISABLE_CAMERA_CONTEXT_RULES", "")).strip())
        self.assertEqual("1", str(probe_env.get("XBOT_DEBUG_SKIP_RUNTIME_ENEMY_ROSTER", "")).strip())
        self.assertNotEqual("1", str(probe_env.get("XBOT_DEBUG_SKIP_RUNTIME_NPC_SPAWNS", "")).strip())

    def test_animation_smoke_scenarios_run_in_clean_room_mode(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})

        weapon = scenarios.get("loc-anim-weapon-modes", {})
        self.assertIsInstance(weapon, dict)
        self.assertEqual("movement", str(weapon.get("launcher_test", "")).strip().lower())
        self.assertEqual("castle_interior", str(weapon.get("launcher_location", "")).strip().lower())
        weapon_env = weapon.get("game_env", {}) if isinstance(weapon, dict) else {}
        self.assertEqual("movement_04", str(weapon_env.get("XBOT_TEST_SCENARIO", "")).strip())
        self.assertEqual("1", str(weapon_env.get("XBOT_DEBUG_DISABLE_CUTSCENE_TRIGGERS", "")).strip())
        self.assertEqual("1", str(weapon_env.get("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO", "")).strip())
        self.assertEqual("1", str(weapon_env.get("XBOT_DEBUG_SKIP_RUNTIME_ROSTER_SPAWNS", "")).strip())
        self.assertNotEqual("1", str(weapon_env.get("XBOT_FORCE_AGGRO_MOBS", "")).strip())

        locomotion = scenarios.get("loc-anim-locomotion-transitions", {})
        self.assertIsInstance(locomotion, dict)
        locomotion_env = locomotion.get("game_env", {}) if isinstance(locomotion, dict) else {}
        self.assertEqual("1", str(locomotion_env.get("XBOT_DEBUG_DISABLE_CUTSCENE_TRIGGERS", "")).strip())
        self.assertEqual("1", str(locomotion_env.get("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO", "")).strip())
        self.assertEqual("1", str(locomotion_env.get("XBOT_DEBUG_SKIP_RUNTIME_ROSTER_SPAWNS", "")).strip())

        defense = scenarios.get("loc-anim-defense-stealth", {})
        self.assertIsInstance(defense, dict)
        self.assertEqual("stealth_climb", str(defense.get("launcher_test", "")).strip().lower())
        defense_env = defense.get("game_env", {}) if isinstance(defense, dict) else {}
        self.assertEqual("anim_defense_stealth", str(defense_env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())
        self.assertEqual("1", str(defense_env.get("XBOT_FORCE_AGGRO_MOBS", "")).strip())
        self.assertEqual("1", str(defense_env.get("XBOT_DEBUG_DISABLE_CUTSCENE_TRIGGERS", "")).strip())
        self.assertEqual("1", str(defense_env.get("XBOT_DEBUG_DISABLE_AUTO_BOSS_INTRO", "")).strip())
        self.assertEqual("1", str(defense_env.get("XBOT_DEBUG_SKIP_RUNTIME_ROSTER_SPAWNS", "")).strip())

    def test_ultimate_sandbox_probe_scenarios_do_not_loop_video_bot_plan(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        for key in {"ultimate-sandbox-mechanics", "ultimate-sandbox-collider-probe"}:
            row = scenarios.get(key, {})
            self.assertIsInstance(row, dict, msg=f"{key} must exist")
            env = row.get("game_env", {}) if isinstance(row, dict) else {}
            self.assertEqual("ultimate_sandbox_probe", str(env.get("XBOT_VIDEO_BOT_PLAN", "")).strip().lower())
            self.assertEqual("0", str(env.get("XBOT_VIDEO_BOT_LOOP_PLAN", "")).strip(), msg=f"{key} must disable bot plan loop")

    def test_ultimate_sandbox_collider_probe_declares_context_and_verdict_rules(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        row = scenarios.get("ultimate-sandbox-collider-probe", {})
        self.assertIsInstance(row, dict)
        env = row.get("game_env", {}) if isinstance(row, dict) else {}
        self.assertIsInstance(env, dict)
        context_rules = json.loads(str(env.get("XBOT_VIDEO_BOT_CONTEXT_RULES", "")).strip())
        success_if = json.loads(str(env.get("XBOT_VIDEO_BOT_SUCCESS_IF", "")).strip())
        fail_if = json.loads(str(env.get("XBOT_VIDEO_BOT_FAIL_IF", "")).strip())
        self.assertIsInstance(context_rules, list)
        self.assertTrue(any(str(rule.get("id", "")).strip().lower() == "sandbox_story_focus" for rule in context_rules))
        self.assertIsInstance(success_if, dict)
        self.assertIsInstance(fail_if, dict)

    def test_ultimate_sandbox_collider_probe_enables_runtime_trace(self):
        payload = json.loads(SCENARIO_REGISTRY.read_text(encoding="utf-8-sig"))
        scenarios = payload.get("scenarios", {})
        row = scenarios.get("ultimate-sandbox-collider-probe", {})
        self.assertIsInstance(row, dict)
        env = row.get("game_env", {}) if isinstance(row, dict) else {}
        self.assertIsInstance(env, dict)
        self.assertEqual("1", str(env.get("XBOT_VIDEO_BOT_TRACE", "")).strip())


if __name__ == "__main__":
    unittest.main()
