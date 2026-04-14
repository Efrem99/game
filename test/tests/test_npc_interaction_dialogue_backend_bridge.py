import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.npc_interaction_manager import NPCInteractionManager


class _Backend:
    def __init__(self, files=None):
        self._files = dict(files or {})

    def load_file(self, rel_path):
        return self._files.get(str(rel_path), {})


class NpcInteractionDialogueBackendBridgeTests(unittest.TestCase):
    def test_load_dialogue_resolves_canonical_dialogues_backend_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            backend = _Backend(
                files={
                    "dialogues/backend_only_dialogue.json": {
                        "npc_id": "backend_only_npc",
                        "dialogue_tree": {"start": {"text": "Welcome."}},
                    }
                }
            )
            app = SimpleNamespace(
                data_mgr=SimpleNamespace(backend=backend, data_dir=root / "data"),
                project_root=str(root),
            )
            manager = object.__new__(NPCInteractionManager)
            manager.app = app

            payload = manager._load_dialogue("backend_only_dialogue")

            self.assertIsInstance(payload, dict)
            self.assertEqual("backend_only_npc", payload.get("npc_id"))


if __name__ == "__main__":
    unittest.main()
