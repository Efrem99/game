import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.npc_manager import NPCManager


class NPCManagerDialogueProfileTests(unittest.TestCase):
    def setUp(self):
        self.manager = NPCManager(SimpleNamespace())

    def test_resolve_dialogue_path_prefers_explicit_dialogue(self):
        payload = {
            "name": "Eldrin",
            "role": "Elven Scout",
            "dialogue": "eldrin_recruitment",
        }

        path = self.manager._resolve_dialogue_path("eldrin_elf", payload)

        self.assertEqual("eldrin_recruitment", path)

    def test_resolve_dialogue_path_uses_guard_profile_for_guard_roles(self):
        payload = {
            "name": "Marcus",
            "role": "Gate Guard",
        }

        path = self.manager._resolve_dialogue_path("sandbox_guard", payload)

        self.assertEqual("guard_dialogue", path)

    def test_resolve_dialogue_path_uses_villager_profile_for_generic_worker_roles(self):
        payload = {
            "name": "Old Tom",
            "role": "Head Miner",
        }

        path = self.manager._resolve_dialogue_path("miner0", payload)

        self.assertEqual("villager_dialogue", path)


if __name__ == "__main__":
    unittest.main()
