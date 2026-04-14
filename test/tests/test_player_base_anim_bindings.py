import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _BaseAnimDummy:
    _resolve_base_anims = Player._resolve_base_anims
    _resolve_xbot_runtime_anims = Player._resolve_xbot_runtime_anims

    def __init__(self, cfg, manifest_mapping=None):
        self._cfg = dict(cfg or {})
        self._manifest_mapping = dict(manifest_mapping or {})

    def _player_model_config(self):
        return dict(self._cfg)

    def _load_manifest_animation_sources(self):
        return dict(self._manifest_mapping), True


class PlayerBaseAnimBindingTests(unittest.TestCase):
    def test_xbot_runtime_loads_curated_motion_and_combat_clips(self):
        runtime_dir = "assets/models/xbot/runtime_clips"
        dummy = _BaseAnimDummy(
            {
                "model": "assets/models/xbot/Xbot.glb",
                "base_anims": {
                    "idle": "assets/models/xbot/idle.glb",
                    "walk": "assets/models/xbot/walk.glb",
                    "run": "assets/models/xbot/run.glb",
                },
            },
            manifest_mapping={
                "jumping": "assets/anims/jump_takeoff.fbx",
                "falling": "assets/anims/fall_air.fbx",
                "falling_hard": f"{runtime_dir}/falling_hard.glb",
                "landing": "assets/anims/land_recover.fbx",
                "dodging": f"{runtime_dir}/dodging.glb",
                "crouch_idle": "assets/anims/mixamo/player/crouch_idle.fbx",
                "crouch_move": "assets/anims/mixamo/player/crouch_move.fbx",
                "flying": f"{runtime_dir}/flying.glb",
                "flight_takeoff": f"{runtime_dir}/flight_takeoff.glb",
                "flight_hover": f"{runtime_dir}/flight_hover.glb",
                "flight_glide": f"{runtime_dir}/flight_glide.glb",
                "flight_dive": f"{runtime_dir}/flight_dive.glb",
                "flight_land": f"{runtime_dir}/flight_land.glb",
                "attacking": f"{runtime_dir}/attacking.glb",
                "casting": f"{runtime_dir}/casting.glb",
                "cast_prepare": f"{runtime_dir}/cast_prepare.glb",
                "cast_channel": f"{runtime_dir}/cast_channel.glb",
                "cast_release": f"{runtime_dir}/cast_release.glb",
                "blocking": f"{runtime_dir}/blocking.glb",
                "recovering": f"{runtime_dir}/recovering.glb",
                "run_blade": "assets/anims/mixamo/player/run_blade.fbx",
                "weapon_unsheathe": f"{runtime_dir}/weapon_unsheathe.glb",
                "weapon_sheathe": f"{runtime_dir}/weapon_sheathe.glb",
                "draw_sword": f"{runtime_dir}/weapon_unsheathe.glb",
                "attack_light_left": "assets/anims/attack_sword_slash.fbx",
                "attack_heavy_left": "assets/anims/attack_sword_slash.fbx",
                "attack_thrust_forward": "assets/anims/mixamo/player/attack_thrust_right.fbx",
                "attack_forward": "assets/anims/attack_sword_slash.fbx",
                "climbing": "assets/anims/mixamo/player/climb_fast.fbx",
                "wallrun": f"{runtime_dir}/wallrun.glb",
                "vaulting": "assets/anims/mixamo/player/vault_low.fbx",
                "swim": f"{runtime_dir}/swim.glb",
            },
        )

        resolved = dummy._resolve_base_anims()

        self.assertEqual(f"{runtime_dir}/idle.glb", resolved["idle"])
        self.assertEqual(f"{runtime_dir}/walk.glb", resolved["walk"])
        self.assertEqual(f"{runtime_dir}/run.glb", resolved["run"])
        self.assertEqual("assets/anims/jump_takeoff.fbx", resolved["jumping"])
        self.assertEqual("assets/anims/fall_air.fbx", resolved["falling"])
        self.assertEqual(f"{runtime_dir}/falling_hard.glb", resolved["falling_hard"])
        self.assertEqual("assets/anims/land_recover.fbx", resolved["landing"])
        self.assertEqual(f"{runtime_dir}/dodging.glb", resolved["dodging"])
        self.assertEqual("assets/anims/mixamo/player/crouch_idle.fbx", resolved["crouch_idle"])
        self.assertEqual("assets/anims/mixamo/player/crouch_move.fbx", resolved["crouch_move"])
        self.assertEqual(f"{runtime_dir}/flying.glb", resolved["flying"])
        self.assertEqual(f"{runtime_dir}/flight_takeoff.glb", resolved["flight_takeoff"])
        self.assertEqual(f"{runtime_dir}/flight_hover.glb", resolved["flight_hover"])
        self.assertEqual(f"{runtime_dir}/flight_glide.glb", resolved["flight_glide"])
        self.assertEqual(f"{runtime_dir}/flight_dive.glb", resolved["flight_dive"])
        self.assertEqual(f"{runtime_dir}/flight_land.glb", resolved["flight_land"])
        self.assertEqual(f"{runtime_dir}/attacking.glb", resolved["attacking"])
        self.assertEqual(f"{runtime_dir}/casting.glb", resolved["casting"])
        self.assertEqual(f"{runtime_dir}/cast_prepare.glb", resolved["cast_prepare"])
        self.assertEqual(f"{runtime_dir}/cast_channel.glb", resolved["cast_channel"])
        self.assertEqual(f"{runtime_dir}/cast_release.glb", resolved["cast_release"])
        self.assertEqual(f"{runtime_dir}/blocking.glb", resolved["blocking"])
        self.assertEqual(f"{runtime_dir}/recovering.glb", resolved["recovering"])
        self.assertEqual("assets/anims/mixamo/player/run_blade.fbx", resolved["run_blade"])
        self.assertEqual(f"{runtime_dir}/weapon_unsheathe.glb", resolved["weapon_unsheathe"])
        self.assertEqual(f"{runtime_dir}/weapon_sheathe.glb", resolved["weapon_sheathe"])
        self.assertEqual(f"{runtime_dir}/weapon_unsheathe.glb", resolved["draw_sword"])
        self.assertEqual("assets/anims/attack_sword_slash.fbx", resolved["attack_light_left"])
        self.assertEqual("assets/anims/attack_sword_slash.fbx", resolved["attack_heavy_left"])
        self.assertEqual("assets/anims/mixamo/player/attack_thrust_right.fbx", resolved["attack_thrust_forward"])
        self.assertEqual("assets/anims/attack_sword_slash.fbx", resolved["attack_forward"])
        self.assertEqual("assets/anims/mixamo/player/climb_fast.fbx", resolved["climbing"])
        self.assertEqual(f"{runtime_dir}/wallrun.glb", resolved["wallrun"])
        self.assertEqual("assets/anims/mixamo/player/vault_low.fbx", resolved["vaulting"])
        self.assertEqual(f"{runtime_dir}/swim.glb", resolved["swim"])

    def test_non_xbot_runtime_keeps_declared_base_anims_only(self):
        dummy = _BaseAnimDummy(
            {
                "model": "assets/models/hero/sherward/sherward_rework.glb",
                "base_anims": {
                    "idle": "assets/models/xbot/idle.glb",
                    "walk": "assets/models/xbot/walk.glb",
                    "run": "assets/models/xbot/run.glb",
                },
            },
            manifest_mapping={"dodging": "assets/anims/dodge_roll.fbx"},
        )

        resolved = dummy._resolve_base_anims()

        self.assertEqual(
            {
                "idle": "assets/models/xbot/idle.glb",
                "walk": "assets/models/xbot/walk.glb",
                "run": "assets/models/xbot/run.glb",
            },
            resolved,
        )


if __name__ == "__main__":
    unittest.main()
