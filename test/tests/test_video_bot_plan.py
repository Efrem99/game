import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.video_bot_plan import (
    build_video_bot_events,
    parse_video_bot_plan_json,
    parse_video_bot_events_json,
    resolve_action_binding,
    resolve_video_bot_plan_name,
)


class VideoBotPlanTests(unittest.TestCase):
    def _location_changes_inside_force_aggro_windows(self, events):
        violations = []
        combat_until = -1.0
        for row in events:
            try:
                at = float(row.get("at", 0.0) or 0.0)
            except Exception:
                at = 0.0
            if row.get("type") == "force_aggro":
                try:
                    duration = max(0.0, float(row.get("duration", 0.0) or 0.0))
                except Exception:
                    duration = 0.0
                combat_until = max(combat_until, at + duration)
                continue
            if row.get("type") not in {"teleport", "transition_next"}:
                continue
            if at <= 1e-6:
                continue
            if at + 1e-6 < combat_until:
                violations.append((at, row.get("type"), row.get("target", "")))
        return violations

    def _has_overlapping_hold_pair(self, events, first_action, second_action):
        windows_a = []
        windows_b = []
        for row in events:
            if row.get("type") != "hold":
                continue
            action = str(row.get("action", "") or "").strip().lower()
            try:
                start = float(row.get("at", 0.0) or 0.0)
            except Exception:
                start = 0.0
            try:
                duration = max(0.0, float(row.get("duration", 0.0) or 0.0))
            except Exception:
                duration = 0.0
            end = start + duration
            if action == first_action:
                windows_a.append((start, end))
            elif action == second_action:
                windows_b.append((start, end))
        for start_a, end_a in windows_a:
            for start_b, end_b in windows_b:
                if max(start_a, start_b) < min(end_a, end_b):
                    return True
        return False

    def test_plan_aliases_resolve_to_expected_names(self):
        self.assertEqual("idle", resolve_video_bot_plan_name("idle"))
        self.assertEqual("ground", resolve_video_bot_plan_name("mechanics"))
        self.assertEqual("swim", resolve_video_bot_plan_name("water"))
        self.assertEqual("flight", resolve_video_bot_plan_name("air"))
        self.assertEqual("parkour", resolve_video_bot_plan_name("vault"))
        self.assertEqual("excursion", resolve_video_bot_plan_name("tour"))
        self.assertEqual("environment_visual_probe", resolve_video_bot_plan_name("nature"))
        self.assertEqual("ui_inventory", resolve_video_bot_plan_name("inventory"))
        self.assertEqual("ui_pause", resolve_video_bot_plan_name("menu"))
        self.assertEqual("ui_full", resolve_video_bot_plan_name("ui"))
        self.assertEqual("dialogue", resolve_video_bot_plan_name("dialog"))
        self.assertEqual("loot_chest", resolve_video_bot_plan_name("loot"))
        self.assertEqual("crouch_stealth", resolve_video_bot_plan_name("crouch"))
        self.assertEqual("storm_quake", resolve_video_bot_plan_name("storm"))
        self.assertEqual("quake_escape", resolve_video_bot_plan_name("catastrophe"))
        self.assertEqual("showcase_extended", resolve_video_bot_plan_name("showcase"))
        self.assertEqual("combat_marathon", resolve_video_bot_plan_name("combat_marathon"))
        self.assertEqual("arena_boss_probe", resolve_video_bot_plan_name("boss_arena"))
        self.assertEqual("combat_magic_probe", resolve_video_bot_plan_name("combat_magic"))
        self.assertEqual("anim_melee_core", resolve_video_bot_plan_name("anim_melee"))
        self.assertEqual("anim_combo_chain", resolve_video_bot_plan_name("combo_chain"))
        self.assertEqual("anim_weapon_modes", resolve_video_bot_plan_name("weapon_modes"))
        self.assertEqual("anim_defense_stealth", resolve_video_bot_plan_name("defense_stealth"))
        self.assertEqual("anim_defense_stealth", resolve_video_bot_plan_name("shield_roll_stealth"))
        self.assertEqual("anim_locomotion_transitions", resolve_video_bot_plan_name("locomotion_transitions"))
        self.assertEqual("anim_enemy_visibility_aggro", resolve_video_bot_plan_name("enemy_visibility"))
        self.assertEqual("anim_camera_variation", resolve_video_bot_plan_name("camera_variation"))
        self.assertEqual("hud_combat_feedback", resolve_video_bot_plan_name("hud_feedback"))
        self.assertEqual("perf_animation_stability", resolve_video_bot_plan_name("perf_animation"))
        self.assertEqual("location_dialogue_probe", resolve_video_bot_plan_name("location_dialogue"))
        self.assertEqual("caves_visual_probe", resolve_video_bot_plan_name("caves_debug"))
        self.assertEqual("caves_visual_probe", resolve_video_bot_plan_name("dwarven_caves"))
        self.assertEqual("world_story_showcase", resolve_video_bot_plan_name("cinematic"))
        self.assertEqual("wallcrawl", resolve_video_bot_plan_name("wallrun"))
        self.assertEqual("ultimate_sandbox_probe", resolve_video_bot_plan_name("sandbox_probe"))
        self.assertEqual("ground", resolve_video_bot_plan_name("unknown-plan"))

    def test_idle_plan_is_empty(self):
        self.assertEqual([], build_video_bot_events("idle"))

    def test_parse_custom_plan_json_normalizes_and_sorts_rows(self):
        events = parse_video_bot_events_json(
            """
            [
              {"at": "1.4", "type": "tap", "action": "jump"},
              {"type": "hold", "action": "forward", "duration": 0.8},
              "skip-me",
              {"at": -2, "type": "teleport", "target": "sandbox_stairs_approach"}
            ]
            """
        )

        self.assertEqual(
            [
                ("hold", 0.0),
                ("teleport", 0.0),
                ("tap", 1.4),
            ],
            [(row.get("type"), float(row.get("at", 0.0) or 0.0)) for row in events],
        )

    def test_parse_custom_plan_json_supports_wrapped_events_object(self):
        events = parse_video_bot_events_json(
            """
            {
              "events": [
                {"at": 0.2, "type": "camera_profile", "profile": "exploration"},
                {"at": 0.0, "type": "teleport", "target": "sandbox_story_book_approach"}
              ]
            }
            """
        )

        self.assertEqual(2, len(events))
        self.assertEqual("teleport", events[0]["type"])
        self.assertEqual("camera_profile", events[1]["type"])

    def test_parse_custom_plan_json_supports_route_steps_ui_macros_and_context_rules(self):
        bundle = parse_video_bot_plan_json(
            """
            {
              "route": [
                {"teleport": "town"},
                {"move": ["forward", "right"], "run": true, "duration": 1.4},
                {"tap": "jump"},
                {"ui": "inventory"},
                {"ui": "map"},
                {"ui": "skills"},
                {"ui": "journal"},
                {"ui": "close_inventory"},
                {"ui": "pause"},
                {"ui": "settings"},
                {"ui": "resume"},
                {"include_plan": "dialogue"}
              ],
              "context_rules": [
                {
                  "id": "npc_dialogue_when_close",
                  "when": {"npc_distance_lte": 2.2},
                  "then": {"type": "tap", "action": "interact"},
                  "cooldown_sec": 2.0
                },
                {
                  "id": "fight_when_enemy_close",
                  "when": {"enemy_distance_lte": 3.0},
                  "then": [
                    {"type": "tap", "action": "block"},
                    {"type": "tap", "action": "attack_light"}
                  ],
                  "cooldown_sec": 1.5
                }
              ],
              "success_if": {"executed_action_contains": "interact"},
              "fail_if": {"player_z_min_lte": -1.0}
            }
            """
        )

        events = bundle["events"]
        self.assertEqual("teleport", events[0]["type"])
        move_holds = [row for row in events if row.get("type") == "hold" and float(row.get("at", 0.0) or 0.0) == 0.35]
        self.assertEqual({"forward", "right", "run"}, {str(row.get("action", "")) for row in move_holds})
        ui_actions = [row for row in events if row.get("type") == "ui_action"]
        ui_action_names = [str(row.get("action", "")) for row in ui_actions]
        self.assertIn("open_inventory", ui_action_names)
        self.assertIn("close_inventory", ui_action_names)
        self.assertIn("open_pause", ui_action_names)
        self.assertIn("pause_open_settings", ui_action_names)
        self.assertIn("close_pause", ui_action_names)
        tabs = {str(row.get("tab", "")) for row in ui_actions if row.get("action") == "inventory_tab"}
        self.assertTrue({"inventory", "map", "skills", "journal"}.issubset(tabs))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "interact" for row in events))
        self.assertEqual(2, len(bundle["context_rules"]))
        self.assertEqual({"executed_action_contains": "interact"}, bundle["success_if"])
        self.assertEqual({"player_z_min_lte": -1.0}, bundle["fail_if"])

    def test_ground_plan_contains_core_mechanics_actions(self):
        events = build_video_bot_events("ground")
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "jump" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "crouch_toggle" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "attack_light" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "attack_heavy" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "spell_1" for row in events))

    def test_default_attack_thrust_binding_uses_mouse3(self):
        self.assertEqual("mouse3", resolve_action_binding("attack_thrust", {}))

    def test_combo_chain_plan_exercises_directional_hits_and_thrust(self):
        events = build_video_bot_events("anim_combo_chain")
        held_actions = {str(row.get("action", "") or "") for row in events if row.get("type") == "hold"}
        tap_actions = {str(row.get("action", "") or "") for row in events if row.get("type") == "tap"}

        self.assertTrue({"left", "right", "forward"}.issubset(held_actions))
        self.assertIn("attack_thrust", tap_actions)

    def test_swim_plan_contains_water_forcing_segment(self):
        events = build_video_bot_events("swim")
        self.assertTrue(any(row.get("type") == "teleport" and row.get("target") == "training_pool" for row in events))
        self.assertTrue(
            any(
                row.get("type") == "set_flag"
                and row.get("flag") == "in_water"
                and bool(row.get("value")) is True
                for row in events
            )
        )

    def test_flight_plan_contains_air_controls(self):
        events = build_video_bot_events("flight")
        self.assertTrue(
            any(
                row.get("type") == "set_flag"
                and row.get("flag") == "is_flying"
                and bool(row.get("value")) is True
                for row in events
            )
        )
        self.assertTrue(any(row.get("action") == "flight_up" for row in events))
        self.assertTrue(any(row.get("action") == "flight_down" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "dash" for row in events))

    def test_anim_defense_stealth_plan_exercises_roll_and_dash(self):
        events = build_video_bot_events("anim_defense_stealth")
        tap_actions = [str(row.get("action", "") or "") for row in events if row.get("type") == "tap"]

        self.assertIn("roll", tap_actions)
        self.assertIn("dash", tap_actions)

    def test_parkour_plan_contains_jump_dash_pattern(self):
        events = build_video_bot_events("parkour")
        jump_taps = [row for row in events if row.get("type") == "tap" and row.get("action") == "jump"]
        self.assertGreaterEqual(len(jump_taps), 2)
        self.assertTrue(any(row.get("type") == "hold" and row.get("action") == "run" for row in events))

    def test_excursion_plan_contains_location_transitions(self):
        events = build_video_bot_events("excursion")
        transitions = [row for row in events if row.get("type") == "transition_next"]
        teleports = [row for row in events if row.get("type") == "teleport"]
        self.assertGreaterEqual(len(transitions), 2)
        self.assertGreaterEqual(len(teleports), 1)

    def test_environment_visual_probe_covers_sky_trees_paths_and_water(self):
        events = build_video_bot_events("environment_visual_probe")
        teleports = {str(row.get("target", "")) for row in events if row.get("type") == "teleport"}
        self.assertIn("kremor_forest", teleports)
        self.assertIn("docks", teleports)
        self.assertIn("training_pool", teleports)
        self.assertTrue(any(row.get("type") == "set_time" and row.get("preset") == "dusk" for row in events))
        self.assertTrue(any(row.get("type") == "set_weather" and row.get("preset") == "rainy" for row in events))
        self.assertTrue(any(row.get("type") == "set_flag" and row.get("flag") == "in_water" for row in events))

    def test_caves_visual_probe_focuses_on_dwarven_caves_scenic_route(self):
        events = build_video_bot_events("caves_visual_probe")
        teleports = [row for row in events if row.get("type") == "teleport"]
        self.assertGreaterEqual(len(teleports), 2)
        targets = {str(row.get("target", "")).strip().lower() for row in teleports}
        self.assertIn("dwarven_caves_gate", targets)
        self.assertIn("dwarven_caves_halls", targets)
        self.assertIn("dwarven_caves_throne", targets)
        self.assertTrue(any(row.get("type") == "set_time" and row.get("preset") == "noon" for row in events))
        self.assertTrue(any(row.get("type") == "set_weather" and row.get("preset") == "clear" for row in events))
        self.assertTrue(any(row.get("type") == "camera_impact" for row in events))
        self.assertTrue(any(row.get("type") == "camera_profile" for row in events))
        self.assertTrue(any(row.get("type") == "camera_shot" for row in events))
        self.assertTrue(any(row.get("type") == "hold" and row.get("action") == "forward" for row in events))
        self.assertTrue(any(row.get("type") == "hold" and row.get("action") == "run" for row in events))

    def test_ui_inventory_plan_covers_inventory_tabs(self):
        events = build_video_bot_events("ui_inventory")
        ui_actions = [row for row in events if row.get("type") == "ui_action"]
        tabs = {str(row.get("tab", "")) for row in ui_actions if row.get("action") == "inventory_tab"}
        self.assertIn("inventory", tabs)
        self.assertIn("map", tabs)
        self.assertIn("skills", tabs)
        self.assertIn("journal", tabs)
        tab_rows = [row for row in ui_actions if row.get("action") == "inventory_tab"]
        self.assertTrue(tab_rows)
        for row in tab_rows:
            cursor = row.get("cursor")
            self.assertIsInstance(cursor, dict)
            self.assertIn("x", cursor)
            self.assertIn("y", cursor)
            self.assertTrue(bool(cursor.get("click", False)))

    def test_ui_pause_plan_covers_pause_menu_panels(self):
        events = build_video_bot_events("ui_pause")
        ui_actions = [row for row in events if row.get("type") == "ui_action"]
        action_set = {str(row.get("action", "")) for row in ui_actions}
        for token in {
            "open_pause",
            "pause_open_settings",
            "pause_open_load",
            "pause_close_load",
            "close_pause",
        }:
            self.assertIn(token, action_set)
        for row in ui_actions:
            cursor = row.get("cursor")
            self.assertIsInstance(cursor, dict)
            self.assertIn("x", cursor)
            self.assertIn("y", cursor)

    def test_defense_stealth_plan_covers_shield_roll_and_stealth_actions(self):
        events = build_video_bot_events("anim_defense_stealth")

        self.assertTrue(any(row.get("type") == "teleport" and row.get("target") == "stealth_climb" for row in events))
        self.assertTrue(
            any(
                row.get("type") == "equip_item"
                and row.get("item_id") == "training_shield"
                for row in events
            )
        )
        self.assertTrue(any(row.get("type") == "force_aggro" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "crouch_toggle" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "roll" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "block" for row in events))

    def test_binding_resolution_uses_fallback_when_binding_is_none(self):
        bindings = {"attack_light": "none", "flight_toggle": "v", "block": "none"}
        self.assertEqual("mouse1", resolve_action_binding("attack_light", bindings))
        self.assertEqual("v", resolve_action_binding("flight_toggle", bindings))
        self.assertEqual("q", resolve_action_binding("block", bindings))
        self.assertEqual("t", resolve_action_binding("target_lock", {}))

    def test_dialogue_plan_focuses_on_one_conversation_without_parkour_noise(self):
        events = build_video_bot_events("dialogue")
        teleports = [row for row in events if row.get("type") == "teleport"]
        named_teleports = [row for row in teleports if "," not in str(row.get("target", "") or "")]
        anchor_teleports = [row for row in teleports if "," in str(row.get("target", "") or "")]
        interact_taps = [
            row for row in events
            if row.get("type") == "tap" and str(row.get("action", "") or "") == "interact"
        ]
        self.assertEqual([{"at": 0.0, "type": "teleport", "target": "castle_interior"}], named_teleports)
        self.assertEqual(1, len(anchor_teleports))
        self.assertGreaterEqual(len(interact_taps), 4)
        self.assertTrue(any(row.get("type") == "camera_profile" for row in events))
        self.assertTrue(any(row.get("type") == "camera_shot" for row in events))
        noisy_taps = {
            str(row.get("action", "") or "")
            for row in events
            if row.get("type") == "tap"
            and str(row.get("action", "") or "") in {"jump", "attack_light", "attack_heavy", "spell_1", "spell_cast"}
        }
        self.assertEqual(set(), noisy_taps)
        self.assertFalse(any(row.get("type") == "force_aggro" for row in events))
        self.assertGreaterEqual(float(events[-1].get("at", 0.0) or 0.0), 9.0)

    def test_storm_quake_plan_contains_weather_and_quake_events(self):
        events = build_video_bot_events("storm_quake")
        self.assertTrue(any(row.get("type") == "set_weather" and row.get("preset") == "stormy" for row in events))
        self.assertTrue(any(row.get("type") == "camera_impact" for row in events))

    def test_quake_escape_plan_focuses_on_stealth_climb_and_impacts(self):
        events = build_video_bot_events("quake_escape")
        self.assertTrue(any(row.get("type") == "teleport" and row.get("target") == "stealth_climb" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "crouch_toggle" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "jump" for row in events))
        impact_count = sum(1 for row in events if row.get("type") == "camera_impact")
        self.assertGreaterEqual(impact_count, 3)

    def test_showcase_extended_plan_covers_multi_zone_mechanics(self):
        events = build_video_bot_events("showcase_extended")
        teleports = {str(row.get("target", "")) for row in events if row.get("type") == "teleport"}
        self.assertIn("parkour", teleports)
        self.assertIn("stealth_climb", teleports)
        self.assertIn("training_pool", teleports)
        self.assertIn("flight", teleports)
        self.assertTrue(any(row.get("type") == "camera_impact" for row in events))
        self.assertTrue(any(row.get("type") == "ui_action" for row in events))
        self.assertTrue(any(row.get("type") == "ui_action" and row.get("tab") == "journal" for row in events))
        self.assertTrue(any(row.get("type") == "equip_item" for row in events))
        self.assertTrue(any(row.get("type") == "quest_action" for row in events))
        self.assertTrue(any(row.get("type") == "portal_jump" for row in events))
        self.assertTrue(any(row.get("type") == "damage_player" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "block" for row in events))
        self.assertTrue(
            any(
                row.get("type") == "tap"
                and row.get("action") in {"spell_2", "spell_3", "spell_4"}
                for row in events
            )
        )
        self.assertGreaterEqual(len(events), 120)

    def test_combat_marathon_plan_has_dense_combat_actions(self):
        events = build_video_bot_events("combat_marathon")
        attacks = [
            row
            for row in events
            if row.get("type") == "tap" and row.get("action") in {"attack_light", "attack_heavy"}
        ]
        spells = [row for row in events if row.get("type") == "tap" and str(row.get("action", "")).startswith("spell_")]
        self.assertGreaterEqual(len(attacks), 16)
        self.assertGreaterEqual(len(spells), 8)
        self.assertTrue(any(row.get("type") == "teleport" and row.get("target") == "dragon_arena" for row in events))
        self.assertTrue(any(row.get("type") == "force_aggro" for row in events))

    def test_combat_marathon_plan_waits_for_battle_windows_before_changing_location(self):
        events = build_video_bot_events("combat_marathon")
        self.assertEqual([], self._location_changes_inside_force_aggro_windows(events))

    def test_arena_boss_probe_focuses_on_arena_boss_lockon_and_hp_readability(self):
        events = build_video_bot_events("arena_boss_probe")
        teleports = [row for row in events if row.get("type") == "teleport"]
        self.assertTrue(teleports)
        self.assertTrue(all(str(row.get("target", "")).strip().lower() == "dragon_arena" for row in teleports))
        self.assertTrue(any(row.get("type") == "force_aggro" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "target_lock" for row in events))
        self.assertTrue(any(row.get("type") == "camera_profile" and row.get("profile") == "boss" for row in events))
        self.assertTrue(any(row.get("type") == "camera_shot" and row.get("name") == "boss_intro" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "block" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "spell_cast" for row in events))

    def test_combat_magic_probe_focuses_on_magic_and_keeps_location(self):
        events = build_video_bot_events("combat_magic_probe")
        self.assertTrue(any(row.get("type") == "equip_item" and row.get("item_id") == "chainmail_armor" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "spell_cast" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "block" for row in events))
        self.assertTrue(any(row.get("type") == "force_aggro" for row in events))
        self.assertFalse(any(row.get("type") == "teleport" for row in events))

    def test_anim_melee_core_plan_contains_enemy_contact_and_block_windows(self):
        events = build_video_bot_events("anim_melee_core")
        self.assertTrue(any(row.get("type") == "teleport" and row.get("target") == "dragon_arena" for row in events))
        self.assertTrue(any(row.get("type") == "force_aggro" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "target_lock" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "attack_light" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "attack_heavy" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "block" for row in events))

    def test_anim_locomotion_transitions_plan_covers_swim_climb_flight(self):
        events = build_video_bot_events("anim_locomotion_transitions")
        teleports = {str(row.get("target", "")) for row in events if row.get("type") == "teleport"}
        self.assertIn("training_pool", teleports)
        self.assertIn("stealth_climb", teleports)
        self.assertIn("flight", teleports)
        self.assertTrue(any(row.get("type") == "set_flag" and row.get("flag") == "in_water" for row in events))
        self.assertTrue(any(row.get("type") == "set_flag" and row.get("flag") == "is_flying" for row in events))
        self.assertTrue(self._has_overlapping_hold_pair(events, "forward", "right"))
        self.assertTrue(self._has_overlapping_hold_pair(events, "forward", "left"))
        self.assertTrue(self._has_overlapping_hold_pair(events, "backward", "right"))
        self.assertTrue(self._has_overlapping_hold_pair(events, "backward", "left"))

    def test_anim_weapon_modes_plan_explicitly_toggles_weapon_ready_states(self):
        events = build_video_bot_events("anim_weapon_modes")
        ready_events = [row for row in events if row.get("type") == "weapon_ready"]
        teleports = [row for row in events if row.get("type") == "teleport"]
        self.assertTrue(any(bool(row.get("drawn", False)) for row in ready_events))
        self.assertTrue(any((not bool(row.get("drawn", True))) for row in ready_events))
        self.assertEqual({"castle_interior"}, {str(row.get("target", "")).strip().lower() for row in teleports})
        self.assertFalse(any(row.get("type") == "force_aggro" for row in events))
        self.assertFalse(
            any(
                row.get("type") == "tap" and str(row.get("action", "")).strip().lower() == "target_lock"
                for row in events
            )
        )

    def test_anim_camera_variation_plan_contains_distinct_camera_profiles_and_shots(self):
        events = build_video_bot_events("anim_camera_variation")
        profiles = {str(row.get("profile", "")) for row in events if row.get("type") == "camera_profile"}
        self.assertIn("exploration", profiles)
        self.assertIn("combat", profiles)
        self.assertIn("boss", profiles)
        shots = [row for row in events if row.get("type") == "camera_shot"]
        self.assertGreaterEqual(len(shots), 3)

    def test_hud_combat_feedback_plan_contains_damage_and_boss_targeting_events(self):
        events = build_video_bot_events("hud_combat_feedback")
        self.assertTrue(any(row.get("type") == "force_aggro" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "target_lock" for row in events))
        self.assertTrue(any(row.get("type") == "damage_player" for row in events))

    def test_location_dialogue_probe_plan_uses_dialogue_hubs_without_unrelated_actions(self):
        events = build_video_bot_events("location_dialogue_probe")
        teleports = [row for row in events if row.get("type") == "teleport"]
        named_teleports = {
            str(row.get("target", "")).strip().lower()
            for row in teleports
            if "," not in str(row.get("target", "") or "")
        }
        anchor_teleports = [row for row in teleports if "," in str(row.get("target", "") or "")]
        self.assertIn("castle_interior", named_teleports)
        self.assertIn("dwarven_caves_gate", named_teleports)
        self.assertIn("port_market_memory", named_teleports)
        interact_taps = [
            row for row in events
            if row.get("type") == "tap" and str(row.get("action", "") or "") == "interact"
        ]
        close_dialogue_actions = [
            row
            for row in events
            if row.get("type") == "ui_action"
            and str(row.get("action", "") or "").strip().lower() == "close_dialogue"
        ]
        self.assertEqual(2, len(interact_taps))
        self.assertEqual(2, len(close_dialogue_actions))
        self.assertGreaterEqual(len(anchor_teleports), 2)
        self.assertTrue(any(row.get("type") == "camera_shot" for row in events))
        noisy_rows = [
            row
            for row in events
            if row.get("type") == "force_aggro"
            or (
                row.get("type") == "tap"
                and str(row.get("action", "") or "") in {"jump", "attack_light", "attack_heavy", "spell_1", "spell_cast"}
            )
        ]
        self.assertEqual([], noisy_rows)
        self.assertGreaterEqual(float(events[-1].get("at", 0.0) or 0.0), 24.0)

    def test_all_locations_grand_tour_plan_covers_major_world_clusters_and_ui(self):
        events = build_video_bot_events("all_locations_grand_tour")
        teleports = {str(row.get("target", "")).strip().lower() for row in events if row.get("type") == "teleport"}
        for expected in {
            "town",
            "castle_hill",
            "castle",
            "castle_interior",
            "docks",
            "training",
            "parkour",
            "stealth_climb",
            "flight",
            "old_forest",
            "kremor_forest",
            "dwarven_caves_halls",
        }:
            self.assertIn(expected, teleports)
        self.assertTrue(any(row.get("type") == "ui_action" and row.get("action") == "open_inventory" for row in events))
        self.assertTrue(any(row.get("type") == "ui_action" and row.get("action") == "open_pause" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "interact" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "spell_cast" for row in events))

    def test_stealth_climb_plan_includes_spell_and_aggro_segments(self):
        events = build_video_bot_events("stealth_climb")
        self.assertTrue(any(row.get("type") == "force_aggro" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "spell_cast" for row in events))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "block" for row in events))

    def test_world_story_showcase_plan_combines_dialogue_ui_and_loot(self):
        events = build_video_bot_events("world_story_showcase")
        ui_actions = [row for row in events if row.get("type") == "ui_action"]
        self.assertTrue(any(row.get("action") == "open_inventory" for row in ui_actions))
        self.assertTrue(any(row.get("action") == "open_pause" for row in ui_actions))
        self.assertTrue(any(row.get("action") == "inventory_tab" and row.get("tab") == "journal" for row in ui_actions))
        self.assertTrue(any(row.get("action") == "interact" for row in events))
        self.assertTrue(any(row.get("type") == "quest_action" for row in events))
        self.assertTrue(any(row.get("type") == "portal_jump" for row in events))
        self.assertTrue(any(row.get("type") == "transition_next" for row in events))

    def test_wallcrawl_plan_contains_wallrun_like_movement(self):
        events = build_video_bot_events("wallcrawl")
        self.assertTrue(any(row.get("type") == "hold" and row.get("action") == "run" for row in events))
        jump_count = sum(1 for row in events if row.get("type") == "tap" and row.get("action") == "jump")
        self.assertGreaterEqual(jump_count, 3)

    def test_ultimate_sandbox_probe_plan_reanchors_to_sandbox_features(self):
        events = build_video_bot_events("ultimate_sandbox_probe")
        teleports = [str(row.get("target", "")).strip().lower() for row in events if row.get("type") == "teleport"]
        self.assertEqual(
            [
                "sandbox_stairs_approach",
                "sandbox_traversal_approach",
                "sandbox_wallrun_approach",
                "sandbox_tower_approach",
                "sandbox_pool_edge",
                "sandbox_story_chest_approach",
                "sandbox_story_book_approach",
            ],
            teleports,
        )
        self.assertTrue(all("," not in target for target in teleports))
        self.assertTrue(any(row.get("type") == "tap" and row.get("action") == "interact" for row in events))
        self.assertTrue(any(row.get("type") == "hold" and row.get("action") == "left" for row in events))
        self.assertTrue(any(row.get("type") == "camera_profile" for row in events))
        self.assertTrue(any(row.get("type") == "camera_shot" for row in events))
        tap_actions = {
            str(row.get("action", "")).strip().lower()
            for row in events
            if row.get("type") == "tap"
        }
        self.assertTrue({"jump", "attack_light", "crouch_toggle", "interact"}.issubset(tap_actions))


if __name__ == "__main__":
    unittest.main()
