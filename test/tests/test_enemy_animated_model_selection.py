import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import EnemyUnit


class EnemyAnimatedModelSelectionTests(unittest.TestCase):
    def test_build_external_model_skips_missing_candidate_paths_without_name_error(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.cfg = {"id": "goblin_raider_1", "kind": "goblin", "model": "assets/models/enemies/missing.glb", "scale": 1.0}
        unit.kind = "goblin"
        unit.id = "goblin_raider_1"
        unit.actor = None
        unit._anim_map = {}
        unit._anim_active_clip = ""
        unit._anim_active_state = ""
        unit._fallback_model_for_kind = lambda: ""
        unit._try_load_external_model = lambda *args, **kwargs: True

        with patch("entities.boss_manager.prefer_bam_path", side_effect=lambda token: token):
            self.assertFalse(EnemyUnit._build_external_model(unit))

    def test_kind_fallback_models_prefer_animated_standins(self):
        cases = {
            "fire_elemental": "assets/models/enemies/fire_elemental_animated.glb",
            "shadow": "assets/models/enemies/shadow_stalker_animated.glb",
            "goblin": "assets/models/enemies/goblin_raider_animated.glb",
        }
        for kind, expected in cases.items():
            unit = EnemyUnit.__new__(EnemyUnit)
            unit.kind = kind
            self.assertEqual(expected, EnemyUnit._fallback_model_for_kind(unit))

    def test_enemy_roster_uses_animated_models_for_non_boss_enemy_units(self):
        payload = json.loads((ROOT / "data" / "enemies" / "boss_roster.json").read_text(encoding="utf-8-sig"))
        rows = {
            str(row.get("id", "")).strip().lower(): row
            for row in payload.get("enemies", [])
            if isinstance(row, dict)
        }

        goblin = rows["goblin_raider_1"]
        fire_elemental = rows["fire_elemental_1"]
        shadow = rows["shadow_stalker_1"]

        self.assertEqual("assets/models/enemies/goblin_raider_animated.glb", goblin.get("model"))
        self.assertEqual("assets/models/enemies/fire_elemental_animated.glb", fire_elemental.get("model"))
        self.assertEqual("assets/models/enemies/shadow_stalker_animated.glb", shadow.get("model"))

    def test_enemy_roster_replaces_dragon_clip_names_with_humanoid_clip_names(self):
        payload = json.loads((ROOT / "data" / "enemies" / "boss_roster.json").read_text(encoding="utf-8-sig"))
        rows = {
            str(row.get("id", "")).strip().lower(): row
            for row in payload.get("enemies", [])
            if isinstance(row, dict)
        }

        fire_elemental = rows["fire_elemental_1"]
        shadow = rows["shadow_stalker_1"]

        for row in (fire_elemental, shadow):
            anims = row.get("animations", {})
            self.assertIsInstance(anims, dict)
            self.assertFalse(any("characterarmature|" in str(v).lower() for v in anims.values()))
            self.assertEqual("run", anims.get("chase"))
            self.assertEqual("headShake", anims.get("hit"))
            self.assertEqual("sad_pose", anims.get("dead"))


if __name__ == "__main__":
    unittest.main()
