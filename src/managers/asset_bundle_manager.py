import json
from pathlib import Path

from panda3d.core import Filename, Multifile, VirtualFileSystem

from utils.logger import logger


class AssetBundleManager:
    """Mounts thematic .mf bundles and returns prewarm targets for active contexts."""

    def __init__(self, app):
        self.app = app
        self._vfs = VirtualFileSystem.get_global_ptr()
        self._bundles = {}
        self._profiles = {}
        self._location_profiles = {}
        self._root_dir = "assets/mf"
        self._mount_point = "/"
        self._mounted = {}
        self._active_profiles = set()
        self._load_config()

    def _load_config(self):
        cfg = {}
        dm_cfg = getattr(getattr(self.app, "data_mgr", None), "asset_multifiles_config", None)
        if isinstance(dm_cfg, dict) and dm_cfg:
            cfg = dm_cfg
        else:
            path = Path(getattr(self.app, "project_root", ".")) / "data" / "asset_multifiles.json"
            if path.exists():
                try:
                    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
                except Exception as exc:
                    logger.warning(f"[AssetBundle] Failed to read config: {exc}")
                    cfg = {}

        if not isinstance(cfg, dict):
            cfg = {}

        self._root_dir = str(cfg.get("multifile_root", "assets/mf") or "assets/mf").strip().replace("\\", "/")
        self._mount_point = str(cfg.get("mount_point", "/") or "/").strip() or "/"

        bundles = cfg.get("bundles", {})
        self._bundles = bundles if isinstance(bundles, dict) else {}

        profiles = cfg.get("profiles", {})
        self._profiles = profiles if isinstance(profiles, dict) else {}

        loc_profiles = cfg.get("location_profiles", {})
        self._location_profiles = loc_profiles if isinstance(loc_profiles, dict) else {}

    def _project_path(self, rel_path):
        root = Path(getattr(self.app, "project_root", "."))
        return root / str(rel_path or "")

    def _normalize_assets(self, values):
        out = []
        seen = set()
        for raw in list(values or []):
            token = str(raw or "").strip().replace("\\", "/")
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out

    def _bundle_def(self, bundle_name):
        token = str(bundle_name or "").strip()
        row = self._bundles.get(token, {}) if isinstance(self._bundles, dict) else {}
        return row if isinstance(row, dict) else {}

    def _bundle_mf_path(self, bundle_name):
        row = self._bundle_def(bundle_name)
        mf_name = str(row.get("mf", "") or "").strip()
        if not mf_name:
            return None
        return self._project_path(f"{self._root_dir}/{mf_name}")

    def mount_bundle(self, bundle_name):
        token = str(bundle_name or "").strip()
        if not token:
            return False
        if token in self._mounted:
            return True

        mf_path = self._bundle_mf_path(token)
        if not mf_path or not mf_path.exists():
            logger.debug(f"[AssetBundle] Missing bundle file for '{token}'")
            return False

        mf = Multifile()
        fname = Filename.from_os_specific(str(mf_path))
        if not mf.openRead(fname):
            logger.warning(f"[AssetBundle] Failed to open multifile: {mf_path}")
            return False

        mounted = False
        try:
            mounted = bool(self._vfs.mount(mf, self._mount_point, 0))
        except Exception as exc:
            logger.warning(f"[AssetBundle] Mount failed for {mf_path}: {exc}")
            mounted = False

        if mounted:
            self._mounted[token] = mf
            logger.info(f"[AssetBundle] Mounted '{token}' ({mf_path.name})")
            return True

        return False

    def _profile_bundles(self, profile_name):
        token = str(profile_name or "").strip()
        row = self._profiles.get(token, []) if isinstance(self._profiles, dict) else []
        if isinstance(row, dict):
            row = row.get("bundles", [])
        if not isinstance(row, list):
            return []
        return [str(v).strip() for v in row if str(v or "").strip()]

    def _profile_prewarm(self, profile_name):
        token = str(profile_name or "").strip()
        row = self._profiles.get(token, {}) if isinstance(self._profiles, dict) else {}
        if isinstance(row, dict):
            return self._normalize_assets(row.get("prewarm", []))
        return []

    def activate_profile(self, profile_name):
        token = str(profile_name or "").strip()
        if not token:
            return []

        prewarm = []
        prewarm.extend(self._profile_prewarm(token))

        for bundle_name in self._profile_bundles(token):
            self.mount_bundle(bundle_name)
            row = self._bundle_def(bundle_name)
            prewarm.extend(self._normalize_assets(row.get("prewarm", [])))

        self._active_profiles.add(token)
        return self._normalize_assets(prewarm)

    def activate_for_location(self, loc_name):
        token = str(loc_name or "").strip().lower()
        if not token:
            return []

        profile = str(self._location_profiles.get(token, token) or "").strip()
        if not profile:
            return []
        return self.activate_profile(profile)

    def active_profiles(self):
        return sorted(self._active_profiles)
