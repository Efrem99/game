"""
Refine Shervard hero likeness from references in Blender.

This script is a second-pass helper after `build_sherward_base.py`.
It automates:
- loading existing scene/base model
- reference image board setup (front/side/three-quarter)
- review cameras and neutral lights
- realistic material tuning hooks (skin/eyes/stubble)
- subtle facial asymmetry shape key
- optional exports

Run example:
blender --background --python models/refine_sherward_likeness.py -- \
  --scene-blend models/sherward_character.blend \
  --references-dir data/characters/sherward_refs \
  --output-blend models/sherward_character_likeness.blend \
  --export-glb assets/models/hero/sherward/sherward.glb \
  --eye-color dark_green \
  --asymmetry 0.35 \
  --stubble-strength 0.45
"""

import argparse
import os
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector


def _log(msg):
    print(f"[SherwardLikeness] {msg}")


def parse_args():
    argv = []
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]

    parser = argparse.ArgumentParser(description="Refine Shervard likeness from references.")
    parser.add_argument("--scene-blend", default="", help="Existing .blend scene to open.")
    parser.add_argument("--base-model", default="", help="Base model to import if scene-blend not provided.")
    parser.add_argument("--armature", default="", help="Optional armature object name.")
    parser.add_argument("--hero-mesh", default="", help="Optional main body mesh object name.")
    parser.add_argument("--head-mesh", default="", help="Optional head mesh object name.")
    parser.add_argument("--target-height", type=float, default=1.85, help="Target height in meters.")

    parser.add_argument("--references-dir", default="", help="Directory with reference images.")
    parser.add_argument("--front-ref", default="", help="Explicit front reference image path.")
    parser.add_argument("--side-ref", default="", help="Explicit side reference image path.")
    parser.add_argument("--threeq-ref", default="", help="Explicit three-quarter reference image path.")

    parser.add_argument("--eye-color", default="dark_green", help="dark_green | gray_brown | r,g,b")
    parser.add_argument("--asymmetry", type=float, default=0.25, help="0..1 subtle facial asymmetry amount.")
    parser.add_argument("--stubble-strength", type=float, default=0.35, help="0..1 stubble tint intensity.")
    parser.add_argument("--stubble-mask", default="", help="Optional stubble mask texture image.")

    parser.add_argument("--create-review-cameras", action="store_true", help="Create portrait/profile/fullbody cameras.")
    parser.add_argument("--create-neutral-lights", action="store_true", help="Create neutral 3-point lights.")

    parser.add_argument("--output-blend", required=True, help="Output .blend path.")
    parser.add_argument("--export-glb", default="", help="Optional .glb export path.")
    parser.add_argument("--export-fbx", default="", help="Optional .fbx export path.")
    return parser.parse_args(argv)


def _safe_make_dirs(path_str):
    if not path_str:
        return
    p = Path(path_str).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)


def _open_or_import_scene(args):
    if args.scene_blend:
        blend = Path(args.scene_blend)
        if not blend.exists():
            raise RuntimeError(f"scene-blend does not exist: {args.scene_blend}")
        bpy.ops.wm.open_mainfile(filepath=str(blend.resolve()))
        _log(f"Opened blend: {args.scene_blend}")
        return

    if not args.base_model:
        raise RuntimeError("Provide --scene-blend or --base-model")

    base = Path(args.base_model)
    if not base.exists():
        raise RuntimeError(f"base-model does not exist: {args.base_model}")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    ext = base.suffix.lower()
    if ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(base.resolve()))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(base.resolve()), use_anim=True)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(base.resolve()))
    else:
        raise RuntimeError(f"Unsupported base-model format: {ext}")
    _log(f"Imported base model: {args.base_model}")


def _find_armature(args):
    if args.armature:
        obj = bpy.data.objects.get(args.armature)
        if obj and obj.type == "ARMATURE":
            return obj

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
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
    return meshes


def _select_main_mesh(args, skinned):
    if args.hero_mesh:
        obj = bpy.data.objects.get(args.hero_mesh)
        if obj and obj.type == "MESH":
            return obj
    if not skinned:
        raise RuntimeError("No skinned meshes found.")
    ordered = sorted(skinned, key=lambda o: len(o.data.vertices), reverse=True)
    return ordered[0]


def _select_head_mesh(args, skinned, fallback_main):
    if args.head_mesh:
        obj = bpy.data.objects.get(args.head_mesh)
        if obj and obj.type == "MESH":
            return obj
    token_hits = []
    for obj in skinned:
        name = obj.name.lower()
        if "head" in name or "face" in name:
            token_hits.append(obj)
    if token_hits:
        token_hits.sort(key=lambda o: len(o.data.vertices), reverse=True)
        return token_hits[0]
    return fallback_main


def _world_bounds(objects):
    min_v = Vector((float("inf"), float("inf"), float("inf")))
    max_v = Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in objects:
        if obj.type not in {"MESH", "ARMATURE"}:
            continue
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            min_v.x = min(min_v.x, w.x)
            min_v.y = min(min_v.y, w.y)
            min_v.z = min(min_v.z, w.z)
            max_v.x = max(max_v.x, w.x)
            max_v.y = max(max_v.y, w.y)
            max_v.z = max(max_v.z, w.z)
    if min_v.x == float("inf"):
        raise RuntimeError("Failed to compute bounds.")
    return min_v, max_v


def _normalize_height(armature, objects, target_h):
    lo, hi = _world_bounds([armature] + list(objects))
    h = max(1e-5, hi.z - lo.z)
    factor = max(0.1, min(10.0, float(target_h) / h))
    armature.scale = (
        armature.scale.x * factor,
        armature.scale.y * factor,
        armature.scale.z * factor,
    )
    _log(f"Height normalized: current={h:.4f}m target={target_h:.4f}m factor={factor:.4f}")


def _find_principled_nodes(material):
    if material is None or not material.use_nodes:
        return []
    return [n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"]


def _parse_eye_color(token):
    lookup = {
        "dark_green": (0.14, 0.23, 0.14, 1.0),
        "gray_brown": (0.24, 0.21, 0.17, 1.0),
    }
    t = str(token or "").strip().lower()
    if t in lookup:
        return lookup[t]
    parts = [p.strip() for p in t.split(",")]
    if len(parts) == 3:
        try:
            r, g, b = [max(0.0, min(1.0, float(v))) for v in parts]
            return (r, g, b, 1.0)
        except Exception:
            pass
    return lookup["dark_green"]


def _apply_realism_material_tuning(meshes, eye_color_rgba, stubble_strength):
    ss = max(0.0, min(1.0, float(stubble_strength)))
    for obj in meshes:
        for mat in obj.data.materials:
            if mat is None:
                continue
            lname = mat.name.lower()
            bsdfs = _find_principled_nodes(mat)
            for bsdf in bsdfs:
                if "skin" in lname or "face" in lname or "head" in lname:
                    bsdf.inputs["Roughness"].default_value = 0.50 + (0.08 * ss)
                    bsdf.inputs["Subsurface Weight"].default_value = 0.14
                    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.40, 0.30)
                elif "metal" in lname or "steel" in lname or "armor" in lname:
                    bsdf.inputs["Metallic"].default_value = 0.88
                    bsdf.inputs["Roughness"].default_value = 0.60
                elif "leather" in lname:
                    bsdf.inputs["Metallic"].default_value = 0.0
                    bsdf.inputs["Roughness"].default_value = 0.78
                elif "cloth" in lname or "linen" in lname or "cloak" in lname:
                    bsdf.inputs["Metallic"].default_value = 0.0
                    bsdf.inputs["Roughness"].default_value = 0.88

                if "eye" in lname or "iris" in lname:
                    bsdf.inputs["Base Color"].default_value = eye_color_rgba
                    bsdf.inputs["Roughness"].default_value = 0.22
                    bsdf.inputs["IOR"].default_value = 1.40


def _apply_stubble_mask(head_obj, stubble_mask_path, strength):
    if not stubble_mask_path:
        return
    tex_path = Path(stubble_mask_path)
    if not tex_path.exists():
        _log(f"Stubble mask not found: {stubble_mask_path}")
        return
    ss = max(0.0, min(1.0, float(strength)))
    if ss <= 0.0:
        return

    image = bpy.data.images.load(str(tex_path.resolve()), check_existing=True)
    for mat in head_obj.data.materials:
        if mat is None or not mat.use_nodes:
            continue
        lname = mat.name.lower()
        if "skin" not in lname and "face" not in lname and "head" not in lname:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdfs = _find_principled_nodes(mat)
        if not bsdfs:
            continue
        bsdf = bsdfs[0]

        tex = nodes.new("ShaderNodeTexImage")
        tex.name = "Sherward_StubbleMask"
        tex.image = image
        tex.interpolation = "Smart"

        mix = nodes.new("ShaderNodeMixRGB")
        mix.name = "Sherward_StubbleMix"
        mix.blend_type = "MIX"
        mix.inputs["Fac"].default_value = 0.22 * ss
        mix.inputs["Color2"].default_value = (0.19, 0.14, 0.11, 1.0)

        src = bsdf.inputs["Base Color"]
        if src.is_linked:
            in_link = src.links[0]
            links.remove(in_link)
            links.new(in_link.from_socket, mix.inputs["Color1"])
        else:
            mix.inputs["Color1"].default_value = src.default_value
        links.new(tex.outputs["Color"], mix.inputs["Fac"])
        links.new(mix.outputs["Color"], src)

        bsdf.inputs["Roughness"].default_value = min(1.0, bsdf.inputs["Roughness"].default_value + (0.08 * ss))


def _add_asymmetry_shape_key(head_obj, strength):
    s = max(0.0, min(1.0, float(strength)))
    if s <= 0.0 or head_obj.type != "MESH":
        return

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    head_obj.select_set(True)
    bpy.context.view_layer.objects.active = head_obj

    if head_obj.data.shape_keys is None:
        head_obj.shape_key_add(name="Basis", from_mix=False)
    key = head_obj.shape_key_add(name="Sherward_Asymmetry", from_mix=False)

    xs = [v.co.x for v in key.data]
    ys = [v.co.y for v in key.data]
    zs = [v.co.z for v in key.data]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    span_x = max(1e-6, max_x - min_x)
    span_y = max(1e-6, max_y - min_y)
    span_z = max(1e-6, max_z - min_z)

    # Limit changes to front upper region (face area approximation).
    y_gate = min_y + (0.46 * span_y)
    z_gate = min_z + (0.38 * span_z)

    for i, v in enumerate(key.data):
        co = v.co
        if co.y < y_gate or co.z < z_gate:
            continue
        norm_x = (co.x - min_x) / span_x
        center_weight = 1.0 - abs((norm_x * 2.0) - 1.0)
        side = 1.0 if co.x >= 0.0 else -1.0
        v.co.x += side * (0.0040 * s * (0.3 + center_weight))
        v.co.y += (0.0020 * s * side)
        v.co.z += (0.0008 * s * side)

    key.value = 1.0
    _log("Added shape key: Sherward_Asymmetry")


def _get_head_anchor_world(armature):
    for name in ("mixamorig:Head", "Head"):
        p = armature.pose.bones.get(name)
        if p:
            return armature.matrix_world @ p.matrix @ Vector((0.0, 0.0, 0.0))
    return armature.matrix_world.translation + Vector((0.0, 0.0, 1.65))


def _load_image(path):
    p = Path(path)
    if not p.exists():
        return None
    return bpy.data.images.load(str(p.resolve()), check_existing=True)


def _create_reference_plane(name, image, location, rotation, scale):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=location, rotation=rotation)
    plane = bpy.context.active_object
    plane.name = name
    plane.scale = scale

    mat = bpy.data.materials.new(name=f"MAT_{name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    emiss = nodes.new("ShaderNodeEmission")
    emiss.inputs["Strength"].default_value = 1.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emiss.inputs["Color"])
    links.new(emiss.outputs["Emission"], out.inputs["Surface"])

    if hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    plane.data.materials.append(mat)
    return plane


def _ensure_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link_only_to_collection(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def _resolve_reference_images(args):
    refs = {"front": "", "side": "", "threeq": ""}
    refs["front"] = args.front_ref or ""
    refs["side"] = args.side_ref or ""
    refs["threeq"] = args.threeq_ref or ""

    if args.references_dir:
        root = Path(args.references_dir)
        if root.exists():
            def _first(patterns):
                for pat in patterns:
                    hits = list(root.glob(pat))
                    if hits:
                        return str(hits[0])
                return ""
            if not refs["front"]:
                refs["front"] = _first(["front.*", "*front*.*", "*_f.*"])
            if not refs["side"]:
                refs["side"] = _first(["side.*", "*side*.*", "*_s.*"])
            if not refs["threeq"]:
                refs["threeq"] = _first(["threeq.*", "three_quarter.*", "*three*quarter*.*", "*3q*.*"])
    return refs


def _build_reference_board(armature, args):
    refs = _resolve_reference_images(args)
    images = {k: _load_image(v) for k, v in refs.items() if v}
    if not images:
        _log("No reference images found. Skipping reference board.")
        return

    anchor = _get_head_anchor_world(armature)
    col = _ensure_collection("Sherward_ReferenceBoard")

    if "front" in images:
        obj = _create_reference_plane(
            "REF_Front",
            images["front"],
            location=(anchor.x, anchor.y + 1.25, anchor.z),
            rotation=Euler((1.5708, 0.0, 3.14159), "XYZ"),
            scale=(0.58, 0.58, 0.58),
        )
        _link_only_to_collection(obj, col)

    if "side" in images:
        obj = _create_reference_plane(
            "REF_Side",
            images["side"],
            location=(anchor.x + 1.25, anchor.y, anchor.z),
            rotation=Euler((1.5708, 0.0, -1.5708), "XYZ"),
            scale=(0.58, 0.58, 0.58),
        )
        _link_only_to_collection(obj, col)

    if "threeq" in images:
        obj = _create_reference_plane(
            "REF_3Q",
            images["threeq"],
            location=(anchor.x + 0.95, anchor.y + 0.95, anchor.z),
            rotation=Euler((1.5708, 0.0, -2.35619), "XYZ"),
            scale=(0.58, 0.58, 0.58),
        )
        _link_only_to_collection(obj, col)

    _log("Reference board created.")


def _create_camera(name, location, rotation_euler, focal=80.0):
    bpy.ops.object.camera_add(location=location, rotation=rotation_euler)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = float(focal)
    return cam


def _build_review_cameras(armature, main_mesh):
    lo, hi = _world_bounds([armature, main_mesh])
    center = Vector(((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, (lo.z + hi.z) * 0.5))
    head = _get_head_anchor_world(armature)

    col = _ensure_collection("Sherward_ReviewCameras")
    cams = []
    cams.append(
        _create_camera(
            "CAM_Sherward_FaceFront",
            location=(head.x, head.y + 1.05, head.z),
            rotation_euler=(1.5708, 0.0, 3.14159),
            focal=95.0,
        )
    )
    cams.append(
        _create_camera(
            "CAM_Sherward_Face3Q",
            location=(head.x + 0.85, head.y + 0.85, head.z + 0.03),
            rotation_euler=(1.5708, 0.0, -2.35619),
            focal=95.0,
        )
    )
    cams.append(
        _create_camera(
            "CAM_Sherward_FullBody",
            location=(center.x, center.y + 3.9, lo.z + 1.2),
            rotation_euler=(1.39626, 0.0, 3.14159),
            focal=55.0,
        )
    )
    for cam in cams:
        _link_only_to_collection(cam, col)
    if cams:
        bpy.context.scene.camera = cams[0]
    _log("Review cameras created.")


def _create_light(name, kind, location, energy, color=(1.0, 1.0, 1.0)):
    bpy.ops.object.light_add(type=kind, location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = float(energy)
    light.data.color = color
    return light


def _build_neutral_lights(armature):
    anchor = _get_head_anchor_world(armature)
    col = _ensure_collection("Sherward_ReviewLights")
    lights = []
    lights.append(_create_light("LGT_Key", "AREA", (anchor.x + 1.2, anchor.y + 1.4, anchor.z + 0.7), 700.0))
    lights.append(_create_light("LGT_Fill", "AREA", (anchor.x - 1.4, anchor.y + 1.0, anchor.z + 0.5), 350.0))
    lights.append(_create_light("LGT_Rim", "AREA", (anchor.x, anchor.y - 1.2, anchor.z + 0.8), 420.0))
    for l in lights:
        _link_only_to_collection(l, col)
    _log("Neutral review lights created.")


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
    _open_or_import_scene(args)

    armature = _find_armature(args)
    skinned = _collect_skinned_meshes(armature)
    main_mesh = _select_main_mesh(args, skinned)
    head_mesh = _select_head_mesh(args, skinned, main_mesh)

    _normalize_height(armature, skinned, args.target_height)
    _apply_realism_material_tuning(skinned, _parse_eye_color(args.eye_color), args.stubble_strength)
    _apply_stubble_mask(head_mesh, args.stubble_mask, args.stubble_strength)
    _add_asymmetry_shape_key(head_mesh, args.asymmetry)
    _build_reference_board(armature, args)

    if args.create_review_cameras:
        _build_review_cameras(armature, main_mesh)
    if args.create_neutral_lights:
        _build_neutral_lights(armature)

    _save_and_export(args)
    _log("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _log(f"FAILED: {exc}")
        raise
