"""Convert runtime model/animation assets to Panda3D BAM.

Default behavior is targeted, not global:
- Converts files referenced by core configs (player/enemy/dragon/world location meshes).
- Optionally scans selected roots when --include-roots is used.
"""

import argparse
import json
import sys
from pathlib import Path

from panda3d.core import Filename, loadPrcFileData


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (
    "assets/models",
    "assets/anims",
    "models/animations",
)
SUPPORTED_EXTS = {".glb", ".gltf", ".fbx", ".egg", ".obj"}


def _norm(path_token):
    return str(path_token or "").strip().replace("\\", "/")


def _read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _collect_paths_from_obj(obj, out):
    if isinstance(obj, str):
        token = _norm(obj)
        if token and Path(token).suffix.lower() in SUPPORTED_EXTS:
            out.add(token)
        return
    if isinstance(obj, dict):
        for value in obj.values():
            _collect_paths_from_obj(value, out)
        return
    if isinstance(obj, list):
        for value in obj:
            _collect_paths_from_obj(value, out)


def collect_config_sources():
    paths = set()
    config_files = (
        ROOT / "data" / "actors" / "player.json",
        ROOT / "data" / "actors" / "player_animations.json",
        ROOT / "data" / "actors" / "dragon_animations.json",
        ROOT / "data" / "world" / "location_meshes.json",
        ROOT / "data" / "enemies" / "dragon.json",
        ROOT / "data" / "enemies" / "golem_boss.json",
        ROOT / "data" / "enemies" / "fire_elemental.json",
        ROOT / "data" / "enemies" / "shadow_stalker.json",
        ROOT / "data" / "enemies" / "goblin_raider.json",
    )
    for cfg in config_files:
        payload = _read_json(cfg)
        _collect_paths_from_obj(payload, paths)
    return sorted(paths)


def collect_root_sources(roots, exts):
    out = set()
    ext_set = {f".{e.lower().lstrip('.')}" for e in exts}
    for raw in roots:
        base = ROOT / _norm(raw)
        if not base.exists():
            continue
        if base.is_file():
            if base.suffix.lower() in ext_set:
                out.add(base.resolve().as_posix())
            continue
        for ext in sorted(ext_set):
            for path in base.rglob(f"*{ext}"):
                out.add(path.resolve().as_posix())
    return sorted(out)


def _to_abs(token):
    path = Path(_norm(token))
    if not path.is_absolute():
        path = (ROOT / path)
    return path.resolve()


def _to_rel(path):
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return path.as_posix()


def _dst_bam(src):
    return src.with_suffix(".bam")


def _load_model(loader, path):
    fname = Filename.from_os_specific(str(path))
    return loader.loadModel(fname)


def convert_sources(sources, *, overwrite=False, dry_run=False, verify=False, limit=0):
    rows = []
    filtered = []
    for token in sources:
        src = _to_abs(token)
        if src.suffix.lower() == ".bam":
            continue
        if src.suffix.lower() not in SUPPORTED_EXTS:
            continue
        if not src.exists():
            rows.append(("missing", src, _dst_bam(src), "source_not_found"))
            continue
        filtered.append(src)

    if limit and limit > 0:
        filtered = filtered[: int(limit)]

    if dry_run:
        for src in filtered:
            dst = _dst_bam(src)
            state = "would_overwrite" if dst.exists() else "would_create"
            rows.append((state, src, dst, "dry_run"))
        return rows

    loadPrcFileData("", "window-type offscreen")
    loadPrcFileData("", "audio-library-name null")
    from direct.showbase.ShowBase import ShowBase  # lazy import

    base = ShowBase(windowType="offscreen")
    try:
        for src in filtered:
            dst = _dst_bam(src)
            if dst.exists() and (not overwrite):
                rows.append(("skip", src, dst, "exists"))
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                model = _load_model(base.loader, src)
                if not model or model.isEmpty():
                    rows.append(("error", src, dst, "loader_empty"))
                    continue
                ok = bool(model.writeBamFile(Filename.from_os_specific(str(dst))))
                model.removeNode()
                if not ok:
                    rows.append(("error", src, dst, "write_failed"))
                    continue
                if verify:
                    test = _load_model(base.loader, dst)
                    if not test or test.isEmpty():
                        rows.append(("error", src, dst, "verify_failed"))
                        continue
                    test.removeNode()
                rows.append(("ok", src, dst, "converted"))
            except Exception as exc:
                rows.append(("error", src, dst, str(exc)))
    finally:
        try:
            base.destroy()
        except Exception:
            pass
    return rows


def parse_args():
    parser = argparse.ArgumentParser(description="Convert runtime assets to BAM format.")
    parser.add_argument("--include-roots", action="store_true", help="Also scan root dirs for source assets.")
    parser.add_argument("--root", action="append", default=list(DEFAULT_ROOTS), help="Root dir (repeatable).")
    parser.add_argument("--ext", action="append", default=["glb", "gltf", "fbx"], help="Extensions to scan in roots.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing BAM files.")
    parser.add_argument("--verify", action="store_true", help="Verify written BAM can be loaded.")
    parser.add_argument("--dry-run", action="store_true", help="Preview operations without conversion.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of conversions.")
    parser.add_argument("--quiet", action="store_true", help="Print summary only.")
    return parser.parse_args()


def main():
    args = parse_args()
    sources = set(collect_config_sources())
    if args.include_roots:
        for token in collect_root_sources(args.root, args.ext):
            sources.add(token)
    ordered = sorted(sources)
    rows = convert_sources(
        ordered,
        overwrite=bool(args.overwrite),
        dry_run=bool(args.dry_run),
        verify=bool(args.verify),
        limit=int(args.limit or 0),
    )

    ok = 0
    skip = 0
    err = 0
    for status, src, dst, reason in rows:
        if status == "ok":
            ok += 1
        elif status in {"skip", "would_create", "would_overwrite"}:
            skip += 1
        else:
            err += 1
        if not args.quiet:
            print(f"[{status}] {_to_rel(src)} -> {_to_rel(dst)} ({reason})")

    print(f"[BAM] total={len(rows)} ok={ok} skipped={skip} errors={err}")
    if args.dry_run:
        return 0
    return 1 if err > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
