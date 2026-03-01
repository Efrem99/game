"""
Head swap helper for Blender.

Run example:
blender --background models/character.blend --python models/blender_head_swap.py -- \
  --armature XBot_Armature \
  --body Character_Body \
  --head-bone mixamorig:Head \
  --new-head "C:/path/to/new_head.glb" \
  --new-head-name NewHead \
  --old-head Character_Head \
  --output models/character_headswap.blend \
  --export-glb models/character_headswap.glb
"""

import argparse
import os
import sys

import bpy
from mathutils import Matrix


def parse_args():
    argv = []
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]

    parser = argparse.ArgumentParser(description="Swap character head mesh and transfer rig weights.")
    parser.add_argument("--armature", required=True, help="Armature object name.")
    parser.add_argument("--body", required=True, help="Body mesh object name (weight source).")
    parser.add_argument("--head-bone", default="mixamorig:Head", help="Bone to align new head to.")
    parser.add_argument("--new-head", required=True, help="Path to new head mesh (glb/fbx/obj).")
    parser.add_argument("--new-head-name", default="Head_New", help="Name for imported head object.")
    parser.add_argument("--old-head", default="", help="Optional old head object name to hide.")
    parser.add_argument("--scale", type=float, default=1.0, help="Uniform scale for new head.")
    parser.add_argument("--join-body", action="store_true", help="Join new head into body mesh.")
    parser.add_argument("--output", required=True, help="Output blend file path.")
    parser.add_argument("--export-glb", default="", help="Optional GLB export path.")
    parser.add_argument("--export-fbx", default="", help="Optional FBX export path.")
    return parser.parse_args(argv)


def deselect_all():
    bpy.ops.object.select_all(action="DESELECT")


def import_mesh(filepath):
    before = set(o.name for o in bpy.data.objects)
    ext = os.path.splitext(filepath)[1].lower()
    if ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=filepath, use_anim=False)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=filepath)
    else:
        raise RuntimeError(f"Unsupported head format: {ext}")

    imported = [o for o in bpy.data.objects if o.name not in before and o.type == "MESH"]
    if not imported:
        raise RuntimeError("No mesh was imported from the new head file.")

    # Choose the most detailed imported mesh by polygon count.
    imported.sort(key=lambda o: len(o.data.polygons), reverse=True)
    return imported[0]


def ensure_object_mode():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def align_to_head_bone(head_obj, armature_obj, head_bone_name, scale=1.0):
    pbone = armature_obj.pose.bones.get(head_bone_name)
    if pbone is None:
        raise RuntimeError(f"Head bone not found: {head_bone_name}")

    bone_world = armature_obj.matrix_world @ pbone.matrix
    head_obj.matrix_world = Matrix.Translation(bone_world.to_translation())
    head_obj.rotation_euler = bone_world.to_euler()
    head_obj.scale = (scale, scale, scale)


def transfer_weights_from_body(head_obj, body_obj):
    ensure_object_mode()
    deselect_all()
    head_obj.select_set(True)
    bpy.context.view_layer.objects.active = head_obj

    dt = head_obj.modifiers.new(name="HeadWeightTransfer", type="DATA_TRANSFER")
    dt.object = body_obj
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    bpy.ops.object.modifier_apply(modifier=dt.name)


def ensure_armature_binding(head_obj, armature_obj):
    mod = None
    for m in head_obj.modifiers:
        if m.type == "ARMATURE":
            mod = m
            break
    if mod is None:
        mod = head_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = armature_obj


def hide_old_head(old_head_name):
    if not old_head_name:
        return
    old = bpy.data.objects.get(old_head_name)
    if old:
        old.hide_set(True)
        old.hide_render = True


def join_head_with_body(head_obj, body_obj):
    ensure_object_mode()
    deselect_all()
    body_obj.select_set(True)
    head_obj.select_set(True)
    bpy.context.view_layer.objects.active = body_obj
    bpy.ops.object.join()
    return body_obj


def save_and_export(args, active_obj):
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=False)

    if args.export_glb:
        glb_dir = os.path.dirname(args.export_glb)
        if glb_dir:
            os.makedirs(glb_dir, exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=args.export_glb,
            export_format="GLB",
            use_selection=False,
            export_apply=True,
            export_animations=True,
        )

    if args.export_fbx:
        fbx_dir = os.path.dirname(args.export_fbx)
        if fbx_dir:
            os.makedirs(fbx_dir, exist_ok=True)
        bpy.ops.export_scene.fbx(
            filepath=args.export_fbx,
            use_selection=False,
            bake_anim=True,
            add_leaf_bones=False,
        )

    print(f"[HeadSwap] Done. Output: {args.output}")
    if args.export_glb:
        print(f"[HeadSwap] GLB: {args.export_glb}")
    if args.export_fbx:
        print(f"[HeadSwap] FBX: {args.export_fbx}")


def main():
    args = parse_args()
    ensure_object_mode()

    if not os.path.exists(args.new_head):
        raise RuntimeError(f"New head mesh does not exist: {args.new_head}")

    armature = bpy.data.objects.get(args.armature)
    if armature is None or armature.type != "ARMATURE":
        raise RuntimeError(f"Armature not found or not ARMATURE: {args.armature}")

    body = bpy.data.objects.get(args.body)
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Body mesh not found or not MESH: {args.body}")

    imported_head = import_mesh(args.new_head)
    imported_head.name = args.new_head_name
    align_to_head_bone(imported_head, armature, args.head_bone, args.scale)
    transfer_weights_from_body(imported_head, body)
    ensure_armature_binding(imported_head, armature)
    hide_old_head(args.old_head)

    active_obj = imported_head
    if args.join_body:
        active_obj = join_head_with_body(imported_head, body)

    save_and_export(args, active_obj)


if __name__ == "__main__":
    main()
