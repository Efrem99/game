"""Asset path helpers that prefer authored BAM variants without runtime sidecars."""

import hashlib
from pathlib import Path

from utils.runtime_paths import project_root, user_data_root


SOURCE_MODEL_EXTS = (".glb", ".gltf", ".fbx", ".egg", ".obj")


def normalize_asset_path(path_token):
    return str(path_token or "").strip().replace("\\", "/")


def _source_path_for_token(path_token):
    path = normalize_asset_path(path_token)
    if not path:
        return None
    src = Path(path)
    if src.is_absolute():
        return src
    return project_root() / src


def cached_bam_path(path_token, *, cache_root=None):
    path = normalize_asset_path(path_token)
    if not path:
        return None

    src = _source_path_for_token(path)
    if src is None:
        return None
    ext = src.suffix.lower()
    if ext == ".bam":
        return None
    if ext and ext not in SOURCE_MODEL_EXTS:
        return None
    if not src.exists():
        return None

    try:
        stat = src.stat()
        resolved = src.resolve()
        digest_input = f"{resolved.as_posix()}|{int(stat.st_mtime_ns)}|{int(stat.st_size)}"
    except Exception:
        return None

    digest = hashlib.md5(digest_input.encode("utf-8")).hexdigest()[:16]
    cache_dir = Path(cache_root) if cache_root is not None else (user_data_root() / "cache" / "asset_bam")
    return cache_dir / f"{src.stem}-{digest}.bam"


def prefer_bam_path(path_token, *, prefer_bam=True, cache_root=None):
    path = normalize_asset_path(path_token)
    if not path:
        return ""
    if not prefer_bam:
        return path

    src = Path(path)
    ext = src.suffix.lower()
    if ext == ".bam":
        return path
    if ext and ext not in SOURCE_MODEL_EXTS:
        return path

    bam_candidate = src.with_suffix(".bam")
    if bam_candidate.exists():
        return bam_candidate.as_posix()
    return path


def existing_variants(path_token, *, prefer_bam=True, cache_root=None):
    """Return existing path variants in load order."""
    path = normalize_asset_path(path_token)
    if not path:
        return []
    src = Path(path)
    variants = []

    def _add(candidate):
        token = normalize_asset_path(candidate)
        if token and token not in variants and Path(token).exists():
            variants.append(token)

    if prefer_bam:
        _add(src.with_suffix(".bam").as_posix())
    _add(path)
    return variants
