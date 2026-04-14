
import os
import re

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"
world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

# --- Patch SharuanWorld (Void World Logic) ---
if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Patch __init__ to detect sandbox early
    init_detect_logic = """        self.tx = {}
        
        # --- VOID SANDBOX DETECTION ---
        is_sandbox = (str(getattr(app, "_test_profile", "")).lower() == "ultimate_sandbox" or 
                    str(getattr(app, "_test_location_raw", "")).lower() == "ultimate_sandbox")
        
        if is_sandbox:
            self.active_location = "ultimate_sandbox"
            self._gen_steps = [
                (0.2, self._init_textures, "Waking up the void..."),
                (1.0, self._build_ultimate_sandbox, "Forging the Ultimate Sandbox..."),
            ]
        else:
            self._gen_steps = [
"""
    content = content.replace('self.tx = {}\n        self._gen_steps = [', init_detect_logic)
    
    # 2. Patch _build_ultimate_sandbox with "Beautiful" but safe version at (0,0,5)
    new_method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Isolated Void Sandbox: Beautiful testing grounds at (0,0,5).\"\"\"
        if str(self.active_location).lower() != "ultimate_sandbox":
            return

        tx, ty, tz = 0.0, 0.0, 5.0
        
        stone_mat = mk_mat((0.48, 0.46, 0.44, 1.0), 0.72, 0.04)
        dirt_mat = mk_mat((0.38, 0.32, 0.24, 1.0), 0.90, 0.0)
        water_mat = mk_mat((0.12, 0.32, 0.52, 0.78), 0.10, 0.20)
        wood_mat = mk_mat((0.28, 0.18, 0.10, 1.0), 0.82, 0.0)
        accent_mat = mk_mat((0.8, 0.6, 0.2, 1.0), 0.3, 0.6)
        
        from panda3d.core import TransparencyAttrib, Vec3
        import random, math
        rng = random.Random(42)
        
        # 1. Isolated Base (Stone/Dirt mix)
        self._pl(
            mk_box("sandbox_void_base", 160.0, 160.0, 1.2),
            tx, ty, tz - 0.6,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox",
            is_platform=True
        )
        
        # 2. Parkour Zone (Floating Cubes)
        for i in range(12):
            h = 1.0 + (i * 0.8)
            self._pl(
                mk_box(f"sandbox_cube_{i}", 4.0, 4.0, h),
                tx + 25.0 + (i * 6.0), ty + (5.0 if i % 2 == 0 else -5.0),
                tz + (h * 0.5),
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
            )
            
        # 3. Wallrun & Climbing Area
        # Long wall for wallrun
        self._pl(mk_box("sandbox_wallrun", 1.5, 60.0, 16.0), tx-35.0, ty, tz+8.0, self.tx.get("stone"), stone_mat, "Ultimate Sandbox")
        # High Climbing Tower
        self._pl(mk_box("sandbox_climb_tower", 10.0, 10.0, 30.0), tx-20.0, ty-50.0, tz+15.0, self.tx.get("stone"), stone_mat, "Ultimate Sandbox")
        
        # 4. Swimming / Diving Pool
        # Build a "glass" container for water
        self._pl(mk_box("pool_frame", 50.0, 40.0, 6.0), tx, ty+50.0, tz-3.0, None, stone_mat, "Ultimate Sandbox")
        self._pl(mk_plane("sandbox_water", 48.0, 38.0, 5.0), tx, ty+50.0, tz-0.1, None, water_mat, "Ultimate Sandbox", is_platform=False)
        
        # 5. Flight Launch Pad with Floating Rings
        # Pad
        self._pl(mk_cyl("sandbox_flight_pad", 8.0, 2.0, 16), tx+50.0, ty-30.0, tz+1.0, self.tx.get("stone"), stone_mat, "Ultimate Sandbox")
        # Rings
        for i in range(5):
            angle = i * 0.4
            rx = tx + 50.0 + math.cos(angle) * 30.0
            ry = ty - 30.0 + math.sin(angle) * 30.0
            rz = tz + 15.0 + (i * 8.0)
            ring = self._pl(mk_cyl(f"flight_ring_{i}", 6.0, 0.4, 12), rx, ry, rz, None, accent_mat, "Ultimate Sandbox", is_platform=False)
            ring.setP(90)
            
        # 6. "Real" Scenery Props (Trees, Rocks in the void)
        models = self._collect_world_model_paths("trees", ["common_tree_1.glb", "pine_tree_2.glb"])
        for i in range(15):
            if not models: break
            mx = tx + rng.uniform(-70, 70)
            my = ty + rng.uniform(-70, 70)
            if abs(mx - tx) < 15 and abs(my - ty) < 15: continue # clear spawn area
            self._spawn_world_model(rng.choice(models), mx, my, tz, scale=rng.uniform(0.8, 1.4), h=rng.uniform(0, 360))

        # 7. Interactive Story Pillars (Books / Chests)
        chest = self._pl(mk_box("sandbox_chest_void", 1.6, 1.0, 1.1), tx+12, ty+12, tz+0.55, self.tx.get("wood"), wood_mat, "Ultimate Sandbox")
        self._register_story_anchor("sandbox_chest_v", chest, name="Void Treasure", hint="Loot Chest")
        
        book = self._pl(mk_box("sandbox_book_void", 0.6, 0.8, 0.15), tx-12, ty+12, tz+0.05, None, mk_mat((0.15,0.3,0.9)), "Ultimate Sandbox")
        self._register_story_anchor("sandbox_book_v", book, name="Void Chronicles", hint="Read Insights")

        from utils.logger import logger
        logger.info(f"[SharuanWorld] Isolated Void Sandbox built at ({tx}, {ty}, {tz})")
"""
    # Replace the existing _build_ultimate_sandbox (which is currently the barebones one)
    pattern = r'def _build_ultimate_sandbox\(self\):.*?logger\.info\("\[SharuanWorld\] Minimal Sandbox Triggered\."\)'
    content = re.sub(pattern, new_method_code, content, flags=re.DOTALL)

    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- Patch app.py (Adjust coordinates for Void) ---
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update global coordinate to (0,0,10) for safe drop onto platform
    content = content.replace('"ultimate_sandbox": Vec3(50.0, 50.0, 5.0),', '"ultimate_sandbox": Vec3(0.0, 0.0, 10.0),')

    # Update profile logic to move player to void center
    if 'elif profile == "ultimate_sandbox":' in content:
        spawn_logic = """elif profile == "ultimate_sandbox":
            if self.world:
                self.world.active_location = "ultimate_sandbox"
            
            # Move player to Void center (0,0,10)
            if self.player and self.player.actor:
                self.player.actor.setPos(0.0, 0.0, 10.0)
                if hasattr(self, 'char_state') and self.char_state:
                    try:
                        import panda3d.core as p3d
                        self.char_state.position = p3d.LPoint3f(0.0, 0.0, 10.0)
                        self.char_state.velocity = p3d.LVecBase3f(0,0,0)
                    except: pass
            
            if self.npc_mgr:
                self.npc_mgr.spawn_from_data({
                    "sandbox_wolf_1": {"name": "Wolf 1", "role": "enemy", "pos": [15, 15, 5], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.1}},
                    "sandbox_wolf_2": {"name": "Wolf 2", "role": "enemy", "pos": [-15, 15, 5], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.1}},
                    "sandbox_guard": {"name": "Sentinel", "role": "guard", "pos": [0, 18, 5], "appearance": {"species": "dracolid", "scale": 1.1}},
                    "sandbox_golem": {"name": "Boss Golem", "role": "enemy", "pos": [-40, 40, 5], "appearance": {"model": "assets/models/enemies/golem.glb", "scale": 2.5}}
                })
        """
        pattern = r'elif profile == "ultimate_sandbox":.*?elif profile == "music":'
        content = re.sub(pattern, spawn_logic + '        elif profile == "music":', content, flags=re.DOTALL)

    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Isolated Void World applied.")
