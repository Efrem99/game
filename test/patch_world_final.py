
import os

world_path = r"C:/xampp/htdocs/king-wizard/src/world/sharuan_world.py"

method_code = """
    def _build_ultimate_sandbox(self):
        \"\"\"Ultra-consolidated test arena for all core mechanics: parkour, wallrun, climbing, swimming, combat.\"\"\"
        if str(self.active_location).lower() != "ultimate_sandbox":
            return

        tx, ty = 150.0, 150.0
        center_z = self._th(tx, ty)
        
        stone_mat = mk_mat((0.48, 0.46, 0.44, 1.0), 0.72, 0.04)
        dirt_mat = mk_mat((0.38, 0.32, 0.24, 1.0), 0.90, 0.0)
        water_mat = mk_mat((0.12, 0.32, 0.52, 0.78), 0.10, 0.20)
        wood_mat = mk_mat((0.28, 0.18, 0.10, 1.0), 0.82, 0.0)
        from panda3d.core import TransparencyAttrib
        
        # 1. Main Plaza Base
        self._pl(
            mk_plane("sandbox_base", 80.0, 80.0, 3.0),
            tx, ty, center_z + 0.05,
            self.tx.get("dirt"), dirt_mat, "Ultimate Sandbox",
            is_platform=False
        )
        
        # 2. Parkour Zone: Staggered Cubes
        for i in range(6):
            h = 1.2 + (i * 1.8)
            cx, cy = tx + 12.0 + (i * 6.0), ty + (2.0 if i % 2 == 0 else -2.0)
            self._pl(
                mk_box(f"sandbox_cube_{i}", 4.0, 4.0, h),
                cx, cy, center_z + (h * 0.5),
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
            )
            
        # 3. Wallrun & Climbing Area
        # Long wall for wallrunning
        self._pl(
            mk_box("sandbox_wallrun_wall", 1.2, 32.0, 10.0),
            tx - 12.0, ty, center_z + 5.0,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        
        # Climbing Tower (Tall vertical challenge)
        self._pl(
            mk_box("sandbox_climb_tower", 6.0, 6.0, 14.0),
            tx - 8.0, ty - 24.0, center_z + 7.0,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        # Small climbing ledge
        self._pl(
            mk_box("sandbox_climb_ledge", 4.0, 3.0, 4.5),
            tx + 8.0, ty - 24.0, center_z + 2.25,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
        )
        
        # 4. Swimming / Diving Pool
        pool_x, pool_y = tx, ty + 28.0
        pool_z = center_z - 2.8
        pool = self._pl(
            mk_plane("sandbox_water", 28.0, 20.0, 4.5),
            pool_x, pool_y, pool_z,
            None, water_mat, "Ultimate Sandbox",
            is_platform=False
        )
        pool.setTransparency(TransparencyAttrib.M_alpha)
        
        if self.phys:
            from entities import game_constants as gc
            p = gc.Platform()
            p.aabb.min = gc.Vec3(pool_x - 14.0, pool_y - 10.0, pool_z - 6.0)
            p.aabb.max = gc.Vec3(pool_x + 14.0, pool_y + 10.0, pool_z + 0.1)
            p.isWater = True
            self.phys.addPlatform(p)
            
        # 5. Spawner Markers (for combat testing)
        for i, (ox, oy) in enumerate([(10, 10), (-10, 10), (10, -10), (-10, -10)]):
            self._pl(
                mk_cyl(f"sandbox_spawner_{i}", 0.5, 0.2, 10),
                tx + ox, ty + oy, center_z + 0.1,
                self.tx.get("stone"), stone_mat, "Ultimate Sandbox",
                is_platform=False
            )

        from utils.logger import logger
        logger.info(f"[SharuanWorld] Ultimate Sandbox built at ({tx}, {ty}) with Parkour, Climbing, Swimming, and Combat Spawners.")
"""

if os.path.exists(world_path):
    with open(world_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'def _build_ultimate_sandbox(self):' not in content:
        with open(world_path, 'a', encoding='utf-8') as f:
            f.write(method_code)
        print("Appended _build_ultimate_sandbox to SharuanWorld")
    else:
        print("_build_ultimate_sandbox already exists")
