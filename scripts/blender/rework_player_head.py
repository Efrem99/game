import bpy
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_MODEL = PROJECT_ROOT / "assets" / "models" / "xbot" / "Xbot.glb"
OUTPUT_MODEL = PROJECT_ROOT / "assets" / "models" / "hero" / "sherward" / "sherward_rework.glb"
OUTPUT_BLEND = PROJECT_ROOT / "assets" / "models" / "hero" / "sherward" / "sherward_rework.blend"

HEAD_BONE_CANDIDATES = (
    "mixamorig:Head",
    "Head",
    "head",
    "mixamorig_Head",
)
CHEST_BONE_CANDIDATES = (
    "mixamorig:Spine2",
    "mixamorig:Spine1",
    "Spine2",
    "Spine1",
    "Spine",
)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def make_material(name, base_color, *, metallic=0.0, roughness=0.5):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Metallic"].default_value = float(metallic)
    bsdf.inputs["Roughness"].default_value = float(roughness)
    output = nodes.new(type="ShaderNodeOutputMaterial")
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def find_armature():
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    return None


def resolve_bone_name(armature, candidates):
    if not armature:
        return None
    for token in candidates:
        if token in armature.data.bones:
            return token
    return None


def parent_to_bone(obj, armature, bone_name):
    if not obj or not armature or not bone_name:
        return
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name


def add_scaled_sphere(name, scale, material, location=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def add_scaled_cube(name, scale, material, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def add_head_rework(armature):
    head_bone = resolve_bone_name(armature, HEAD_BONE_CANDIDATES)
    chest_bone = resolve_bone_name(armature, CHEST_BONE_CANDIDATES)
    if not head_bone:
        raise RuntimeError("Head bone not found on imported rig.")

    skin_mat = make_material("HeroSkin", (0.76, 0.66, 0.58), roughness=0.62)
    hair_mat = make_material("HeroHair", (0.24, 0.20, 0.16), roughness=0.68)
    steel_mat = make_material("HeroSteel", (0.62, 0.66, 0.72), metallic=0.9, roughness=0.24)
    dark_steel_mat = make_material("HeroDarkSteel", (0.30, 0.34, 0.40), metallic=0.88, roughness=0.28)

    head_root = bpy.data.objects.new("hero_head_rework_root", None)
    bpy.context.scene.collection.objects.link(head_root)
    parent_to_bone(head_root, armature, head_bone)
    head_root.location = (0.0, 0.03, 0.02)

    # Human-like head base.
    skull = add_scaled_sphere("hero_head_skull", (0.22, 0.20, 0.24), skin_mat)
    skull.parent = head_root
    skull.location = (0.0, 0.06, 0.06)

    jaw = add_scaled_cube("hero_head_jaw", (0.13, 0.11, 0.06), skin_mat, location=(0.0, 0.18, -0.03))
    jaw.parent = head_root

    nose = add_scaled_cube("hero_head_nose", (0.04, 0.05, 0.05), skin_mat, location=(0.0, 0.24, 0.03))
    nose.parent = head_root

    # Hair cap.
    hair_cap = add_scaled_sphere("hero_hair_cap", (0.24, 0.21, 0.16), hair_mat, location=(0.0, 0.00, 0.16))
    hair_cap.parent = head_root

    # Steel helmet shell to keep silhouette close to knight look and hide base head artifacts.
    helmet_shell = add_scaled_sphere("hero_helmet_shell", (0.26, 0.23, 0.27), steel_mat, location=(0.0, 0.05, 0.07))
    helmet_shell.parent = head_root

    visor = add_scaled_cube(
        "hero_helmet_visor",
        (0.14, 0.03, 0.06),
        dark_steel_mat,
        location=(0.0, 0.26, 0.04),
    )
    visor.parent = head_root

    helm_rim = add_scaled_cube(
        "hero_helmet_rim",
        (0.18, 0.03, 0.02),
        steel_mat,
        location=(0.0, 0.25, -0.02),
    )
    helm_rim.parent = head_root

    if chest_bone:
        gorget_root = bpy.data.objects.new("hero_gorget_root", None)
        bpy.context.scene.collection.objects.link(gorget_root)
        parent_to_bone(gorget_root, armature, chest_bone)
        gorget_root.location = (0.0, 0.08, 0.16)

        gorget_front = add_scaled_cube(
            "hero_gorget_front",
            (0.18, 0.08, 0.08),
            dark_steel_mat,
            location=(0.0, 0.16, 0.06),
            rotation=(math.radians(8.0), 0.0, 0.0),
        )
        gorget_front.parent = gorget_root

        gorget_back = add_scaled_cube(
            "hero_gorget_back",
            (0.16, 0.07, 0.06),
            steel_mat,
            location=(0.0, -0.10, 0.04),
        )
        gorget_back.parent = gorget_root


def run():
    if not SOURCE_MODEL.exists():
        raise FileNotFoundError(f"Source model not found: {SOURCE_MODEL}")

    OUTPUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    clear_scene()

    bpy.ops.import_scene.gltf(filepath=str(SOURCE_MODEL))
    armature = find_armature()
    if not armature:
        raise RuntimeError("Armature was not imported from source model.")

    add_head_rework(armature)

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND), compress=False)
    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT_MODEL),
        export_format="GLB",
        use_selection=False,
        export_apply=False,
    )
    print(f"HEAD_REWORK_DONE: {OUTPUT_MODEL}")


if __name__ == "__main__":
    run()
