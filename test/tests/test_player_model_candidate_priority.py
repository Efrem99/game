import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _CandidateDummy:
    _resolve_player_model_candidates = Player._resolve_player_model_candidates
    _resolve_base_anims = Player._resolve_base_anims

    def __init__(self):
        self._cfg = {
            "model": "assets/models/hero/sherward/sherward.glb",
            "model_candidates": [
                "assets/models/hero/sherward/sherward.glb",
                "assets/models/xbot/Xbot.glb",
            ],
            "fallback_model": "assets/models/xbot/Xbot.glb",
            "prefer_animation_compatible": True,
            "base_anims": {
                "idle": "assets/models/xbot/idle.glb",
                "walk": "assets/models/xbot/walk.glb",
                "run": "assets/models/xbot/run.glb",
            },
        }
        self.app = type("AppStub", (), {"_test_profile": "movement"})()

    def _player_model_config(self):
        return dict(self._cfg)


class PlayerModelCandidatePriorityTests(unittest.TestCase):
    def test_core_runtime_keeps_compatible_hero_first_when_xbot_base_anims_are_used(self):
        dummy = _CandidateDummy()
        dummy._cfg["model"] = "assets/models/hero/sherward/sherward_rework_full_corrective.glb"
        dummy._cfg["model_candidates"] = [
            "assets/models/hero/sherward/sherward_rework_full_corrective.glb",
            "assets/models/hero/sherward/sherward_rework.glb",
            "assets/models/hero/sherward/sherward.glb",
            "assets/models/xbot/Xbot.glb",
        ]
        dummy._cfg["prefer_animation_compatible"] = False
        dummy.app = type("AppStub", (), {"_test_profile": ""})()

        with patch("entities.player.HAS_CORE", True):
            candidates = dummy._resolve_player_model_candidates()

        self.assertTrue(candidates)
        self.assertIn("sherward", candidates[0].lower())

    def test_sherward_glb_still_stays_first_when_it_contains_the_full_xbot_rig(self):
        dummy = _CandidateDummy()
        candidates = dummy._resolve_player_model_candidates()
        self.assertTrue(candidates)
        self.assertIn("sherward", candidates[0].lower())

    def test_non_core_runtime_prioritizes_xbot_even_when_config_prefers_hero_visual(self):
        dummy = _CandidateDummy()
        dummy._cfg["prefer_animation_compatible"] = False

        with patch("entities.player.HAS_CORE", False):
            candidates = dummy._resolve_player_model_candidates()

        self.assertTrue(candidates)
        self.assertIn("xbot", candidates[0].lower())

    def test_runtime_test_profile_keeps_compatible_hero_first_when_core_is_available(self):
        dummy = _CandidateDummy()
        dummy._cfg["model"] = "assets/models/hero/sherward/sherward_rework_full_corrective.glb"
        dummy._cfg["model_candidates"] = [
            "assets/models/hero/sherward/sherward_rework_full_corrective.glb",
            "assets/models/hero/sherward/sherward_rework.glb",
            "assets/models/hero/sherward/sherward.glb",
            "assets/models/xbot/Xbot.glb",
        ]
        dummy._cfg["prefer_animation_compatible"] = False

        with patch("entities.player.HAS_CORE", True):
            candidates = dummy._resolve_player_model_candidates()

        self.assertTrue(candidates)
        self.assertIn("sherward", candidates[0].lower())

    def test_explicit_hero_runtime_override_keeps_hero_first(self):
        dummy = _CandidateDummy()
        dummy._cfg["model"] = "assets/models/hero/sherward/sherward_rework_full_corrective.glb"
        dummy._cfg["model_candidates"] = [
            "assets/models/hero/sherward/sherward_rework_full_corrective.glb",
            "assets/models/hero/sherward/sherward_rework.glb",
            "assets/models/hero/sherward/sherward.glb",
            "assets/models/xbot/Xbot.glb",
        ]
        dummy._cfg["prefer_animation_compatible"] = False
        dummy.app = type("AppStub", (), {"_test_profile": ""})()

        with patch("entities.player.HAS_CORE", True), patch.dict(
            "os.environ", {"XBOT_PREFER_HERO_RUNTIME_MODEL": "1"}, clear=False
        ):
            candidates = dummy._resolve_player_model_candidates()

        self.assertTrue(candidates)
        self.assertIn("sherward", candidates[0].lower())

    def test_incompatible_hero_candidate_still_yields_xbot_first(self):
        dummy = _CandidateDummy()
        dummy._cfg["model"] = "assets/models/hero/placeholder/not_xbot_compatible.glb"
        dummy._cfg["model_candidates"] = [
            "assets/models/hero/placeholder/not_xbot_compatible.glb",
            "assets/models/xbot/Xbot.glb",
        ]
        dummy._cfg["prefer_animation_compatible"] = False

        with patch("entities.player.HAS_CORE", True):
            candidates = dummy._resolve_player_model_candidates()

        self.assertTrue(candidates)
        self.assertIn("xbot", candidates[0].lower())

    def test_candidate_resolution_skips_placeholder_blender_exports(self):
        dummy = _CandidateDummy()
        placeholder = "assets/models/hero/sherward/sherward_RESTORED_v2.glb"
        corrective = "assets/models/hero/sherward/sherward_rework_full_corrective.glb"
        dummy._cfg["model"] = placeholder
        dummy._cfg["model_candidates"] = [
            placeholder,
            corrective,
            "assets/models/xbot/Xbot.glb",
        ]
        dummy._cfg["prefer_animation_compatible"] = False
        dummy.app = type("AppStub", (), {"_test_profile": ""})()

        with patch("entities.player.HAS_CORE", True), patch(
            "entities.player._glb_contains_xbot_skin",
            side_effect=lambda path, _ref: "full_corrective" in str(path).lower(),
        ), patch(
            "entities.player._looks_like_blender_placeholder_export",
            side_effect=lambda path: str(path).endswith("sherward_RESTORED_v2.glb"),
            create=True,
        ):
            candidates = dummy._resolve_player_model_candidates()

        self.assertNotIn(placeholder, candidates)
        self.assertTrue(candidates)
        self.assertEqual(corrective, candidates[0])


if __name__ == "__main__":
    unittest.main()
