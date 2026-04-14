
import bpy
import bmesh
from mathutils import Vector

def _log(msg):
    print(f"[Shaping] {msg}")

def adjust_proportions():
    _log("Fixing 'feminine' proportions...")
    
    # Target mesh: Body
    body = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and ("body" in obj.name.lower() or "hero" in obj.name.lower()):
            body = obj
            break
            
    if not body:
        _log("Body mesh not found.")
        return

    # 1. Widen shoulders (mixamorig:LeftShoulder / RightShoulder)
    # We move them further apart on X-axis
    armature = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    
    shoulder_l = armature.data.edit_bones.get("mixamorig:LeftShoulder")
    shoulder_r = armature.data.edit_bones.get("mixamorig:RightShoulder")
    
    if shoulder_l and shoulder_r:
        # Move them outward by ~2cm
        offset = 0.02
        shoulder_l.head.x += offset
        shoulder_l.tail.x += offset
        shoulder_r.head.x -= offset
        shoulder_r.tail.x -= offset
        _log("Shoulders widened.")

    bpy.ops.object.mode_set(mode='OBJECT')

    # 2. Straighten waist (Spine1 / Spine2 area)
    # Original 'xbot' has a narrow waist. We'll increase X scale of the mesh around Spine1.
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(body.data)
    
    # Identify vertex groups
    vg_spine1 = body.vertex_groups.get("mixamorig:Spine1")
    vg_hips = body.vertex_groups.get("mixamorig:Hips")
    
    if vg_spine1:
        # Indices of vertices in Spine1 group
        idx_set = {vg_spine1.index}
        for v in bm.verts:
            for g in v.link_faces: # Not used, just checking loop
                pass
            
            # Simple check for weight
            weight = 0.0
            try:
                # In BMesh, weights are accessed via layers
                d_layer = bm.verts.layers.deform.active
                if d_layer:
                    weight = v[d_layer].get(vg_spine1.index, 0.0)
            except:
                pass
                
            if weight > 0.4: # Only mid-spine area
                # Expand outward on X
                # factor based on weight for smooth falloff
                factor = 1.0 + (weight * 0.15) # +15% width at peak
                v.co.x *= factor
                
        _log("Waist narrowing reduced (Square-off applied).")

    bmesh.update_edit_mesh(body.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    _log("Character proportions finalized.")

if __name__ == "__main__":
    adjust_proportions()
