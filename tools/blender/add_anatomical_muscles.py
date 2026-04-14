
import bpy
from mathutils import Vector

def _log(msg):
    print(f"[Anatomy] {msg}")

def add_muscle_driver(obj, shape_key_name, armature, bone_name, transform_type, axis, expression):
    """Link shape key value to bone rotation."""
    if not obj.data.shape_keys:
        return
    
    sk = obj.data.shape_keys.key_blocks.get(shape_key_name)
    if not sk:
        return
        
    driver = sk.driver_add("value").driver
    driver.type = 'SCRIPTED'
    
    var = driver.variables.new()
    var.name = "rot"
    var.type = 'TRANSFORMS'
    
    target = var.targets[0]
    target.id = armature
    target.bone_target = bone_name
    target.transform_type = transform_type
    target.transform_space = 'LOCAL_SPACE'
    
    driver.expression = expression

def create_muscle_bulge(obj, name, vg_name, scale_factor=0.08):
    """Create a shape key that 'inflates' vertices in a vertex group."""
    if not obj.data.shape_keys:
        obj.shape_key_add(name="Basis")
    
    sk = obj.shape_key_add(name=name, from_mix=False)
    vg = obj.vertex_groups.get(vg_name)
    if not vg:
        _log(f"Vertex group {vg_name} not found for {name}")
        return None

    # Calculate center of the group for outward direction
    # Simple strategy: move vertices along their normals scaled by weight
    for i, v in enumerate(obj.data.vertices):
        weight = 0.0
        for g in v.groups:
            if g.group == vg.index:
                weight = g.weight
                break
        
        if weight > 0.1:
            # Move along normal
            sk.data[i].co += v.normal * (scale_factor * weight)
            
    return sk

def setup_anatomical_muscles():
    _log("Injecting Bio-Anatomical Muscle Pack...")
    
    # Robustly find Body and Legs (assuming Body is Largest, Legs is Second Largest)
    all_meshes = sorted([o for o in bpy.data.objects if o.type == 'MESH'], 
                        key=lambda o: len(o.data.vertices), reverse=True)
    
    if len(all_meshes) < 2:
        _log(f"Failed to find enough meshes (Found: {len(all_meshes)})")
        return

    body = all_meshes[0]
    legs = all_meshes[1]
                
    _log(f"Recognized Body: {body.name}, Legs: {legs.name}")

    armature = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    
    # 1. Biceps (L/R)
    # Driven by Elbow rotation (ROT_X or ROT_Z depending on orientation)
    create_muscle_bulge(body, "Musc_Bicep_L", "mixamorig:LeftArm", scale_factor=0.12)
    create_muscle_bulge(body, "Musc_Bicep_R", "mixamorig:RightArm", scale_factor=0.12)
    
    # 2. Quads (L/R)
    create_muscle_bulge(legs, "Musc_Quad_L", "mixamorig:LeftUpLeg", scale_factor=0.15)
    create_muscle_bulge(legs, "Musc_Quad_R", "mixamorig:RightUpLeg", scale_factor=0.15)
    
    # 3. Pectorals (L/R)
    create_muscle_bulge(body, "Musc_Pec_L", "mixamorig:LeftShoulder", scale_factor=0.08)
    create_muscle_bulge(body, "Musc_Pec_R", "mixamorig:RightShoulder", scale_factor=0.08)

    # 4. Setup Drivers (PSD logic)
    # Bicep bulge when forearm is bent (ROT_X usually)
    # Expression: abs(rot) * factor
    add_muscle_driver(body, "Musc_Bicep_L", armature, "mixamorig:LeftForeArm", 'ROT_X', 0, "abs(rot)*0.6")
    add_muscle_driver(body, "Musc_Bicep_R", armature, "mixamorig:RightForeArm", 'ROT_X', 0, "abs(rot)*0.6")
    
    # Quad bulge when leg is bent
    add_muscle_driver(legs, "Musc_Quad_L", armature, "mixamorig:LeftLeg", 'ROT_X', 0, "abs(rot)*0.5")
    add_muscle_driver(legs, "Musc_Quad_R", armature, "mixamorig:RightLeg", 'ROT_X', 0, "abs(rot)*0.5")

    _log("Muscle Pack Integrated with PSD Drivers.")

if __name__ == "__main__":
    setup_anatomical_muscles()
