import bpy
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = PROJECT_ROOT / "models" / "xbot_customized_slim.blend"

def check_state():
    if not os.path.exists(BLEND_PATH):
        print("ERROR: File not found!")
        return
        
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_PATH))
    print("\n--- STATUS CHECK ---")
    
    # 1. Workspace
    print(f"Current Workspace: {bpy.context.workspace.name}")
    
    # 2. Objects and Visibility
    print("\nObjects Visibility & Parenting:")
    for obj in bpy.data.objects:
        if obj.type == 'MESH' or obj.type == 'ARMATURE':
            v = "VISIBLE" if not obj.hide_viewport else "HIDDEN"
            p = obj.parent.name if obj.parent else "None"
            b = obj.parent_bone if obj.parent_bone else "None"
            print(f"  {obj.name:<20} | {v:<10} | Parent: {p:<20} | Bone: {b}")

    # 3. Animations
    arm = bpy.data.objects.get("XBot_Armature")
    if arm and arm.animation_data:
        print(f"\nNLA Tracks: {len(arm.animation_data.nla_tracks)}")
        for t in arm.animation_data.nla_tracks:
            mute = "MUTED" if t.mute else "ACTIVE"
            print(f"  Track: {t.name:<20} | {mute}")
    else:
        print("\nNLA Tracks: None or Armature missing")
        
    print("\n--- CHECK COMPLETE ---")

if __name__ == "__main__":
    check_state()
