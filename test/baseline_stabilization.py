
import os
import re

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"
world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

# --- 1. Fix app.py (Disable complexpbr & Mute Vehicles/NPCs for sandbox) ---
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Disable complexpbr for this profile
    if 'if self._advanced_rendering:' in content:
        pbr_disable = """        # --- SANDBOX PBR STABILIZATION ---
        is_sandbox_profile = (str(getattr(self, "_test_profile", "")).lower() == "ultimate_sandbox")
        if is_sandbox_profile:
            logger.info("[Render] Disabling complexpbr for sandbox stability (Nuclear Option).")
            self._advanced_rendering = False
        
        if self._advanced_rendering:"""
        content = content.replace('if self._advanced_rendering:', pbr_disable)

    # Mute VehicleManager
    if 'self.transport_mgr.spawn_transports()' in content:
        mute_vehicles = """        if not is_sandbox_profile:
            self.transport_mgr.spawn_transports()
        else:
             logger.info("[Vehicle] Muting vehicles for sandbox.")"""
        content = content.replace('self.transport_mgr.spawn_transports()', mute_vehicles)

    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- 2. Fix SharuanWorld (Add location & Mute NPCs) ---
if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add ultimate_sandbox to locations list in __init__
    loc_inject = """            self.active_location = "ultimate_sandbox"
            # Prevent Old Forest override by making sandbox a real location
            self.locations.append({"name": "ultimate_sandbox", "pos": [0.0, 0.0, 5.0], "radius": 1000.0})
"""
    content = content.replace('self.active_location = "ultimate_sandbox"', loc_inject)

    # Mute _build_ultimate_sandbox NPCs (for now)
    # Actually, they are spawned in app.py's _apply_test_profile.
    # I already mutted them in my mind, let's mute them in code too.
    
    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- 3. Mute NPCs in app.py _apply_test_profile ---
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'self.npc_mgr.spawn_from_data({' in content:
        mute_npcs = "# self.npc_mgr.spawn_from_data({"
        content = content.replace('self.npc_mgr.spawn_from_data({', mute_npcs)
    
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Baseline Stabilization applied.")
