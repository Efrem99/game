"""Generate handcrafted location blockouts in Blender and export GLB/FBX.

Run:
  blender -b -P tools/blender/generate_location_blockouts.py
  blender -b -P tools/blender/generate_location_blockouts.py -- --target sherward_room
"""

import argparse
import sys
import math
from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "assets" / "models" / "locations"


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Generate location blockouts and export GLB/FBX.")
    parser.add_argument(
        "--target",
        choices=["all", "sherward_room", "castle_keep"],
        default="all",
        help="Which location preset to generate.",
    )
    parser.add_argument(
        "--export",
        choices=["both", "glb", "fbx"],
        default="both",
        help="Which export formats to write.",
    )
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)


def ensure_collection(name):
    existing = bpy.data.collections.get(name)
    if existing:
        return existing
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def ensure_material(name, color, roughness=0.65, metallic=0.0, alpha=1.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], alpha)
    bsdf.inputs["Roughness"].default_value = float(roughness)
    bsdf.inputs["Metallic"].default_value = float(metallic)
    if alpha < 0.999:
        mat.blend_method = "BLEND"
        bsdf.inputs["Alpha"].default_value = alpha
    output = nodes.new(type="ShaderNodeOutputMaterial")
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def _attach_material(obj, material):
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)


def create_box(collection, name, dims, location, material):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dims
    _attach_material(obj, material)
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    if obj.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(obj)
    return obj


def create_cylinder(collection, name, radius, depth, location, material, vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=int(vertices),
        radius=float(radius),
        depth=float(depth),
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    _attach_material(obj, material)
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    if obj.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(obj)
    return obj


def build_sherward_room():
    col = ensure_collection("loc_sherward_room")
    stone = ensure_material("loc_stone", (0.57, 0.55, 0.52), roughness=0.82, metallic=0.03)
    wood = ensure_material("loc_wood", (0.37, 0.25, 0.15), roughness=0.74, metallic=0.01)
    fabric = ensure_material("loc_fabric", (0.52, 0.29, 0.23), roughness=0.9, metallic=0.0)
    linen = ensure_material("loc_linen", (0.82, 0.80, 0.75), roughness=0.92, metallic=0.0)
    metal = ensure_material("loc_metal", (0.66, 0.65, 0.64), roughness=0.33, metallic=0.75)
    glass = ensure_material("loc_glass", (0.64, 0.77, 0.90), roughness=0.08, metallic=0.0, alpha=0.28)

    width = 8.4
    depth = 7.2
    wall_h = 3.6
    wall_t = 0.22
    door_w = 1.5

    create_box(col, "sr_floor", (width, depth, 0.20), (0.0, 0.0, 0.10), stone)
    create_box(col, "sr_wall_n", (width, wall_t, wall_h), (0.0, (depth * 0.5) - (wall_t * 0.5), wall_h * 0.5), stone)
    create_box(col, "sr_wall_w", (wall_t, depth, wall_h), (-(width * 0.5) + (wall_t * 0.5), 0.0, wall_h * 0.5), stone)
    create_box(col, "sr_wall_e", (wall_t, depth, wall_h), ((width * 0.5) - (wall_t * 0.5), 0.0, wall_h * 0.5), stone)
    seg = (width - door_w) * 0.5
    create_box(
        col,
        "sr_wall_s_l",
        (seg, wall_t, wall_h),
        (-(door_w * 0.5) - (seg * 0.5), -(depth * 0.5) + (wall_t * 0.5), wall_h * 0.5),
        stone,
    )
    create_box(
        col,
        "sr_wall_s_r",
        (seg, wall_t, wall_h),
        ((door_w * 0.5) + (seg * 0.5), -(depth * 0.5) + (wall_t * 0.5), wall_h * 0.5),
        stone,
    )
    create_box(
        col,
        "sr_lintel",
        (door_w + 0.24, wall_t, 0.30),
        (0.0, -(depth * 0.5) + (wall_t * 0.5), wall_h - 0.15),
        wood,
    )

    create_box(col, "bed_frame", (2.4, 1.5, 0.42), (-2.2, 1.6, 0.31), wood)
    create_box(col, "bed_mattress", (2.2, 1.3, 0.24), (-2.2, 1.6, 0.56), linen)
    create_box(col, "bed_pillow", (0.8, 0.5, 0.12), (-2.2, 2.05, 0.72), linen)
    create_box(col, "desk_top", (1.5, 0.8, 0.10), (2.1, 1.8, 0.83), wood)
    create_box(col, "desk_leg_lf", (0.08, 0.08, 0.75), (1.45, 2.10, 0.38), wood)
    create_box(col, "desk_leg_rf", (0.08, 0.08, 0.75), (2.75, 2.10, 0.38), wood)
    create_box(col, "desk_leg_lb", (0.08, 0.08, 0.75), (1.45, 1.50, 0.38), wood)
    create_box(col, "desk_leg_rb", (0.08, 0.08, 0.75), (2.75, 1.50, 0.38), wood)
    create_box(col, "chair", (0.52, 0.52, 0.85), (2.1, 0.95, 0.43), wood)
    create_box(col, "wardrobe", (1.2, 0.64, 2.2), (-3.15, -1.75, 1.1), wood)
    create_box(col, "carpet", (3.6, 2.6, 0.03), (0.4, 0.6, 0.215), fabric)

    create_box(col, "window_frame", (1.8, 0.15, 1.4), (0.0, (depth * 0.5) - 0.09, 1.95), wood)
    create_box(col, "window_glass", (1.58, 0.05, 1.18), (0.0, (depth * 0.5) - 0.02, 1.95), glass)

    create_cylinder(col, "chandelier_core", 0.18, 0.22, (0.0, 0.0, 3.05), metal, vertices=20)
    for i in range(4):
        angle = (i / 4.0) * 6.2831853
        x = 0.38 * math.cos(angle)
        y = 0.38 * math.sin(angle)
        create_box(col, f"chandelier_arm_{i}", (0.26, 0.08, 0.06), (x, y, 2.98), metal)

    return col, "sherward_room"


def build_castle_keep():
    col = ensure_collection("loc_castle_keep_block")
    stone = ensure_material("loc_castle_stone", (0.58, 0.57, 0.53), roughness=0.84, metallic=0.02)
    trim = ensure_material("loc_castle_trim", (0.40, 0.32, 0.24), roughness=0.68, metallic=0.01)

    create_box(col, "ck_ground", (24.0, 22.0, 0.30), (0.0, 0.0, 0.15), stone)
    create_box(col, "ck_keep", (7.6, 7.6, 10.0), (0.0, 0.0, 5.0), stone)
    create_box(col, "ck_gate", (3.0, 1.8, 3.2), (0.0, -3.9, 1.6), trim)
    for idx, (x, y) in enumerate(((-6.2, -5.7), (6.2, -5.7), (-6.2, 5.7), (6.2, 5.7))):
        create_cylinder(col, f"ck_tower_{idx}", 1.6, 11.0, (x, y, 5.5), stone, vertices=20)
        create_cylinder(col, f"ck_cap_{idx}", 1.8, 0.44, (x, y, 11.22), trim, vertices=20)

    wall_h = 4.2
    wall_t = 0.85
    create_box(col, "ck_wall_n", (16.0, wall_t, wall_h), (0.0, 8.2, wall_h * 0.5), stone)
    create_box(col, "ck_wall_s_l", (6.2, wall_t, wall_h), (-4.9, -8.2, wall_h * 0.5), stone)
    create_box(col, "ck_wall_s_r", (6.2, wall_t, wall_h), (4.9, -8.2, wall_h * 0.5), stone)
    create_box(col, "ck_wall_w", (wall_t, 16.0, wall_h), (-8.2, 0.0, wall_h * 0.5), stone)
    create_box(col, "ck_wall_e", (wall_t, 16.0, wall_h), (8.2, 0.0, wall_h * 0.5), stone)

    return col, "castle_keep_block"


def export_collection(collection, stem, export_mode):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in collection.all_objects:
        obj.select_set(True)
    if collection.all_objects:
        bpy.context.view_layer.objects.active = collection.all_objects[0]

    if export_mode in {"both", "glb"}:
        glb_path = OUTPUT_DIR / f"{stem}.glb"
        bpy.ops.export_scene.gltf(
            filepath=str(glb_path),
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_yup=True,
        )
        print(f"[location-gen] exported {glb_path}")

    if export_mode in {"both", "fbx"}:
        fbx_path = OUTPUT_DIR / f"{stem}.fbx"
        bpy.ops.export_scene.fbx(
            filepath=str(fbx_path),
            use_selection=True,
            apply_scale_options="FBX_SCALE_UNITS",
            bake_anim=False,
            add_leaf_bones=False,
        )
        print(f"[location-gen] exported {fbx_path}")


def main():
    args = parse_args()
    clear_scene()
    jobs = []
    if args.target in {"all", "sherward_room"}:
        jobs.append(build_sherward_room())
    if args.target in {"all", "castle_keep"}:
        jobs.append(build_castle_keep())
    for collection, stem in jobs:
        export_collection(collection, stem, args.export)
    print("[location-gen] done")


if __name__ == "__main__":
    main()
