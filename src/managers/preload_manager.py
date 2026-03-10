import json
import time
from pathlib import Path

from panda3d.core import Filename, VirtualFileSystem

from utils.asset_pathing import prefer_bam_path
from utils.logger import logger
from utils.runtime_paths import runtime_file


class PreloadManager:
    """Handles asynchronous asset loading with runtime + persistent warm cache."""

    CACHE_REL_PATH = Path("cache") / "preload_manifest.json"
    MAX_HOT_ASSETS = 160

    def __init__(self, app):
        self.app = app
        self.loader = app.loader
        self.pending_count = 0
        self.total_count = 0
        self.finished = False
        self.on_complete = None
        self.assets = {}  # Runtime cache: {path: model/actor}
        self._pending_started = {}
        self._hot_scores = {}
        self._cache_path = runtime_file("cache", "preload_manifest.json")
        self._load_cache_profile()

    def _norm(self, path):
        return str(path or "").strip().replace("\\", "/")

    def _asset_exists(self, path):
        token = self._norm(path)
        if not token:
            return False
        root = Path(getattr(self.app, "project_root", "."))
        if (root / token).exists():
            return True
        try:
            vfs = VirtualFileSystem.get_global_ptr()
            fname = Filename(token)
            if vfs.exists(fname):
                return True
            fname_os = Filename.from_os_specific(token)
            return bool(vfs.exists(fname_os))
        except Exception:
            return False

    def _load_cache_profile(self):
        self._hot_scores = {}
        path = self._cache_path
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug(f"[PreloadManager] Failed to load cache profile: {exc}")
            return
        rows = payload.get("hot_assets", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset_path = self._norm(row.get("path"))
            if not asset_path:
                continue
            try:
                score = float(row.get("score", 0.0) or 0.0)
            except Exception:
                score = 0.0
            if score <= 0.0:
                continue
            self._hot_scores[asset_path] = score

    def _save_cache_profile(self):
        rows = []
        for path, score in sorted(
            self._hot_scores.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        ):
            if len(rows) >= self.MAX_HOT_ASSETS:
                break
            if not self._asset_exists(path):
                continue
            rows.append({"path": path, "score": round(float(score), 3)})
        payload = {
            "version": 1,
            "hot_assets": rows,
        }
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug(f"[PreloadManager] Failed to save cache profile: {exc}")

    def _bump_hot_score(self, path, weight=1.0):
        token = self._norm(path)
        if not token:
            return
        cur = float(self._hot_scores.get(token, 0.0) or 0.0)
        self._hot_scores[token] = cur + max(0.05, float(weight))

    def merge_with_cached(self, model_paths, limit=56):
        requested = []
        seen = set()
        for raw in list(model_paths or []):
            token = self._norm(prefer_bam_path(raw))
            if not token or token in seen:
                continue
            seen.add(token)
            if self._asset_exists(token):
                requested.append(token)

        hot = []
        for path, _score in sorted(
            self._hot_scores.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        ):
            if path in seen:
                continue
            if not self._asset_exists(path):
                continue
            hot.append(path)
            seen.add(path)

        plan = hot + requested
        max_count = max(1, int(limit or 1))
        if len(plan) > max_count:
            plan = plan[:max_count]
        return plan

    def preload_assets(self, model_paths, callback=None):
        self.on_complete = callback
        self.finished = False
        requested = []
        seen = set()
        for raw in list(model_paths or []):
            path = self._norm(prefer_bam_path(raw))
            if not path or path in seen:
                continue
            seen.add(path)
            if self._asset_exists(path):
                requested.append(path)

        remaining_paths = [p for p in requested if p not in self.assets]

        if not remaining_paths:
            logger.info("[PreloadManager] All requested assets already in cache.")
            self.finished = True
            if callback:
                callback()
            return

        self.total_count = len(remaining_paths)
        self.pending_count = self.total_count

        logger.info(f"[PreloadManager] Starting async preload of {self.total_count} new assets...")

        for path in remaining_paths:
            self._pending_started[path] = time.perf_counter()
            self.loader.loadModel(path, callback=self._item_loaded, extraArgs=[path])

    def preload_area(self, area_name, callback=None, extra_assets=None):
        """Preloads assets specific to a game area."""
        area_assets = {
            "SHARUAN": ["assets/models/xbot/Xbot.glb"],
            "DUNGEON": ["assets/models/props/torch.glb", "assets/models/props/chest.glb"],
        }
        paths = list(area_assets.get(str(area_name or "").upper(), []))
        if isinstance(extra_assets, (list, tuple)):
            for raw in extra_assets:
                token = self._norm(raw)
                if token:
                    paths.append(token)
        self.preload_assets(paths, callback)

    def is_cached(self, path):
        return self._norm(path) in self.assets

    def get_asset(self, path):
        return self.assets.get(self._norm(path))

    def _item_loaded(self, model, path):
        token = self._norm(path)
        if token:
            self.assets[token] = model
        self.pending_count -= 1

        started = self._pending_started.pop(token, None)
        elapsed = 0.0
        if started is not None:
            try:
                elapsed = max(0.0, float(time.perf_counter() - started))
            except Exception:
                elapsed = 0.0
        # Heavier load time -> slightly higher warm-cache score.
        weight = 1.0 + min(2.4, elapsed * 0.35)
        self._bump_hot_score(token, weight=weight)

        progress = self.get_progress()
        logger.debug(f"[PreloadManager] Loaded {token} ({progress*100:.1f}%)")

        if self.pending_count <= 0:
            self.finished = True
            self._save_cache_profile()
            logger.info("[PreloadManager] All assets preloaded.")
            if self.on_complete:
                self.on_complete()

    def get_progress(self):
        if self.total_count == 0:
            return 1.0
        return (self.total_count - self.pending_count) / self.total_count
