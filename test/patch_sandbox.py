
import os
import re

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"
world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

# Patch app.py
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Add spawn location
    if '"ultimate_sandbox"' not in content:
        # Try a more generic pattern
        pattern = r'("dwarven_caves_throne":\s*Vec3\(.*?\))'
        if re.search(pattern, content):
            content = re.sub(pattern, r'\1,\n            "ultimate_sandbox": Vec3(150.0, 150.0, 5.0)', content)
            print("Patched app.py spawn locations")
        else:
            print("Could not find spawn location pattern")

    # 2. Fix active_location string case in _apply_test_profile to match SharuanWorld check
    content = content.replace('self.world.active_location = "Ultimate Sandbox"', 'self.world.active_location = "ultimate_sandbox"')
    print("Standardized active_location string case in app.py")

    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

# Patch sharuan_world.py - ensure the check is robust
if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        w_content = f.read()
    
    # Ensure active_location check is case-insensitive for safety
    w_content = w_content.replace('if self.active_location != "ultimate_sandbox":', 'if str(self.active_location).lower() != "ultimate_sandbox":')
    
    # Add explicit climbing markers if not present
    if "sandbox_climb_tower" not in w_content:
        print("Climbing geometry should already be in the appended method from previous turn.")

    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(w_content)

print("Final patching complete.")
