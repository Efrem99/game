import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from utils.asset_animation_viewer import (  # noqa: E402
    asset_load_candidates,
    build_clip_option_labels,
    build_default_animation_map,
    build_default_model_list,
    option_index_for_anim_key,
    resolve_existing_asset_paths,
)


def _touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"stub")


class AssetAnimationViewerCatalogTests(unittest.TestCase):
    def test_clip_option_label_helpers_keep_index_mapping(self):
        keys = ["idle", "walk", "attack_heavy"]
        labels = build_clip_option_labels(keys)
        self.assertEqual(["01. idle", "02. walk", "03. attack_heavy"], labels)
        self.assertEqual(0, option_index_for_anim_key(keys, "idle"))
        self.assertEqual(2, option_index_for_anim_key(keys, "attack_heavy"))
        self.assertEqual(-1, option_index_for_anim_key(keys, "missing"))

    def test_resolve_existing_asset_paths_dedupes_and_normalizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_a = root / "assets" / "models" / "hero" / "hero.glb"
            model_b = root / "assets" / "models" / "npc" / "npc.fbx"
            _touch(model_a)
            _touch(model_b)

            rows = resolve_existing_asset_paths(
                root,
                [
                    "assets/models/hero/hero.glb",
                    "assets\\models\\hero\\hero.glb",
                    str(model_b),
                    "missing/path.glb",
                ],
            )

            self.assertEqual(
                [
                    "assets/models/hero/hero.glb",
                    "assets/models/npc/npc.fbx",
                ],
                rows,
            )

    def test_asset_load_candidates_prefers_bam_then_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "assets" / "models" / "hero" / "hero.glb"
            bam = src.with_suffix(".bam")
            _touch(src)
            _touch(bam)

            rows = asset_load_candidates(root, "assets/models/hero/hero.glb")
            self.assertEqual(
                [
                    "assets/models/hero/hero.bam",
                    "assets/models/hero/hero.glb",
                ],
                rows,
            )

    def test_build_default_model_list_prioritizes_player_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _touch(root / "assets" / "models" / "hero" / "sherward.glb")
            _touch(root / "assets" / "models" / "xbot" / "Xbot.glb")
            _touch(root / "assets" / "models" / "props" / "crate.glb")

            player_cfg = {
                "player": {
                    "model": "assets/models/hero/sherward.glb",
                    "model_candidates": [
                        "assets/models/hero/sherward.glb",
                        "assets/models/xbot/Xbot.glb",
                    ],
                    "fallback_model": "assets/models/xbot/Xbot.glb",
                }
            }
            path = root / "data" / "actors" / "player.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(player_cfg), encoding="utf-8")

            models = build_default_model_list(root)

            self.assertGreaterEqual(len(models), 3)
            self.assertEqual("assets/models/hero/sherward.glb", models[0])
            self.assertEqual("assets/models/xbot/Xbot.glb", models[1])
            self.assertIn("assets/models/props/crate.glb", models)

    def test_build_default_animation_map_merges_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _touch(root / "assets" / "models" / "xbot" / "idle.glb")
            _touch(root / "assets" / "models" / "xbot" / "walk.glb")
            _touch(root / "assets" / "models" / "xbot" / "run.glb")
            _touch(root / "assets" / "anims" / "attack_sword_slash.fbx")
            _touch(root / "models" / "animations" / "jump_takeoff.fbx")

            player_cfg = {
                "player": {
                    "base_anims": {
                        "idle": "assets/models/xbot/idle.glb",
                        "walk": "assets/models/xbot/walk.glb",
                        "run": "assets/models/xbot/run.glb",
                    }
                }
            }
            manifest_cfg = {
                "manifest": {
                    "sources": [
                        {"key": "attacking", "path": "assets/anims/attack_sword_slash.fbx"},
                    ]
                }
            }
            player_path = root / "data" / "actors" / "player.json"
            manifest_path = root / "data" / "actors" / "player_animations.json"
            player_path.parent.mkdir(parents=True, exist_ok=True)
            player_path.write_text(json.dumps(player_cfg), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest_cfg), encoding="utf-8")

            animation_map = build_default_animation_map(root)

            self.assertEqual("assets/models/xbot/idle.glb", animation_map.get("idle"))
            self.assertEqual("assets/models/xbot/walk.glb", animation_map.get("walk"))
            self.assertEqual("assets/models/xbot/run.glb", animation_map.get("run"))
            self.assertEqual(
                "assets/anims/attack_sword_slash.fbx",
                animation_map.get("attacking"),
            )
            self.assertIn(
                "models/animations/jump_takeoff.fbx",
                set(animation_map.values()),
            )


if __name__ == "__main__":
    unittest.main()
