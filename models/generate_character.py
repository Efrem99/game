import bpy
import math
import os
import glob
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _pick_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


XBOT_PATH = str(
    _pick_existing_path(
        PROJECT_ROOT / "assets" / "models" / "xbot" / "Xbot.glb",
        PROJECT_ROOT / "test" / "models" / "Xbot.glb",
        PROJECT_ROOT / "models" / "Xbot.glb",
    )
)
ANIM_DIR = str(PROJECT_ROOT / "models" / "animations")
OUTPUT_PATH = str(PROJECT_ROOT / "models" / "xbot_customized.blend")

# Bone Mapping (Mixamo -> Blender Bone Name)
BONES = {
    "Head": "mixamorig:Head",
    "Chest": "mixamorig:Spine1",
    "Hips": "mixamorig:Hips",
    "Shoulder_L": "mixamorig:LeftShoulder",
    "Shoulder_R": "mixamorig:RightShoulder",
    "Arm_L": "mixamorig:LeftArm",
    "Arm_R": "mixamorig:RightArm",
    "Forearm_L": "mixamorig:LeftForeArm",
    "Forearm_R": "mixamorig:RightForeArm",
    "Hand_L": "mixamorig:LeftHand",
    "Hand_R": "mixamorig:RightHand",
    "Leg_L": "mixamorig:LeftLeg",
    "Leg_R": "mixamorig:RightLeg",
    "UpLeg_L": "mixamorig:LeftUpLeg",
    "UpLeg_R": "mixamorig:RightUpLeg",
    "Foot_L": "mixamorig:LeftFoot",
    "Foot_R": "mixamorig:RightFoot",
}

# --- UTILS ---

def clear_scene():
    bpy.context.preferences.edit.use_global_undo = False
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.outliner.orphans_purge()

def create_material(name, color, metallic=0.0, roughness=0.5):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.use_fake_user = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat

def create_primitive(name, type_name, scale=(1,1,1), material=None):
    bpy.ops.object.select_all(action='DESELECT')
    if type_name == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(size=1)
    elif type_name == 'SPHERE':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5)
    elif type_name == 'CYLINDER':
        bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1)
    
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if material:
        obj.data.materials.append(material)
    return obj

def parent_to_bone(obj, armature, bone_name):
    if not armature or bone_name not in armature.data.bones:
        print(f"BONE NOT FOUND: {bone_name}")
        return
    
    # Direct API parenting is more reliable in background mode
    obj.parent = armature
    obj.parent_type = 'BONE'
    obj.parent_bone = bone_name
    
    # Reset pose matrix so it stays at bone location
    bone_mat = armature.data.bones[bone_name].matrix_local
    obj.matrix_local = bone_mat.inverted() @ obj.matrix_local

class XBotCustomizer:
    def __init__(self):
        self.armature = None
        self.mat_steel = None
        self.mat_gold = None
        self.mat_leather = None
        self.mat_skin = None

    def setup_materials(self):
        self.mat_steel = create_material("Steel_Damascus", (0.3, 0.3, 0.35, 1), metallic=1.0, roughness=0.15)
        self.mat_gold = create_material("Gold_Royal", (0.85, 0.65, 0.1, 1), metallic=1.0, roughness=0.2)
        self.mat_leather = create_material("Leather_Worked", (0.15, 0.08, 0.04, 1), roughness=0.8)
        self.mat_skin = create_material("XBot_Skin", (0.6, 0.45, 0.4, 1), roughness=0.6)

    def import_base(self):
        print(f"Importing Base XBot...")
        bpy.ops.import_scene.gltf(filepath=XBOT_PATH)
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                self.armature = obj
                break
        self.armature.name = "XBot_Armature"
        self.armature.scale = (1, 1, 1)
        bpy.ops.object.select_all(action='DESELECT')
        self.armature.select_set(True)
        bpy.context.view_layer.objects.active = self.armature
        bpy.ops.object.transform_apply(scale=True)
        
        # Cleanup and FIX SKIN
        for obj in bpy.data.objects:
            if "Icosphere" in obj.name or "glTF_not_exported" in str(obj.users_collection):
                bpy.data.objects.remove(obj, do_unlink=True)
            elif obj.type == 'MESH' and "Beta" in obj.name:
                obj.data.materials.clear()
                obj.data.materials.append(self.mat_skin)

    def create_attachments(self):
        print("Adding high-quality attachments...")
        
        # 1. Chestplate
        chest = create_primitive("Chestplate", "CYLINDER", scale=(0.3, 0.22, 0.35), material=self.mat_steel)
        for v in chest.data.vertices:
            if v.co.z > 0: v.co.x *= 0.7; v.co.y *= 0.6
        parent_to_bone(chest, self.armature, BONES["Chest"])
        chest.rotation_euler = (math.radians(90), 0, 0)
        chest.location = (0, 0.38, 0.05)

        # 2. Pauldrons
        for side, bone_key in [("L", "Shoulder_L"), ("R", "Shoulder_R")]:
            p = create_primitive(f"Pauldron.{side}", "SPHERE", scale=(0.16, 0.1, 0.16), material=self.mat_steel)
            parent_to_bone(p, self.armature, BONES[bone_key])
            p.location = (0, 0.1, 0)

        # 3. Sword
        blade = create_primitive("Sword_Blade", "CUBE", scale=(0.04, 0.012, 0.9), material=self.mat_steel)
        guard = create_primitive("Sword_Guard", "CYLINDER", scale=(0.2, 0.04, 0.04), material=self.mat_gold)
        guard.location = (0, 0, -0.45); guard.rotation_euler = (0, math.radians(90), 0)
        hilt = create_primitive("Sword_Hilt", "CYLINDER", scale=(0.035, 0.035, 0.25), material=self.mat_leather)
        hilt.location = (0, 0, -0.6)
        
        bpy.ops.object.select_all(action='DESELECT')
        for o in [blade, guard, hilt]: o.select_set(True)
        bpy.context.view_layer.objects.active = blade
        bpy.ops.object.join()
        sword = bpy.context.active_object
        sword.name = "Sword"
        parent_to_bone(sword, self.armature, BONES["Hand_R"])
        sword.rotation_euler = (math.radians(-90), 0, math.radians(90))

        # 4. Shield
        s_body = create_primitive("Shield_Body", "CYLINDER", scale=(0.35, 0.35, 0.04), material=self.mat_leather)
        s_rim = create_primitive("Shield_Rim", "CYLINDER", scale=(0.36, 0.36, 0.03), material=self.mat_gold)
        bpy.ops.object.select_all(action='DESELECT')
        for o in [s_body, s_rim]: o.select_set(True)
        bpy.context.view_layer.objects.active = s_body
        bpy.ops.object.join()
        shield = bpy.context.active_object
        shield.name = "Shield"
        parent_to_bone(shield, self.armature, BONES["Forearm_L"])
        shield.location = (0, 0.2, -0.05)
        shield.rotation_euler = (0, 0, math.radians(90))

    def fix_action(self, action):
        fcurves = getattr(action, "fcurves", None)
        if not fcurves: return
        for fc in fcurves:
            path = fc.data_path
            for pref in ["Armature:", "XBot_Armature:", "mixamorig_"]:
                path = path.replace(pref, "")
            if 'pose.bones["' in path and 'mixamorig:' not in path:
                path = path.replace('pose.bones["', 'pose.bones["mixamorig:')
            try: fc.data_path = path
            except: pass

    def import_single_animation(self):
        anim_files = sorted(glob.glob(os.path.join(ANIM_DIR, "*.fbx")) + glob.glob(os.path.join(ANIM_DIR, "*.glb")))
        done_tracks = [t.name for t in self.armature.animation_data.nla_tracks] if self.armature.animation_data and self.armature.animation_data.nla_tracks else []
        
        for anim_path in anim_files:
            name = os.path.basename(anim_path).split('.')[0]
            if name in done_tracks or name in bpy.data.actions: continue

            print(f"Importing: {name}")
            bpy.ops.object.select_all(action='DESELECT') # CRITICAL: Don't delete existing items
            old_acts = set(bpy.data.actions.keys())
            try:
                if anim_path.endswith('.fbx'): bpy.ops.import_scene.fbx(filepath=anim_path, use_anim=True)
                else: bpy.ops.import_scene.gltf(filepath=anim_path)
            except: continue

            for act_key in (set(bpy.data.actions.keys()) - old_acts):
                action = bpy.data.actions[act_key]
                action.name = name
                action.use_fake_user = True
                self.fix_action(action)
                if not self.armature.animation_data: self.armature.animation_data_create()
                t = self.armature.animation_data.nla_tracks.new()
                t.name = name
                try: t.strips.new(name, int(action.frame_range[0]), action)
                except: pass

            # Delete only the objects from THIS import
            bpy.ops.object.delete()
            bpy.ops.outliner.orphans_purge()
            return True
        return False

    def run(self):
        if os.path.exists(OUTPUT_PATH):
            bpy.ops.wm.open_mainfile(filepath=OUTPUT_PATH)
            self.setup_materials()
            for o in bpy.data.objects:
                if o.type == 'ARMATURE': self.armature = o; break
        else:
            clear_scene()
            self.setup_materials()
            self.import_base()
            self.create_attachments()
            bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_PATH, compress=False)

        if self.import_single_animation():
            bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_PATH, compress=False)
            print("ANIM_IMPORTED")
        else:
            print("ALL_ANIMATIONS_DONE")
            bpy.ops.export_scene.gltf(filepath=OUTPUT_PATH.replace(".blend", ".glb"), export_format='GLB', export_anim_single_armature=True)
            bpy.ops.export_scene.fbx(filepath=OUTPUT_PATH.replace(".blend", ".fbx"), use_selection=False, bake_anim=True)
            print("EXPORTS_COMPLETE")

if __name__ == "__main__":
    XBotCustomizer().run()
