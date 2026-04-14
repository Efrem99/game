import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.dialogue_manager import DialogueManager


class _Backend:
    def __init__(self, recursive=None, files=None):
        self._recursive = dict(recursive or {})
        self._files = dict(files or {})

    def load_recursive(self, rel_dir):
        return dict(self._recursive.get(str(rel_dir), {}))

    def load_file(self, rel_path):
        return self._files.get(str(rel_path), {})


class DialogueManagerBackendBridgeTests(unittest.TestCase):
    def test_load_dialogue_data_reads_from_backend_dialogues_dir(self):
        backend = _Backend(
            recursive={
                "dialogues": {
                    "merchant": {
                        "npc_name": "Merchant Aldric",
                        "dialogue_tree": {"start": {"text": "Welcome."}},
                    }
                }
            }
        )
        app = SimpleNamespace(
            data_mgr=SimpleNamespace(backend=backend, data_dir=ROOT / "data"),
            project_root=str(ROOT),
        )
        manager = object.__new__(DialogueManager)
        manager.app = app
        manager._dialogue_data = {}

        manager._load_dialogue_data()

        self.assertIn("merchant", manager._dialogue_data)
        self.assertEqual("Merchant Aldric", manager._dialogue_data["merchant"]["npc_name"])

    def test_load_dialogue_data_logs_human_readable_count_message(self):
        backend = _Backend(
            recursive={
                "dialogues": {
                    "merchant": {
                        "npc_name": "Merchant Aldric",
                        "dialogue_tree": {"start": {"text": "Welcome."}},
                    }
                }
            }
        )
        app = SimpleNamespace(
            data_mgr=SimpleNamespace(backend=backend, data_dir=ROOT / "data"),
            project_root=str(ROOT),
        )
        manager = object.__new__(DialogueManager)
        manager.app = app
        manager._dialogue_data = {}

        with patch("managers.dialogue_manager.logger.info") as log_info:
            manager._load_dialogue_data()

        messages = [str(call.args[0]) for call in log_info.call_args_list if call.args]
        self.assertTrue(
            any("Загружено диалоговых записей" in message for message in messages),
            msg=messages,
        )


if __name__ == "__main__":
    unittest.main()
