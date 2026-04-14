"""
Blender script: Generate stylized medieval assets for King Wizard RPG.
Run with: blender --background --python scripts/generate_medieval_assets.py

Generates GLB files into assets/models/world/ with proper PBR materials.
Categories: trees, buildings (exterior + interior), props, furniture.
"""

import bpy
import bmesh
import os
import sys
import math
import random
from mathutils import Vector, Matrix

# ── Configuration ──────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_TREES = os.path.join(ROOT, "assets", "models", "world", "trees")
OUT_PROPS = os.path.join(ROOT, "assets", "models", "world", "props")
OUT_BUILDINGS = os.path.join(ROOT, "assets", "models", "world", "buildings")
OUT_FURNITURE = os.path.join(ROOT, "assets", "models", "world", "furniture")

for d in [OUT_TREES, OUT_PROPS, OUT_BUILDINGS, OUT_FURNITURE]:
    os.makedirs(d, exist_ok=True)

SEED = 42
random.seed(SEED)


# ── Utility ────────────────────────────────────────────────────────────────
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)


def make_material(name, base_color, roughness=0.7, metallic=0.0):
    """Create a simple PBR material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    output.location = (300, 0)
    bsdf.location = (0, 0)
    return mat


def assign_material(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def export_glb(filepath):
    """Export all visible objects as GLB."""
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_materials='EXPORT',
    )
    print(f"  ✓ Exported: {os.path.basename(filepath)}")


def parent_to(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


# ── Trees ──────────────────────────────────────────────────────────────────
def build_stylized_tree(name, trunk_h=2.5, trunk_r=0.15, canopy_r=1.8, canopy_h=2.0,
                        trunk_color=(0.35, 0.22, 0.10, 1.0),
                        leaf_color=(0.15, 0.45, 0.12, 1.0),
                        canopy_type="sphere"):
    """Build a stylized low-poly tree."""
    clear_scene()

    mat_trunk = make_material(f"{name}_trunk", trunk_color, roughness=0.85)
    mat_leaf = make_material(f"{name}_leaves", leaf_color, roughness=0.75)

    # Trunk — tapered cylinder
    bpy.ops.mesh.primitive_cone_add(
        vertices=8, radius1=trunk_r * 1.3, radius2=trunk_r * 0.6,
        depth=trunk_h, location=(0, 0, trunk_h / 2)
    )
    trunk = bpy.context.active_object
    trunk.name = f"{name}_trunk"
    assign_material(trunk, mat_trunk)

    # Slight random bend
    bm = bmesh.new()
    bm.from_mesh(trunk.data)
    for v in bm.verts:
        if v.co.z > trunk_h * 0.5:
            v.co.x += random.uniform(-0.05, 0.05)
            v.co.y += random.uniform(-0.05, 0.05)
    bm.to_mesh(trunk.data)
    bm.free()

    # Canopy
    if canopy_type == "sphere":
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=2, radius=canopy_r,
            location=(0, 0, trunk_h + canopy_h * 0.4)
        )
    elif canopy_type == "cone":
        bpy.ops.mesh.primitive_cone_add(
            vertices=8, radius1=canopy_r, radius2=0.1,
            depth=canopy_h * 1.5, location=(0, 0, trunk_h + canopy_h * 0.5)
        )
    elif canopy_type == "multi":
        # Multiple spheres for a lush look
        offsets = [
            (0, 0, trunk_h + canopy_h * 0.3),
            (0.5, 0.3, trunk_h + canopy_h * 0.6),
            (-0.4, -0.2, trunk_h + canopy_h * 0.5),
            (0.1, -0.5, trunk_h + canopy_h * 0.7),
        ]
        for i, pos in enumerate(offsets):
            r = canopy_r * random.uniform(0.6, 1.0)
            bpy.ops.mesh.primitive_ico_sphere_add(
                subdivisions=2, radius=r, location=pos
            )
            sphere = bpy.context.active_object
            sphere.name = f"{name}_canopy_{i}"
            assign_material(sphere, mat_leaf)
            # Deform slightly
            bm = bmesh.new()
            bm.from_mesh(sphere.data)
            for v in bm.verts:
                v.co.x *= random.uniform(0.85, 1.15)
                v.co.y *= random.uniform(0.85, 1.15)
                v.co.z *= random.uniform(0.9, 1.1)
            bm.to_mesh(sphere.data)
            bm.free()
        return  # Multi already assigned materials per sphere

    canopy = bpy.context.active_object
    canopy.name = f"{name}_canopy"
    assign_material(canopy, mat_leaf)

    # Slight vertex deformation for organic feel
    bm = bmesh.new()
    bm.from_mesh(canopy.data)
    for v in bm.verts:
        v.co.x *= random.uniform(0.85, 1.15)
        v.co.y *= random.uniform(0.85, 1.15)
        v.co.z *= random.uniform(0.9, 1.1)
    bm.to_mesh(canopy.data)
    bm.free()


TREE_DEFS = [
    ("oak_tree_1", dict(trunk_h=3.0, trunk_r=0.2, canopy_r=2.2, canopy_h=2.5,
                        trunk_color=(0.30, 0.18, 0.08, 1), leaf_color=(0.12, 0.42, 0.10, 1),
                        canopy_type="multi")),
    ("oak_tree_2", dict(trunk_h=3.5, trunk_r=0.22, canopy_r=2.5, canopy_h=2.8,
                        trunk_color=(0.33, 0.20, 0.09, 1), leaf_color=(0.18, 0.50, 0.15, 1),
                        canopy_type="multi")),
    ("oak_tree_3", dict(trunk_h=2.8, trunk_r=0.18, canopy_r=2.0, canopy_h=2.2,
                        trunk_color=(0.28, 0.17, 0.07, 1), leaf_color=(0.20, 0.55, 0.12, 1),
                        canopy_type="sphere")),
    ("pine_tree_1", dict(trunk_h=4.0, trunk_r=0.12, canopy_r=1.2, canopy_h=3.5,
                         trunk_color=(0.25, 0.15, 0.06, 1), leaf_color=(0.08, 0.30, 0.08, 1),
                         canopy_type="cone")),
    ("pine_tree_2", dict(trunk_h=5.0, trunk_r=0.14, canopy_r=1.4, canopy_h=4.0,
                         trunk_color=(0.22, 0.14, 0.05, 1), leaf_color=(0.06, 0.25, 0.06, 1),
                         canopy_type="cone")),
    ("birch_tree_1", dict(trunk_h=4.5, trunk_r=0.10, canopy_r=1.5, canopy_h=2.0,
                          trunk_color=(0.85, 0.82, 0.75, 1), leaf_color=(0.25, 0.55, 0.15, 1),
                          canopy_type="multi")),
    ("willow_tree_1", dict(trunk_h=3.0, trunk_r=0.25, canopy_r=3.0, canopy_h=2.5,
                           trunk_color=(0.30, 0.20, 0.10, 1), leaf_color=(0.15, 0.50, 0.18, 1),
                           canopy_type="sphere")),
    ("dead_tree_1", dict(trunk_h=3.0, trunk_r=0.15, canopy_r=0, canopy_h=0,
                         trunk_color=(0.25, 0.20, 0.15, 1), leaf_color=(0, 0, 0, 0),
                         canopy_type="sphere")),
]


# ── Buildings ──────────────────────────────────────────────────────────────
def build_medieval_house(name, width=4.0, depth=5.0, wall_h=3.0, roof_h=2.0,
                         wall_color=(0.75, 0.68, 0.55, 1),
                         roof_color=(0.45, 0.20, 0.10, 1),
                         wood_color=(0.35, 0.22, 0.10, 1),
                         has_door=True, has_windows=True, has_chimney=False):
    """Build a stylized medieval building."""
    clear_scene()

    mat_wall = make_material(f"{name}_wall", wall_color, roughness=0.9)
    mat_roof = make_material(f"{name}_roof", roof_color, roughness=0.8)
    mat_wood = make_material(f"{name}_wood", wood_color, roughness=0.85)
    mat_window = make_material(f"{name}_window", (0.3, 0.5, 0.7, 1.0), roughness=0.1, metallic=0.05)
    mat_door = make_material(f"{name}_door", (0.25, 0.15, 0.08, 1), roughness=0.8)

    # Walls — box
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, wall_h / 2))
    walls = bpy.context.active_object
    walls.scale = (width / 2, depth / 2, wall_h / 2)
    bpy.ops.object.transform_apply(scale=True)
    walls.name = f"{name}_walls"
    assign_material(walls, mat_wall)

    # Roof — prism (triangular cross-section)
    bm = bmesh.new()
    hw, hd = width / 2, depth / 2
    overhang = 0.3
    verts = [
        bm.verts.new((-hw - overhang, -hd - overhang, wall_h)),
        bm.verts.new((hw + overhang, -hd - overhang, wall_h)),
        bm.verts.new((hw + overhang, hd + overhang, wall_h)),
        bm.verts.new((-hw - overhang, hd + overhang, wall_h)),
        bm.verts.new((0, -hd - overhang, wall_h + roof_h)),
        bm.verts.new((0, hd + overhang, wall_h + roof_h)),
    ]
    faces = [
        (verts[0], verts[1], verts[4]),        # front triangle
        (verts[2], verts[3], verts[5]),        # back triangle
        (verts[0], verts[4], verts[5], verts[3]),  # left slope
        (verts[1], verts[2], verts[5], verts[4]),  # right slope
        (verts[0], verts[3], verts[2], verts[1]),  # bottom (hidden)
    ]
    for f in faces:
        bm.faces.new(f)
    roof_mesh = bpy.data.meshes.new(f"{name}_roof_mesh")
    bm.to_mesh(roof_mesh)
    bm.free()
    roof_obj = bpy.data.objects.new(f"{name}_roof", roof_mesh)
    bpy.context.collection.objects.link(roof_obj)
    assign_material(roof_obj, mat_roof)

    # Door
    if has_door:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -depth / 2 + 0.01, 1.0))
        door = bpy.context.active_object
        door.scale = (0.5, 0.05, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        door.name = f"{name}_door"
        assign_material(door, mat_door)

        # Door frame (wooden posts)
        for x_off in [-0.55, 0.55]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x_off, -depth / 2 + 0.01, 1.0))
            frame = bpy.context.active_object
            frame.scale = (0.05, 0.06, 1.05)
            bpy.ops.object.transform_apply(scale=True)
            frame.name = f"{name}_door_frame"
            assign_material(frame, mat_wood)

    # Windows
    if has_windows:
        for side in [-1, 1]:
            bpy.ops.mesh.primitive_cube_add(
                size=1, location=(side * width / 2 - side * 0.01, 0, wall_h * 0.6)
            )
            win = bpy.context.active_object
            win.scale = (0.02, 0.4, 0.4)
            bpy.ops.object.transform_apply(scale=True)
            win.name = f"{name}_window"
            assign_material(win, mat_window)

    # Half-timber beams (decorative)
    beam_positions = [
        ((0, -depth / 2 - 0.02, wall_h * 0.5), (width / 2, 0.03, 0.05)),
        ((0, -depth / 2 - 0.02, wall_h * 0.75), (width / 2, 0.03, 0.05)),
    ]
    for pos, scale in beam_positions:
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        beam = bpy.context.active_object
        beam.scale = scale
        bpy.ops.object.transform_apply(scale=True)
        beam.name = f"{name}_beam"
        assign_material(beam, mat_wood)

    # Chimney
    if has_chimney:
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=(width / 4, 0, wall_h + roof_h * 0.7)
        )
        chimney = bpy.context.active_object
        chimney.scale = (0.25, 0.25, roof_h * 0.5)
        bpy.ops.object.transform_apply(scale=True)
        chimney.name = f"{name}_chimney"
        assign_material(chimney, make_material(f"{name}_stone", (0.4, 0.38, 0.35, 1), roughness=0.95))


BUILDING_DEFS = [
    ("medieval_house_1", dict(width=4.0, depth=5.0, wall_h=3.0, roof_h=2.0,
                              wall_color=(0.75, 0.68, 0.55, 1), roof_color=(0.45, 0.20, 0.10, 1),
                              has_chimney=True)),
    ("medieval_house_2", dict(width=5.0, depth=6.0, wall_h=3.5, roof_h=2.5,
                              wall_color=(0.80, 0.72, 0.58, 1), roof_color=(0.35, 0.18, 0.08, 1),
                              has_chimney=False)),
    ("medieval_shop", dict(width=5.0, depth=4.0, wall_h=3.0, roof_h=1.8,
                           wall_color=(0.70, 0.62, 0.50, 1), roof_color=(0.50, 0.25, 0.12, 1),
                           wood_color=(0.30, 0.18, 0.08, 1), has_chimney=False)),
    ("medieval_tavern", dict(width=7.0, depth=8.0, wall_h=4.0, roof_h=3.0,
                             wall_color=(0.65, 0.58, 0.45, 1), roof_color=(0.40, 0.22, 0.10, 1),
                             has_chimney=True)),
    ("medieval_blacksmith", dict(width=5.0, depth=6.0, wall_h=3.5, roof_h=2.0,
                                 wall_color=(0.50, 0.45, 0.38, 1), roof_color=(0.30, 0.15, 0.08, 1),
                                 has_chimney=True)),
    ("medieval_tower", dict(width=3.0, depth=3.0, wall_h=8.0, roof_h=2.5,
                            wall_color=(0.55, 0.50, 0.45, 1), roof_color=(0.35, 0.18, 0.10, 1),
                            has_chimney=False)),
]


# ── Props ──────────────────────────────────────────────────────────────────
def build_prop(name, prop_type):
    """Build small world props."""
    clear_scene()

    if prop_type == "barrel":
        mat = make_material(f"{name}_mat", (0.40, 0.25, 0.12, 1), roughness=0.8)
        mat_band = make_material(f"{name}_band", (0.3, 0.3, 0.3, 1), roughness=0.4, metallic=0.6)
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.35, depth=0.9, location=(0, 0, 0.45))
        barrel = bpy.context.active_object
        barrel.name = name
        assign_material(barrel, mat)
        # Metal bands
        for z in [0.15, 0.45, 0.75]:
            bpy.ops.mesh.primitive_torus_add(
                major_radius=0.36, minor_radius=0.015,
                major_segments=16, minor_segments=6, location=(0, 0, z)
            )
            band = bpy.context.active_object
            band.name = f"{name}_band"
            assign_material(band, mat_band)

    elif prop_type == "crate":
        mat = make_material(f"{name}_mat", (0.50, 0.35, 0.18, 1), roughness=0.85)
        bpy.ops.mesh.primitive_cube_add(size=0.7, location=(0, 0, 0.35))
        crate = bpy.context.active_object
        crate.name = name
        assign_material(crate, mat)
        # Cross planks
        mat_plank = make_material(f"{name}_plank", (0.42, 0.28, 0.12, 1), roughness=0.9)
        for rot_z in [0, math.pi / 2]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.35))
            plank = bpy.context.active_object
            plank.scale = (0.36, 0.02, 0.36)
            plank.rotation_euler.z = rot_z
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            plank.name = f"{name}_plank"
            assign_material(plank, mat_plank)

    elif prop_type == "fence":
        mat = make_material(f"{name}_mat", (0.40, 0.28, 0.15, 1), roughness=0.85)
        # Posts
        for x in [-1.0, 0.0, 1.0]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 0.5))
            post = bpy.context.active_object
            post.scale = (0.05, 0.05, 0.5)
            bpy.ops.object.transform_apply(scale=True)
            post.name = f"{name}_post"
            assign_material(post, mat)
        # Rails
        for z in [0.35, 0.7]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
            rail = bpy.context.active_object
            rail.scale = (1.05, 0.03, 0.04)
            bpy.ops.object.transform_apply(scale=True)
            rail.name = f"{name}_rail"
            assign_material(rail, mat)

    elif prop_type == "sign":
        mat_post = make_material(f"{name}_post", (0.35, 0.22, 0.10, 1), roughness=0.85)
        mat_board = make_material(f"{name}_board", (0.55, 0.40, 0.22, 1), roughness=0.8)
        # Post
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=1.8, location=(0, 0, 0.9))
        post = bpy.context.active_object
        post.name = f"{name}_post"
        assign_material(post, mat_post)
        # Sign board
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.5))
        board = bpy.context.active_object
        board.scale = (0.5, 0.03, 0.3)
        bpy.ops.object.transform_apply(scale=True)
        board.name = f"{name}_board"
        assign_material(board, mat_board)

    elif prop_type == "well":
        mat_stone = make_material(f"{name}_stone", (0.45, 0.42, 0.38, 1), roughness=0.95)
        mat_wood = make_material(f"{name}_wood", (0.35, 0.22, 0.10, 1), roughness=0.85)
        # Stone base
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.6, depth=0.8, location=(0, 0, 0.4))
        base = bpy.context.active_object
        base.name = f"{name}_base"
        assign_material(base, mat_stone)
        # Inner hole
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.45, depth=0.85, location=(0, 0, 0.42))
        inner = bpy.context.active_object
        inner.name = f"{name}_inner"
        assign_material(inner, make_material(f"{name}_water", (0.1, 0.2, 0.4, 1), roughness=0.1))
        # Roof frame
        for x in [-0.5, 0.5]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 1.2))
            pole = bpy.context.active_object
            pole.scale = (0.04, 0.04, 0.5)
            bpy.ops.object.transform_apply(scale=True)
            pole.name = f"{name}_pole"
            assign_material(pole, mat_wood)
        # Crossbar
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.7))
        bar = bpy.context.active_object
        bar.scale = (0.6, 0.04, 0.04)
        bpy.ops.object.transform_apply(scale=True)
        bar.name = f"{name}_bar"
        assign_material(bar, mat_wood)

    elif prop_type == "torch":
        mat_wood = make_material(f"{name}_wood", (0.30, 0.18, 0.08, 1), roughness=0.85)
        mat_fire = make_material(f"{name}_fire", (1.0, 0.6, 0.1, 1), roughness=0.0)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.03, depth=1.0, location=(0, 0, 0.5))
        stick = bpy.context.active_object
        stick.name = f"{name}_stick"
        assign_material(stick, mat_wood)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.08, location=(0, 0, 1.05))
        flame = bpy.context.active_object
        flame.name = f"{name}_flame"
        flame.scale.z = 1.5
        bpy.ops.object.transform_apply(scale=True)
        assign_material(flame, mat_fire)

    elif prop_type == "market_stall":
        mat_wood = make_material(f"{name}_wood", (0.40, 0.28, 0.15, 1), roughness=0.85)
        mat_cloth = make_material(f"{name}_cloth", (0.6, 0.15, 0.12, 1), roughness=0.7)
        # Counter
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
        counter = bpy.context.active_object
        counter.scale = (1.2, 0.5, 0.5)
        bpy.ops.object.transform_apply(scale=True)
        counter.name = f"{name}_counter"
        assign_material(counter, mat_wood)
        # Awning poles
        for x in [-1.1, 1.1]:
            bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=2.0, location=(x, -0.4, 1.5))
            pole = bpy.context.active_object
            pole.name = f"{name}_pole"
            assign_material(pole, mat_wood)
        # Awning cloth
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 2.5))
        cloth = bpy.context.active_object
        cloth.scale = (1.3, 0.7, 0.02)
        bpy.ops.object.transform_apply(scale=True)
        cloth.name = f"{name}_awning"
        assign_material(cloth, mat_cloth)


PROP_DEFS = [
    ("barrel_1", "barrel"), ("barrel_2", "barrel"),
    ("crate_1", "crate"), ("crate_2", "crate"),
    ("fence_section_1", "fence"),
    ("sign_post_1", "sign"),
    ("village_well", "well"),
    ("wall_torch_1", "torch"),
    ("market_stall_1", "market_stall"),
]


# ── Furniture (Interiors) ─────────────────────────────────────────────────
def build_furniture(name, furn_type):
    """Build interior furniture."""
    clear_scene()

    if furn_type == "table":
        mat = make_material(f"{name}_mat", (0.45, 0.30, 0.15, 1), roughness=0.8)
        # Tabletop
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.75))
        top = bpy.context.active_object
        top.scale = (0.8, 0.5, 0.03)
        bpy.ops.object.transform_apply(scale=True)
        top.name = f"{name}_top"
        assign_material(top, mat)
        # Legs
        for x, y in [(-0.7, -0.4), (0.7, -0.4), (-0.7, 0.4), (0.7, 0.4)]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.37))
            leg = bpy.context.active_object
            leg.scale = (0.04, 0.04, 0.37)
            bpy.ops.object.transform_apply(scale=True)
            leg.name = f"{name}_leg"
            assign_material(leg, mat)

    elif furn_type == "chair":
        mat = make_material(f"{name}_mat", (0.42, 0.28, 0.12, 1), roughness=0.8)
        # Seat
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.45))
        seat = bpy.context.active_object
        seat.scale = (0.25, 0.25, 0.02)
        bpy.ops.object.transform_apply(scale=True)
        seat.name = f"{name}_seat"
        assign_material(seat, mat)
        # Legs
        for x, y in [(-0.2, -0.2), (0.2, -0.2), (-0.2, 0.2), (0.2, 0.2)]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.22))
            leg = bpy.context.active_object
            leg.scale = (0.025, 0.025, 0.22)
            bpy.ops.object.transform_apply(scale=True)
            leg.name = f"{name}_leg"
            assign_material(leg, mat)
        # Backrest
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.22, 0.65))
        back = bpy.context.active_object
        back.scale = (0.22, 0.02, 0.2)
        bpy.ops.object.transform_apply(scale=True)
        back.name = f"{name}_back"
        assign_material(back, mat)

    elif furn_type == "bookshelf":
        mat = make_material(f"{name}_mat", (0.35, 0.22, 0.10, 1), roughness=0.85)
        mat_book = make_material(f"{name}_book", (0.5, 0.15, 0.10, 1), roughness=0.7)
        # Frame
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.0))
        frame = bpy.context.active_object
        frame.scale = (0.6, 0.15, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        frame.name = f"{name}_frame"
        assign_material(frame, mat)
        # Shelves
        for z in [0.5, 1.0, 1.5]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
            shelf = bpy.context.active_object
            shelf.scale = (0.58, 0.14, 0.02)
            bpy.ops.object.transform_apply(scale=True)
            shelf.name = f"{name}_shelf"
            assign_material(shelf, mat)
        # Books
        for z_base, count in [(0.55, 5), (1.05, 4), (1.55, 3)]:
            for i in range(count):
                x = -0.4 + i * 0.18
                bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, z_base + 0.1))
                book = bpy.context.active_object
                book.scale = (0.06, 0.10, 0.12)
                bpy.ops.object.transform_apply(scale=True)
                book.name = f"{name}_book"
                c = random.choice([
                    (0.5, 0.15, 0.10, 1), (0.15, 0.25, 0.5, 1),
                    (0.10, 0.35, 0.15, 1), (0.50, 0.40, 0.10, 1),
                ])
                assign_material(book, make_material(f"{name}_book_{i}", c, roughness=0.7))

    elif furn_type == "fireplace":
        mat_stone = make_material(f"{name}_stone", (0.40, 0.38, 0.35, 1), roughness=0.95)
        mat_fire = make_material(f"{name}_fire", (1.0, 0.5, 0.1, 1), roughness=0.0)
        # Surround
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.3, 0.6))
        surround = bpy.context.active_object
        surround.scale = (0.8, 0.15, 0.6)
        bpy.ops.object.transform_apply(scale=True)
        surround.name = f"{name}_surround"
        assign_material(surround, mat_stone)
        # Mantle
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.28, 1.25))
        mantle = bpy.context.active_object
        mantle.scale = (0.9, 0.18, 0.04)
        bpy.ops.object.transform_apply(scale=True)
        mantle.name = f"{name}_mantle"
        assign_material(mantle, mat_stone)
        # Fire glow
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.15, location=(0, -0.2, 0.25))
        fire = bpy.context.active_object
        fire.name = f"{name}_fire"
        assign_material(fire, mat_fire)

    elif furn_type == "bed":
        mat_wood = make_material(f"{name}_wood", (0.35, 0.22, 0.10, 1), roughness=0.85)
        mat_fabric = make_material(f"{name}_fabric", (0.6, 0.55, 0.45, 1), roughness=0.75)
        mat_pillow = make_material(f"{name}_pillow", (0.8, 0.78, 0.72, 1), roughness=0.7)
        # Frame
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.25))
        frame = bpy.context.active_object
        frame.scale = (0.5, 1.0, 0.1)
        bpy.ops.object.transform_apply(scale=True)
        frame.name = f"{name}_frame"
        assign_material(frame, mat_wood)
        # Mattress
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.38))
        mattress = bpy.context.active_object
        mattress.scale = (0.45, 0.95, 0.06)
        bpy.ops.object.transform_apply(scale=True)
        mattress.name = f"{name}_mattress"
        assign_material(mattress, mat_fabric)
        # Pillow
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.7, 0.48))
        pillow = bpy.context.active_object
        pillow.scale = (0.3, 0.15, 0.06)
        bpy.ops.object.transform_apply(scale=True)
        pillow.name = f"{name}_pillow"
        assign_material(pillow, mat_pillow)
        # Headboard
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.97, 0.5))
        headboard = bpy.context.active_object
        headboard.scale = (0.5, 0.04, 0.3)
        bpy.ops.object.transform_apply(scale=True)
        headboard.name = f"{name}_headboard"
        assign_material(headboard, mat_wood)

    elif furn_type == "counter":
        mat = make_material(f"{name}_mat", (0.40, 0.28, 0.15, 1), roughness=0.8)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
        counter = bpy.context.active_object
        counter.scale = (1.5, 0.4, 0.5)
        bpy.ops.object.transform_apply(scale=True)
        counter.name = f"{name}_counter"
        assign_material(counter, mat)

    elif furn_type == "chandelier":
        mat_metal = make_material(f"{name}_metal", (0.3, 0.25, 0.15, 1), roughness=0.5, metallic=0.7)
        mat_candle = make_material(f"{name}_candle", (0.9, 0.85, 0.7, 1), roughness=0.6)
        mat_flame = make_material(f"{name}_flame", (1.0, 0.7, 0.2, 1), roughness=0.0)
        # Ring
        bpy.ops.mesh.primitive_torus_add(
            major_radius=0.4, minor_radius=0.02,
            major_segments=12, minor_segments=6, location=(0, 0, 2.5)
        )
        ring = bpy.context.active_object
        ring.name = f"{name}_ring"
        assign_material(ring, mat_metal)
        # Candles
        for angle in range(0, 360, 60):
            rad = math.radians(angle)
            x, y = 0.4 * math.cos(rad), 0.4 * math.sin(rad)
            bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.02, depth=0.12, location=(x, y, 2.56))
            candle = bpy.context.active_object
            candle.name = f"{name}_candle"
            assign_material(candle, mat_candle)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.02, location=(x, y, 2.65))
            flame = bpy.context.active_object
            flame.name = f"{name}_flame"
            assign_material(flame, mat_flame)
        # Chain
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.01, depth=0.5, location=(0, 0, 2.75))
        chain = bpy.context.active_object
        chain.name = f"{name}_chain"
        assign_material(chain, mat_metal)


FURNITURE_DEFS = [
    ("tavern_table_1", "table"),
    ("tavern_table_2", "table"),
    ("wooden_chair_1", "chair"),
    ("wooden_chair_2", "chair"),
    ("bookshelf_1", "bookshelf"),
    ("stone_fireplace_1", "fireplace"),
    ("inn_bed_1", "bed"),
    ("shop_counter_1", "counter"),
    ("iron_chandelier_1", "chandelier"),
]


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print("\n=== King Wizard Asset Generator ===\n")

    # Trees
    print("▸ Generating trees...")
    for name, kwargs in TREE_DEFS:
        if kwargs.get("canopy_r", 1) == 0:
            # Dead tree: just trunk
            clear_scene()
            mat_trunk = make_material(f"{name}_trunk", kwargs["trunk_color"], roughness=0.85)
            bpy.ops.mesh.primitive_cone_add(
                vertices=8, radius1=kwargs["trunk_r"] * 1.3, radius2=kwargs["trunk_r"] * 0.3,
                depth=kwargs["trunk_h"], location=(0, 0, kwargs["trunk_h"] / 2)
            )
            trunk = bpy.context.active_object
            trunk.name = name
            assign_material(trunk, mat_trunk)
            # Add gnarled branches
            for i in range(3):
                angle = random.uniform(0, math.pi * 2)
                h = random.uniform(kwargs["trunk_h"] * 0.5, kwargs["trunk_h"] * 0.9)
                bpy.ops.mesh.primitive_cone_add(
                    vertices=5, radius1=0.04, radius2=0.01,
                    depth=0.6, location=(
                        math.cos(angle) * 0.15, math.sin(angle) * 0.15, h
                    )
                )
                branch = bpy.context.active_object
                branch.rotation_euler = (
                    random.uniform(-0.5, 0.5),
                    random.uniform(-0.5, 0.5),
                    angle
                )
                branch.name = f"{name}_branch_{i}"
                assign_material(branch, mat_trunk)
        else:
            build_stylized_tree(name, **kwargs)
        export_glb(os.path.join(OUT_TREES, f"{name}.glb"))

    # Buildings
    print("▸ Generating buildings...")
    for name, kwargs in BUILDING_DEFS:
        build_medieval_house(name, **kwargs)
        export_glb(os.path.join(OUT_BUILDINGS, f"{name}.glb"))

    # Props
    print("▸ Generating props...")
    for name, prop_type in PROP_DEFS:
        build_prop(name, prop_type)
        export_glb(os.path.join(OUT_PROPS, f"{name}.glb"))

    # Furniture
    print("▸ Generating furniture...")
    for name, furn_type in FURNITURE_DEFS:
        build_furniture(name, furn_type)
        export_glb(os.path.join(OUT_FURNITURE, f"{name}.glb"))

    print(f"\n✓ Generated {len(TREE_DEFS)} trees, {len(BUILDING_DEFS)} buildings,")
    print(f"  {len(PROP_DEFS)} props, {len(FURNITURE_DEFS)} furniture pieces.")
    print(f"  Output dirs: {OUT_TREES}")
    print(f"               {OUT_BUILDINGS}")
    print(f"               {OUT_PROPS}")
    print(f"               {OUT_FURNITURE}\n")


if __name__ == "__main__":
    main()
