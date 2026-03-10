"""Asset path helpers with BAM-first runtime preference for Panda3D."""

from pathlib import Path


SOURCE_MODEL_EXTS = (".glb", ".gltf", ".fbx", ".egg", ".obj")


def normalize_asset_path(path_token):
    return str(path_token or "").strip().replace("\\", "/")


def prefer_bam_path(path_token, *, prefer_bam=True):
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


def existing_variants(path_token, *, prefer_bam=True):
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

