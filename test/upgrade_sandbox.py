
import os
import re

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"
world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

# --- Patch SharuanWorld ---
if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 1. Update _gen_steps registration (ensure it's there and at correct progress)
    # Already done in previous turns, but let's make sure.
    
    # 2. Complete _build_ultimate_sandbox method
    # We will replace the existing one or append if not there.
    # Since we appended it last time, let's find and replace it for a clean update.
    
    content = "".join(lines)
    method_start_marker = 'def _build_ultimate_sandbox(self):'
    
    new_method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Ultra-consolidated test arena for all core mechanics: parkour, wallrun, climbing, swimming, combat, loot.\"\"\"
        if str(self.active_location).lower() != "ultimate_sandbox":
            return

        tx, ty = 150.0, 150.0
        center_z = self._th(tx, ty)
        
        stone_mat = mk_mat((0.48, 0.46, 0.44, 1.0), 0.72, 0.04)
        dirt_mat = mk_mat((0.38, 0.32, 0.24, 1.0), 0.90, 0.0)
        water_mat = mk_mat((0.12, 0.32, 0.52, 0.78), 0.10, 0.20)
        wood_mat = mk_mat((0.28, 0.18, 0.10, 1.0), 0.82, 0.0)
        gold_mat = mk_mat((0.74, 0.62, 0.18, 1.0), 0.20, 0.72)
        from panda3d.core import TransparencyAttrib
        import random
        rng = random.Random(42)
        
        # 1. Main Plaza Base
        self._pl(
            mk_plane("sandbox_base", 120.0, 120.0, 3.0),
            tx, ty, center_z + 0.05,
            self.tx.get("dirt"), dirt_mat, "Ultimate Sandbox",
            is_platform=False
        )
        
        # 2. Parkour Zone: Staggered Cubes
        for i in range(8):
            h = 1.2 + (i * 1.5)
            cx, cy = tx + 18.0 + (i * 5.0), ty + (3.0 if i % 2 == 0 else -3.0)
            self._pl(
                mk_box(f"sandbox_cube_{i}", 4.0, 4.0, h),
                cx, cy, center_z + (h * 0.5),
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
            )
            
        # 3. Wallrun & Climbing Area
        # Long wall for wallrunning
        self._pl(
            mk_box("sandbox_wallrun_wall", 1.2, 40.0, 12.0),
            tx - 18.0, ty, center_z + 6.0,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        
        # Climbing Tower (Tall vertical challenge)
        self._pl(
            mk_box("sandbox_climb_tower", 7.0, 7.0, 16.0),
            tx - 10.0, ty - 30.0, center_z + 8.0,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        # Small climbing ledge
        self._pl(
            mk_box("sandbox_climb_ledge", 5.0, 4.0, 5.0),
            tx + 10.0, ty - 30.0, center_z + 2.5,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        
        # 4. Swimming / Diving Pool
        pool_x, pool_y = tx, ty + 35.0
        pool_z = center_z - 3.0
        pool = self._pl(
            mk_plane("sandbox_water", 40.0, 25.0, 5.0),
            pool_x, pool_y, pool_z,
            None, water_mat, "Ultimate Sandbox",
            is_platform=False
        )
        pool.setTransparency(TransparencyAttrib.M_alpha)
        
        if self.phys:
            from entities import game_constants as gc
            p = gc.Platform()
            p.aabb.min = gc.Vec3(pool_x - 20.0, pool_y - 12.5, pool_z - 6.0)
            p.aabb.max = gc.Vec3(pool_x + 20.0, pool_y + 12.5, pool_z + 0.1)
            p.isWater = True
            self.phys.addPlatform(p)
            
        # 5. Spawner Markers (for combat testing)
        # Standard enemy spawner
        for i, (ox, oy) in enumerate([(15, 15), (-15, 15), (15, -15), (-15, -15)]):
            self._pl(
                mk_cyl(f"sandbox_spawner_{i}", 0.6, 0.2, 10),
                tx + ox, ty + oy, center_z + 0.1,
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox",
                is_platform=False
            )
            
        # BOSS Markers
        # Dragon Spawner at the edge of the plaza
        self._pl(
            mk_box("sandbox_dragon_marker", 5.0, 5.0, 0.5),
            tx + 40.0, ty + 40.0, center_z + 0.25,
            None, mk_mat((1, 0, 0, 1), 0.5, 0.5), "Ultimate Sandbox", is_platform=False
        )
        # Golem Spawner
        self._pl(
            mk_box("sandbox_golem_marker", 3.0, 3.0, 0.5),
            tx - 40.0, ty + 40.0, center_z + 0.25,
            None, mk_mat((0, 0.5, 1, 1), 0.5, 0.5), "Ultimate Sandbox", is_platform=False
        )

        # 6. Interactive Props: Chests & Books
        # Treasure Chest
        chest_node = self._pl(
            mk_box("sandbox_treasure_chest", 1.2, 0.8, 0.9),
            tx + 5.0, ty + 5.0, center_z + 0.45,
            self.tx.get("wood"), wood_mat, "Ultimate Sandbox"
        )
        self._register_story_anchor(
            "sandbox_chest_01",
            chest_node,
            name="Ancient Sandbox Chest",
            hint="Open the testing chest",
            single_use=False,
            rewards={"xp": 100, "gold": 500, "items": ["sword_legendary"]},
            event_name="test.sandbox_chest_opened",
            location_name="Ultimate Sandbox"
        )
        
        # Magic Book
        book_node = self._pl(
            mk_box("sandbox_magic_book", 0.4, 0.6, 0.1),
            tx - 5.0, ty + 5.0, center_z + 0.1,
            None, mk_mat((0.1, 0.3, 0.8, 1.0), 0.8, 0.1), "Ultimate Sandbox"
        )
        self._register_story_anchor(
            "sandbox_book_01",
            book_node,
            name="Tome of Infinite Testing",
            hint="Read the magic book",
            single_use=False,
            rewards={"xp": 50},
            event_name="test.sandbox_book_read",
            location_name="Ultimate Sandbox"
        )
        
        # 7. Visual Polish: Trees and Vegetation
        if hasattr(self, "_spawn_world_model"):
            tree_paths = self._collect_world_model_paths("trees", ["common_tree_1.glb", "pine_tree_1.glb"])
            if tree_paths:
                for idx in range(12):
                    angle = (math.tau * idx) / 12.0
                    rad = 50.0 + rng.uniform(-5, 5)
                    px = tx + math.cos(angle) * rad
                    py = ty + math.sin(angle) * rad
                    pz = self._th(px, py)
                    self._spawn_world_model(
                        rng.choice(tree_paths),
                        px, py, pz,
                        scale=rng.uniform(0.8, 1.4),
                        h=rng.uniform(0, 360),
                        loc_name="Ultimate Sandbox"
                    )

        from utils.logger import logger
        logger.info(f"[SharuanWorld] Ultimate Sandbox fully upgraded with Bosses, Chests, and Books at ({tx}, {ty})")
"""
    
    if method_start_marker in content:
        # Replace existing
        pattern = re.escape(method_start_marker) + r".*?(?=\n\s*def|\Z)"
        content = re.sub(pattern, new_method_code, content, flags=re.DOTALL)
        print("Updated existing _build_ultimate_sandbox in SharuanWorld")
    else:
        # Append
        content += new_method_code
        print("Appended _build_ultimate_sandbox to SharuanWorld")
        
    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- Patch app.py ---
if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ensure ultimate_sandbox spawns bosses in _apply_test_profile
    if 'elif profile == "ultimate_sandbox":' in content:
        # Replace the existing block with an upgraded one
        spawn_logic = """elif profile == "ultimate_sandbox":
            # Spawn a squad of wolves for combat testing
            if self.world:
                self.world.active_location = "ultimate_sandbox"
            
            p = self.player.actor.getPos(self.render) if self.player and self.player.actor else Vec3(150, 150, 5)
            
            # 1. Standard Enemies
            if self.npc_manager:
                self.npc_manager.spawn_from_data({
                    "sandbox_wolf_1": {"name": "Test Wolf 1", "role": "enemy", "pos": [165.0, 165.0, 5.0], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.2}},
                    "sandbox_wolf_2": {"name": "Test Wolf 2", "role": "enemy", "pos": [135.0, 165.0, 5.0], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.2}},
                    "sandbox_sentinel": {"name": "Test Sentinel", "role": "guard", "pos": [150.0, 135.0, 5.0], "appearance": {"species": "dracolite", "armor_type": "plate", "scale": 1.1}}
                })
            
            # 2. Bosses
            # Spawn Golem at marker location
            if self.boss_manager:
                golem = self.boss_manager.get_primary("golem")
                if golem and hasattr(golem, "root"):
                    golem.root.setPos(110.0, 190.0, 5.5)
            
            # Spawn Dragon
            if hasattr(self, "dragon_boss") and self.dragon_boss and hasattr(self.dragon_boss, "root"):
                self.dragon_boss.root.setPos(190.0, 190.0, 6.0)
        """
        pattern = r'elif profile == "ultimate_sandbox":.*?elif profile == "music":'
        content = re.sub(pattern, spawn_logic + '        elif profile == "music":', content, flags=re.DOTALL)
        print("Upgraded boss spawning logic in app.py")

    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Sandbox Upgrade Complete.")
