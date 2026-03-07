"""Build themed Panda3D .mf archives from data/asset_multifiles.json."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from panda3d.core import Filename, Multifile


def _norm(token: str) -> str:
    return str(token or "").strip().replace("\\", "/")


def _load_config(project_root: Path) -> dict:
    cfg_path = project_root / "data" / "asset_multifiles.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    return json.loads(cfg_path.read_text(encoding="utf-8-sig"))


def _expand_sources(project_root: Path, patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    seen = set()
    for raw in patterns:
        pat = _norm(raw)
        if not pat:
            continue
        matches = glob.glob(str(project_root / pat), recursive=True)
        for m in matches:
            p = Path(m)
            if not p.is_file():
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out


def _bundle_names(cfg: dict, selected_profiles: list[str], selected_bundles: list[str]) -> list[str]:
    names: list[str] = []
    seen = set()

    def add(name: str):
        token = str(name or "").strip()
        if not token or token in seen:
            return
        seen.add(token)
        names.append(token)

    if selected_bundles:
        for name in selected_bundles:
            add(name)

    profiles = cfg.get("profiles", {}) if isinstance(cfg.get("profiles"), dict) else {}
    if selected_profiles:
        for profile in selected_profiles:
            row = profiles.get(str(profile), {})
            if isinstance(row, dict):
                for b in row.get("bundles", []) if isinstance(row.get("bundles"), list) else []:
                    add(str(b))
            elif isinstance(row, list):
                for b in row:
                    add(str(b))

    if not names:
        bundles = cfg.get("bundles", {}) if isinstance(cfg.get("bundles"), dict) else {}
        for name in bundles.keys():
            add(str(name))

    return names


def _build_bundle(project_root: Path, root_dir: Path, bundle_name: str, bundle_cfg: dict) -> tuple[int, str]:
    mf_name = _norm(bundle_cfg.get("mf", ""))
    if not mf_name:
        return 0, "skipped (missing 'mf')"

    sources = bundle_cfg.get("sources", []) if isinstance(bundle_cfg.get("sources"), list) else []
    files = _expand_sources(project_root, [str(v) for v in sources])
    if not files:
        return 0, "skipped (no matched files)"

    root_dir.mkdir(parents=True, exist_ok=True)
    out_path = root_dir / mf_name

    mf = Multifile()
    out_fname = Filename.from_os_specific(str(out_path))
    out_fname.set_binary()
    if not mf.openWrite(out_fname):
        return 0, f"failed to open for write: {out_path}"

    added = 0
    for src in files:
        rel = src.resolve().relative_to(project_root.resolve()).as_posix()
        src_fname = Filename.from_os_specific(str(src))
        src_fname.set_binary()
        # Compression level 6 keeps archives compact while staying fast enough to build.
        if mf.addSubfile(rel, src_fname, 6):
            added += 1

    mf.flush()
    mf.close()
    return added, str(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build themed .mf archives")
    parser.add_argument("--project-root", default=".", help="Path to project root")
    parser.add_argument("--profile", action="append", default=[], help="Build bundles from profile name")
    parser.add_argument("--bundle", action="append", default=[], help="Build a specific bundle by name")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    cfg = _load_config(project_root)

    root_rel = _norm(cfg.get("multifile_root", "assets/mf")) or "assets/mf"
    out_root = project_root / root_rel

    bundles = cfg.get("bundles", {}) if isinstance(cfg.get("bundles"), dict) else {}
    names = _bundle_names(cfg, list(args.profile or []), list(args.bundle or []))

    total_files = 0
    built = 0
    def safe_text(value):
        try:
            return str(value).encode("ascii", "replace").decode("ascii")
        except Exception:
            return str(value)
    for name in names:
        row = bundles.get(name, {}) if isinstance(bundles.get(name), dict) else {}
        count, info = _build_bundle(project_root, out_root, name, row)
        if count > 0:
            built += 1
            total_files += count
            print(f"[OK] {safe_text(name)}: {count} files -> {safe_text(info)}")
        else:
            print(f"[SKIP] {safe_text(name)}: {safe_text(info)}")

    print(f"Done. bundles={built} files={total_files} out={safe_text(out_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
