
import os
import re

world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    method_start_marker = 'def _build_ultimate_sandbox(self):'
    
    new_method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Ultra-consolidated test arena for all core mechanics: parkour, wallrun, climbing, swimming, combat, loot, flight.\"\"\"
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
            tx, ty, center_z + 0.05,
            self.tx.get("dirt"), dirt_mat, "Ultimate Sandbox",
            is_platform=False
        )
        
        # 2. Parkour Zone: Staggered Cubes
        for i in range(10):
            h = 1.2 + (i * 1.5)
            cx, cy = tx + 20.0 + (i * 6.0), ty + (4.0 if i % 2 == 0 else -4.0)
            self._pl(
                mk_box(f"sandbox_cube_{i}", 4.5, 4.5, h),
                cx, cy, center_z + (h * 0.5),
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
            )
            
        # 3. Wallrun & Climbing Area
        self._pl(
            mk_box("sandbox_wallrun_wall", 1.2, 50.0, 14.0),
            tx - 25.0, ty, center_z + 7.0,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        
        # Climbing Tower
        self._pl(
            mk_box("sandbox_climb_tower", 8.0, 8.0, 20.0),
            tx - 15.0, ty - 40.0, center_z + 10.0,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        
        # 4. Swimming / Diving Pool
        pool_x, pool_y = tx, ty + 45.0
        pool_z = center_z - 3.5
        pool = self._pl(
            mk_plane("sandbox_water", 50.0, 30.0, 6.0),
            pool_x, pool_y, pool_z,
            None, water_mat, "Ultimate Sandbox",
            is_platform=False
        )
        pool.setTransparency(TransparencyAttrib.M_alpha)
        
        if self.phys:
            from entities import game_constants as gc
            p = gc.Platform()
            p.aabb.min = gc.Vec3(pool_x - 25.0, pool_y - 15.0, pool_z - 7.0)
            p.aabb.max = gc.Vec3(pool_x + 25.0, pool_y + 15.0, pool_z + 0.1)
            p.isWater = True
            self.phys.addPlatform(p)
            
        # 5. Flight Launch Pad & Rings
        self._pl(
            mk_cyl("sandbox_flight_pad", 6.0, 1.2, 24),
            tx + 40.0, ty - 20.0, center_z + 0.6,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        # Floating Rings for flight test
        for i in range(5):
            rx = tx + 40.0 + (i * 15.0)
            ry = ty - 20.0 + (i * 10.0)
            rz = center_z + 15.0 + (i * 5.0)
            for seg in range(12):
                ang = (math.tau * seg) / 12.0
                px = rx + (math.cos(ang) * 3.0)
                py = ry + (math.sin(ang) * 3.0)
                self._pl(
                    mk_sphere(f"sandbox_flight_ring_{i}_{seg}", 0.3, 8, 8),
                    px, py, rz,
                    None, accent_mat, "Ultimate Sandbox", is_platform=False
                )

        # 6. Combat & Spawners
        self._pl(
            mk_box("sandbox_dragon_marker", 6.0, 6.0, 0.5),
            tx + 60.0, ty + 60.0, center_z + 0.25,
            None, mk_mat((1, 0.1, 0.1, 1), 0.4, 0.6), "Ultimate Sandbox", is_platform=False
        )
        self._pl(
            mk_box("sandbox_golem_marker", 4.0, 4.0, 0.5),
            tx - 60.0, ty + 60.0, center_z + 0.25,
            None, mk_mat((0.1, 0.4, 1, 1), 0.4, 0.6), "Ultimate Sandbox", is_platform=False
        )

        # 7. Interactive Props: Chests & Books
        chest_node = self._pl(
            mk_box("sandbox_treasure_chest", 1.4, 0.9, 1.0),
            tx + 8.0, ty + 8.0, center_z + 0.5,
            self.tx.get("wood"), wood_mat, "Ultimate Sandbox"
        )
        self._register_story_anchor("sandbox_chest_01", chest_node, name="Ultimate Test Chest", hint="Open Loot Chest", rewards={"xp": 500, "gold": 1000})
        
        book_node = self._pl(
            mk_box("sandbox_magic_book", 0.5, 0.7, 0.12),
            tx - 8.0, ty + 8.0, center_z + 0.1,
            None, mk_mat((0.2, 0.4, 1.0, 1.0), 0.7, 0.2), "Ultimate Sandbox"
        )
        self._register_story_anchor("sandbox_book_01", book_node, name="Tome of Development", hint="Read Lore Book", rewards={"xp": 150})

        # 8. Visual Polish: Trees, Grass, Props
        if hasattr(self, "_spawn_world_model"):
            tree_paths = self._collect_world_model_paths("trees", ["common_tree_1.glb", "pine_tree_1.glb"])
            bush_paths = self._collect_world_model_paths("props", ["bush_1.glb", "bush_2.glb", "mushroom_group_1.glb"])
            if tree_paths:
                for idx in range(20):
                    angle = (math.tau * idx) / 20.0
                    rad = 70.0 + rng.uniform(-8, 8)
                    px, py = tx + math.cos(angle) * rad, ty + math.sin(angle) * rad
                    self._spawn_world_model(rng.choice(tree_paths), px, py, self._th(px, py), scale=rng.uniform(0.9, 1.5), h=rng.uniform(0, 360), loc_name="Ultimate Sandbox")
            if bush_paths:
                for idx in range(30):
                    px, py = tx + rng.uniform(-60, 60), ty + rng.uniform(-60, 60)
                    if abs(px-tx) > 10 or abs(py-ty) > 10:
                        self._spawn_world_model(rng.choice(bush_paths), px, py, self._th(px, py)+0.05, scale=rng.uniform(0.6, 1.2), h=rng.uniform(0, 360), loc_name="Ultimate Sandbox")

        # GPU Grass (triunka)
        if hasattr(self, "_spawn_gpu_grass") and hasattr(self, "_grass_blade_texture"):
            foliage_tex = self._grass_blade_texture(256)
            for idx in range(15):
                gx, gy = tx + rng.uniform(-65, 65), ty + rng.uniform(-65, 65)
                if abs(gx-tx) > 12 or abs(gy-ty) > 12:
                    self._spawn_gpu_grass(gx, gy, 0.0, rng.uniform(15, 25), density=1.0, tex=foliage_tex)

        from utils.logger import logger
        logger.info(f"[SharuanWorld] Ultimate Sandbox Final Version at ({tx}, {ty})")
"""
    
    if method_start_marker in content:
        pattern = re.escape(method_start_marker) + r".*?(?=\n\s*def|\Z)"
        content = re.sub(pattern, new_method_code, content, flags=re.DOTALL)
        print("Updated SharuanWorld for 'Beautiful' Ultimate Sandbox")
    else:
        content += new_method_code
        print("Appended final _build_ultimate_sandbox to SharuanWorld")
        
    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)
"""
