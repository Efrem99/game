"""Interactive utility to inspect 3D models and animation clips quickly."""

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from utils.asset_animation_viewer import (  # noqa: E402
    build_default_animation_map,
    build_default_model_list,
    normalize_asset_token,
    resolve_existing_asset_paths,
    run_asset_animation_viewer,
)


def _prepend_unique(rows, values):
    out = list(rows)
    for token in reversed(list(values or [])):
        clean = normalize_asset_token(token)
        if not clean:
            continue
        if clean in out:
            out.remove(clean)
        out.insert(0, clean)
    return out


def parse_args():
    parser = argparse.ArgumentParser(description="Asset + animation viewer for Panda3D project.")
    parser.add_argument("--model", action="append", default=[], help="Model path to prioritize (repeatable).")
    parser.add_argument("--model-root", action="append", default=[], help="Extra model scan root (repeatable).")
    parser.add_argument("--anim-root", action="append", default=[], help="Extra animation scan root (repeatable).")
    parser.add_argument("--start-model", default="", help="Model path suffix to open first.")
    parser.add_argument("--start-anim", default="", help="Animation key to open first.")
    parser.add_argument("--max-models", type=int, default=160, help="Clamp model scan count (0 = no clamp).")
    parser.add_argument("--max-anims", type=int, default=260, help="Clamp animation scan count (0 = no clamp).")
    parser.add_argument("--autoplay", action="store_true", help="Auto-switch clips every --clip-seconds.")
    parser.add_argument("--clip-seconds", type=float, default=3.6, help="Autoplay clip time.")
    parser.add_argument("--parkour-debug", dest="parkour_debug", action="store_true", help="Show minimalist parkour debug course + IK preview hooks.")
    parser.add_argument("--no-parkour-debug", dest="parkour_debug", action="store_false", help="Disable parkour debug course and IK preview hooks.")
    parser.add_argument("--list", action="store_true", help="Print resolved model/animation catalog and exit.")
    parser.set_defaults(parkour_debug=True)
    return parser.parse_args()


def _with_extra_roots(default_roots, extra_roots):
    roots = list(default_roots)
    for token in extra_roots or []:
        clean = normalize_asset_token(token)
        if clean and clean not in roots:
            roots.append(clean)
    return roots


def _print_catalog(models, animation_map):
    print(f"[Viewer] models={len(models)} animations={len(animation_map)}")
    print("[Viewer] Model sample:")
    for idx, token in enumerate(models[:20], start=1):
        print(f"{idx:02d}. {token}")
    print("[Viewer] Animation sample:")
    for idx, (key, token) in enumerate(list(animation_map.items())[:40], start=1):
        print(f"{idx:02d}. {key} -> {token}")


def main():
    args = parse_args()

    model_roots = _with_extra_roots(("assets/models", "models"), args.model_root)
    anim_roots = _with_extra_roots(("assets/anims", "models/animations", "assets/models/xbot"), args.anim_root)

    models = build_default_model_list(ROOT, scan_roots=model_roots, limit=int(args.max_models or 0))
    explicit_models = resolve_existing_asset_paths(ROOT, args.model)
    if explicit_models:
        models = _prepend_unique(models, explicit_models)

    animation_map = build_default_animation_map(ROOT, scan_roots=anim_roots, limit=int(args.max_anims or 0))

    if args.list:
        _print_catalog(models, animation_map)
        return 0

    if not models:
        print("[Viewer] No models were found. Use --model or --model-root.")
        return 2

    return run_asset_animation_viewer(
        ROOT,
        models,
        animation_map,
        start_model=args.start_model,
        start_anim=args.start_anim,
        autoplay=bool(args.autoplay),
        clip_seconds=float(args.clip_seconds),
        parkour_debug=bool(args.parkour_debug),
    )


if __name__ == "__main__":
    raise SystemExit(main())
