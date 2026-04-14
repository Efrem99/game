
import os
import re

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"
world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

# --- Patch SharuanWorld (Minimal) ---
if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    method_start_marker = 'def _build_ultimate_sandbox(self):'
    
    new_method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Minimal version to troubleshoot crash.\"\"\"
        if str(self.active_location).lower() != "ultimate_sandbox":
            return
        from utils.logger import logger
        logger.info("[SharuanWorld] Minimal Sandbox Triggered.")
"""
    
    if method_start_marker in content:
        pattern = re.escape(method_start_marker) + r".*?(?=\n\s*def|\Z)"
        content = re.sub(pattern, new_method_code, content, flags=re.DOTALL)
    
    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- Patch app.py (No profile extras) ---
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'elif profile == "ultimate_sandbox":' in content:
        spawn_logic = """elif profile == "ultimate_sandbox":
            if self.world:
                self.world.active_location = "ultimate_sandbox"
"""
        pattern = r'elif profile == "ultimate_sandbox":.*?elif profile == "music":'
        content = re.sub(pattern, spawn_logic + '        elif profile == "music":', content, flags=re.DOTALL)

    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Barebones Sandbox applied.")
