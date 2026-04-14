import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DialoguePayloadDefaultsTests(unittest.TestCase):
    def test_villager_dialogue_is_linear_for_runtime_smoke_paths(self):
        payload = json.loads(
            (ROOT / "data" / "dialogues" / "villager_dialogue.json").read_text(encoding="utf-8")
        )

        tree = payload.get("dialogue_tree", {})
        start = tree.get("start", {})
        player_start = tree.get("player_reply_start", {})
        about = tree.get("about_sharuan", {})
        player_trouble = tree.get("player_reply_trouble", {})
        trouble = tree.get("trouble", {})
        player_farewell = tree.get("player_reply_farewell", {})

        self.assertEqual([], start.get("choices"))
        self.assertEqual("player_reply_start", start.get("next_node"))
        self.assertEqual("npc", start.get("camera"))
        self.assertEqual([], player_start.get("choices"))
        self.assertEqual("about_sharuan", player_start.get("next_node"))
        self.assertEqual("player", player_start.get("camera"))
        self.assertEqual([], about.get("choices"))
        self.assertEqual("player_reply_trouble", about.get("next_node"))
        self.assertEqual("npc", about.get("camera"))
        self.assertEqual([], player_trouble.get("choices"))
        self.assertEqual("trouble", player_trouble.get("next_node"))
        self.assertEqual("player", player_trouble.get("camera"))
        self.assertEqual([], trouble.get("choices"))
        self.assertEqual("player_reply_farewell", trouble.get("next_node"))
        self.assertEqual("npc", trouble.get("camera"))
        self.assertEqual([], player_farewell.get("choices"))
        self.assertEqual("farewell", player_farewell.get("next_node"))
        self.assertEqual("player", player_farewell.get("camera"))


if __name__ == "__main__":
    unittest.main()
