
import os
import re

world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    method_start_marker = 'def _build_ultimate_sandbox(self):'
    
    # Final Upgraded Method with REAL Grass and Path Decals
    new_method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Ultra-consolidated test arena: parkour, wallrun, climbing, swimming, combat, loot, flight, paths, REAL grass.\"\"\"
        if str(self.active_location).lower() != "ultimate_sandbox":
            return

        tx, ty = 150.0, 150.0
        center_z = self._th(tx, ty)
        
        stone_mat = mk_mat((0.48, 0.46, 0.44, 1.0), 0.72, 0.04)
        dirt_mat = mk_mat((0.38, 0.32, 0.24, 1.0), 0.90, 0.0)
        water_mat = mk_mat((0.12, 0.32, 0.52, 0.78), 0.10, 0.20)
        wood_mat = mk_mat((0.28, 0.18, 0.10, 1.0), 0.82, 0.0)
        accent_mat = mk_mat((0.8, 0.6, 0.2, 1.0), 0.3, 0.6)
        mud_mat = mk_mat((0.39, 0.31, 0.22, 0.80), 0.96, 0.0)
        
        from panda3d.core import TransparencyAttrib
        import random, math
        rng = random.Random(42)
        
        # 1. Main Plaza Base
        self._pl(
            mk_plane("sandbox_base", 160.0, 160.0, 3.0),
            tx, ty, center_z + 0.05,
            self.tx.get("dirt"), dirt_mat, "Ultimate Sandbox",
            is_platform=False
        )
        
        # 2. Parkour Zone: Staggered Cubes
        for i in range(12):
            h = 1.2 + (i * 1.4)
            cx, cy = tx + 25.0 + (i * 5.0), ty + (4.0 if i % 2 == 0 else -4.0)
            self._pl(
                mk_box(f"sandbox_cube_{i}", 4.5, 4.5, h),
                cx, cy, center_z + (h * 0.5),
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
            )
            
        # 3. Wallrun & Climbing Area
        self._pl(
            mk_box("sandbox_wallrun_wall", 1.2, 60.0, 15.0),
            tx - 30.0, ty, center_z + 7.5,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        # Giant Climbing Tower
        self._pl(
            mk_box("sandbox_climb_tower", 10.0, 10.0, 25.0),
            tx - 20.0, ty - 50.0, center_z + 12.5,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        
        # 4. Swimming / Diving Pool
        pool_x, pool_y = tx, ty + 55.0
        pool_z = center_z - 3.8
        pool = self._pl(
            mk_plane("sandbox_water", 60.0, 35.0, 6.0),
            pool_x, pool_y, pool_z,
            None, water_mat, "Ultimate Sandbox",
            is_platform=False
        )
        pool.setTransparency(TransparencyAttrib.M_alpha)
        
        if self.phys:
            from entities import game_constants as gc
            p = gc.Platform()
            p.aabb.min = gc.Vec3(pool_x - 30.0, pool_y - 17.5, pool_z - 7.0)
            p.aabb.max = gc.Vec3(pool_x + 30.0, pool_y + 17.5, pool_z + 0.1)
            p.isWater = True
            self.phys.addPlatform(p)
            
        # 5. Flight Launch Pad & Rings
        self._pl(
            mk_cyl("sandbox_flight_pad", 7.0, 1.4, 24),
            tx + 50.0, ty - 30.0, center_z + 0.7,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        for i in range(6):
            rx = tx + 50.0 + (i * 20.0)
            ry = ty - 30.0 + (i * 12.0)
            rz = center_z + 20.0 + (i * 6.0)
            for seg in range(12):
                ang = (math.tau * seg) / 12.0
                px, py = rx + (math.cos(ang) * 4.0), ry + (math.sin(ang) * 4.0)
                self._pl(mk_sphere(f"flight_ring_{i}_{seg}", 0.35, 8, 8), px, py, rz, None, accent_mat, "Ultimate Sandbox", is_platform=False)

        # 6. Path Decals (Tropinki)
        # Create a visual path from spawn (tx, ty) to Dragon Marker (tx+70, ty+70)
        route_points = []
        for step in range(15):
            lerp = step / 14.0
            px = tx + (70.0 * lerp) + rng.uniform(-2, 2)
            py = ty + (70.0 * lerp) + rng.uniform(-2, 2)
            route_points.append((px, py))
            
        for idx, (px, py) in enumerate(route_points):
            pz = self._th(px, py)
            decal = self._pl(
                mk_plane(f"sandbox_path_{idx}", 2.2, 1.4, 1.1),
                px, py, pz + 0.05,
                self.tx["dirt"], mud_mat, "Ultimate Sandbox Trail", is_platform=False
            )
            decal.setH(rng.uniform(0, 360))
            decal.setColorScale(0.9, 0.8, 0.7, 0.6)
            decal.setTransparency(TransparencyAttrib.M_alpha)

        # 7. Combat & Spawners
        self._pl(mk_box("sandbox_dragon_marker", 8.0, 8.0, 0.5), tx+70.0, ty+70.0, center_z+0.25, None, mk_mat((1,0,0,1),0.4,0.6), "Ultimate Sandbox", is_platform=False)
        self._pl(mk_box("sandbox_golem_marker", 5.0, 5.0, 0.5), tx-70.0, ty+70.0, center_z+0.25, None, mk_mat((0,0.5,1,1),0.4,0.6), "Ultimate Sandbox", is_platform=False)

        # 8. Interactive Props
        chest = self._pl(mk_box("sandbox_chest", 1.5, 1.0, 1.1), tx+10.0, ty+10.0, center_z+0.55, self.tx.get("wood"), wood_mat, "Ultimate Sandbox")
        self._register_story_anchor("sandbox_chest_final", chest, name="Legendary Sandbox Chest", hint="Open for Test Loot", rewards={"xp": 1000, "gold": 5000})
        
        book = self._pl(mk_box("sandbox_book", 0.6, 0.8, 0.15), tx-10.0, ty+10.0, center_z+0.1, None, mk_mat((0.1,0.2,0.9,1),0.7,0.2), "Ultimate Sandbox")
        self._register_story_anchor("sandbox_book_final", book, name="Universal Testing Tome", hint="Read Developer Lore", rewards={"xp": 250})

        # 9. Real Grass & Environmental Props
        if hasattr(self, "_spawn_world_model"):
            tree_paths = self._collect_world_model_paths("trees", ["common_tree_1.glb", "pine_tree_1.glb", "dead_tree_1.glb"])
            bush_paths = self._collect_world_model_paths("props", ["bush_1.glb", "bush_2.glb", "mushroom_group_1.glb", "stone_1.glb"])
            for _ in range(40):
                angle = rng.uniform(0, math.tau)
                rad = rng.uniform(20, 80)
                px, py = tx + math.cos(angle)*rad, ty + math.sin(angle)*rad
                if abs(px-tx) > 15 or abs(py-ty) > 15:
                    self._spawn_world_model(rng.choice(tree_paths if rad > 45 else bush_paths), px, py, self._th(px, py)+0.02, scale=rng.uniform(0.7, 1.6), h=rng.uniform(0, 360), loc_name="Ultimate Sandbox")

        # REAL 3D Grass
        if hasattr(self, "_spawn_gpu_grass") and hasattr(self, "_grass_blade_texture"):
            foliage_tex = self._grass_blade_texture(256)
            for _ in range(30): # High density patches
                gx, gy = tx + rng.uniform(-80, 80), ty + rng.uniform(-80, 80)
                if abs(gx-tx) > 10 or abs(gy-ty) > 10:
                    self._spawn_gpu_grass(gx, gy, 0.0, rng.uniform(18, 28), density=1.2, tex=foliage_tex)

        from utils.logger import logger
        logger.info(f"[SharuanWorld] Ultimate Sandbox BEAUTIFIED with Paths, Real Grass, and Bosses at ({tx}, {ty})")
"""
    
    if method_start_marker in content:
        pattern = re.escape(method_start_marker) + r".*?(?=\n\s*def|\Z)"
        content = re.sub(pattern, new_method_code, content, flags=re.DOTALL)
        print("Final BEAUTIFIED Sandbox update applied to SharuanWorld")
    else:
        content += new_method_code
        print("Error: Could not find method to replace, appended instead.")
        
    with open(world_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Beautiful Sandbox Upgrade Complete.")
