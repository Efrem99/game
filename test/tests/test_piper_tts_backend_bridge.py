import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.piper_tts_manager import PiperTTSManager


class _Backend:
    def __init__(self, files=None):
        self._files = dict(files or {})

    def load_file(self, rel_path):
        return self._files.get(str(rel_path), {})


class PiperTtsBackendBridgeTests(unittest.TestCase):
    def test_load_profiles_reads_from_backend_before_disk_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            backend = _Backend(
                files={
                    "audio/piper_voices.json": {
                        "default": {"model": "en_GB-alan-medium.onnx", "speed": 1.0},
                        "merchant": {"model": "en_US-amy-low.onnx", "speed": 1.05},
                    }
                }
            )
            app = SimpleNamespace(
                data_mgr=SimpleNamespace(backend=backend, data_dir=root / "data"),
                project_root=str(root),
            )
            manager = object.__new__(PiperTTSManager)
            manager.app = app
            manager.root = str(root)
            manager.binary_path = str(root / "tools" / "piper" / "piper.exe")
            manager.models_dir = str(root / "tools" / "piper" / "models")
            manager.cache_dir = str(root / "cache" / "audio" / "piper")
            manager.profiles_path = str(root / "data" / "audio" / "piper_voices.json")
            manager._profiles = {}

            manager._load_profiles()

            self.assertEqual("en_US-amy-low.onnx", manager._profiles["merchant"]["model"])


if __name__ == "__main__":
    unittest.main()
