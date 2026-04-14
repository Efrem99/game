import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from panda3d.core import LPoint3, Vec3


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.camera_director import CameraDirector


class _NodeStub:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self._pos = LPoint3(float(x), float(y), float(z))

    def getPos(self, _render=None):
        return LPoint3(self._pos.x, self._pos.y, self._pos.z)


class _PlayerStub:
    def __init__(self):
        self.actor = _NodeStub(0.0, 0.0, 0.0)
        self._is_aiming = False
        self._aim_mode = ""
        self._anim_state = "idle"
        self._pending_spell = None
        self._spell_cast_lock_until = 0.0
        self._stealth_crouch = False
        self._shadow_mode = False
        self._ranged_equipped = False
        self.brain = SimpleNamespace(mental={"fear": 0.0})
        self.cs = SimpleNamespace(health=100.0, maxHealth=100.0, inWater=False)

    def get_hud_combat_event(self):
        return None

    def _is_ranged_weapon_equipped(self):
        return bool(self._ranged_equipped)


class _CameraDirectorAppStub:
    def __init__(self, camera_profiles=None, active_location=""):
        self.data_mgr = SimpleNamespace(camera_profiles=camera_profiles or {})
        self.event_bus = None
        self.player = _PlayerStub()
        self.camera = _NodeStub(0.0, -18.0, 12.0)
        self.render = object()
        self.world = SimpleNamespace(active_location=str(active_location or ""))
        self.state_mgr = SimpleNamespace(current_state=SimpleNamespace(name="playing"))
        self.boss_manager = SimpleNamespace(any_engaged=lambda: False)
        self.dragon_boss = None
        self.vehicle_mgr = None
        self.movement_tutorial = None
        self.char_state = SimpleNamespace(
            position=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0),
        )
        self._cam_dist = 22.0
        self._cam_pitch = -20.0
        self._cam_yaw = 0.0
        self._cam_zoom_offset = 0.0
        self._aim_target_info = None


class CameraDirectorExtendedModesTests(unittest.TestCase):
    def test_shoulder_profile_offsets_look_target_for_stable_anchor_composition(self):
        app = _CameraDirectorAppStub(
            camera_profiles={
                "profiles": {
                    "shoulder_right": {
                        "dist": 10.0,
                        "pitch": -8.0,
                        "target_z": 1.72,
                        "side": 1.85,
                        "smooth": 14.0,
                        "look_side": -0.85,
                        "look_ahead": 2.4,
                    }
                }
            }
        )
        director = CameraDirector(app)

        self.assertTrue(director.set_profile("shoulder_right", hold_seconds=1.0, owner="test"))
        profile_cfg = director.update(0.016, manual_look=False)
        cam_pos, look = director.resolve_transform(
            center=Vec3(0.0, 0.0, 0.0),
            base_z=0.0,
            yaw_rad=0.0,
            pitch_rad=math.radians(-8.0),
            profile_cfg=profile_cfg,
        )

        self.assertGreater(float(cam_pos.x), 1.0)
        self.assertLess(float(look.x), -0.5)
        self.assertGreater(float(look.y), 2.0)

    def test_location_rule_forces_profile_and_triggers_enter_shot_once(self):
        app = _CameraDirectorAppStub(
            camera_profiles={
                "profiles": {
                    "shoulder_right": {
                        "dist": 10.0,
                        "pitch": -8.0,
                        "target_z": 1.72,
                        "side": 1.85,
                        "smooth": 14.0,
                    }
                },
                "shots": {
                    "location_reveal": {
                        "duration": 1.1,
                        "profile": "cinematic",
                        "side": 3.8,
                        "yaw_bias_deg": 14.0,
                    }
                },
                "locations": {
                    "training grounds": {
                        "profile": "shoulder_right",
                        "enter_shot": "location_reveal",
                    }
                },
            },
            active_location="Training Grounds",
        )
        director = CameraDirector(app)

        director.update(0.016, manual_look=False)
        first_cutscene = dict(director._cutscene or {})
        director.update(0.016, manual_look=False)

        self.assertEqual("shoulder_right", director._active_profile)
        self.assertEqual("location_reveal", str(first_cutscene.get("name", "")))
        self.assertEqual(first_cutscene, dict(director._cutscene or {}))

    def test_camera_sequence_advances_through_multiple_shots_without_manual_retrigger(self):
        app = _CameraDirectorAppStub(
            camera_profiles={
                "sequences": {
                    "portal_arrival": [
                        {
                            "name": "arrival_wide",
                            "duration": 0.9,
                            "profile": "cinematic",
                            "side": 4.0,
                            "yaw_bias_deg": 12.0,
                        },
                        {
                            "name": "arrival_close",
                            "duration": 0.7,
                            "profile": "dialog",
                            "side": -2.0,
                            "yaw_bias_deg": -8.0,
                        },
                    ]
                }
            }
        )
        director = CameraDirector(app)
        fake_time = {"now": 100.0}
        director._now = lambda: float(fake_time["now"])

        self.assertTrue(director.play_camera_sequence("portal_arrival", owner="test"))
        self.assertEqual("arrival_wide", str(director._cutscene.get("name", "")))

        fake_time["now"] = 101.0
        director.resolve_transform(
            center=Vec3(0.0, 0.0, 0.0),
            base_z=0.0,
            yaw_rad=0.0,
            pitch_rad=math.radians(-12.0),
            profile_cfg={"dist": 18.0, "target_z": 1.8, "side": 0.0},
        )
        self.assertEqual("arrival_close", str(director._cutscene.get("name", "")))

        fake_time["now"] = 102.0
        director.resolve_transform(
            center=Vec3(0.0, 0.0, 0.0),
            base_z=0.0,
            yaw_rad=0.0,
            pitch_rad=math.radians(-12.0),
            profile_cfg={"dist": 18.0, "target_z": 1.8, "side": 0.0},
        )
        self.assertFalse(director.is_cutscene_active())

    def test_zone_rule_forces_profile_inside_location_and_retriggers_after_reentry(self):
        app = _CameraDirectorAppStub(
            camera_profiles={
                "zones": [
                    {
                        "id": "training_pool_anchor",
                        "location": "training grounds",
                        "center": [6.0, 46.0, 1.0],
                        "radius": 8.0,
                        "profile": "stealth",
                        "priority": 82,
                        "enter_sequence": "portal_arrival",
                    }
                ]
            },
            active_location="Training Grounds",
        )
        director = CameraDirector(app)
        fake_time = {"now": 120.0}
        director._now = lambda: float(fake_time["now"])

        app.char_state.position = SimpleNamespace(x=6.0, y=46.0, z=1.0)
        director.update(0.016, manual_look=False)
        first_name = str((director._cutscene or {}).get("name", ""))

        app.char_state.position = SimpleNamespace(x=30.0, y=30.0, z=1.0)
        fake_time["now"] = 123.0
        director.update(0.016, manual_look=False)

        app.char_state.position = SimpleNamespace(x=6.0, y=46.0, z=1.0)
        fake_time["now"] = 126.0
        director.update(0.016, manual_look=False)
        second_name = str((director._cutscene or {}).get("name", ""))

        self.assertEqual("stealth", director._active_profile)
        self.assertEqual("portal_wide", first_name)
        self.assertEqual("portal_wide", second_name)

    def test_runtime_stealth_flags_select_stealth_profile(self):
        app = _CameraDirectorAppStub()
        app.player._stealth_crouch = True
        director = CameraDirector(app)

        director.update(0.016, manual_look=False)

        self.assertEqual("stealth", director._active_profile)

    def test_dialog_pair_framing_prefers_shoulder_closer_to_current_camera(self):
        app = _CameraDirectorAppStub()
        app.camera = _NodeStub(8.35, 32.15, 5.32)
        director = CameraDirector(app)

        center = LPoint3(4.8, 44.1, 1.05)
        npc_focus = LPoint3(5.0, 45.0, 1.65)
        player_focus = LPoint3(4.6, 43.2, 4.4)

        ok = director.play_anchor_camera_shot(
            name="dialog_npc",
            duration=0.3,
            profile="dialog",
            center=center,
            base_z=1.05,
            yaw_deg=12.5,
            look_target=npc_focus,
            partner_target=player_focus,
            framing="dialog_pair",
            side=-1.45,
            yaw_bias_deg=0.0,
            owner="dialog",
        )

        self.assertTrue(ok)
        cutscene = dict(director._cutscene or {})
        to_pos = cutscene.get("to_pos")
        self.assertIsNotNone(to_pos)
        self.assertGreater(float(to_pos.x), float(center.x))

    def test_dialog_pair_framing_keeps_staged_camera_height_close_to_current_pose(self):
        app = _CameraDirectorAppStub()
        app.camera = _NodeStub(8.35, 32.15, 5.32)
        director = CameraDirector(app)

        center = LPoint3(4.8, 44.1, 1.05)
        npc_focus = LPoint3(5.0, 45.0, 1.65)
        player_focus = LPoint3(4.6, 43.2, 4.4)

        ok = director.play_anchor_camera_shot(
            name="dialog_npc",
            duration=0.3,
            profile="dialog",
            center=center,
            base_z=1.05,
            yaw_deg=12.5,
            look_target=npc_focus,
            partner_target=player_focus,
            framing="dialog_pair",
            side=-1.45,
            yaw_bias_deg=0.0,
            owner="dialog",
        )

        self.assertTrue(ok)
        cutscene = dict(director._cutscene or {})
        to_pos = cutscene.get("to_pos")
        self.assertIsNotNone(to_pos)
        self.assertGreater(float(to_pos.z), 4.4)

    def test_ranged_aim_prefers_bow_aim_profile_over_generic_aim(self):
        app = _CameraDirectorAppStub(
            camera_profiles={
                "profiles": {
                    "bow_aim": {
                        "dist": 8.9,
                        "pitch": -7.0,
                        "target_z": 1.7,
                        "side": 1.72,
                        "smooth": 15.0,
                    }
                }
            }
        )
        app.player._is_aiming = True
        app.player._aim_mode = "bow"
        app.player._ranged_equipped = True
        director = CameraDirector(app)

        director.update(0.016, manual_look=False)

        self.assertEqual("bow_aim", director._active_profile)

    def test_pending_spell_prefers_magic_cast_profile(self):
        app = _CameraDirectorAppStub(
            camera_profiles={
                "profiles": {
                    "magic_cast": {
                        "dist": 11.0,
                        "pitch": -9.5,
                        "target_z": 1.85,
                        "side": -1.3,
                        "smooth": 12.8,
                    }
                }
            }
        )
        app.player._pending_spell = {"key": "firebolt"}
        app.player._anim_state = "casting"
        director = CameraDirector(app)

        director.update(0.016, manual_look=False)

        self.assertEqual("magic_cast", director._active_profile)

    def test_flight_profile_uses_velocity_heading_instead_of_stale_camera_yaw(self):
        app = _CameraDirectorAppStub(
            camera_profiles={
                "profiles": {
                    "flight": {
                        "dist": 21.5,
                        "pitch": -18.0,
                        "target_z": 2.2,
                        "side": 0.0,
                        "smooth": 12.5,
                        "look_ahead": 3.4,
                    }
                }
            }
        )
        app.player._is_flying = True
        app.char_state.velocity = SimpleNamespace(x=18.0, y=0.0, z=0.0)
        director = CameraDirector(app)

        profile_cfg = director.update(0.016, manual_look=False)
        _cam_pos, look = director.resolve_transform(
            center=Vec3(0.0, 0.0, 0.0),
            base_z=0.0,
            yaw_rad=0.0,
            pitch_rad=math.radians(-18.0),
            profile_cfg=profile_cfg,
        )

        self.assertEqual("flight", director._active_profile)
        self.assertGreater(float(look.x), 2.0)
        self.assertLess(abs(float(look.y)), 1.0)

    def test_anchor_camera_shot_uses_custom_center_and_focus_target(self):
        app = _CameraDirectorAppStub()
        director = CameraDirector(app)

        ok = director.play_anchor_camera_shot(
            name="dialog_pair",
            duration=0.4,
            profile="dialog",
            center=Vec3(8.0, 42.0, 1.2),
            base_z=1.2,
            yaw_deg=18.0,
            look_target=LPoint3(10.0, 45.0, 2.8),
            side=-1.4,
            yaw_bias_deg=0.0,
            owner="dialog",
        )

        self.assertTrue(ok)
        self.assertAlmostEqual(10.0, float(director._cutscene["to_look"].x), delta=0.001)
        self.assertAlmostEqual(45.0, float(director._cutscene["to_look"].y), delta=0.001)
        self.assertGreater(float(director._cutscene["to_pos"].y), 30.0)

    def test_dialog_pair_framing_uses_partner_target_instead_of_generic_orbit(self):
        app = _CameraDirectorAppStub()
        director = CameraDirector(app)

        ok = director.play_anchor_camera_shot(
            name="dialog_npc",
            duration=0.4,
            profile="dialog",
            center=Vec3(2.0, 43.0, 1.0),
            base_z=1.0,
            yaw_deg=33.0,
            look_target=LPoint3(4.0, 46.0, 3.65),
            partner_target=LPoint3(0.0, 40.0, 1.65),
            framing="dialog_pair",
            side=-1.45,
            yaw_bias_deg=0.0,
            owner="dialog",
        )

        self.assertTrue(ok)
        self.assertAlmostEqual(4.0, float(director._cutscene["to_look"].x), delta=0.001)
        self.assertAlmostEqual(46.0, float(director._cutscene["to_look"].y), delta=0.001)
        self.assertGreater(float(director._cutscene["to_pos"].y), 39.0)
        self.assertLess(float(director._cutscene["to_pos"].y), 45.0)
        self.assertLess((director._cutscene["to_pos"] - director._cutscene["to_look"]).length(), 7.0)

    def test_chained_dialog_shot_uses_current_cutscene_pose_instead_of_origin_camera(self):
        app = _CameraDirectorAppStub()
        app.camera = _NodeStub(0.0, 0.0, 0.0)
        director = CameraDirector(app)
        fake_time = {"now": 100.5}
        director._now = lambda: float(fake_time["now"])
        director._cutscene = {
            "name": "dialog",
            "start_t": 100.0,
            "end_t": 101.0,
            "from_pos": LPoint3(0.0, 27.0, 11.5),
            "to_pos": LPoint3(3.8, 37.0, 5.4),
            "from_look": LPoint3(0.0, 48.0, 3.8),
            "to_look": LPoint3(0.0, 48.0, 3.8),
            "priority": 92,
            "owner": "dialog",
        }
        director._active_shot_priority = 92
        director._active_shot_owner = "dialog"

        ok = director.play_camera_shot(
            name="dialog_npc",
            duration=0.3,
            profile="dialog",
            side=2.3,
            yaw_bias_deg=8.0,
            owner="dialog",
        )

        self.assertTrue(ok)
        self.assertGreater(float(director._cutscene["from_pos"].y), 20.0)
        self.assertGreater(float(director._cutscene["from_pos"].z), 4.0)

    def test_dialog_shot_uses_last_resolved_pose_when_camera_node_falls_back_to_origin(self):
        app = _CameraDirectorAppStub()
        app.camera = _NodeStub(0.0, 0.0, 0.0)
        director = CameraDirector(app)

        profile_cfg = director.update(0.016, manual_look=False)
        gameplay_pos, gameplay_look = director.resolve_transform(
            center=Vec3(0.0, 0.0, 0.0),
            base_z=0.0,
            yaw_rad=0.0,
            pitch_rad=math.radians(-20.0),
            profile_cfg=profile_cfg,
        )

        ok = director.play_camera_shot(
            name="dialog_npc",
            duration=0.3,
            profile="dialog",
            side=2.3,
            yaw_bias_deg=8.0,
            owner="dialog",
        )

        self.assertTrue(ok)
        self.assertAlmostEqual(float(director._cutscene["from_pos"].x), float(gameplay_pos.x), delta=0.001)
        self.assertAlmostEqual(float(director._cutscene["from_pos"].y), float(gameplay_pos.y), delta=0.001)
        self.assertAlmostEqual(float(director._cutscene["from_pos"].z), float(gameplay_pos.z), delta=0.001)
        self.assertAlmostEqual(float(director._cutscene["from_look"].y), float(gameplay_look.y), delta=0.001)


if __name__ == "__main__":
    unittest.main()
