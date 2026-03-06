"""
Build a baseline Shervard hero model from an existing rigged character in Blender.

This script is intended as a production helper, not a one-click final likeness generator.
It automates:
- base import
- target height normalization
- material tuning for realistic dark-fantasy look
- peaceful outfit props (doublet/shoulders/cloak + belt sword)
- optional head replacement with weight transfer
- export to GLB/FBX

Run example:
blender --background --python models/build_sherward_base.py -- \
  --base-model assets/models/xbot/Xbot.glb \
  --target-height 1.85 \
  --output-blend models/sherward_character.blend \
  --export-glb assets/models/hero/sherward/sherward.glb
"""

import argparse
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _log(msg):
    print(f"[SherwardBuilder] {msg}")


def parse_args():
    argv = []
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]

    parser = argparse.ArgumentParser(description="Build baseline Shervard hero model.")
    parser.add_argument("--base-model", required=True, help="Path to base rigged model (.glb/.gltf/.fbx/.obj).")
    parser.add_argument("--target-height", type=float, default=1.85, help="Target character height in meters.")
    parser.add_argument("--output-blend", required=True, help="Output .blend path.")
    parser.add_argument("--export-glb", default="", help="Optional output .glb path.")
    parser.add_argument("--export-fbx", default="", help="Optional output .fbx path.")

    parser.add_argument("--head-model", default="", help="Optional replacement head model (.glb/.fbx/.obj).")
    parser.add_argument("--head-bone", default="mixamorig:Head", help="Head bone name for head replacement.")
    parser.add_argument("--head-scale", type=float, default=1.0, help="Uniform scale for replacement head.")
    parser.add_argument("--hide-old-head", default="", help="Optional old head object name to hide.")

    parser.add_argument("--add-facial-control-hooks", action="store_true", help="Add non-deforming facial control bones.")
    return parser.parse_args(argv)


def _safe_make_dirs(path_str):
    if not path_str:
        return
    p = Path(path_str).resolve()
    parent = p.parent
    parent.mkdir(parents=True, exist_ok=True)


def _clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    if bpy.ops.outliner.orphans_purge.poll():
        for _ in range(3):
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def _import_scene_asset(filepath):
    path = Path(filepath)
    if not path.exists():
        raise RuntimeError(f"Base model does not exist: {filepath}")

    ext = path.suffix.lower()
    before = set(obj.name for obj in bpy.data.objects)

    if ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise RuntimeError(f"Unsupported base model format: {ext}")

    imported = [obj for obj in bpy.data.objects if obj.name not in before]
    if not imported:
        raise RuntimeError("Import did not create any objects.")
    return imported


def _find_armature(candidates):
    arms = [obj for obj in candidates if obj.type == "ARMATURE"]
    if not arms:
        arms = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not arms:
        raise RuntimeError("No armature found in scene.")
    arms.sort(key=lambda a: len(a.data.bones), reverse=True)
    return arms[0]


def _collect_skinned_meshes(armature):
    meshes = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if obj.parent == armature:
            meshes.append(obj)
            continue
        for mod in obj.modifiers:
            if mod.type == "ARMATURE" and mod.object == armature:
                meshes.append(obj)
                break
    if not meshes:
        raise RuntimeError("No skinned meshes found for selected armature.")
    return meshes


def _select_body_mesh(meshes):
    meshes = list(meshes)
    meshes.sort(key=lambda o: len(o.data.vertices), reverse=True)
    return meshes[0]


def _world_bounds_for_objects(objects):
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    for obj in objects:
        if obj.type not in {"MESH", "ARMATURE"}:
            continue
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            min_x = min(min_x, world.x)
            min_y = min(min_y, world.y)
            min_z = min(min_z, world.z)
            max_x = max(max_x, world.x)
            max_y = max(max_y, world.y)
            max_z = max(max_z, world.z)

    if min_x == float("inf"):
        raise RuntimeError("Failed to compute object bounds.")

    return (min_x, min_y, min_z), (max_x, max_y, max_z)


def _fit_character_height(armature, meshes, target_height_m):
    low, high = _world_bounds_for_objects([armature] + list(meshes))
    current_h = max(1e-5, float(high[2] - low[2]))
    factor = max(0.1, min(10.0, float(target_height_m) / current_h))
    armature.scale = (
        armature.scale.x * factor,
        armature.scale.y * factor,
        armature.scale.z * factor,
    )
    _log(f"Height fit: current={current_h:.4f}m factor={factor:.4f} target={target_height_m:.4f}m")


def _create_principled_material(name, base_color, roughness, metallic=0.0, sss=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = float(roughness)
    bsdf.inputs["Metallic"].default_value = float(metallic)
    bsdf.inputs["Subsurface Weight"].default_value = float(sss)
    if sss > 0.0:
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.25)

    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _tune_existing_material(mat):
    if mat is None or not mat.use_nodes:
        return
    token = mat.name.lower()
    for node in mat.node_tree.nodes:
        if node.type != "BSDF_PRINCIPLED":
            continue
        if "skin" in token or "face" in token:
            node.inputs["Roughness"].default_value = 0.48
            node.inputs["Subsurface Weight"].default_value = 0.12
            node.inputs["Subsurface Radius"].default_value = (1.0, 0.38, 0.28)
        elif "metal" in token or "steel" in token or "armor" in token:
            node.inputs["Metallic"].default_value = 0.9
            node.inputs["Roughness"].default_value = 0.62
        elif "leather" in token:
            node.inputs["Metallic"].default_value = 0.0
            node.inputs["Roughness"].default_value = 0.78
        elif "cloth" in token or "linen" in token:
            node.inputs["Metallic"].default_value = 0.0
            node.inputs["Roughness"].default_value = 0.86


def _ensure_material_slot(obj, mat):
    for slot in obj.material_slots:
        if slot.material == mat:
            return
    obj.data.materials.append(mat)


def _tune_character_materials(meshes):
    # Palette materials for generated outfit props.
    mat_skin = _create_principled_material(
        "Sherward_Skin",
        (0.59, 0.47, 0.42, 1.0),
        roughness=0.52,
        metallic=0.0,
        sss=0.12,
    )
    mat_linen = _create_principled_material(
        "Sherward_Linen",
        (0.40, 0.37, 0.33, 1.0),
        roughness=0.88,
        metallic=0.0,
    )
    mat_leather = _create_principled_material(
        "Sherward_Leather",
        (0.22, 0.14, 0.10, 1.0),
        roughness=0.80,
        metallic=0.0,
    )
    mat_steel = _create_principled_material(
        "Sherward_Steel",
        (0.46, 0.46, 0.48, 1.0),
        roughness=0.64,
        metallic=0.9,
    )
    mat_cloak = _create_principled_material(
        "Sherward_Cloak",
        (0.18, 0.16, 0.12, 1.0),
        roughness=0.90,
        metallic=0.0,
    )

    for obj in meshes:
        if obj.data.materials:
            for mat in obj.data.materials:
                _tune_existing_material(mat)
        else:
            _ensure_material_slot(obj, mat_skin)

    return {
        "skin": mat_skin,
        "linen": mat_linen,
        "leather": mat_leather,
        "steel": mat_steel,
        "cloak": mat_cloak,
    }


def _resolve_pose_bone(armature, names):
    for name in names:
        b = armature.pose.bones.get(name)
        if b:
            return b
    # case-insensitive fallback
    lower_map = {b.name.lower(): b for b in armature.pose.bones}
    for name in names:
        b = lower_map.get(str(name).lower())
        if b:
            return b
    return None


def _add_box(name, size_xyz, material):
    sx, sy, sz = size_xyz
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx * 0.5, sy * 0.5, sz * 0.5)
    obj.data.materials.append(material)
    return obj


def _parent_to_bone(obj, armature, bone_name, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0)):
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.location = tuple(float(v) for v in loc)
    obj.rotation_euler = tuple(float(v) for v in rot)


def _create_peace_outfit_props(armature, mats):
    spine = _resolve_pose_bone(armature, ["mixamorig:Spine2", "Spine2", "mixamorig:Spine1", "Spine1"])
    hips = _resolve_pose_bone(armature, ["mixamorig:Hips", "Hips"])
    shoulder_l = _resolve_pose_bone(armature, ["mixamorig:LeftShoulder", "LeftShoulder"])
    shoulder_r = _resolve_pose_bone(armature, ["mixamorig:RightShoulder", "RightShoulder"])
    if not spine or not hips:
        _log("Skipping outfit props: required bones were not found.")
        return

    # Leather doublet torso shell.
    doublet = _add_box("Sherward_Doublet", (0.48, 0.22, 0.62), mats["leather"])
    _parent_to_bone(doublet, armature, spine.name, loc=(0.0, 0.06, -0.02))

    # Lightweight metal inserts on shoulders.
    if shoulder_l:
        pauld_l = _add_box("Sherward_SteelInset_L", (0.18, 0.12, 0.16), mats["steel"])
        _parent_to_bone(pauld_l, armature, shoulder_l.name, loc=(0.02, 0.03, 0.00), rot=(0.0, 0.2, 0.0))
    if shoulder_r:
        pauld_r = _add_box("Sherward_SteelInset_R", (0.18, 0.12, 0.16), mats["steel"])
        _parent_to_bone(pauld_r, armature, shoulder_r.name, loc=(-0.02, 0.03, 0.00), rot=(0.0, -0.2, 0.0))

    # Linen underlayer hint.
    linen = _add_box("Sherward_LinenLayer", (0.46, 0.20, 0.56), mats["linen"])
    _parent_to_bone(linen, armature, spine.name, loc=(0.0, 0.04, -0.04))

    # Cloak to knee (simple panel).
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    cloak = bpy.context.active_object
    cloak.name = "Sherward_Cloak"
    cloak.scale = (0.52, 0.01, 0.86)
    cloak.rotation_euler = (1.5708, 0.0, 0.0)
    cloak.data.materials.append(mats["cloak"])
    _parent_to_bone(cloak, armature, spine.name, loc=(0.0, -0.16, -0.35), rot=(0.0, 0.0, 0.0))
    solid = cloak.modifiers.new("CloakSolid", "SOLIDIFY")
    solid.thickness = 0.006

    # Functional sword at belt.
    blade = _add_box("Sherward_SwordBlade", (0.05, 0.015, 0.92), mats["steel"])
    guard = _add_box("Sherward_SwordGuard", (0.24, 0.05, 0.04), mats["steel"])
    grip = _add_box("Sherward_SwordGrip", (0.045, 0.045, 0.24), mats["leather"])

    # Join sword pieces.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (blade, guard, grip):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = blade
    bpy.ops.object.join()
    sword = bpy.context.active_object
    sword.name = "Sherward_Sword"
    _parent_to_bone(sword, armature, hips.name, loc=(-0.16, -0.10, -0.10), rot=(-0.6, 0.4, -1.4))


def _import_head_mesh(filepath):
    if not filepath:
        return None
    path = Path(filepath)
    if not path.exists():
        raise RuntimeError(f"Replacement head does not exist: {filepath}")

    before = set(o.name for o in bpy.data.objects)
    ext = path.suffix.lower()
    if ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=False)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise RuntimeError(f"Unsupported head format: {ext}")

    imported_meshes = [o for o in bpy.data.objects if o.name not in before and o.type == "MESH"]
    if not imported_meshes:
        raise RuntimeError("No mesh imported from replacement head file.")
    imported_meshes.sort(key=lambda o: len(o.data.polygons), reverse=True)
    return imported_meshes[0]


def _align_object_to_pose_bone(obj, armature, bone_name):
    bone = armature.pose.bones.get(bone_name)
    if bone is None:
        raise RuntimeError(f"Head bone not found: {bone_name}")
    obj.matrix_world = armature.matrix_world @ bone.matrix


def _transfer_weights_from_body(head_obj, body_mesh):
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    head_obj.select_set(True)
    bpy.context.view_layer.objects.active = head_obj

    dt = head_obj.modifiers.new("HeadWeightTransfer", "DATA_TRANSFER")
    dt.object = body_mesh
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    bpy.ops.object.modifier_apply(modifier=dt.name)


def _bind_head_to_armature(head_obj, armature):
    arm_mod = None
    for mod in head_obj.modifiers:
        if mod.type == "ARMATURE":
            arm_mod = mod
            break
    if arm_mod is None:
        arm_mod = head_obj.modifiers.new("Armature", "ARMATURE")
    arm_mod.object = armature


def _optional_replace_head(args, armature, body_mesh):
    if not args.head_model:
        return
    new_head = _import_head_mesh(args.head_model)
    new_head.name = "Sherward_Head"
    _align_object_to_pose_bone(new_head, armature, args.head_bone)
    new_head.scale = (
        new_head.scale.x * args.head_scale,
        new_head.scale.y * args.head_scale,
        new_head.scale.z * args.head_scale,
    )
    _transfer_weights_from_body(new_head, body_mesh)
    _bind_head_to_armature(new_head, armature)

    if args.hide_old_head:
        old = bpy.data.objects.get(args.hide_old_head)
        if old:
            old.hide_set(True)
            old.hide_render = True
    _log("Replacement head integrated.")


def _add_facial_control_hooks(armature, head_bone_name):
    # Optional non-deforming helper bones for future facial rig wiring.
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")

    head = armature.data.edit_bones.get(head_bone_name)
    if head is None:
        for candidate in ["mixamorig:Head", "Head"]:
            head = armature.data.edit_bones.get(candidate)
            if head:
                break
    if head is None:
        bpy.ops.object.mode_set(mode="OBJECT")
        _log("Facial control hooks skipped: head bone not found.")
        return

    def _mk(name, offset_head, offset_tail):
        if armature.data.edit_bones.get(name):
            return
        b = armature.data.edit_bones.new(name)
        b.parent = head
        b.use_deform = False
        b.head = head.head + offset_head
        b.tail = head.head + offset_tail

    _mk("CTRL_Jaw", Vector((0.0, 0.01, -0.03)), Vector((0.0, 0.02, -0.08)))
    _mk("CTRL_Brow_L", Vector((0.03, 0.03, 0.05)), Vector((0.04, 0.04, 0.08)))
    _mk("CTRL_Brow_R", Vector((-0.03, 0.03, 0.05)), Vector((-0.04, 0.04, 0.08)))
    _mk("CTRL_LipCorner_L", Vector((0.04, 0.03, -0.01)), Vector((0.06, 0.04, -0.01)))
    _mk("CTRL_LipCorner_R", Vector((-0.04, 0.03, -0.01)), Vector((-0.06, 0.04, -0.01)))
    _mk("CTRL_EyeAim_L", Vector((0.03, 0.12, 0.03)), Vector((0.03, 0.20, 0.03)))
    _mk("CTRL_EyeAim_R", Vector((-0.03, 0.12, 0.03)), Vector((-0.03, 0.20, 0.03)))

    bpy.ops.object.mode_set(mode="OBJECT")
    _log("Added non-deforming facial control hooks.")


def _save_and_export(args):
    _safe_make_dirs(args.output_blend)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.output_blend).resolve()), compress=False)
    _log(f"Saved blend: {args.output_blend}")

    if args.export_glb:
        _safe_make_dirs(args.export_glb)
        bpy.ops.export_scene.gltf(
            filepath=str(Path(args.export_glb).resolve()),
            export_format="GLB",
            use_selection=False,
            export_apply=True,
            export_animations=True,
        )
        _log(f"Exported GLB: {args.export_glb}")

    if args.export_fbx:
        _safe_make_dirs(args.export_fbx)
        bpy.ops.export_scene.fbx(
            filepath=str(Path(args.export_fbx).resolve()),
            use_selection=False,
            bake_anim=True,
            add_leaf_bones=False,
        )
        _log(f"Exported FBX: {args.export_fbx}")


def main():
    args = parse_args()
    _log("Starting Shervard baseline build.")
    _clear_scene()

    imported = _import_scene_asset(args.base_model)
    armature = _find_armature(imported)
    meshes = _collect_skinned_meshes(armature)
    body = _select_body_mesh(meshes)

    _fit_character_height(armature, meshes, args.target_height)
    mats = _tune_character_materials(meshes)
    _create_peace_outfit_props(armature, mats)
    _optional_replace_head(args, armature, body)
    if args.add_facial_control_hooks:
        _add_facial_control_hooks(armature, args.head_bone)

    _save_and_export(args)
    _log("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _log(f"FAILED: {exc}")
        raise
