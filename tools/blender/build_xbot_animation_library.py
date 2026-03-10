"""Build a single Blender animation library for XBot from many source clips.

Run:
  blender -b -P tools/blender/build_xbot_animation_library.py
  blender -b -P tools/blender/build_xbot_animation_library.py -- --export-glb
"""

import argparse
import json
import sys
from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Build XBot animation library blend.")
    parser.add_argument(
        "--base-model",
        default=str(PROJECT_ROOT / "assets" / "models" / "xbot" / "Xbot.glb"),
        help="Base rig model file (GLB/FBX).",
    )
    parser.add_argument(
        "--anims-dir",
        action="append",
        default=[
            str(PROJECT_ROOT / "assets" / "anims"),
            str(PROJECT_ROOT / "models" / "animations"),
        ],
        help="Animation source directory (repeatable).",
    )
    parser.add_argument(
        "--output-blend",
        default=str(PROJECT_ROOT / "assets" / "models" / "xbot" / "xbot_animation_library.blend"),
        help="Output blend file path.",
    )
    parser.add_argument(
        "--report-json",
        default=str(PROJECT_ROOT / "logs" / "xbot_animation_library_report.json"),
        help="JSON report path.",
    )
    parser.add_argument("--export-glb", action="store_true", help="Also export a combined GLB file.")
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in list(bpy.data.collections):
        if coll.name != "Collection":
            bpy.data.collections.remove(coll)


def import_model(path):
    token = str(path).lower()
    if token.endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=False)
        return
    bpy.ops.import_scene.gltf(filepath=str(path))


def import_anim(path):
    token = str(path).lower()
    if token.endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
        return
    bpy.ops.import_scene.gltf(filepath=str(path))


def find_armature():
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    return None


def collect_anim_files(dirs):
    out = []
    exts = {".fbx", ".glb", ".gltf"}
    for raw in dirs:
        base = Path(raw)
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() in exts:
                out.append(path.resolve())
    return sorted(set(out), key=lambda p: p.as_posix().lower())


def unique_action_name(stem):
    base = "".join(ch for ch in str(stem) if ch.isalnum() or ch in {"_", "-"}).strip("_-")
    if not base:
        base = "anim"
    candidate = base
    idx = 1
    while candidate in bpy.data.actions:
        idx += 1
        candidate = f"{base}_{idx}"
    return candidate


def remove_imported_objects(keep_names):
    for obj in list(bpy.data.objects):
        if obj.name in keep_names:
            continue
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            continue


def add_action_to_nla(armature, action):
    if armature.animation_data is None:
        armature.animation_data_create()
    track = armature.animation_data.nla_tracks.new()
    track.name = action.name
    start = int(action.frame_range[0]) if action.frame_range else 1
    track.strips.new(action.name, start, action)


def build_library(args):
    clear_scene()
    base_path = Path(args.base_model)
    if not base_path.exists():
        raise FileNotFoundError(f"Base model not found: {base_path}")

    import_model(base_path)
    base_arm = find_armature()
    if base_arm is None:
        raise RuntimeError("Base armature not found after import.")

    keep_names = {obj.name for obj in bpy.data.objects}
    anim_files = collect_anim_files(args.anims_dir)
    created = []
    skipped = []
    failed = []

    for anim_path in anim_files:
        before_actions = set(bpy.data.actions.keys())
        try:
            import_anim(anim_path)
        except Exception as exc:
            failed.append({"path": anim_path.as_posix(), "error": str(exc)})
            continue

        new_actions = [bpy.data.actions[name] for name in (set(bpy.data.actions.keys()) - before_actions)]
        if not new_actions:
            skipped.append(anim_path.as_posix())
            remove_imported_objects(keep_names)
            continue

        for action in new_actions:
            target_name = unique_action_name(anim_path.stem)
            action.name = target_name
            action.use_fake_user = True
            try:
                add_action_to_nla(base_arm, action)
            except Exception:
                pass
            created.append({"action": target_name, "source": anim_path.as_posix()})

        remove_imported_objects(keep_names)
        bpy.ops.outliner.orphans_purge(do_recursive=True)

    out_blend = Path(args.output_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    if args.export_glb:
        glb_path = out_blend.with_suffix(".glb")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in keep_names:
            if obj in bpy.data.objects:
                bpy.data.objects[obj].select_set(True)
        bpy.ops.export_scene.gltf(
            filepath=str(glb_path),
            export_format="GLB",
            use_selection=True,
            export_animations=True,
        )

    report = {
        "base_model": base_path.as_posix(),
        "output_blend": out_blend.as_posix(),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "created": created,
        "skipped_sources": skipped,
        "failed": failed,
    }
    report_path = Path(args.report_json)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[xbot-anim-lib] created={len(created)} skipped={len(skipped)} failed={len(failed)}")
    print(f"[xbot-anim-lib] blend={out_blend.as_posix()}")
    print(f"[xbot-anim-lib] report={report_path.as_posix()}")


def main():
    args = parse_args()
    build_library(args)


if __name__ == "__main__":
    main()
