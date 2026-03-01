from utils.logger import logger

class PreloadManager:
    """Handles asynchronous asset loading with caching to prevent UI freezing."""

    def __init__(self, app):
        self.app = app
        self.loader = app.loader
        self.pending_count = 0
        self.total_count = 0
        self.finished = False
        self.on_complete = None
        self.assets = {} # Cache: {path: model/actor}

    def preload_assets(self, model_paths, callback=None):
        self.on_complete = callback

        # Filter out already cached assets
        remaining_paths = [p for p in model_paths if p not in self.assets]

        if not remaining_paths:
            logger.info("[PreloadManager] All requested assets already in cache.")
            self.finished = True
            if callback: callback()
            return

        self.total_count = len(remaining_paths)
        self.pending_count = self.total_count
        self.finished = False

        logger.info(f"[PreloadManager] Starting async preload of {self.total_count} new assets...")

        for path in remaining_paths:
            self.loader.loadModel(path, callback=self._item_loaded, extraArgs=[path])

    def preload_area(self, area_name, callback=None):
        """Preloads assets specific to a game area."""
        # Example area asset mapping (this could come from DataManager)
        area_assets = {
            "SHARUAN": ["assets/models/xbot/Xbot.glb"],
            "DUNGEON": ["assets/models/props/torch.glb", "assets/models/props/chest.glb"]
        }
        paths = area_assets.get(area_name.upper(), [])
        self.preload_assets(paths, callback)

    def is_cached(self, path):
        return path in self.assets

    def get_asset(self, path):
        return self.assets.get(path)

    def _item_loaded(self, model, path):
        self.assets[path] = model
        self.pending_count -= 1

        progress = self.get_progress()
        logger.debug(f"[PreloadManager] Loaded {path} ({progress*100:.1f}%)")

        if self.pending_count <= 0:
            self.finished = True
            logger.info("[PreloadManager] All assets preloaded.")
            if self.on_complete:
                self.on_complete()

    def get_progress(self):
        if self.total_count == 0: return 1.0
        return (self.total_count - self.pending_count) / self.total_count
