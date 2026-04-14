"""Helpers for data-driven handcrafted location mesh entries."""


def _to_triplet(value, fallback):
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            return fallback
    return fallback


def _to_scale_triplet(value):
    if isinstance(value, (int, float)):
        s = float(value)
        return (s, s, s)
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            return (1.0, 1.0, 1.0)
    return (1.0, 1.0, 1.0)


def normalize_location_mesh_entries(layout):
    payload = layout if isinstance(layout, dict) else {}
    raw_rows = payload.get("location_meshes", [])
    if not isinstance(raw_rows, list):
        return []

    out = []
    for idx, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            continue
        if row.get("enabled", True) is False:
            continue
        model = str(row.get("model", "") or "").strip().replace("\\", "/")
        if not model:
            continue
        mesh_id = str(row.get("id", "") or "").strip() or f"location_mesh_{idx}"
        pos = _to_triplet(row.get("pos", row.get("position")), (0.0, 0.0, 0.0))
        hpr = _to_triplet(row.get("hpr", row.get("rotation")), (0.0, 0.0, 0.0))
        scale = _to_scale_triplet(row.get("scale", 1.0))
        label = str(row.get("label", row.get("name", mesh_id)) or mesh_id).strip() or mesh_id
        is_platform = bool(row.get("is_platform", row.get("collider", True)))
        out.append(
            {
                "id": mesh_id,
                "model": model,
                "pos": pos,
                "hpr": hpr,
                "scale": scale,
                "label": label,
                "is_platform": is_platform,
                "batch_static": bool(row.get("batch_static", True)),
                "never_cull": bool(row.get("never_cull", False)),
                "hlod_enabled": bool(row.get("hlod_enabled", True)),
                "location": str(row.get("location", row.get("zone", "")) or "").strip(),
                "hlod_group": str(row.get("hlod_group", row.get("cluster", "")) or "").strip(),
                "lod_profile": str(row.get("lod_profile", "") or "").strip(),
                "impostor_model": str(row.get("impostor_model", "") or "").strip().replace("\\", "/"),
            }
        )
    return out
