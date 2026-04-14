import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.preload_manager import PreloadManager
from utils.asset_pathing import cached_bam_path


class _LoaderStub:
    def __init__(self):
        self.calls = []

    def loadModel(self, path, callback=None, extraArgs=None):
        self.calls.append(str(path))
        if callback:
            callback(_ModelStub(), *(list(extraArgs or [])))


class _ModelStub:
    def __init__(self):
        self.writes = []

    def writeBamFile(self, filename):
        token = filename.to_os_specific() if hasattr(filename, "to_os_specific") else str(filename)
        self.writes.append(str(token))
        Path(token).parent.mkdir(parents=True, exist_ok=True)
        Path(token).write_text("bam-cache", encoding="utf-8")
        return True


class PreloadManagerCacheTests(unittest.TestCase):
    def test_item_loaded_does_not_persist_runtime_bam_cache_copy(self):
        prev_user_dir = os.environ.get("XBOT_USER_DATA_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["XBOT_USER_DATA_DIR"] = tmp
                root = Path(tmp)
                src = root / "assets" / "unit_model.glb"
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_text("glb", encoding="utf-8")
                app = types.SimpleNamespace(loader=_LoaderStub(), project_root=root)
                mgr = PreloadManager(app)
                model = _ModelStub()

                mgr._item_loaded(model, src.as_posix())

                cached = cached_bam_path(src.as_posix())
                self.assertIsNotNone(cached)
                self.assertFalse(cached.exists())
                self.assertEqual([], model.writes)
        finally:
            if prev_user_dir is None:
                os.environ.pop("XBOT_USER_DATA_DIR", None)
            else:
                os.environ["XBOT_USER_DATA_DIR"] = prev_user_dir

    def test_preload_assets_ignores_runtime_cached_bam_variant(self):
        prev_user_dir = os.environ.get("XBOT_USER_DATA_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["XBOT_USER_DATA_DIR"] = tmp
                root = Path(tmp)
                src = root / "assets" / "unit_model.glb"
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_text("glb", encoding="utf-8")
                cached = cached_bam_path(src.as_posix())
                self.assertIsNotNone(cached)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text("bam", encoding="utf-8")
                loader = _LoaderStub()
                app = types.SimpleNamespace(loader=loader, project_root=root)
                mgr = PreloadManager(app)

                mgr.preload_assets([src.as_posix()])

                self.assertEqual([src.as_posix()], loader.calls)
        finally:
            if prev_user_dir is None:
                os.environ.pop("XBOT_USER_DATA_DIR", None)
            else:
                os.environ["XBOT_USER_DATA_DIR"] = prev_user_dir

    def test_merge_with_cached_ignores_stale_runtime_sidecars_from_manifest(self):
        prev_user_dir = os.environ.get("XBOT_USER_DATA_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["XBOT_USER_DATA_DIR"] = tmp
                root = Path(tmp)
                src = root / "assets" / "unit_model.glb"
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_text("glb", encoding="utf-8")
                cached = cached_bam_path(src.as_posix())
                self.assertIsNotNone(cached)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text("bam", encoding="utf-8")
                manifest = root / "cache" / "preload_manifest.json"
                manifest.parent.mkdir(parents=True, exist_ok=True)
                manifest.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "hot_assets": [
                                {"path": cached.as_posix(), "score": 9.0},
                                {"path": src.as_posix(), "score": 8.0},
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                app = types.SimpleNamespace(loader=_LoaderStub(), project_root=root)

                mgr = PreloadManager(app)
                plan = mgr.merge_with_cached([], limit=10)

                self.assertEqual([src.as_posix()], plan)
        finally:
            if prev_user_dir is None:
                os.environ.pop("XBOT_USER_DATA_DIR", None)
            else:
                os.environ["XBOT_USER_DATA_DIR"] = prev_user_dir

    def test_save_cache_profile_omits_runtime_sidecars(self):
        prev_user_dir = os.environ.get("XBOT_USER_DATA_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["XBOT_USER_DATA_DIR"] = tmp
                root = Path(tmp)
                src = root / "assets" / "unit_model.glb"
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_text("glb", encoding="utf-8")
                cached = cached_bam_path(src.as_posix())
                self.assertIsNotNone(cached)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text("bam", encoding="utf-8")
                app = types.SimpleNamespace(loader=_LoaderStub(), project_root=root)

                mgr = PreloadManager(app)
                mgr._hot_scores = {
                    cached.as_posix(): 9.0,
                    src.as_posix(): 8.0,
                }
                mgr._save_cache_profile()

                payload = json.loads((root / "cache" / "preload_manifest.json").read_text(encoding="utf-8"))
                rows = [str(row.get("path")) for row in payload.get("hot_assets", [])]
                self.assertEqual([src.as_posix()], rows)
        finally:
            if prev_user_dir is None:
                os.environ.pop("XBOT_USER_DATA_DIR", None)
            else:
                os.environ["XBOT_USER_DATA_DIR"] = prev_user_dir


if __name__ == "__main__":
    unittest.main()
