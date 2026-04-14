import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player


class _PlayerBackendDummy:
    _load_player_state_animation_tokens = Player._load_player_state_animation_tokens
    _load_actor_animation_overrides = Player._load_actor_animation_overrides
    _load_manifest_loop_hints = Player._load_manifest_loop_hints
    _normalize_anim_key = Player._normalize_anim_key
    _alias_animation_key = Player._alias_animation_key

    def __init__(self):
        self.data_mgr = SimpleNamespace(
            get_player_state_config=lambda: {
                "states": [{"name": "running", "animation": "run_blade"}],
                "transitions": [{"from": ["idle"], "to": "running", "trigger": "move"}],
                "rules": [{"from": ["*"], "to": "running", "condition": "speed_gt_1"}],
            },
            get_player_animation_manifest=lambda: {
                "player": {"running": ["run_blade"], "casting": {"animation": "cast_fast"}},
                "manifest": {
                    "sources": [
                        {"key": "run_blade", "loop": True, "path": "assets/models/xbot/xbot_transition_pack.glb"},
                        {"key": "cast_fast", "loop": False, "path": "assets/anims/mixamo/player/cast_fire.fbx"},
                    ]
                },
            },
        )
        self._state_defs = {}
        self._state_transitions = []
        self._state_rules = []


class _PlayerConfigBackendDummy:
    _player_model_config = Player._player_model_config

    def __init__(self):
        self.app = SimpleNamespace()
        self.data_mgr = SimpleNamespace()


class _PlayerManifestBackendDummy:
    _load_manifest_animation_sources = Player._load_manifest_animation_sources

    def __init__(self):
        self.data_mgr = SimpleNamespace(
            get_player_animation_manifest=lambda: {
                "manifest": {
                    "strict_runtime_sources": True,
                    "sources": [
                        {
                            "key": "cast_fast",
                            "path": "assets/anims/mixamo/player/cast_fire.fbx",
                            "loop": False,
                        }
                    ],
                }
            }
        )


class PlayerBackendBridgeTests(unittest.TestCase):
    def test_state_animation_tokens_read_from_data_manager(self):
        dummy = _PlayerBackendDummy()

        mapping = dummy._load_player_state_animation_tokens()

        self.assertEqual("run_blade", mapping["running"])
        self.assertEqual("running", dummy._state_transitions[0]["to"])
        self.assertEqual("running", dummy._state_rules[0]["to"])

    def test_animation_overrides_and_loop_hints_read_from_data_manager_manifest(self):
        dummy = _PlayerBackendDummy()

        overrides = dummy._load_actor_animation_overrides()
        hints = dummy._load_manifest_loop_hints()

        self.assertEqual(["run_blade"], overrides["running"])
        self.assertEqual(["cast_fast"], overrides["casting"])
        self.assertTrue(hints["runblade"])
        self.assertFalse(hints["castfast"])

    def test_player_model_config_falls_back_to_runtime_data_access_when_getter_is_missing(self):
        dummy = _PlayerConfigBackendDummy()
        payload = {
            "player": {
                "model": "assets/models/hero/sherward/sherward_rework_full_corrective.glb",
                "scale": 0.92,
            }
        }

        with patch("pathlib.Path.exists", return_value=False), patch(
            "entities.player.load_data_file",
            return_value=payload,
        ):
            cfg = dummy._player_model_config()

        self.assertEqual(
            "assets/models/hero/sherward/sherward_rework_full_corrective.glb",
            cfg["model"],
        )
        self.assertEqual(0.92, cfg["scale"])

    def test_manifest_animation_sources_use_backend_payload_before_disk_path(self):
        dummy = _PlayerManifestBackendDummy()

        with patch(
            "entities.player.load_player_manifest_sources",
            return_value=({"cast_fast": "assets/anims/mixamo/player/cast_fire.fbx"}, True, []),
        ) as mocked_loader:
            mapping, strict_mode = dummy._load_manifest_animation_sources()

        self.assertTrue(strict_mode)
        self.assertIn("cast_fast", mapping)
        self.assertEqual(
            dummy.data_mgr.get_player_animation_manifest(),
            mocked_loader.call_args.kwargs.get("manifest_payload"),
        )
        self.assertTrue(mocked_loader.call_args.kwargs.get("require_existing_files"))


if __name__ == "__main__":
    unittest.main()
