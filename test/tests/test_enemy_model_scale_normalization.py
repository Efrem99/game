import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import EnemyUnit


class EnemyModelScaleNormalizationTests(unittest.TestCase):
    def test_large_animated_enemy_assets_are_downscaled_to_world_units(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.kind = "goblin"

        corrected = EnemyUnit._normalize_external_model_scale(
            unit,
            "assets/models/enemies/goblin_raider_animated.glb",
            0.72,
            2977.0,
        )

        self.assertGreater(corrected, 0.0001)
        self.assertLess(corrected, 0.01)

    def test_regular_sized_static_enemy_assets_keep_authored_scale(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.kind = "golem"

        corrected = EnemyUnit._normalize_external_model_scale(
            unit,
            "assets/models/enemies/golem_boss.glb",
            1.42,
            2.0,
        )

        self.assertAlmostEqual(1.42, corrected, places=3)

    def test_large_enemy_assets_expose_visual_scale_ratio_for_offsets(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.kind = "goblin"

        ratio = EnemyUnit._resolved_visual_scale_ratio(
            unit,
            "assets/models/enemies/goblin_raider_animated.glb",
            0.72,
            2977.0,
        )

        self.assertGreater(ratio, 0.0)
        self.assertLess(ratio, 0.01)

    def test_regular_enemy_assets_keep_unity_visual_scale_ratio(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.kind = "golem"

        ratio = EnemyUnit._resolved_visual_scale_ratio(
            unit,
            "assets/models/enemies/golem_boss.glb",
            1.42,
            2.0,
        )

        self.assertAlmostEqual(1.0, ratio, places=4)

    def test_microscale_corrected_enemy_assets_are_rejected_for_live_runtime(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.kind = "shadow"

        safe = EnemyUnit._is_external_model_runtime_safe(
            unit,
            "assets/models/enemies/shadow_stalker_animated.glb",
            0.78,
            2977.36,
        )

        self.assertFalse(safe)

    def test_regular_enemy_assets_remain_runtime_safe(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.kind = "golem"

        safe = EnemyUnit._is_external_model_runtime_safe(
            unit,
            "assets/models/enemies/golem_boss.glb",
            1.42,
            2.0,
        )

        self.assertTrue(safe)

    def test_env_override_can_allow_unsafe_external_enemy_model_for_local_experiments(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.kind = "goblin"

        with patch.dict("os.environ", {"XBOT_ALLOW_UNSAFE_ENEMY_EXTERNAL_MODELS": "1"}, clear=False):
            safe = EnemyUnit._is_external_model_runtime_safe(
                unit,
                "assets/models/enemies/goblin_raider_animated.glb",
                0.72,
                2977.36,
            )

        self.assertTrue(safe)


if __name__ == "__main__":
    unittest.main()
