import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world import sharuan_world
from world.sharuan_world import resolve_ultimate_sandbox_features


class _TreeAssetSelectionDummy:
    _leafy_tree_model_paths = sharuan_world.SharuanWorld._leafy_tree_model_paths
    _ultimate_sandbox_tree_model_paths = sharuan_world.SharuanWorld._ultimate_sandbox_tree_model_paths
    _ultimate_sandbox_portal_anchor_kwargs = sharuan_world.SharuanWorld._ultimate_sandbox_portal_anchor_kwargs

    def __init__(self):
        self.calls = []

    def _collect_world_model_paths(self, family, names):
        row = (str(family), tuple(str(name) for name in names))
        self.calls.append(row)
        return [f"assets/models/world/{family}/{name}" for name in names]


class SharuanWorldSandboxFeatureTests(unittest.TestCase):
    def test_world_source_initializes_stable_rng_for_procedural_variation(self):
        source = Path(sharuan_world.__file__).read_text(encoding="utf-8")

        self.assertIn("self._rng = random.Random(20260308)", source)

    def test_grass_pipeline_no_longer_depends_on_missing_instance_rng_helper(self):
        source = Path(sharuan_world.__file__).read_text(encoding="utf-8")

        self.assertNotIn("def _spawn_grass_tuft", source)
        self.assertIn("def _spawn_gpu_grass", source)
        self.assertIn("rng = random.Random(int(x + y * 1337))", source)

    def test_full_mode_enables_all_optional_sections(self):
        features = resolve_ultimate_sandbox_features("full")

        self.assertIn("sun", features)
        self.assertIn("traversal", features)
        self.assertIn("water", features)
        self.assertIn("vfx", features)
        self.assertIn("scenery", features)
        self.assertIn("stairs", features)
        self.assertIn("story", features)

    def test_minimal_mode_only_keeps_base(self):
        self.assertEqual(set(), resolve_ultimate_sandbox_features("minimal"))

    def test_custom_feature_list_is_resolved(self):
        features = resolve_ultimate_sandbox_features("water,story")

        self.assertEqual({"water", "story"}, features)

    def test_leafy_tree_pool_prefers_leaf_specific_assets_over_common_blob_canopies(self):
        world = _TreeAssetSelectionDummy()

        rows = world._leafy_tree_model_paths()

        self.assertEqual(
            [
                "assets/models/world/trees/oak_tree_1.glb",
                "assets/models/world/trees/oak_tree_2.glb",
                "assets/models/world/trees/oak_tree_3.glb",
                "assets/models/world/trees/birch_tree_1.glb",
                "assets/models/world/trees/willow_tree_1.glb",
            ],
            rows,
        )
        self.assertEqual(
            [
                (
                    "trees",
                    (
                        "oak_tree_1.glb",
                        "oak_tree_2.glb",
                        "oak_tree_3.glb",
                        "birch_tree_1.glb",
                        "willow_tree_1.glb",
                    ),
                )
            ],
            world.calls,
        )

    def test_ultimate_sandbox_portal_is_repeatable_runtime_jump_to_origin(self):
        world = _TreeAssetSelectionDummy()

        spec = world._ultimate_sandbox_portal_anchor_kwargs()

        self.assertEqual("Void Portal (Center)", spec.get("name"))
        self.assertEqual("Teleport to Origin", spec.get("hint"))
        self.assertEqual("portal_jump", spec.get("event_name"))
        self.assertEqual({"target": "ultimate_sandbox", "kind": "void"}, spec.get("event_payload"))
        self.assertFalse(bool(spec.get("single_use", True)))


if __name__ == "__main__":
    unittest.main()
