
import bpy
import bmesh
import math
from mathutils import Vector

def _log(msg):
    print(f"[ShapeKeyGen] {msg}")

def ensure_shape_keys(obj):
    if not obj.data.shape_keys:
        obj.shape_key_add(name="Basis")
    return obj.data.shape_keys

def create_proximity_shape_key(obj, name, center, radius, offset):
    """
    Moves vertices within radius of center by offset.
    Used for basic blinking/speech.
    """
    sk = obj.shape_key_add(name=name, from_mix=False)
    matrix_world_inv = obj.matrix_world.inverted()
    local_center = matrix_world_inv @ center
    local_offset = matrix_world_inv.to_quaternion() @ offset
    
    # Falloff: vertices closer to center move more
    for i, v in enumerate(obj.data.vertices):
        dist = (v.co - local_center).length
        if dist < radius:
            weight = 1.0 - (dist / radius)
            # Apply smooth falloff
            weight = weight * weight * (3 - 2 * weight)
            sk.data[i].co += local_offset * weight
    return sk

def setup_facial_expressions():
    # 1. Find the Head mesh
    head_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and ("head" in obj.name.lower() or "hero" in obj.name.lower()):
            # Select the one with substantial vertices but smaller than body
            if 1000 < len(obj.data.vertices) < 10000:
                head_obj = obj
                break
    
    if not head_obj:
        # Fallback: largest mesh if head specifically not found
        head_obj = sorted([o for o in bpy.data.objects if o.type == 'MESH'], 
                          key=lambda o: len(o.data.vertices), reverse=True)[0]

    _log(f"Targeting mesh for shape keys: {head_obj.name}")
    ensure_shape_keys(head_obj)
    
    # 2. Find Head Bone for reference
    armature = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    head_bone = armature.pose.bones.get("mixamorig:Head") or armature.pose.bones.get("Head")
    
    if not head_bone:
        _log("Head bone not found, skipping shape key generation.")
        return

    # Head world position
    head_world_pos = armature.matrix_world @ head_bone.head
    
    # 3. Generate Basic Keys
    # NOTE: These offsets are estimates for a standard humanoid at 1.85m height.
    
    # Blinking (Eyelids)
    create_proximity_shape_key(head_obj, "Eyes_Close_L", 
                               head_world_pos + Vector((0.032, 0.065, 0.05)), 
                               radius=0.03, offset=Vector((0, 0, -0.012)))
    create_proximity_shape_key(head_obj, "Eyes_Close_R", 
                               head_world_pos + Vector((-0.032, 0.065, 0.05)), 
                               radius=0.03, offset=Vector((0, 0, -0.012)))
    
    # Eyebrows (Emotions)
    create_proximity_shape_key(head_obj, "Angry_Brows", 
                               head_world_pos + Vector((0.0, 0.07, 0.08)), 
                               radius=0.08, offset=Vector((0, 0.01, -0.015)))
    create_proximity_shape_key(head_obj, "Surprise_Brows", 
                               head_world_pos + Vector((0.0, 0.07, 0.08)), 
                               radius=0.08, offset=Vector((0, -0.01, 0.02)))

    # Mouth (Speech & Emotion)
    # Open
    create_proximity_shape_key(head_obj, "Mouth_Open", 
                               head_world_pos + Vector((0.0, 0.08, -0.08)), 
                               radius=0.06, offset=Vector((0, 0.01, -0.03)))
    # Smile (Corner lift)
    create_proximity_shape_key(head_obj, "Smile", 
                               head_world_pos + Vector((0.0, 0.08, -0.07)), 
                               radius=0.08, offset=Vector((0, -0.015, 0.01)))
    # Sad (Corner drop)
    create_proximity_shape_key(head_obj, "Sad", 
                               head_world_pos + Vector((0.0, 0.08, -0.07)), 
                               radius=0.08, offset=Vector((0, 0.01, -0.015)))

    # Jaw (Structural)
    create_proximity_shape_key(head_obj, "Jaw_Drop", 
                               head_world_pos + Vector((0.0, 0.05, -0.12)), 
                               radius=0.1, offset=Vector((0, 0.03, -0.05)))

    _log(f"Advanced Facial Pack created on {head_obj.name}")

if __name__ == "__main__":
    setup_facial_expressions()
