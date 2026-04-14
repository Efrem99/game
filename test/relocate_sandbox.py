
import os
import re

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"
world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

# --- Patch SharuanWorld (Relocated) ---
if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    method_start_marker = 'def _build_ultimate_sandbox(self):'
    
    # Relocate to (50, 50) - which is inside the 200x200 terrain (-100 to 100)
    new_method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Relocated minimal version at (50, 50).\"\"\"
        if str(self.active_location).lower() != "ultimate_sandbox":
            return
            
        tx, ty = 50.0, 50.0
        center_z = self._th(tx, ty)
        stone_mat = mk_mat((0.48, 0.46, 0.44, 1.0), 0.72, 0.04)
        
        # Base platform to ensure we have ground
        self._pl(
            mk_box("sandbox_base_safe", 40.0, 40.0, 1.0),
            tx, ty, center_z - 0.4,
            None, stone_mat, "Ultimate Sandbox",
            is_platform=True
        )
        
        from utils.logger import logger
        logger.info(f"[SharuanWorld] Relocated Sandbox built at ({tx}, {ty}, {center_z})")
"""
    
    if method_start_marker in content:
        pattern = re.escape(method_start_marker) + r".*?(?=\n\s*def|\Z)"
        content = re.sub(pattern, new_method_code, content, flags=re.DOTALL)
    
    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- Patch app.py (Move player and fix coordinates) ---
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update global coordinate
    content = content.replace('"ultimate_sandbox": Vec3(150.0, 150.0, 5.0),', '"ultimate_sandbox": Vec3(50.0, 50.0, 5.0),')

    # Update profile logic to move player explicitly
    if 'elif profile == "ultimate_sandbox":' in content:
        spawn_logic = """elif profile == "ultimate_sandbox":
            if self.world:
                self.world.active_location = "ultimate_sandbox"
            
            # Move player to relocated sandbox
            if self.player and self.player.actor:
                self.player.actor.setPos(50.0, 50.0, 8.0)
                if hasattr(self, 'char_state') and self.char_state:
                    try:
                        import complexpbr as cp # use same name as app.py
                        import panda3d.core as p3d
                        # Try to move collision state if it exists
                        self.char_state.position = p3d.LPoint3f(50.0, 50.0, 8.0)
                    except: pass
"""
        pattern = r'elif profile == "ultimate_sandbox":.*?elif profile == "music":'
        content = re.sub(pattern, spawn_logic + '        elif profile == "music":', content, flags=re.DOTALL)

    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Relocated Sandbox applied.")
