
import os
import re

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"
world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

# --- Patch SharuanWorld (Safe Version) ---
if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    method_start_marker = 'def _build_ultimate_sandbox(self):'
    
    new_method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Consolidated test arena: parkour, wallrun, climbing, swimming, combat, loot, flight.\"\"\"
        if str(self.active_location).lower() != "ultimate_sandbox":
            return

        tx, ty = 150.0, 150.0
        center_z = self._th(tx, ty)
        
        stone_mat = mk_mat((0.48, 0.46, 0.44, 1.0), 0.72, 0.04)
        dirt_mat = mk_mat((0.38, 0.32, 0.24, 1.0), 0.90, 0.0)
        water_mat = mk_mat((0.12, 0.32, 0.52, 0.78), 0.10, 0.20)
        wood_mat = mk_mat((0.28, 0.18, 0.10, 1.0), 0.82, 0.0)
        accent_mat = mk_mat((0.8, 0.6, 0.2, 1.0), 0.3, 0.6)
        
        from panda3d.core import TransparencyAttrib
        import random, math
        rng = random.Random(42)
        
        # 1. Main Plaza Base
        self._pl(
            mk_plane("sandbox_base", 150.0, 150.0, 3.0),
            tx, ty, center_z + 0.1,
            self.tx.get("dirt"), dirt_mat, "Ultimate Sandbox",
            is_platform=False
        )
        
        # 2. Parkour Zone
        for i in range(8):
            h = 1.2 + (i * 1.5)
            # Use simple cubes
            self._pl(
                mk_box(f"sandbox_cube_{i}", 4.0, 4.0, h),
                tx + 20.0 + (i * 5.0), ty + (3.0 if i % 2 == 0 else -3.0),
                center_z + (h * 0.5),
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
            )
            
        # 3. Wallrun & Climbing Area
        self._pl(mk_box("sandbox_wallrun", 1.2, 50.0, 14.0), tx-25.0, ty, center_z+7.0, self.tx.get("stone"), stone_mat, "Ultimate Sandbox")
        self._pl(mk_box("sandbox_climb_tower", 8.0, 8.0, 20.0), tx-15.0, ty-40.0, center_z+10.0, self.tx.get("stone"), stone_mat, "Ultimate Sandbox")
        
        # 4. Swimming Pool
        self._pl(mk_plane("sandbox_water", 40.0, 30.0, 5.0), tx, ty+45.0, center_z-3.0, None, water_mat, "Ultimate Sandbox", is_platform=False)
        
        # 5. Flight Launch Pad (Simple Cylinder)
        self._pl(mk_cyl("sandbox_flight_pad", 6.0, 1.2, 12), tx+40.0, ty-20.0, center_z+0.6, self.tx.get("stone"), stone_mat, "Ultimate Sandbox")

        # 6. Combat Markers
        self._pl(mk_box("dragon_marker", 6, 6, 0.5), tx+60, ty+60, center_z+0.25, None, mk_mat((1,0,0,1)), "Ultimate Sandbox", is_platform=False)
        self._pl(mk_box("golem_marker", 4, 4, 0.5), tx-60, ty+60, center_z+0.25, None, mk_mat((0,0,1,1)), "Ultimate Sandbox", is_platform=False)

        # 7. Interactive Props
        c = self._pl(mk_box("sandbox_chest", 1.4, 0.9, 1.0), tx+8, ty+8, center_z+0.5, self.tx.get("wood"), wood_mat, "Ultimate Sandbox")
        self._register_story_anchor("sandbox_chest_s", c, name="Sandbox Chest", hint="Open Chest")
        
        b = self._pl(mk_box("sandbox_book", 0.5, 0.7, 0.1), tx-8, ty+8, center_z+0.05, None, mk_mat((0.2,0.4,1)), "Ultimate Sandbox")
        self._register_story_anchor("sandbox_book_s", b, name="Sandbox Book", hint="Read Book")

        from utils.logger import logger
        logger.info(f"[SharuanWorld] Ultimate Sandbox Safe Version at ({tx}, {ty})")
"""
    
    if method_start_marker in content:
        pattern = re.escape(method_start_marker) + r".*?(?=\n\s*def|\Z)"
        content = re.sub(pattern, new_method_code, content, flags=re.DOTALL)
        print("Updated SharuanWorld for 'Safe' Ultimate Sandbox")
    else:
        content += new_method_code
        print("Appended Safe Sandbox code to SharuanWorld")
        
    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- Patch app.py (Sanitize test profile) ---
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ensure profile spawning logic is correct
    if 'elif profile == "ultimate_sandbox":' in content:
        spawn_logic = """elif profile == "ultimate_sandbox":
            if self.world:
                self.world.active_location = "ultimate_sandbox"
            
            p = self.player.actor.getPos(self.render) if self.player and self.player.actor else Vec3(150, 150, 5)
            
            if self.npc_mgr:
                self.npc_mgr.spawn_from_data({
                    "sandbox_wolf_1": {"name": "Wolf 1", "role": "enemy", "pos": [165, 165, 5], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.1}},
                    "sandbox_wolf_2": {"name": "Wolf 2", "role": "enemy", "pos": [135, 165, 5], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.1}},
                    "sandbox_guard": {"name": "Guard", "role": "guard", "pos": [150, 135, 5], "appearance": {"species": "dracolid", "scale": 1.1}}
                })
        """
        # Match the block carefully
        pattern = r'elif profile == "ultimate_sandbox":.*?elif profile == "music":'
        content = re.sub(pattern, spawn_logic + '        elif profile == "music":', content, flags=re.DOTALL)
        print("Sanitized boss positioning logic in app.py (Removing dangerous setPos calls)")

    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Safe Sandbox applied.")
