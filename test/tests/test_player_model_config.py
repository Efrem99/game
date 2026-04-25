import json
import unittest
from pathlib import Path

from panda3d.core import Filename, getModelPath, loadPrcFileData
from direct.actor.Actor import Actor

ROOT = Path(__file__).resolve().parents[2]
loadPrcFileData("", "window-type none")


class PlayerModelConfigTests(unittest.TestCase):
    def test_player_config_keeps_primary_sherward_model_first_for_runtime(self):
        payload = json.loads((ROOT / "data" / "actors" / "player.json").read_text(encoding="utf-8-sig"))
        player = payload.get("player", payload) if isinstance(payload, dict) else {}
        candidates = player.get("model_candidates", []) if isinstance(player, dict) else []

        self.assertIsInstance(player, dict)
        self.assertEqual(
            "assets/models/hero/sherward/sherward.glb",
            str(player.get("model", "") or "").strip(),
        )
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
        self.assertEqual(str(player.get("model", "") or "").strip(), str(candidates[0] or "").strip())
        self.assertFalse(bool(player.get("prefer_animation_compatible", True)))
        self.assertGreater(float(player.get("scale", 0.0) or 0.0), 0.5)

    def test_player_config_excludes_known_placeholder_sherward_exports(self):
        payload = json.loads((ROOT / "data" / "actors" / "player.json").read_text(encoding="utf-8-sig"))
        player = payload.get("player", payload) if isinstance(payload, dict) else {}
        candidates = player.get("model_candidates", []) if isinstance(player, dict) else []

        self.assertIsInstance(candidates, list)
        self.assertNotIn(
            "assets/models/hero/sherward/sherward_RESTORED_v2.glb",
            candidates,
        )
        self.assertNotIn(
            "assets/models/hero/sherward/sherward_SUPREME.glb",
            candidates,
        )
        self.assertNotIn(
            "assets/models/hero/sherward/sherward_SUPREME_MUSCLE.glb",
            candidates,
        )

    def test_primary_player_model_loads_with_runtime_base_anims(self):
        payload = json.loads((ROOT / "data" / "actors" / "player.json").read_text(encoding="utf-8-sig"))
        player = payload.get("player", payload) if isinstance(payload, dict) else {}
        model = str(player.get("model", "") or "").strip()
        base_anims = player.get("base_anims", {}) if isinstance(player, dict) else {}

        self.assertTrue(model)
        self.assertIsInstance(base_anims, dict)
        workspace_root = Path.cwd()
        if not (workspace_root / "data" / "actors" / "player.json").exists():
            workspace_root = ROOT
        model_path = getModelPath()
        for path in (
            workspace_root,
            workspace_root / "assets",
            workspace_root / "assets" / "models",
            workspace_root / "assets" / "anims",
        ):
            model_path.appendDirectory(Filename.from_os_specific(str(path)))
        actor = Actor(model, dict(base_anims))
        try:
            self.assertGreater(len(actor.getAnimNames()), 0)
        finally:
            try:
                actor.cleanup()
                actor.removeNode()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
