"""Blender script to add a comprehensive set of corrective helper bones and drivers.

Run:
  blender assets/models/hero/sherward/sherward_rework.blend -b -P tools/blender/add_corrective_bones.py
"""

import bpy
import math

def add_corrective_driver(armature, bone_name, target_bone, prop, axis_idx, transform_type, expression):
    """Add a scripted driver to a bone property."""
    pose_bone = armature.pose.bones.get(bone_name)
    if not pose_bone:
        return

    # Blender 5 PoseBone no longer exposes animation_data directly.
    # Re-runs rely on driver_add replacing/reusing matching channels below.

    fcurve = pose_bone.driver_add(prop, axis_idx)
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    
    var = driver.variables.new()
    var.name = "rot"
    var.type = 'TRANSFORMS'
    
    target = var.targets[0]
    target.id = armature
    target.bone_target = target_bone
    target.transform_type = transform_type
    target.transform_space = 'LOCAL_SPACE'
    
    driver.expression = expression

def setup_corrective_rig():
    # Find armature
    armature = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break
            
    if not armature:
        print("No armature found in scene.")
        return

    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    
    # helper mapping: (Parent, TargetJoint, CorrectiveName, TransformType, ExpressionLoc, ExpressionScale)
    # Note: ExpressionLoc is Y-offset (local forward), ExpressionScale is X/Z bulge
    helpers_config = [
        # Arms
        ("mixamorig:LeftArm", "mixamorig:LeftForeArm", "elbow_corr_L", 'ROT_X', "abs(rot)*0.1", "1.0+abs(rot)*0.2"),
        ("mixamorig:RightArm", "mixamorig:RightForeArm", "elbow_corr_R", 'ROT_X', "abs(rot)*0.1", "1.0+abs(rot)*0.2"),
        ("mixamorig:LeftShoulder", "mixamorig:LeftArm", "shoulder_corr_L", 'ROT_Z', "abs(rot)*0.08", "1.0+abs(rot)*0.15"),
        ("mixamorig:RightShoulder", "mixamorig:RightArm", "shoulder_corr_R", 'ROT_Z', "abs(rot)*0.08", "1.0+abs(rot)*0.15"),
        ("mixamorig:LeftForeArm", "mixamorig:LeftHand", "wrist_corr_L", 'ROT_X', "abs(rot)*0.05", "1.0+abs(rot)*0.1"),
        ("mixamorig:RightForeArm", "mixamorig:RightHand", "wrist_corr_R", 'ROT_X', "abs(rot)*0.05", "1.0+abs(rot)*0.1"),
        
        # Legs
        ("mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "knee_corr_L", 'ROT_X', "abs(rot)*0.1", "1.0+abs(rot)*0.25"),
        ("mixamorig:RightUpLeg", "mixamorig:RightLeg", "knee_corr_R", 'ROT_X', "abs(rot)*0.1", "1.0+abs(rot)*0.25"),
        ("mixamorig:Hips", "mixamorig:LeftUpLeg", "hip_corr_L", 'ROT_X', "abs(rot)*0.12", "1.0+abs(rot)*0.2"),
        ("mixamorig:Hips", "mixamorig:RightUpLeg", "hip_corr_R", 'ROT_X', "abs(rot)*0.12", "1.0+abs(rot)*0.2"),
        
        # Feet
        ("mixamorig:LeftLeg", "mixamorig:LeftFoot", "heel_corr_L", 'ROT_X', "abs(rot)*0.06", "1.0+abs(rot)*0.1"),
        ("mixamorig:RightLeg", "mixamorig:RightFoot", "heel_corr_R", 'ROT_X', "abs(rot)*0.06", "1.0+abs(rot)*0.1"),
        ("mixamorig:LeftFoot", "mixamorig:LeftToeBase", "midfoot_corr_L", 'ROT_X', "abs(rot)*0.04", "1.0+abs(rot)*0.08"),
        ("mixamorig:RightFoot", "mixamorig:RightToeBase", "midfoot_corr_R", 'ROT_X', "abs(rot)*0.04", "1.0+abs(rot)*0.08"),
        
        # Torso/Neck
        ("mixamorig:Spine1", "mixamorig:Spine2", "torso_corr", 'ROT_X', "abs(rot)*0.08", "1.0+abs(rot)*0.12"),
        ("mixamorig:Spine2", "mixamorig:Neck", "neck_corr", 'ROT_X', "abs(rot)*0.05", "1.0+abs(rot)*0.1"),
        
        # Fingers (Detailed for all phalanges L/R)
        # ----------------------------------------
        *[(f"mixamorig:LeftHand{f}{i}", f"mixamorig:LeftHand{f}{i+1}", f"finger_{f}{i}_corr_L", 'ROT_X', "abs(rot)*0.04", "1.0+abs(rot)*0.08") 
          for f in ["Thumb", "Index", "Middle", "Ring", "Pinky"] for i in [1, 2]],
        *[(f"mixamorig:RightHand{f}{i}", f"mixamorig:RightHand{f}{i+1}", f"finger_{f}{i}_corr_R", 'ROT_X', "abs(rot)*0.04", "1.0+abs(rot)*0.08") 
          for f in ["Thumb", "Index", "Middle", "Ring", "Pinky"] for i in [1, 2]],

        # Torso & Bio-Core
        # -------------------
        ("mixamorig:Hips", "mixamorig:Spine", "pelvis_corr", 'ROT_X', "abs(rot)*0.08", "1.0+abs(rot)*0.15"),
        ("mixamorig:Spine", "mixamorig:Spine1", "spine_lower_corr", 'ROT_X', "abs(rot)*0.04", "1.0+abs(rot)*0.08"),
        ("mixamorig:Spine1", "mixamorig:Spine2", "torso_mid_corr", 'ROT_X', "abs(rot)*0.06", "1.0+abs(rot)*0.12"),
        ("mixamorig:Spine2", "mixamorig:Neck", "neck_base_corr", 'ROT_X', "abs(rot)*0.05", "1.0+abs(rot)*0.1"),
        ("mixamorig:Neck", "mixamorig:Head", "neck_upper_corr", 'ROT_X', "abs(rot)*0.04", "1.0+abs(rot)*0.08"),
    ]
    
    edit_bones = armature.data.edit_bones
    active_helpers = []
    
    for parent_name, target_name, corr_name, t_type, exp_loc, exp_scale in helpers_config:
        parent = edit_bones.get(parent_name)
        if not parent:
            print(f"Parent bone {parent_name} not found.")
            continue
            
        if corr_name in edit_bones:
            # Update existing if possible, or just skip
            # For simplicity, we skip re-creation but will re-setup pose drivers
            print(f"Corrective bone {corr_name} already exists. Updating drivers...")
            active_helpers.append((corr_name, target_name, t_type, exp_loc, exp_scale))
            continue
            
        # Create helper at the joint (tip of parent)
        bone = edit_bones.new(corr_name)
        bone.head = parent.tail
        # Pointing slightly along the parent direction
        dir_vec = (parent.tail - parent.head).normalized()
        bone.tail = parent.tail + dir_vec * 0.05
        bone.parent = parent
        bone.use_deform = True
        active_helpers.append((corr_name, target_name, t_type, exp_loc, exp_scale))
        
    bpy.ops.object.mode_set(mode='POSE')
    
    # Setup drivers
    for corr_name, target_name, t_type, exp_loc, exp_scale in active_helpers:
        # location[1] is Y (local forward/outward for many mixamo bones)
        add_corrective_driver(armature, corr_name, target_name, "location", 1, t_type, exp_loc)
        # scale X and Z for bulge
        add_corrective_driver(armature, corr_name, target_name, "scale", 0, t_type, exp_scale)
        add_corrective_driver(armature, corr_name, target_name, "scale", 2, t_type, exp_scale)

    print(f"Corrective rig setup complete. Processed {len(active_helpers)} joints.")
    
    # Save a copy
    output_path = bpy.data.filepath.replace(".blend", "_full_corrective.blend")
    bpy.ops.wm.save_as_mainfile(filepath=output_path)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    setup_corrective_rig()
