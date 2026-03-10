"""
SharuanWorld - Refactored Sharuan Map
Handles procedural generation, PBR materials, and world entities.
Wires generated geometry into C++ physics.
"""
import math
import os
import random
import json
from pathlib import Path
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import (
    Vec3, LColor,
    GeomNode, Geom, GeomTriangles, GeomVertexFormat,
    GeomVertexData, GeomVertexWriter, GeomVertexRewriter,
    TransparencyAttrib, Texture, TextureStage, Material, Shader, PointLight
)

try:
    import game_core as gc
    HAS_CORE = True
except ImportError:
    gc = None
    HAS_CORE = False

from utils.assets_util import _fbm, make_pbr_tex_set
from utils.logger import logger
from world.location_meshes import normalize_location_mesh_entries


def should_enable_world_shader(has_core, env=None):
    """
    Enable heavy world shader path only when native core is present by default.
    Can be overridden for explicit testing via env switches.
    """
    env_map = os.environ if env is None else env
    force = str(env_map.get("XBOT_FORCE_WORLD_SHADER", "0") or "").strip().lower()
    if force in {"1", "true", "yes", "on"}:
        return True
    disable = str(env_map.get("XBOT_DISABLE_WORLD_SHADER", "0") or "").strip().lower()
    if disable in {"1", "true", "yes", "on"}:
        return False
    return bool(has_core)

# ─── Mesh builders ─────────────────────────────────────────────────
def mk_box(nm, sx, sy, sz):
    fmt = GeomVertexFormat.get_v3n3t2()
    vd = GeomVertexData(nm, fmt, Geom.UH_static)
    vw, nw, tw = GeomVertexWriter(vd,'vertex'), GeomVertexWriter(vd,'normal'), GeomVertexWriter(vd,'texcoord')
    hx,hy,hz = sx/2,sy/2,sz/2
    faces=[((0,0,1),[(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)]),
           ((0,0,-1),[(-hx,hy,-hz),(hx,hy,-hz),(hx,-hy,-hz),(-hx,-hy,-hz)]),
           ((0,1,0),[(-hx,hy,-hz),(-hx,hy,hz),(hx,hy,hz),(hx,hy,-hz)]),
           ((0,-1,0),[(-hx,-hy,hz),(-hx,-hy,-hz),(hx,-hy,-hz),(-hx,-hy,hz)]),
           ((1,0,0),[(hx,-hy,-hz),(hx,hy,-hz),(hx,hy,hz),(hx,-hy,hz)]),
           ((-1,0,0),[(-hx,-hy,hz),(-hx,hy,hz),(-hx,hy,-hz),(-hx,-hy,-hz)])]
    uvs=[(0,0),(1,0),(1,1),(0,1)]
    for n,vs in faces:
        for i,v in enumerate(vs):
            vw.add_data3(*v); nw.add_data3(*n); tw.add_data2(*uvs[i])
    tr = GeomTriangles(Geom.UH_static)
    for i in range(6):
        b=i*4; tr.add_vertices(b,b+1,b+2); tr.add_vertices(b,b+2,b+3)
    g=Geom(vd); g.add_primitive(tr); nd=GeomNode(nm); nd.add_geom(g); return nd

def mk_cyl(nm, r, h, seg):
    fmt = GeomVertexFormat.get_v3n3t2()
    vd = GeomVertexData(nm, fmt, Geom.UH_static)
    vw, nw, tw = GeomVertexWriter(vd,'vertex'), GeomVertexWriter(vd,'normal'), GeomVertexWriter(vd,'texcoord')
    tr = GeomTriangles(Geom.UH_static); hz=h/2; idx=0
    for i in range(seg):
        a0,a1 = 2*math.pi*i/seg, 2*math.pi*(i+1)/seg
        x0,y0,x1,y1 = math.cos(a0)*r,math.sin(a0)*r,math.cos(a1)*r,math.sin(a1)*r
        for v,n,uv in [((x0,y0,-hz),(math.cos(a0),math.sin(a0),0),(i/seg,0)),
                        ((x1,y1,-hz),(math.cos(a1),math.sin(a1),0),((i+1)/seg,0)),
                        ((x1,y1,hz),(math.cos(a1),math.sin(a1),0),((i+1)/seg,1)),
                        ((x0,y0,hz),(math.cos(a0),math.sin(a0),0),(i/seg,1))]:
            vw.add_data3(*v); nw.add_data3(*n); tw.add_data2(*uv)
        tr.add_vertices(idx,idx+1,idx+2); tr.add_vertices(idx,idx+2,idx+3); idx+=4
    ct=idx; vw.add_data3(0,0,hz); nw.add_data3(0,0,1); tw.add_data2(0.5,0.5); idx+=1
    for i in range(seg):
        a=2*math.pi*i/seg; vw.add_data3(math.cos(a)*r,math.sin(a)*r,hz)
        nw.add_data3(0,0,1); tw.add_data2(0.5+math.cos(a)*0.5,0.5+math.sin(a)*0.5)
    for i in range(seg): tr.add_vertices(ct,ct+1+i,ct+1+(i+1)%seg)
    idx+=seg
    cb=idx; vw.add_data3(0,0,-hz); nw.add_data3(0,0,-1); tw.add_data2(0.5,0.5); idx+=1
    for i in range(seg):
        a=2*math.pi*i/seg; vw.add_data3(math.cos(a)*r,math.sin(a)*r,-hz)
        nw.add_data3(0,0,-1); tw.add_data2(0.5+math.cos(a)*0.5,0.5+math.sin(a)*0.5)
    for i in range(seg): tr.add_vertices(cb,cb+1+(i+1)%seg,cb+1+i)
    g=Geom(vd); g.add_primitive(tr); nd=GeomNode(nm); nd.add_geom(g); return nd

def mk_cone(nm, r, h, seg):
    fmt = GeomVertexFormat.get_v3n3t2()
    vd = GeomVertexData(nm, fmt, Geom.UH_static)
    vw, nw, tw = GeomVertexWriter(vd,'vertex'), GeomVertexWriter(vd,'normal'), GeomVertexWriter(vd,'texcoord')
    tr = GeomTriangles(Geom.UH_static); hz=h/2; idx=0; sl=r/h; ln=math.sqrt(1+sl*sl)
    for i in range(seg):
        a0,a1 = 2*math.pi*i/seg, 2*math.pi*(i+1)/seg
        vw.add_data3(math.cos(a0)*r,math.sin(a0)*r,-hz); nw.add_data3(math.cos(a0)/ln,math.sin(a0)/ln,sl/ln); tw.add_data2(i/seg,0)
        vw.add_data3(math.cos(a1)*r,math.sin(a1)*r,-hz); nw.add_data3(math.cos(a1)/ln,math.sin(a1)/ln,sl/ln); tw.add_data2((i+1)/seg,0)
        vw.add_data3(0,0,hz); nw.add_data3(0,0,1); tw.add_data2((i+0.5)/seg,1)
        tr.add_vertices(idx,idx+1,idx+2); idx+=3
    c=idx; vw.add_data3(0,0,-hz); nw.add_data3(0,0,-1); tw.add_data2(0.5,0.5); idx+=1
    for i in range(seg):
        a=2*math.pi*i/seg; vw.add_data3(math.cos(a)*r,math.sin(a)*r,-hz)
        nw.add_data3(0,0,-1); tw.add_data2(0.5+math.cos(a)*0.5,0.5+math.sin(a)*0.5)
    for i in range(seg): tr.add_vertices(c,c+1+(i+1)%seg,c+1+i)
    g=Geom(vd); g.add_primitive(tr); nd=GeomNode(nm); nd.add_geom(g); return nd

def mk_sphere(nm, r, rings, slices):
    fmt = GeomVertexFormat.get_v3n3t2()
    vd = GeomVertexData(nm, fmt, Geom.UH_static)
    vw, nw, tw = GeomVertexWriter(vd,'vertex'), GeomVertexWriter(vd,'normal'), GeomVertexWriter(vd,'texcoord')
    tr = GeomTriangles(Geom.UH_static)
    for i in range(rings+1):
        phi=math.pi*i/rings
        for j in range(slices+1):
            th=2*math.pi*j/slices
            x,y,z=math.sin(phi)*math.cos(th),math.sin(phi)*math.sin(th),math.cos(phi)
            vw.add_data3(x*r,y*r,z*r); nw.add_data3(x,y,z); tw.add_data2(j/slices,i/rings)
    for i in range(rings):
        for j in range(slices):
            a0=i*(slices+1)+j; b0=a0+slices+1
            tr.add_vertices(a0,b0,a0+1); tr.add_vertices(a0+1,b0,b0+1)
    g=Geom(vd); g.add_primitive(tr); nd=GeomNode(nm); nd.add_geom(g); return nd

def mk_plane(nm, sx, sy, tile=1.0):
    fmt = GeomVertexFormat.get_v3n3t2()
    vd = GeomVertexData(nm, fmt, Geom.UH_static)
    vw, nw, tw = GeomVertexWriter(vd,'vertex'), GeomVertexWriter(vd,'normal'), GeomVertexWriter(vd,'texcoord')
    hx,hy = sx/2, sy/2
    for v,uv in [((-hx,-hy,0),(0,0)),((hx,-hy,0),(tile,0)),((hx,hy,0),(tile,tile)),((-hx,hy,0),(0,tile))]:
        vw.add_data3(*v); nw.add_data3(0,0,1); tw.add_data2(*uv)
    tr = GeomTriangles(Geom.UH_static); tr.add_vertices(0,1,2); tr.add_vertices(0,2,3)
    g=Geom(vd); g.add_primitive(tr); nd=GeomNode(nm); nd.add_geom(g); return nd

def mk_terrain(nm, sz, res, hfn):
    fmt = GeomVertexFormat.get_v3n3t2()
    vd = GeomVertexData(nm, fmt, Geom.UH_static)
    vw, nw, tw = GeomVertexWriter(vd,'vertex'), GeomVertexWriter(vd,'normal'), GeomVertexWriter(vd,'texcoord')
    tr = GeomTriangles(Geom.UH_static)
    hs=sz/2; step=sz/res; heights=[]
    for iy in range(res+1):
        row=[]
        for ix in range(res+1):
            x,y = -hs+ix*step, -hs+iy*step; z=hfn(x,y); row.append(z)
            vw.add_data3(x,y,z); tw.add_data2(ix/res*12, iy/res*12); nw.add_data3(0,0,1)
        heights.append(row)
    nrw = GeomVertexRewriter(vd, 'normal')
    for iy in range(res+1):
        for ix in range(res+1):
            nrw.set_row(iy*(res+1)+ix)
            zl=heights[iy][max(0,ix-1)]; zr=heights[iy][min(res,ix+1)]
            zd=heights[max(0,iy-1)][ix]; zu=heights[min(res,iy+1)][ix]
            nx,ny,nz = (zl-zr)/(2*step), (zd-zu)/(2*step), 1.0
            ln=math.sqrt(nx*nx+ny*ny+nz*nz)
            nrw.set_data3(nx/ln,ny/ln,nz/ln)
    for iy in range(res):
        for ix in range(res):
            a=iy*(res+1)+ix; b=a+1; c=a+(res+1); d=c+1
            tr.add_vertices(a,b,c); tr.add_vertices(b,d,c)
    g=Geom(vd); g.add_primitive(tr); nd=GeomNode(nm); nd.add_geom(g); return nd

def mk_mat(bc=(0.5,0.5,0.5,1), rough=0.8, metal=0.0):
    m=Material(); m.set_base_color(LColor(*bc)); m.set_roughness(rough); m.set_metallic(metal); return m

def sample_polyline_points(points, spacing=3.0):
    """Sample a polyline into evenly spaced points (keeps corners/endpoints)."""
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        return []
    try:
        step = max(0.2, float(spacing))
    except Exception:
        step = 3.0
    out = []
    last = None
    for i in range(len(points) - 1):
        a = points[i]
        b = points[i + 1]
        if not (isinstance(a, (list, tuple)) and len(a) >= 2 and isinstance(b, (list, tuple)) and len(b) >= 2):
            continue
        ax = float(a[0]); ay = float(a[1])
        bx = float(b[0]); by = float(b[1])
        dx = bx - ax; dy = by - ay
        ln = math.sqrt((dx * dx) + (dy * dy))
        if ln <= 1e-5:
            continue
        steps = max(1, int(math.ceil(ln / step)))
        for s in range(steps + 1):
            t = float(s) / float(steps)
            px = ax + (dx * t)
            py = ay + (dy * t)
            key = (round(px, 4), round(py, 4))
            if key == last:
                continue
            out.append((float(px), float(py)))
            last = key
    return out


def _rotate_xy(x, y, heading_deg):
    angle = math.radians(float(heading_deg))
    ca = math.cos(angle)
    sa = math.sin(angle)
    return (float(x) * ca) - (float(y) * sa), (float(x) * sa) + (float(y) * ca)


def make_grass_tuft_spec(rng, x, y, z):
    """Create deterministic per-tuft parameters from a dedicated RNG stream."""
    if rng is None:
        rng = random.Random(20260308)
    return {
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "tint": 0.88 + (rng.random() * 0.18),
        "blade_h": 1.2 + (rng.random() * 1.1),
        "blade_w": 0.48 + (rng.random() * 0.28),
        "heading": rng.uniform(-180.0, 180.0),
    }


def compose_grass_batch_rows(specs):
    """
    Convert grass tuft specs into packed vertex rows + triangle indices.
    Each tuft emits two crossed vertical quads (8 verts, 4 tris).
    """
    rows = []
    triangles = []
    if not isinstance(specs, (list, tuple)):
        return rows, triangles

    uv_map = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    plane_styles = (
        (0.0, (0.82, 1.00, 0.78, 0.62)),
        (90.0, (0.78, 0.96, 0.74, 0.58)),
    )

    for row in specs:
        if not isinstance(row, dict):
            continue
        x = float(row.get("x", 0.0) or 0.0)
        y = float(row.get("y", 0.0) or 0.0)
        z = float(row.get("z", 0.0) or 0.0)
        tint = float(row.get("tint", 1.0) or 1.0)
        blade_h = max(0.2, float(row.get("blade_h", 1.6) or 1.6))
        blade_w = max(0.08, float(row.get("blade_w", 0.6) or 0.6))
        heading = float(row.get("heading", 0.0) or 0.0)
        half_w = blade_w * 0.5
        local_quad = (
            (-half_w, 0.0, 0.0),
            (half_w, 0.0, 0.0),
            (half_w, 0.0, blade_h),
            (-half_w, 0.0, blade_h),
        )

        for heading_offset, style in plane_styles:
            orient = heading + float(heading_offset)
            nx, ny = _rotate_xy(0.0, -1.0, orient)
            color = (style[0] * tint, style[1] * tint, style[2] * tint, style[3])
            base = len(rows)
            for i, local in enumerate(local_quad):
                rx, ry = _rotate_xy(local[0], local[1], orient)
                rows.append(
                    {
                        "vertex": (x + rx, y + ry, z + local[2]),
                        "normal": (nx, ny, 0.0),
                        "color": color,
                        "uv": uv_map[i],
                    }
                )
            triangles.append((base + 0, base + 1, base + 2))
            triangles.append((base + 0, base + 2, base + 3))

    return rows, triangles

class SharuanWorld:
    DEFAULT_RIVER = [
        (30, 65), (25, 55), (20, 45), (15, 38), (10, 32), (5, 25), (0, 18), (-5, 10),
        (-8, 2), (-10, -5), (-10, -15), (-8, -25), (-5, -35), (-3, -45), (0, -55), (0, -70)
    ]

    def __init__(self, app):
        self.app = app
        self.render = app.render
        self.loader = app.loader
        self.phys = app.phys if HAS_CORE else None
        self.data_mgr = app.data_mgr

        get_layout = getattr(self.data_mgr, "get_world_layout", None)
        self.layout = get_layout() if callable(get_layout) else {}
        if not isinstance(self.layout, dict):
            self.layout = {}

        terrain_cfg = self.layout.get("terrain", {}) if isinstance(self.layout.get("terrain"), dict) else {}
        self.terrain_size = float(terrain_cfg.get("size", 200.0) or 200.0)
        self.terrain_res = int(terrain_cfg.get("resolution", 72) or 72)
        self.castle_hill_cfg = terrain_cfg.get("castle_hill", {}) if isinstance(terrain_cfg.get("castle_hill"), dict) else {}
        self.sea_cfg = terrain_cfg.get("sea", {}) if isinstance(terrain_cfg.get("sea"), dict) else {}
        self.hills_cfg = terrain_cfg.get("hills", {}) if isinstance(terrain_cfg.get("hills"), dict) else {}
        self.river_cfg = self.layout.get("river", {}) if isinstance(self.layout.get("river"), dict) else {}
        river_points = self.river_cfg.get("points", [])
        if isinstance(river_points, list) and len(river_points) >= 2:
            parsed = []
            for row in river_points:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    try:
                        parsed.append((float(row[0]), float(row[1])))
                    except Exception:
                        continue
            self.RIVER = parsed if len(parsed) >= 2 else list(self.DEFAULT_RIVER)
        else:
            self.RIVER = list(self.DEFAULT_RIVER)

        self.locations = self._prepare_locations()
        self.active_location = None
        self.colliders = [] # Python-only fallback AABB list
        self._water_surfaces = []
        self._castle_lights = []
        self._chest_nodes = []
        self._location_mesh_nodes = []
        # Stable RNG for procedural decoration jitter (grass, decals, micro-variation).
        self._rng = random.Random(20260308)
        self._location_meshes_cfg = self._load_location_meshes_cfg()

        self.terrain_shader = None
        if should_enable_world_shader(HAS_CORE):
            try:
                self.terrain_shader = Shader.load(
                    Shader.SL_GLSL,
                    "shaders/simple_pbr.vert",
                    "shaders/simple_pbr.frag"
                )
            except Exception as e:
                logger.error(f"Failed to load terrain fallback shader: {e}")
                self.terrain_shader = None
        else:
            logger.info(
                "[SharuanWorld] World shader disabled in safe rendering mode. "
                "Set XBOT_FORCE_WORLD_SHADER=1 to override."
            )

        self.tx = {}
        self._gen_steps = [
            (0.1, self._init_textures, "Generating procedural materials..."),
            (0.24, self._build_terrain, "Drafting Sharuan terrain..."),
            (0.34, self._build_sea, "Simulating sea and water bodies..."),
            (0.42, self._build_river, "Mapping river paths..."),
            (0.54, self._build_castle, "Constructing Castle Sharuan..."),
            (0.59, self._build_location_meshes, "Streaming handcrafted location meshes..."),
            (0.63, self._build_city_wall, "Erecting city fortifications..."),
            (0.72, self._build_districts, "Laying out city districts..."),
            (0.80, self._build_port_town, "Building port and market district..."),
            (0.86, self._build_center, "Designing town center..."),
            (0.90, self._build_movement_training_ground, "Preparing movement training grounds..."),
            (0.94, self._build_scenery, "Adding scenery and decorations..."),
            (0.955, self._build_treasure_chests, "Placing treasure chests across locations..."),
            (0.97, self._build_dwarven_caves_story_setpiece, "Carving dwarven cave sectors..."),
            (1.0, self._build_flora_fauna, "Populating world flora..."),
        ]
        self._current_step = 0
        self.is_built = False

    def generate_step(self):
        """Executes one chunk of world generation and returns (progress, status_text)."""
        if self._current_step >= len(self._gen_steps):
            self.is_built = True
            return 1.0, "Ready."

        from utils.logger import logger
        progress, func, status = self._gen_steps[self._current_step]
        logger.info(f"[SharuanWorld] Step {self._current_step+1}/{len(self._gen_steps)}: {status}")
        func()
        self._current_step += 1

        if self._current_step >= len(self._gen_steps):
            self.is_built = True

        return progress, status

    def _load_location_meshes_cfg(self):
        merged = []
        merged.extend(normalize_location_mesh_entries(self.layout))

        path = Path("data/world/location_meshes.json")
        if not path.exists():
            return merged

        payload = {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            logger.warning(f"[World] Failed to parse {path.as_posix()}: {exc}")
            return merged

        file_rows = normalize_location_mesh_entries(payload)
        if file_rows:
            merged.extend(file_rows)
        return merged

    def _add_platform_from_bounds(self, bounds, *, is_wallrun=False):
        if not bounds or len(bounds) < 2:
            return
        mins, maxs = bounds[0], bounds[1]
        if mins is None or maxs is None:
            return
        if self.phys:
            p = gc.Platform()
            p.aabb.min = gc.Vec3(mins.x, mins.y, mins.z)
            p.aabb.max = gc.Vec3(maxs.x, maxs.y, maxs.z)
            p.normal = gc.Vec3(0, 0, 1)
            p.isWallRun = bool(is_wallrun)
            self.phys.addPlatform(p)
            return
        self.colliders.append(
            {
                "min_x": mins.x,
                "min_y": mins.y,
                "min_z": mins.z,
                "max_x": maxs.x,
                "max_y": maxs.y,
                "max_z": maxs.z,
            }
        )

    def update(self, player_pos):
        self._animate_water(globalClock.getFrameTime())
        next_location = None
        best_score = None
        best_radius = None
        # Choose the most specific overlapping zone instead of first match.
        for loc in self.locations:
            lp = loc["pos"]
            dist = (player_pos - Vec3(lp[0], lp[1], lp[2])).length()
            radius = max(0.1, float(loc.get("radius", 1.0) or 1.0))
            if dist < radius:
                score = dist / radius
                if (
                    best_score is None
                    or score < best_score
                    or (abs(score - best_score) <= 0.05 and best_radius is not None and radius < best_radius)
                ):
                    best_score = score
                    best_radius = radius
                    next_location = loc["name"]
        if self.active_location != next_location and next_location:
            print(f"[World] Entered: {next_location}")
        self.active_location = next_location

    def _prepare_locations(self):
        locations = self.data_mgr.world_config.get("locations", [])
        zones = self.layout.get("zones", []) if isinstance(self.layout.get("zones"), list) else []
        if not zones:
            return locations if isinstance(locations, list) else []

        out = []
        for zone in zones:
            if not isinstance(zone, dict):
                continue
            center = zone.get("center", [])
            if not (isinstance(center, list) and len(center) >= 3):
                continue
            try:
                x = float(center[0]); y = float(center[1]); z = float(center[2])
            except Exception:
                continue
            out.append(
                {
                    "name": str(zone.get("name", zone.get("id", "Location"))),
                    "pos": [x, y, z],
                    "radius": float(zone.get("radius", 20.0) or 20.0),
                }
            )
        return out if out else (locations if isinstance(locations, list) else [])

    def _animate_water(self, t):
        for row in self._water_surfaces:
            node = row.get("node")
            if not node:
                continue
            base_z = float(row.get("base_z", 0.0))
            amp = float(row.get("amp", 0.1))
            speed = float(row.get("speed", 1.0))
            phase = float(row.get("phase", 0.0))
            wobble = math.sin((t * speed) + phase) * amp
            node.setZ(base_z + wobble)

    def sample_water_height(self, x, y):
        sea_y = float(self.sea_cfg.get("start_y", -50.0) or -50.0)
        sea_level = float(self.sea_cfg.get("level", -1.5) or -1.5)
        best = None
        if y <= sea_y:
            best = sea_level
        for idx in range(len(self.RIVER) - 1):
            ax, ay = self.RIVER[idx]
            bx, by = self.RIVER[idx + 1]
            dx, dy = bx - ax, by - ay
            ln_sq = (dx * dx) + (dy * dy)
            if ln_sq <= 1e-6:
                continue
            tt = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ln_sq))
            px = ax + (tt * dx)
            py = ay + (tt * dy)
            dist = math.sqrt(((x - px) ** 2) + ((y - py) ** 2))
            w0 = float(self.river_cfg.get("width_start", 3.0) or 3.0)
            w1 = float(self.river_cfg.get("width_end", 6.0) or 6.0)
            width = w0 + ((w1 - w0) * (idx / max(1, len(self.RIVER) - 1)))
            if dist <= width:
                river_height = float(self._th(px, py)) - 0.25
                if best is None:
                    best = river_height
                else:
                    best = min(best, river_height)
        return float(best if best is not None else sea_level)

    def _init_textures(self):
        S = 256 # Higher resolution for sharper, less blurry textures
        biome = self.data_mgr.get_biome("plains")
        gc = biome.get("grass_color", [0.18, 0.52, 0.10])

        # Grass PBR — vivid, smooth, low-frequency variation
        def gn_grass_alb(u,v):
            n=_fbm(u*2,v*2,3,4); n2=_fbm(u*1,v*1,2,5)
            r = gc[0] + n*0.06 + n2*0.02
            g = gc[1] + n*0.12 + n2*0.04
            b = gc[2] + n*0.02
            return r, g, b
        def gn_grass_norm(u,v):
            # Procedural bumpiness
            n1 = _fbm(u*20, v*20, 2, 5)
            n2 = _fbm((u+0.01)*20, v*20, 2, 5)
            n3 = _fbm(u*20, (v+0.01)*20, 2, 5)
            dx = (n1 - n2) * 5.0
            dy = (n1 - n3) * 5.0
            return 0.5 + dx, 0.5 + dy, 1.0
        def gn_grass_rough(u,v):
            n = _fbm(u*10, v*10, 3, 7)
            return 0.7 + n*0.2, 0.7 + n*0.2, 0.7 + n*0.2

        # Stone PBR
        def gn_stone_alb(u,v):
            n=_fbm(u*12,v*12,5,10)
            if abs(math.sin(u*30))<0.06 or abs(math.sin(v*20+(int(v*20)%2)*1.57))<0.06:
                return 0.35+n*0.05, 0.33+n*0.05, 0.30+n*0.05
            b=0.50+n*0.15; return b, b*0.97, b*0.93
        def gn_stone_norm(u,v):
            n1 = _fbm(u*30, v*30, 4, 11)
            n2 = _fbm((u+0.005)*30, v*30, 4, 11)
            n3 = _fbm(u*30, (v+0.005)*30, 4, 11)
            return 0.5 + (n1-n2)*10, 0.5 + (n1-n3)*10, 1.0

        # Roof PBR — warm terracotta tiles
        def gn_roof_alb(u,v):
            tv=(v*8)%1.0; sh=1.0-tv*0.25; n=_fbm(u*15,v*15,2,30)
            e=1.0 if (u*12)%1.0>0.03 and tv>0.05 else 0.65
            return (0.62+n*0.12)*sh*e, (0.28+n*0.06)*sh*e, (0.18+n*0.04)*sh*e

        # Bark PBR
        def gn_bark_alb(u,v):
            n=_fbm(u*5,v*20,4,60); c=abs(math.sin(v*30+n*3))*0.3
            b=0.28+n*0.12-c*0.1; return max(0.0,b), max(0.0,b*0.80), max(0.0,b*0.55)

        # Leaf PBR
        def gn_leaf_alb(u,v):
            n=_fbm(u*8,v*8,3,70); return 0.15+n*0.12, 0.40+n*0.20, 0.10+n*0.06

        self.tx = {
            'grass': make_pbr_tex_set('grass', S, gn_grass_alb, gn_grass_norm, gn_grass_rough),
            'stone': make_pbr_tex_set('stone', S, gn_stone_alb, gn_stone_norm, lambda u,v: (0.35, 0.35, 0.35)),
            'roof':  make_pbr_tex_set('roof',  S, gn_roof_alb),
            'bark':  make_pbr_tex_set('bark',  S, gn_bark_alb, None, lambda u,v: (0.85, 0.85, 0.85)),
            'leaf':  make_pbr_tex_set('leaf',  S, gn_leaf_alb, None, lambda u,v: (0.75, 0.75, 0.75)),
            'dirt':  make_pbr_tex_set('dirt',  S, lambda u,v: (0.45, 0.38, 0.30)),
            'water': make_pbr_tex_set('water', 64, lambda u,v: (0.10, 0.28, 0.48), None, lambda u,v: (0.05, 0.05, 0.05)),
        }

    def _th(self, x, y):
        hill_center = self.castle_hill_cfg.get("center", [0.0, 65.0])
        if not (isinstance(hill_center, list) and len(hill_center) >= 2):
            hill_center = [0.0, 65.0]
        hc_x = float(hill_center[0]); hc_y = float(hill_center[1])
        hill_height = float(self.castle_hill_cfg.get("height", 26.0) or 26.0)
        hill_radius = max(6.0, float(self.castle_hill_cfg.get("radius", 25.0) or 25.0))
        plateau_radius = max(2.0, float(self.castle_hill_cfg.get("plateau_radius", 10.0) or 10.0))

        md = math.sqrt(((x - hc_x) * (x - hc_x)) + ((y - hc_y) * (y - hc_y)))
        mtn = hill_height * math.exp(-(md * md) / (2 * hill_radius * hill_radius))
        if md < plateau_radius:
            mtn = max(mtn, (hill_height * 0.85) + ((plateau_radius - md) * 0.1))

        sea_start = float(self.sea_cfg.get("start_y", -50.0) or -50.0)
        sea_slope = float(self.sea_cfg.get("slope", 0.5) or 0.5)
        sea = min(0.0, (y - sea_start) * sea_slope) if y < sea_start else 0.0
        rv = 0.0
        for i in range(len(self.RIVER)-1):
            ax,ay = self.RIVER[i]; bx,by = self.RIVER[i+1]
            dx,dy = bx-ax, by-ay; ln = math.sqrt(dx*dx+dy*dy)
            if ln < 0.1: continue
            t = max(0, min(1, ((x-ax)*dx+(y-ay)*dy)/(ln*ln)))
            px,py = ax+t*dx, ay+t*dy; dd = math.sqrt((x-px)**2+(y-py)**2)
            w0 = float(self.river_cfg.get("width_start", 2.5) or 2.5)
            w1 = float(self.river_cfg.get("width_end", 4.0) or 4.0)
            depth = float(self.river_cfg.get("depth", 1.5) or 1.5)
            w = w0 + ((w1 - w0) * (1.0 - t))
            if dd < w:
                rv = min(rv, -depth * (1.0 - (dd / max(0.1, w))))
        noise_scale = float(self.hills_cfg.get("noise_scale", 0.05) or 0.05)
        noise_height = float(self.hills_cfg.get("noise_height", 1.2) or 1.2)
        noise = _fbm(x*noise_scale, y*noise_scale, 3, 100) * noise_height
        hills = _fbm(x*(noise_scale*0.6), y*(noise_scale*0.6), 2, 200) * (noise_height * 1.7)
        return mtn + sea + rv + noise + hills

    def _distance_to_river(self, x, y):
        best = float("inf")
        for i in range(len(self.RIVER) - 1):
            ax, ay = self.RIVER[i]
            bx, by = self.RIVER[i + 1]
            dx, dy = bx - ax, by - ay
            ln_sq = dx * dx + dy * dy
            if ln_sq <= 1e-6:
                continue
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ln_sq))
            px = ax + t * dx
            py = ay + t * dy
            best = min(best, math.sqrt((x - px) ** 2 + (y - py) ** 2))
        return best

    def _collect_route_points(self):
        routes_cfg = self.layout.get("routes", {}) if isinstance(self.layout.get("routes"), dict) else {}
        route_keys = ("serpentine_path", "forest_track", "port_road")
        bundles = []
        for key in route_keys:
            raw = routes_cfg.get(key, [])
            parsed = []
            if isinstance(raw, list):
                for row in raw:
                    if isinstance(row, (list, tuple)) and len(row) >= 2:
                        try:
                            parsed.append((float(row[0]), float(row[1])))
                        except Exception:
                            continue
            if len(parsed) >= 2:
                bundles.append(parsed)
        return bundles

    def _scatter_path_decals(self):
        route_sets = self._collect_route_points()
        if not route_sets:
            return

        mud_mat = mk_mat((0.39, 0.31, 0.22, 0.80), 0.96, 0.0)
        rng = random.Random(40407)
        for ridx, points in enumerate(route_sets):
            samples = sample_polyline_points(points, spacing=3.4)
            for idx, (px, py) in enumerate(samples):
                if idx % 2 != 0:
                    continue
                pz = self._th(px, py)
                width = 1.3 + rng.uniform(-0.25, 0.55)
                length = 0.7 + rng.uniform(-0.10, 0.45)
                decal = self._pl(
                    mk_plane(f"path_decal_{ridx}_{idx}", width, length, 1.1),
                    px + rng.uniform(-0.4, 0.4),
                    py + rng.uniform(-0.4, 0.4),
                    pz + 0.05,
                    self.tx["dirt"],
                    mud_mat,
                    "Trail Decal",
                    is_platform=False,
                )
                decal.setH(rng.uniform(-180.0, 180.0))
                decal.setColorScale(0.92, 0.84, 0.72, 0.56)
                decal.set_transparency(TransparencyAttrib.M_alpha)

    def _spawn_grass_tuft(self, idx, x, y, z, tex, spec=None):
        rng = getattr(self, "_rng", None)
        if rng is None:
            # Safety net for partially initialized instances to avoid startup crashes.
            rng = random.Random(20260308)
            self._rng = rng

        if not isinstance(spec, dict):
            spec = make_grass_tuft_spec(rng, x, y, z)
        sx = float(spec.get("x", x) or x)
        sy = float(spec.get("y", y) or y)
        sz = float(spec.get("z", z) or z)
        tint = float(spec.get("tint", 1.0) or 1.0)
        blade_h = max(0.2, float(spec.get("blade_h", 1.6) or 1.6))
        blade_w = max(0.08, float(spec.get("blade_w", 0.6) or 0.6))
        heading = float(spec.get("heading", rng.uniform(-180.0, 180.0)) or 0.0)
        front = self._pl(
            mk_plane(f"grass_front_{idx}", blade_w, blade_h, 1.0),
            sx,
            sy,
            sz + (blade_h * 0.42),
            None,
            mk_mat((0.24, 0.49, 0.18, 0.74), 0.92, 0.0),
            "Grass",
            is_platform=False,
        )
        front.setP(90.0)
        front.setH(heading)
        front.set_transparency(TransparencyAttrib.M_alpha)
        front.setTwoSided(True)
        if tex:
            front.setTexture(tex, 1)
        front.setColorScale(0.82 * tint, 1.0 * tint, 0.78 * tint, 0.62)

        side = self._pl(
            mk_plane(f"grass_side_{idx}", blade_w, blade_h, 1.0),
            sx,
            sy,
            sz + (blade_h * 0.42),
            None,
            mk_mat((0.22, 0.46, 0.16, 0.74), 0.92, 0.0),
            "Grass",
            is_platform=False,
        )
        side.setP(90.0)
        side.setH(heading + 90.0)
        side.set_transparency(TransparencyAttrib.M_alpha)
        side.setTwoSided(True)
        if tex:
            side.setTexture(tex, 1)
        side.setColorScale(0.78 * tint, 0.96 * tint, 0.74 * tint, 0.58)

    def _spawn_grass_batch(self, specs, tex):
        rows, tri_rows = compose_grass_batch_rows(specs)
        if not rows or not tri_rows:
            return None

        fmt = GeomVertexFormat.getV3n3c4t2()
        vdata = GeomVertexData("grass_batch", fmt, Geom.UH_static)
        vwriter = GeomVertexWriter(vdata, "vertex")
        nwriter = GeomVertexWriter(vdata, "normal")
        cwriter = GeomVertexWriter(vdata, "color")
        twriter = GeomVertexWriter(vdata, "texcoord")

        for row in rows:
            vx, vy, vz = row["vertex"]
            nx, ny, nz = row["normal"]
            cr, cg, cb, ca = row["color"]
            tu, tv = row["uv"]
            vwriter.add_data3(vx, vy, vz)
            nwriter.add_data3(nx, ny, nz)
            cwriter.add_data4(cr, cg, cb, ca)
            twriter.add_data2(tu, tv)

        tri = GeomTriangles(Geom.UH_static)
        for a, b, c in tri_rows:
            tri.add_vertices(int(a), int(b), int(c))

        geom = Geom(vdata)
        geom.add_primitive(tri)
        node = GeomNode("grass_batch")
        node.add_geom(geom)

        root = self._pl(
            node,
            0.0,
            0.0,
            0.0,
            None,
            mk_mat((0.24, 0.49, 0.18, 0.74), 0.92, 0.0),
            "Grass",
            is_platform=False,
        )
        root.set_transparency(TransparencyAttrib.M_alpha)
        root.setTwoSided(True)
        if tex:
            root.setTexture(tex, 1)
        return root

    def _pl(self, geom, x, y, z, tx_set=None, mat=None, loc_name=None, is_platform=True):
        np = self.render.attach_new_node(geom)
        np.set_pos(x, y, z)

        if getattr(self, "terrain_shader", None):
            np.set_shader(self.terrain_shader, priority=100)

        # --- PBR texture binding: albedo(0), normal(1), roughness(2) ---
        ts_norm = TextureStage("normal_map")
        ts_norm.setSort(1)
        ts_rough = TextureStage("roughness_map")
        ts_rough.setSort(2)

        if tx_set:
            albedo = tx_set.get('albedo')
            normal = tx_set.get('normal')
            rough  = tx_set.get('rough')
            if albedo:
                np.setTexture(TextureStage.get_default(), albedo)
            if normal:
                np.setTexture(ts_norm, normal)
            else:
                np.setTexture(ts_norm, self._flat_normal_tex())
            if rough:
                np.setTexture(ts_rough, rough)
            else:
                np.setTexture(ts_rough, self._flat_rough_tex())
        elif mat:
            bc = mat.get_base_color()
            from panda3d.core import PNMImage
            img = PNMImage(1, 1)
            img.set_xel(0, 0, bc.x, bc.y, bc.z)
            flat_tex = Texture()
            flat_tex.load(img)
            np.setTexture(TextureStage.get_default(), flat_tex)
            np.setTexture(ts_norm, self._flat_normal_tex())
            np.setTexture(ts_rough, self._flat_rough_tex(mat.get_roughness()))

        if loc_name:
            np.set_tag('info', loc_name)

        if is_platform:
            bounds = np.get_tight_bounds()
            if bounds:
                if self.phys:
                    p = gc.Platform()
                    p.aabb.min = gc.Vec3(bounds[0].x, bounds[0].y, bounds[0].z)
                    p.aabb.max = gc.Vec3(bounds[1].x, bounds[1].y, bounds[1].z)
                    p.normal = gc.Vec3(0, 0, 1)
                    p.isWallRun = (bounds[1].z - bounds[0].z) > 3.0
                    self.phys.addPlatform(p)
                else:
                    self.colliders.append({
                        'min_x': bounds[0].x, 'min_y': bounds[0].y, 'min_z': bounds[0].z,
                        'max_x': bounds[1].x, 'max_y': bounds[1].y, 'max_z': bounds[1].z
                    })
        return np

    def _build_location_meshes(self):
        self._location_mesh_nodes = []
        rows = self._location_meshes_cfg if isinstance(self._location_meshes_cfg, list) else []
        if not rows:
            return

        for row in rows:
            if not isinstance(row, dict):
                continue
            model_path = str(row.get("model", "") or "").strip().replace("\\", "/")
            if not model_path:
                continue
            if not Path(model_path).exists():
                logger.warning(f"[World] Location mesh not found: {model_path}")
                continue
            try:
                node = self.loader.loadModel(model_path)
            except Exception as exc:
                logger.warning(f"[World] Failed to load location mesh '{model_path}': {exc}")
                continue
            if not node or node.isEmpty():
                logger.warning(f"[World] Empty location mesh skipped: {model_path}")
                continue

            pos = row.get("pos", (0.0, 0.0, 0.0))
            hpr = row.get("hpr", (0.0, 0.0, 0.0))
            scale = row.get("scale", (1.0, 1.0, 1.0))
            label = str(row.get("label", row.get("id", "Location Mesh")) or "Location Mesh")
            mesh_id = str(row.get("id", "location_mesh") or "location_mesh")
            is_platform = bool(row.get("is_platform", True))

            node.reparentTo(self.render)
            try:
                node.setPos(float(pos[0]), float(pos[1]), float(pos[2]))
            except Exception:
                node.setPos(0.0, 0.0, 0.0)
            try:
                node.setHpr(float(hpr[0]), float(hpr[1]), float(hpr[2]))
            except Exception:
                node.setHpr(0.0, 0.0, 0.0)
            try:
                node.setScale(float(scale[0]), float(scale[1]), float(scale[2]))
            except Exception:
                node.setScale(1.0)
            node.setTag("info", label)
            node.setTag("mesh_id", mesh_id)

            if is_platform:
                try:
                    bounds = node.getTightBounds()
                except Exception:
                    bounds = None
                self._add_platform_from_bounds(bounds, is_wallrun=False)

            self._location_mesh_nodes.append(node)

    def _flat_normal_tex(self):
        if not hasattr(self, '_cached_flat_normal'):
            from panda3d.core import PNMImage, SamplerState
            img = PNMImage(1, 1)
            img.set_xel(0, 0, 0.5, 0.5, 1.0)
            t = Texture("flat_normal")
            t.load(img)
            t.set_wrap_u(SamplerState.WM_repeat)
            t.set_wrap_v(SamplerState.WM_repeat)
            self._cached_flat_normal = t
        return self._cached_flat_normal

    def _flat_rough_tex(self, roughness=0.8):
        key = f"_cached_flat_rough_{int(roughness*100)}"
        if not hasattr(self, key):
            from panda3d.core import PNMImage, SamplerState
            img = PNMImage(1, 1)
            img.set_xel(0, 0, roughness, roughness, roughness)
            t = Texture(f"flat_rough_{int(roughness*100)}")
            t.load(img)
            t.set_wrap_u(SamplerState.WM_repeat)
            t.set_wrap_v(SamplerState.WM_repeat)
            setattr(self, key, t)
        return getattr(self, key)

    def _register_story_anchor(self, anchor_id, node, **kwargs):
        manager = getattr(self.app, "story_interaction", None)
        if not manager or not hasattr(manager, "register_anchor"):
            return False
        try:
            return bool(manager.register_anchor(anchor_id, node, **kwargs))
        except Exception:
            return False

    def _build_timber_house(
        self,
        house_id,
        x,
        y,
        base_z,
        width,
        depth,
        height,
        wall_mat,
        roof_mat,
        wood_mat,
        loc_name,
        *,
        add_porch=False,
    ):
        # Medieval house composition: masonry base + timber framing + split roof.
        body = self._pl(
            mk_box(f"{house_id}_body", width, depth, height),
            x,
            y,
            base_z + (height * 0.5),
            self.tx["stone"],
            wall_mat,
            loc_name,
        )

        frame_specs = [
            (-0.5, -0.5, 0.0),
            (0.5, -0.5, 0.0),
            (-0.5, 0.5, 0.0),
            (0.5, 0.5, 0.0),
        ]
        for idx, (sx, sy, _) in enumerate(frame_specs):
            fx = x + (sx * (width - 0.22))
            fy = y + (sy * (depth - 0.22))
            self._pl(
                mk_box(f"{house_id}_beam_corner_{idx}", 0.16, 0.16, height + 0.10),
                fx,
                fy,
                base_z + (height * 0.5),
                self.tx["bark"],
                wood_mat,
                loc_name,
                is_platform=False,
            )

        band_z = base_z + (height * 0.58)
        self._pl(
            mk_box(f"{house_id}_beam_band_a", width - 0.12, 0.14, 0.14),
            x,
            y - (depth * 0.5) + 0.08,
            band_z,
            self.tx["bark"],
            wood_mat,
            loc_name,
            is_platform=False,
        )
        self._pl(
            mk_box(f"{house_id}_beam_band_b", width - 0.12, 0.14, 0.14),
            x,
            y + (depth * 0.5) - 0.08,
            band_z,
            self.tx["bark"],
            wood_mat,
            loc_name,
            is_platform=False,
        )

        roof_half_len = max(1.2, (depth * 0.56))
        roof_pitch = 31.0
        left_roof = self._pl(
            mk_box(f"{house_id}_roof_left", width + 0.40, roof_half_len, 0.18),
            x,
            y - (depth * 0.12),
            base_z + height + 0.72,
            self.tx["roof"],
            roof_mat,
            loc_name,
            is_platform=False,
        )
        left_roof.setP(roof_pitch)
        right_roof = self._pl(
            mk_box(f"{house_id}_roof_right", width + 0.40, roof_half_len, 0.18),
            x,
            y + (depth * 0.12),
            base_z + height + 0.72,
            self.tx["roof"],
            roof_mat,
            loc_name,
            is_platform=False,
        )
        right_roof.setP(-roof_pitch)

        self._pl(
            mk_cyl(f"{house_id}_roof_ridge", 0.09, width + 0.24, 9),
            x,
            y,
            base_z + height + 1.02,
            self.tx["bark"],
            wood_mat,
            loc_name,
            is_platform=False,
        ).setR(90.0)

        # Front door + two lit windows for readability at dusk/night.
        self._pl(
            mk_box(f"{house_id}_door", 0.52, 0.08, 1.24),
            x,
            y - (depth * 0.5) + 0.06,
            base_z + 0.64,
            self.tx["bark"],
            wood_mat,
            loc_name,
            is_platform=False,
        )
        for wi, wx in enumerate((-0.28, 0.28)):
            glow = self._pl(
                mk_box(f"{house_id}_window_{wi}", 0.34, 0.06, 0.30),
                x + (wx * width),
                y - (depth * 0.5) + 0.05,
                base_z + (height * 0.58),
                None,
                mk_mat((0.96, 0.78, 0.36, 0.92), 0.18, 0.0),
                loc_name,
                is_platform=False,
            )
            glow.setTransparency(TransparencyAttrib.M_alpha)

        # Stone chimney improves silhouette and reduces "tutorial box" look.
        chimney = self._pl(
            mk_box(f"{house_id}_chimney", 0.34, 0.34, 1.2),
            x + (width * 0.22),
            y + (depth * 0.08),
            base_z + height + 1.10,
            self.tx["stone"],
            mk_mat((0.42, 0.40, 0.38, 1.0), 0.76, 0.04),
            loc_name,
            is_platform=False,
        )
        chimney.setH(12.0)

        if add_porch:
            porch = self._pl(
                mk_box(f"{house_id}_porch", width * 0.66, 0.90, 0.14),
                x,
                y - (depth * 0.5) - 0.40,
                base_z + 0.08,
                self.tx["bark"],
                wood_mat,
                loc_name,
                is_platform=False,
            )
            porch.setP(2.2)

        return body

    def _build_terrain(self):
        t = mk_terrain('terrain', self.terrain_size, self.terrain_res, self._th)
        m = mk_mat((0.25,0.45,0.15,1), 1.0, 0.0)
        np = self._pl(t, 0, 0, 0, self.tx['grass'], m, 'Sharuan Plains', is_platform=False)
        np.set_shader_input("bend_weight", 0.25) # Give it some bend from wind/magic
        # Tile all texture stages for terrain coverage
        for ts in [TextureStage.get_default()]:
            np.set_tex_scale(ts, 10, 10)
        # Also scale normal and roughness if applied
        children_ts = np.findAllTextureStages()
        for ts in children_ts:
            np.set_tex_scale(ts, 10, 10)

    def _build_sea(self):
        wm = mk_mat((0.10, 0.27, 0.44, 0.84), 0.08, 0.22)
        sea_y = float(self.sea_cfg.get("start_y", -50.0) or -50.0)
        sea_level = float(self.sea_cfg.get("level", -1.5) or -1.5)
        sea = mk_plane('sea', self.terrain_size, 72, 4)
        np = self._pl(sea, 0, sea_y - 30.0, sea_level, None, wm, 'Southern Sea', is_platform=False)
        np.set_transparency(TransparencyAttrib.M_alpha)
        np.setColorScale(0.42, 0.65, 0.90, 0.78)
        self._water_surfaces.append(
            {
                "kind": "sea",
                "node": np,
                "base_z": sea_level,
                "amp": 0.14,
                "speed": 0.72,
                "phase": 0.0,
            }
        )

        # Near-shore foam belt adds motion/readability where sea meets coast.
        foam = self._pl(
            mk_plane("sea_shore_foam", self.terrain_size * 0.95, 15.0, 10.0),
            0,
            sea_y + 2.0,
            sea_level + 0.04,
            None,
            mk_mat((0.94, 0.96, 0.98, 0.38), 0.12, 0.0),
            "Southern Sea",
            is_platform=False,
        )
        foam.set_transparency(TransparencyAttrib.M_alpha)
        foam.setColorScale(0.92, 0.95, 1.0, 0.32)
        self._water_surfaces.append(
            {
                "kind": "sea_foam",
                "node": foam,
                "base_z": sea_level + 0.04,
                "amp": 0.03,
                "speed": 1.45,
                "phase": 0.75,
            }
        )

        if self.phys:
            p = gc.Platform()
            p.aabb.min = gc.Vec3(-self.terrain_size * 0.5, sea_y - 60.0, -10)
            p.aabb.max = gc.Vec3(self.terrain_size * 0.5, sea_y + 20.0, sea_level + 0.1)
            p.isWater = True
            self.phys.addPlatform(p)

    def _build_river(self):
        wm = mk_mat((0.12,0.30,0.50,0.8), 0.15, 0.15)
        w0 = float(self.river_cfg.get("width_start", 3.0) or 3.0)
        w1 = float(self.river_cfg.get("width_end", 6.0) or 6.0)
        depth = float(self.river_cfg.get("depth", 1.5) or 1.5)
        for i in range(len(self.RIVER)-1):
            ax,ay = self.RIVER[i]; bx,by = self.RIVER[i+1]
            mx,my = (ax+bx)/2, (ay+by)/2
            dx,dy = bx-ax, by-ay; ln = math.sqrt(dx*dx+dy*dy)
            ang = math.degrees(math.atan2(dx, dy))
            seg_t = i / max(1, len(self.RIVER) - 1)
            w = w0 + ((w1 - w0) * seg_t)
            seg = mk_plane(f'riv{i}', w, ln, 1)
            np = self._pl(seg, mx, my, self._th(mx,my)-0.3, None, wm, 'River Aran', is_platform=False)
            np.set_h(ang)
            np.set_transparency(TransparencyAttrib.M_alpha)
            np.setColorScale(0.46, 0.72, 0.96, 0.70)
            self._water_surfaces.append(
                {
                    "kind": "river",
                    "node": np,
                    "base_z": float(np.getZ()),
                    "amp": 0.06 + (0.03 * seg_t),
                    "speed": 1.05 + (0.22 * seg_t),
                    "phase": i * 0.35,
                }
            )
            edge = self._pl(
                mk_plane(f"river_edge_{i}", w * 1.45, ln * 0.92, 4.0),
                mx,
                my,
                float(np.getZ()) + 0.03,
                None,
                mk_mat((0.88, 0.94, 1.0, 0.22), 0.10, 0.0),
                "River Aran",
                is_platform=False,
            )
            edge.set_h(ang)
            edge.set_transparency(TransparencyAttrib.M_alpha)
            if self.phys:
                p = gc.Platform()
                p.aabb.min = gc.Vec3(mx-w, my-ln*0.5, -5)
                p.aabb.max = gc.Vec3(mx+w, my+ln*0.5, 0)
                p.isWater = True
                self.phys.addPlatform(p)

    def _build_castle(self):
        sm = mk_mat((0.60, 0.58, 0.55, 1), 0.9, 0.05)
        floor_mat = mk_mat((0.56, 0.54, 0.50, 1), 0.82, 0.04)
        wall_mat = mk_mat((0.62, 0.60, 0.56, 1), 0.84, 0.04)
        trim_mat = mk_mat((0.38, 0.30, 0.22, 1), 0.72, 0.02)
        gold_mat = mk_mat((0.78, 0.66, 0.32, 1), 0.28, 0.62)
        flame_mat = mk_mat((0.98, 0.62, 0.22, 0.92), 0.18, 0.04)
        castle_cfg = self.layout.get("castle", {}) if isinstance(self.layout.get("castle"), dict) else {}
        keep = castle_cfg.get("keep", [0.0, 65.0])
        if not (isinstance(keep, list) and len(keep) >= 2):
            keep = [0.0, 65.0]
        cx, cy = float(keep[0]), float(keep[1])
        bz = self._th(cx, cy)
        courtyard_z = bz + 0.6

        def zone_xy(zone_id, fallback):
            zid = str(zone_id or "").strip().lower()
            zones = self.layout.get("zones", []) if isinstance(self.layout.get("zones"), list) else []
            for row in zones:
                if not isinstance(row, dict):
                    continue
                row_id = str(row.get("id", "") or "").strip().lower()
                center = row.get("center", [])
                if row_id != zid or not (isinstance(center, list) and len(center) >= 2):
                    continue
                try:
                    return float(center[0]), float(center[1])
                except Exception:
                    continue
            return fallback

        def place_torch(tag, tx, ty, tz, label):
            self._pl(
                mk_cyl(f"{tag}_handle", 0.05, 0.48, 8),
                tx,
                ty,
                tz + 0.24,
                self.tx["bark"],
                trim_mat,
                label,
                is_platform=False,
            )
            flame = self._pl(
                mk_sphere(f"{tag}_flame", 0.14, 6, 7),
                tx,
                ty,
                tz + 0.52,
                None,
                flame_mat,
                label,
                is_platform=False,
            )
            flame.set_transparency(TransparencyAttrib.M_alpha)
            flame.setColorScale(1.0, 0.74, 0.34, 0.88)
            light = PointLight(f"{tag}_light")
            light.setColor(LColor(1.0, 0.74, 0.45, 1.0))
            light.setAttenuation(Vec3(1.0, 0.04, 0.002))
            lnp = self.render.attachNewNode(light)
            lnp.setPos(tx, ty, tz + 0.58)
            self.render.setLight(lnp)
            self._castle_lights.append(lnp)

        def build_room(room_id, center_x, center_y, width, depth, height, label):
            room_z = self._th(center_x, center_y)
            wall_t = 0.38
            self._pl(
                mk_box(f"{room_id}_floor", width, depth, 0.46),
                center_x,
                center_y,
                room_z + 0.23,
                self.tx["stone"],
                floor_mat,
                label,
            )
            self._pl(
                mk_box(f"{room_id}_wall_w", wall_t, depth, height),
                center_x - (width * 0.5) + (wall_t * 0.5),
                center_y,
                room_z + (height * 0.5),
                self.tx["stone"],
                wall_mat,
                label,
            )
            self._pl(
                mk_box(f"{room_id}_wall_e", wall_t, depth, height),
                center_x + (width * 0.5) - (wall_t * 0.5),
                center_y,
                room_z + (height * 0.5),
                self.tx["stone"],
                wall_mat,
                label,
            )
            self._pl(
                mk_box(f"{room_id}_wall_n", width, wall_t, height),
                center_x,
                center_y + (depth * 0.5) - (wall_t * 0.5),
                room_z + (height * 0.5),
                self.tx["stone"],
                wall_mat,
                label,
            )
            # South wall split for doorway.
            gap = 1.6
            seg_w = max(1.4, (width - gap) * 0.5)
            self._pl(
                mk_box(f"{room_id}_wall_s_l", seg_w, wall_t, height),
                center_x - (gap * 0.5) - (seg_w * 0.5),
                center_y - (depth * 0.5) + (wall_t * 0.5),
                room_z + (height * 0.5),
                self.tx["stone"],
                wall_mat,
                label,
            )
            self._pl(
                mk_box(f"{room_id}_wall_s_r", seg_w, wall_t, height),
                center_x + (gap * 0.5) + (seg_w * 0.5),
                center_y - (depth * 0.5) + (wall_t * 0.5),
                room_z + (height * 0.5),
                self.tx["stone"],
                wall_mat,
                label,
            )
            self._pl(
                mk_box(f"{room_id}_lintel", gap + 0.3, wall_t, 0.42),
                center_x,
                center_y - (depth * 0.5) + (wall_t * 0.5),
                room_z + height - 0.20,
                self.tx["stone"],
                trim_mat,
                label,
                is_platform=False,
            )
            return room_z

        # Courtyard shell and keep tower.
        self._pl(
            mk_box("castle_courtyard_floor", 26.0, 22.0, 0.6),
            cx,
            cy,
            courtyard_z,
            self.tx["stone"],
            floor_mat,
            "Castle Courtyard",
        )
        self._pl(mk_box("keep", 6.0, 6.0, 10.0), cx, cy, bz + 4.5, self.tx["stone"], sm, "Castle Keep")
        for tx, ty in [(-5, -5), (5, -5), (-5, 5), (5, 5)]:
            tz = self._th(cx + tx, cy + ty)
            self._pl(mk_cyl(f"tw_{tx}_{ty}", 1.8, 12.0, 16), cx + tx, cy + ty, tz + 5.5, self.tx["stone"], sm, "Guard Tower")

        # Story rooms for intro route.
        prince_x, prince_y = zone_xy("prince_chamber", (cx + 6.0, cy - 4.0))
        map_x, map_y = zone_xy("world_map_gallery", (cx - 4.0, cy - 6.0))
        laundry_x, laundry_y = zone_xy("royal_laundry", (cx - 9.0, cy - 8.0))
        throne_x, throne_y = zone_xy("throne_hall", (cx, cy + 10.0))

        prince_z = build_room("prince_chamber", prince_x, prince_y, 8.2, 7.2, 4.4, "Prince Chamber")
        map_z = build_room("world_map_gallery", map_x, map_y, 8.6, 7.6, 4.3, "World Map Gallery")
        laundry_z = build_room("royal_laundry", laundry_x, laundry_y, 7.6, 6.8, 3.8, "Royal Laundry")
        throne_z = build_room("throne_hall", throne_x, throne_y, 12.0, 9.5, 5.6, "Throne Hall")

        # Corridors and transitions.
        corridor_specs = [
            ("corridor_a", (prince_x + map_x) * 0.5, (prince_y + map_y) * 0.5, 2.6, 7.2, 0.08),
            ("corridor_b", (map_x + laundry_x) * 0.5, (map_y + laundry_y) * 0.5, 2.3, 6.4, 0.08),
            ("corridor_c", (prince_x + throne_x) * 0.5, (prince_y + throne_y) * 0.5, 3.2, 12.0, 0.08),
        ]
        for cid, px, py, w, d, zoff in corridor_specs:
            pz = self._th(px, py)
            cor = self._pl(
                mk_box(cid, w, d, 0.40),
                px,
                py,
                pz + 0.20 + zoff,
                self.tx["stone"],
                floor_mat,
                "Castle Corridor",
            )
            angle = math.degrees(math.atan2((throne_x - prince_x), (throne_y - prince_y)))
            if cid == "corridor_a":
                angle = math.degrees(math.atan2((map_x - prince_x), (map_y - prince_y)))
            elif cid == "corridor_b":
                angle = math.degrees(math.atan2((laundry_x - map_x), (laundry_y - map_y)))
            cor.setH(angle)

        # Stairway to throne hall approach.
        stair_start_x = cx - 1.8
        stair_start_y = cy + 2.8
        for step in range(10):
            sx = stair_start_x + (step * 0.36)
            sy = stair_start_y + (step * 0.72)
            sz = self._th(sx, sy) + 0.10 + (step * 0.12)
            self._pl(
                mk_box(f"castle_step_{step}", 2.8, 0.82, 0.24),
                sx,
                sy,
                sz,
                self.tx["stone"],
                floor_mat,
                "Castle Stair",
            )

        # Paintings and map boards.
        for idx, (px, py, pz, h) in enumerate(
            [
                (prince_x - 3.8, prince_y + 1.8, prince_z + 2.0, 90.0),
                (map_x + 3.9, map_y + 1.4, map_z + 2.0, -90.0),
                (throne_x - 5.5, throne_y + 2.4, throne_z + 2.4, 90.0),
            ]
        ):
            frame = self._pl(
                mk_box(f"castle_painting_{idx}", 1.8, 0.08, 1.4),
                px,
                py,
                pz,
                self.tx["roof"],
                mk_mat((0.52, 0.22, 0.16, 0.96), 0.34, 0.0),
                "Castle Painting",
                is_platform=False,
            )
            frame.setH(h)

        map_table = self._pl(
            mk_box("world_map_table", 2.8, 1.8, 0.74),
            map_x,
            map_y + 0.6,
            map_z + 0.38,
            self.tx["bark"],
            trim_mat,
            "World Map Gallery",
        )
        map_table.setH(18.0)
        map_board = self._pl(
            mk_plane("world_map_board", 2.4, 1.6, 1.2),
            map_x,
            map_y + 0.6,
            map_z + 0.82,
            self.tx["dirt"],
            mk_mat((0.78, 0.70, 0.48, 0.86), 0.62, 0.0),
            "World Map Gallery",
            is_platform=False,
        )
        map_board.setP(2.5)

        # Statues and throne ornaments.
        statue_spots = [
            (throne_x - 3.2, throne_y + 2.8),
            (throne_x + 3.2, throne_y + 2.8),
        ]
        for idx, (sx, sy) in enumerate(statue_spots):
            sz = self._th(sx, sy)
            self._pl(mk_cyl(f"statue_base_{idx}", 0.62, 0.55, 10), sx, sy, sz + 0.28, self.tx["stone"], wall_mat, "Throne Hall")
            self._pl(mk_cyl(f"statue_body_{idx}", 0.30, 1.8, 10), sx, sy, sz + 1.20, self.tx["stone"], wall_mat, "Throne Hall")
            self._pl(mk_sphere(f"statue_head_{idx}", 0.28, 8, 9), sx, sy, sz + 2.16, self.tx["stone"], wall_mat, "Throne Hall")

        throne_base = self._pl(
            mk_box("throne_base", 4.4, 2.4, 1.2),
            throne_x,
            throne_y + 2.8,
            throne_z + 0.60,
            self.tx["stone"],
            wall_mat,
            "Throne Hall",
        )
        throne_base.setH(180.0)
        throne_back = self._pl(
            mk_box("throne_back", 2.4, 0.8, 2.8),
            throne_x,
            throne_y + 3.5,
            throne_z + 2.0,
            self.tx["stone"],
            gold_mat,
            "Throne Hall",
        )
        throne_back.setH(180.0)

        # Torches and local warm lighting.
        torch_points = [
            (prince_x - 3.6, prince_y - 2.4, prince_z + 1.2, "Prince Chamber"),
            (prince_x + 3.6, prince_y - 2.4, prince_z + 1.2, "Prince Chamber"),
            (map_x - 3.6, map_y - 2.4, map_z + 1.2, "World Map Gallery"),
            (map_x + 3.6, map_y - 2.4, map_z + 1.2, "World Map Gallery"),
            (throne_x - 5.0, throne_y + 0.6, throne_z + 1.5, "Throne Hall"),
            (throne_x + 5.0, throne_y + 0.6, throne_z + 1.5, "Throne Hall"),
        ]
        for tidx, (tx, ty, tz, label) in enumerate(torch_points):
            place_torch(f"castle_torch_{tidx}", tx, ty, tz, label)

    def _build_city_wall(self):
        sm = mk_mat((0.50,0.47,0.43,1), 0.9, 0.05)
        castle_cfg = self.layout.get("castle", {}) if isinstance(self.layout.get("castle"), dict) else {}
        wall_pts = castle_cfg.get("wall_points", [(-35, 95), (0, 108), (35, 95), (95, -75), (-95, -75), (-35, 95)])
        parsed = []
        if isinstance(wall_pts, list):
            for row in wall_pts:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    try:
                        parsed.append((float(row[0]), float(row[1])))
                    except Exception:
                        continue
        if len(parsed) >= 3:
            wall_pts = parsed
        else:
            wall_pts = [(-35, 95), (0, 108), (35, 95), (95, -75), (-95, -75), (-35, 95)]
        for i in range(len(wall_pts) - 1):
            p1, p2 = Vec3(wall_pts[i][0], wall_pts[i][1], 0), Vec3(wall_pts[i+1][0], wall_pts[i+1][1], 0)
            diff = p2 - p1; dist = diff.length()
            ang = math.degrees(math.atan2(diff.x, diff.y))
            mx, my = (p1.x+p2.x)/2, (p1.y+p2.y)/2
            self._pl(mk_box('wall_seg', 1.6, dist, 5.2), mx, my, self._th(mx,my)+2.4, self.tx['stone'], sm, 'City Wall').set_h(ang)

    def _build_center(self):
        sm = mk_mat((0.55,0.53,0.50,1), 0.85, 0.05)
        z = self._th(0, 0)
        self._pl(mk_box('th', 8.2, 6.2, 7), 0, 0, z+3.3, self.tx['stone'], sm, 'Town Hall')

    def _build_districts(self):
        wall_mat = mk_mat((0.56, 0.52, 0.46, 1), 0.82, 0.04)
        roof_mat = mk_mat((0.52, 0.22, 0.18, 1), 0.7, 0.02)
        wood_mat = mk_mat((0.36, 0.24, 0.14, 1.0), 0.78, 0.02)
        castle_cfg = self.layout.get("castle", {}) if isinstance(self.layout.get("castle"), dict) else {}
        keep = castle_cfg.get("keep", [0.0, 65.0])
        if not (isinstance(keep, list) and len(keep) >= 2):
            keep = [0.0, 65.0]
        keep_x = float(keep[0]); keep_y = float(keep[1])
        district_points = [
            (-22, 22), (-12, 18), (12, 20), (24, 18),
            (-28, 8), (-14, 6), (10, 8), (24, 6),
            (-20, -8), (-6, -10), (10, -9), (22, -6),
        ]

        for idx, (x, y) in enumerate(district_points):
            base_z = self._th(x, y)
            width = 5.0 + (idx % 3) * 0.8
            depth = 4.4 + ((idx + 1) % 3) * 0.7
            height = 3.5 + (idx % 2) * 0.6
            self._build_timber_house(
                f"house_{idx}",
                x,
                y,
                base_z,
                width,
                depth,
                height,
                wall_mat,
                roof_mat,
                wood_mat,
                "City District",
            )

        inner = castle_cfg.get("inner_buildings", [])
        if isinstance(inner, list):
            for idx, row in enumerate(inner):
                if not isinstance(row, dict):
                    continue
                pos = row.get("pos", [])
                if not (isinstance(pos, list) and len(pos) >= 2):
                    continue
                try:
                    x = float(pos[0]); y = float(pos[1])
                except Exception:
                    continue
                bz = self._th(x, y)
                bw = 3.8 + (idx % 2) * 0.6
                bd = 3.2 + ((idx + 1) % 2) * 0.6
                bh = 3.0 + (idx % 3) * 0.35
                self._build_timber_house(
                    f"castle_inner_{idx}",
                    x,
                    y,
                    bz,
                    bw,
                    bd,
                    bh,
                    wall_mat,
                    roof_mat,
                    wood_mat,
                    "Castle Courtyard",
                )

    def _build_port_town(self):
        port_cfg = self.layout.get("port", {}) if isinstance(self.layout.get("port"), dict) else {}
        routes_cfg = self.layout.get("routes", {}) if isinstance(self.layout.get("routes"), dict) else {}
        center = port_cfg.get("center", [18.0, -62.0])
        if not (isinstance(center, list) and len(center) >= 2):
            center = [18.0, -62.0]
        cx, cy = float(center[0]), float(center[1])
        district_radius = max(10.0, float(port_cfg.get("district_radius", 26.0) or 26.0))

        wood_mat = mk_mat((0.46, 0.33, 0.20, 1), 0.82, 0.03)
        wall_mat = mk_mat((0.58, 0.53, 0.47, 1), 0.85, 0.02)
        roof_mat = mk_mat((0.50, 0.22, 0.16, 1), 0.72, 0.02)
        road_mat = mk_mat((0.44, 0.38, 0.31, 1), 0.90, 0.00)

        # Harbor quay ring at shoreline edge.
        for idx in range(10):
            ang = (math.pi * 2.0 * idx) / 10.0
            px = cx + (math.cos(ang) * district_radius * 0.8)
            py = cy + (math.sin(ang) * district_radius * 0.42)
            if py > (cy + 8.0):
                continue
            pz = self._th(px, py)
            self._pl(
                mk_box(f"port_quay_{idx}", 4.8, 2.2, 0.55),
                px, py, pz + 0.28,
                self.tx["stone"], wall_mat, "Port Market"
            )

        dock_segments = port_cfg.get("dock_segments", [])
        if isinstance(dock_segments, list):
            for idx, row in enumerate(dock_segments):
                if not isinstance(row, dict):
                    continue
                pos = row.get("pos", [])
                size = row.get("size", [4.8, 10.0])
                if not (isinstance(pos, list) and len(pos) >= 2 and isinstance(size, list) and len(size) >= 2):
                    continue
                try:
                    px = float(pos[0]); py = float(pos[1])
                    sx = max(2.0, float(size[0])); sy = max(4.0, float(size[1]))
                except Exception:
                    continue
                pz = self._th(px, py)
                self._pl(
                    mk_box(f"port_dock_{idx}", sx, sy, 0.38),
                    px, py, pz + 0.20,
                    self.tx["bark"], wood_mat, "Port Docks"
                )
                for post_i in (-1, 1):
                    post = self._pl(
                        mk_cyl(f"port_dock_post_{idx}_{post_i}", 0.12, 1.2, 8),
                        px + (post_i * ((sx * 0.5) - 0.24)),
                        py + (sy * 0.5) - 0.35,
                        pz - 0.15,
                        self.tx["bark"], wood_mat, "Port Docks", is_platform=False
                    )
                    post.setColorScale(0.45, 0.34, 0.22, 1.0)

        houses = port_cfg.get("houses", [])
        if isinstance(houses, list):
            for idx, row in enumerate(houses):
                if not isinstance(row, dict):
                    continue
                pos = row.get("pos", [])
                if not (isinstance(pos, list) and len(pos) >= 2):
                    continue
                try:
                    px = float(pos[0]); py = float(pos[1])
                except Exception:
                    continue
                pz = self._th(px, py)
                bw = 4.2 + ((idx % 2) * 0.8)
                bd = 3.4 + (((idx + 1) % 3) * 0.45)
                bh = 3.1 + ((idx % 3) * 0.35)
                self._build_timber_house(
                    f"port_house_{idx}",
                    px,
                    py,
                    pz,
                    bw,
                    bd,
                    bh,
                    wall_mat,
                    roof_mat,
                    wood_mat,
                    "Port Market",
                    add_porch=True,
                )

        stalls = port_cfg.get("market_stalls", [])
        if isinstance(stalls, list):
            for idx, row in enumerate(stalls):
                if not isinstance(row, dict):
                    continue
                pos = row.get("pos", [])
                if not (isinstance(pos, list) and len(pos) >= 2):
                    continue
                try:
                    px = float(pos[0]); py = float(pos[1])
                except Exception:
                    continue
                pz = self._th(px, py)
                self._pl(
                    mk_box(f"port_stall_table_{idx}", 2.8, 1.4, 0.12),
                    px, py, pz + 0.95,
                    self.tx["bark"], wood_mat, "Port Market"
                )
                self._pl(
                    mk_box(f"port_stall_awning_{idx}", 3.0, 1.7, 0.08),
                    px, py - 0.2, pz + 2.06,
                    self.tx["roof"], roof_mat, "Port Market", is_platform=False
                )
                # Merchant props.
                for crate_i in range(2):
                    cdx = -0.65 + (crate_i * 1.30)
                    self._pl(
                        mk_box(f"port_stall_crate_{idx}_{crate_i}", 0.46, 0.46, 0.46),
                        px + cdx,
                        py + 0.68,
                        pz + 0.23,
                        self.tx["bark"],
                        wood_mat,
                        "Port Market",
                        is_platform=False,
                    )
                barrel = self._pl(
                    mk_cyl(f"port_stall_barrel_{idx}", 0.22, 0.58, 10),
                    px + 0.92,
                    py + 0.62,
                    pz + 0.30,
                    self.tx["bark"],
                    wood_mat,
                    "Port Market",
                    is_platform=False,
                )
                barrel.setH(11.0)

        # Moored boats for coastline readability.
        for bidx in range(4):
            bx = cx - 10.0 + (bidx * 7.5)
            by = cy - 10.5 - (bidx % 2) * 2.8
            water_z = self.sample_water_height(bx, by)
            hull = self._pl(
                mk_box(f"port_boat_hull_{bidx}", 4.8, 1.4, 0.52),
                bx,
                by,
                water_z + 0.12,
                self.tx["bark"],
                wood_mat,
                "Port Docks",
                is_platform=False,
            )
            hull.setH(12.0 if bidx % 2 == 0 else -14.0)
            mast = self._pl(
                mk_cyl(f"port_boat_mast_{bidx}", 0.08, 2.6, 9),
                bx,
                by,
                water_z + 1.48,
                self.tx["bark"],
                wood_mat,
                "Port Docks",
                is_platform=False,
            )
            mast.setP(3.0 if bidx % 2 else -2.0)
            sail = self._pl(
                mk_box(f"port_boat_sail_{bidx}", 0.05, 1.5, 1.1),
                bx + 0.05,
                by + 0.05,
                water_z + 1.52,
                None,
                mk_mat((0.88, 0.82, 0.72, 0.86), 0.54, 0.0),
                "Port Docks",
                is_platform=False,
            )
            sail.setTransparency(TransparencyAttrib.M_alpha)

        # S-shaped hill-to-forest trail from layout route points.
        serp = routes_cfg.get("serpentine_path", [])
        parsed = []
        if isinstance(serp, list):
            for row in serp:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    try:
                        parsed.append((float(row[0]), float(row[1])))
                    except Exception:
                        continue
        if len(parsed) >= 2:
            for i in range(len(parsed) - 1):
                ax, ay = parsed[i]
                bx, by = parsed[i + 1]
                mx, my = (ax + bx) * 0.5, (ay + by) * 0.5
                ln = math.sqrt(((bx - ax) ** 2) + ((by - ay) ** 2))
                if ln <= 0.25:
                    continue
                ang = math.degrees(math.atan2((bx - ax), (by - ay)))
                pz = self._th(mx, my)
                seg = self._pl(
                    mk_plane(f"serpentine_path_{i}", 3.6, ln, 1.6),
                    mx, my, pz + 0.04,
                    self.tx["dirt"], road_mat, "Serpentine Trail", is_platform=False
                )
                seg.setH(ang)

    def _build_scenery(self):
        """Add decorative world detail: boulders, fountain, market stalls, paths."""
        import random
        rng = random.Random(42)
        stone_mat = mk_mat((0.50, 0.48, 0.44, 1), 0.6, 0.0)
        dirt_mat = mk_mat((0.42, 0.36, 0.28, 1), 0.9, 0.0)

        # --- Scattered boulders ---
        boulder_positions = [
            (15, 10), (-20, 25), (35, -15), (-40, 5), (25, 40),
            (-30, -20), (50, 20), (-15, 45), (40, -30), (-50, -10),
            (10, -40), (-25, 60), (55, 35), (-45, 30), (30, 55),
        ]
        for i, (bx, by) in enumerate(boulder_positions):
            bz = self._th(bx, by)
            if bz < -1.0:
                continue
            r = rng.uniform(0.4, 1.2)
            self._pl(
                mk_sphere(f"boulder_{i}", r, 6, 8),
                bx, by, bz + r * 0.3,
                self.tx["stone"], stone_mat, "Sharuan Plains"
            )

        # --- Central fountain (town square) ---
        fc_x, fc_y = 0, 0
        fc_z = self._th(fc_x, fc_y)
        # Base platform
        self._pl(mk_cyl("fountain_base", 2.5, 0.4, 16), fc_x, fc_y, fc_z + 0.2,
                 self.tx["stone"], stone_mat, "Town Fountain")
        # Inner basin ring
        self._pl(mk_cyl("fountain_ring", 1.8, 0.8, 16), fc_x, fc_y, fc_z + 0.5,
                 self.tx["stone"], stone_mat, "Town Fountain")
        # Central column
        self._pl(mk_cyl("fountain_col", 0.25, 2.0, 10), fc_x, fc_y, fc_z + 1.5,
                 self.tx["stone"], stone_mat, "Town Fountain")
        # Top basin
        self._pl(mk_cyl("fountain_top", 0.6, 0.3, 12), fc_x, fc_y, fc_z + 2.6,
                 self.tx["stone"], stone_mat, "Town Fountain")

        # --- Market stalls ---
        stall_positions = [(5, -8), (-6, -7), (4, -14), (-5, -13)]
        for i, (sx, sy) in enumerate(stall_positions):
            sz = self._th(sx, sy)
            # Market table
            self._pl(mk_box(f"stall_table_{i}", 3.0, 1.5, 0.12), sx, sy, sz + 1.0,
                     self.tx["bark"], None, "Market Square")
            # Table legs (4 posts)
            for dx, dy in [(-1.2, -0.6), (1.2, -0.6), (-1.2, 0.6), (1.2, 0.6)]:
                self._pl(mk_cyl(f"stall_leg_{i}_{dx}", 0.08, 1.0, 6),
                         sx + dx, sy + dy, sz + 0.5,
                         self.tx["bark"], None, "Market Square", is_platform=False)
            # Awning (angled roof)
            self._pl(mk_box(f"stall_awning_{i}", 3.4, 2.0, 0.06), sx, sy - 0.3, sz + 2.2,
                     self.tx["roof"], None, "Market Square", is_platform=False)

        # --- Cobblestone path from castle toward town ---
        for py in range(0, 50, 4):
            pz = self._th(0, py)
            self._pl(mk_plane(f"path_{py}", 3.5, 4.2, 2.0), 0, py, pz + 0.02,
                     self.tx["dirt"], dirt_mat, "Castle Road", is_platform=False)

        story_cfg = self.layout.get("story_landmarks", {}) if isinstance(self.layout.get("story_landmarks"), dict) else {}

        # Story bridge in Sharuan forest (memory scene over the stream).
        bridge_cfg = story_cfg.get("sharuan_bridge", {}) if isinstance(story_cfg.get("sharuan_bridge"), dict) else {}
        bridge_center = bridge_cfg.get("center", [-22.0, 20.0])
        if isinstance(bridge_center, list) and len(bridge_center) >= 2:
            try:
                bx = float(bridge_center[0]); by = float(bridge_center[1])
                bl = max(4.0, float(bridge_cfg.get("length", 9.0) or 9.0))
                bw = max(1.6, float(bridge_cfg.get("width", 2.8) or 2.8))
                bz = self._th(bx, by)
                bridge = self._pl(
                    mk_box("story_bridge_deck", bw, bl, 0.35),
                    bx,
                    by,
                    bz + 0.80,
                    self.tx["bark"],
                    mk_mat((0.40, 0.29, 0.18, 1.0), 0.82, 0.03),
                    "Sharuan Forest Bridge",
                )
                bridge.setH(18.0)
                for side in (-1, 1):
                    rail = self._pl(
                        mk_box(f"story_bridge_rail_{side}", 0.16, bl, 0.5),
                        bx + (side * ((bw * 0.5) - 0.08)),
                        by,
                        bz + 1.15,
                        self.tx["bark"],
                        mk_mat((0.36, 0.26, 0.16, 1.0), 0.85, 0.03),
                        "Sharuan Forest Bridge",
                        is_platform=False,
                    )
                    rail.setH(18.0)
            except Exception:
                pass

        # Adrian's cage landmark inside Krimora.
        cage_cfg = story_cfg.get("adrian_cage", {}) if isinstance(story_cfg.get("adrian_cage"), dict) else {}
        cage_center = cage_cfg.get("center", [70.0, 2.0])
        cage_size = cage_cfg.get("size", [3.2, 2.4, 2.8])
        if isinstance(cage_center, list) and len(cage_center) >= 2 and isinstance(cage_size, list) and len(cage_size) >= 3:
            try:
                cx = float(cage_center[0]); cy = float(cage_center[1]); cz = self._th(cx, cy)
                sx = max(1.8, float(cage_size[0])); sy = max(1.4, float(cage_size[1])); sz = max(1.8, float(cage_size[2]))
                self._pl(
                    mk_box("adrian_cage_top", sx, sy, 0.12),
                    cx, cy, cz + sz + 0.05,
                    self.tx["stone"], stone_mat, "Krimora Cage Clearing", is_platform=False
                )
                for side in (-1, 1):
                    for j in range(4):
                        off = (-sy * 0.5) + (0.35 + j * ((sy - 0.70) / 3.0))
                        self._pl(
                            mk_cyl(f"adrian_cage_bar_{side}_{j}", 0.05, sz, 7),
                            cx + (side * (sx * 0.5 - 0.08)),
                            cy + off,
                            cz + (sz * 0.5),
                            self.tx["stone"], stone_mat, "Krimora Cage Clearing", is_platform=False
                        )
                # Bent door section to imply forced opening.
                door = self._pl(
                    mk_box("adrian_cage_door", 0.12, sy * 0.72, sz * 0.9),
                    cx + (sx * 0.5 - 0.04),
                    cy - 0.10,
                    cz + (sz * 0.45),
                    self.tx["stone"], stone_mat, "Krimora Cage Clearing", is_platform=False
                )
                door.setH(-24.0)
            except Exception:
                pass

        # Dwarven gate marker to transition toward cave content.
        gate_cfg = story_cfg.get("dwarven_gate", {}) if isinstance(story_cfg.get("dwarven_gate"), dict) else {}
        gate_center = gate_cfg.get("center", [92.0, -6.0])
        gate_size = gate_cfg.get("size", [8.0, 2.0, 7.5])
        if isinstance(gate_center, list) and len(gate_center) >= 2 and isinstance(gate_size, list) and len(gate_size) >= 3:
            try:
                gx = float(gate_center[0]); gy = float(gate_center[1]); gz = self._th(gx, gy)
                gw = max(5.0, float(gate_size[0])); gd = max(1.2, float(gate_size[1])); gh = max(4.0, float(gate_size[2]))
                dwarven_stone = mk_mat((0.42, 0.40, 0.44, 1.0), 0.62, 0.05)
                self._pl(
                    mk_box("dwarven_gate_frame", gw, gd, gh),
                    gx, gy, gz + (gh * 0.5),
                    self.tx["stone"], dwarven_stone, "Dwarven Caves Gate"
                )
                self._pl(
                    mk_box("dwarven_gate_opening", gw * 0.58, gd + 0.25, gh * 0.68),
                    gx, gy + 0.05, gz + (gh * 0.42),
                    self.tx["stone"], mk_mat((0.14, 0.12, 0.14, 1.0), 0.95, 0.0), "Dwarven Caves Gate", is_platform=False
                )
                for side in (-1, 1):
                    self._pl(
                        mk_sphere(f"dwarven_gate_gem_{side}", 0.42, 8, 9),
                        gx + (side * (gw * 0.35)),
                        gy + 0.22,
                        gz + 1.10,
                        None, mk_mat((0.72, 0.16, 0.10, 1.0), 0.22, 0.58),
                        "Dwarven Caves Gate", is_platform=False
                    )
            except Exception:
                pass

        # Soft dirt decals make routes readable without hard geometry changes.
        self._scatter_path_decals()

    def _spawn_treasure_chest(self, chest_id, x, y, z, loc_name):
        wood_mat = mk_mat((0.34, 0.22, 0.11, 1.0), 0.78, 0.04)
        band_mat = mk_mat((0.67, 0.58, 0.34, 1.0), 0.34, 0.66)
        inner_mat = mk_mat((0.18, 0.08, 0.04, 1.0), 0.90, 0.02)
        coin_mat = mk_mat((0.94, 0.78, 0.30, 1.0), 0.20, 0.82)
        glow_mat = mk_mat((1.00, 0.55, 0.18, 0.42), 0.08, 0.05)

        chest_root = self.render.attach_new_node(f"chest_{chest_id}")
        chest_root.set_pos(x, y, z)
        chest_root.set_tag("info", f"{loc_name} Chest")

        # Base body.
        base = self._pl(
            mk_box(f"chest_base_{chest_id}", 1.08, 0.72, 0.50),
            x,
            y,
            z + 0.25,
            self.tx.get("bark"),
            wood_mat,
            loc_name,
            is_platform=False,
        )
        base.wrtReparentTo(chest_root)
        base.setPos(0.0, 0.0, 0.25)

        # Interior cavity frame.
        inner = self._pl(
            mk_box(f"chest_inner_{chest_id}", 0.88, 0.54, 0.24),
            x,
            y,
            z + 0.37,
            None,
            inner_mat,
            loc_name,
            is_platform=False,
        )
        inner.wrtReparentTo(chest_root)
        inner.setPos(0.0, 0.0, 0.37)

        # Lid opened to reveal interior.
        lid = self._pl(
            mk_box(f"chest_lid_{chest_id}", 1.10, 0.62, 0.26),
            x,
            y,
            z + 0.63,
            self.tx.get("bark"),
            wood_mat,
            loc_name,
            is_platform=False,
        )
        lid.wrtReparentTo(chest_root)
        lid.setPos(0.0, -0.08, 0.63)
        lid.setP(-24.0)

        # Metal banding.
        for side, off in (("left", -0.36), ("right", 0.36)):
            strap = self._pl(
                mk_box(f"chest_strap_{chest_id}_{side}", 0.08, 0.74, 0.54),
                x + off,
                y,
                z + 0.28,
                self.tx.get("stone"),
                band_mat,
                loc_name,
                is_platform=False,
            )
            strap.wrtReparentTo(chest_root)
            strap.setPos(off, 0.0, 0.28)

        latch = self._pl(
            mk_box(f"chest_latch_{chest_id}", 0.12, 0.08, 0.14),
            x,
            y + 0.35,
            z + 0.36,
            self.tx.get("stone"),
            band_mat,
            loc_name,
            is_platform=False,
        )
        latch.wrtReparentTo(chest_root)
        latch.setPos(0.0, 0.35, 0.36)

        # Coin pile for "inner beauty".
        for idx in range(8):
            ang = (idx / 8.0) * (math.pi * 2.0)
            rad = 0.12 + (0.03 * (idx % 3))
            cx = math.cos(ang) * rad
            cy = math.sin(ang) * rad * 0.7
            coin = self._pl(
                mk_cyl(f"chest_coin_{chest_id}_{idx}", 0.05, 0.02, 8),
                x + cx,
                y + cy,
                z + 0.33 + (0.004 * (idx % 2)),
                None,
                coin_mat,
                loc_name,
                is_platform=False,
            )
            coin.wrtReparentTo(chest_root)
            coin.setPos(cx, cy, 0.33 + (0.004 * (idx % 2)))
            coin.setP(90.0)

        glow = self._pl(
            mk_sphere(f"chest_glow_{chest_id}", 0.18, 7, 9),
            x,
            y,
            z + 0.42,
            None,
            glow_mat,
            loc_name,
            is_platform=False,
        )
        glow.wrtReparentTo(chest_root)
        glow.setPos(0.0, 0.0, 0.42)
        glow.setTransparency(TransparencyAttrib.M_alpha)
        glow.setLightOff(1)

        self._chest_nodes.append(chest_root)

    def _build_treasure_chests(self):
        """Guarantee treasure chests in every major location (with visible interior details)."""
        self._chest_nodes = []
        if not isinstance(self.locations, list) or not self.locations:
            return

        for idx, loc in enumerate(self.locations):
            if not isinstance(loc, dict):
                continue
            pos = loc.get("pos", [])
            if not (isinstance(pos, list) and len(pos) >= 2):
                continue
            try:
                lx = float(pos[0])
                ly = float(pos[1])
            except Exception:
                continue
            radius = max(6.0, float(loc.get("radius", 20.0) or 20.0))
            loc_name = str(loc.get("name", f"Location {idx+1}") or f"Location {idx+1}")

            # One guaranteed chest per location + one extra on very large zones.
            count = 2 if radius >= 28.0 else 1
            for cidx in range(count):
                angle = (idx * 1.37) + (cidx * 2.1)
                dist = min(10.0, max(3.4, radius * (0.20 + (0.06 * cidx))))
                cx = lx + (math.cos(angle) * dist)
                cy = ly + (math.sin(angle) * dist)
                cz = self._th(cx, cy)
                self._spawn_treasure_chest(f"{idx}_{cidx}", cx, cy, cz + 0.02, loc_name)

    def _build_movement_training_ground(self):
        """Dedicated test arena for movement tutorial and animation state validation."""
        tx, ty = 18.0, 24.0
        center_z = self._th(tx, ty)
        stone_mat = mk_mat((0.52, 0.49, 0.45, 1.0), 0.72, 0.02)
        dirt_mat = mk_mat((0.42, 0.35, 0.26, 1.0), 0.88, 0.0)
        water_mat = mk_mat((0.12, 0.30, 0.50, 0.82), 0.15, 0.18)
        wood_mat = mk_mat((0.32, 0.22, 0.14, 1.0), 0.78, 0.0)
        accent_mat = mk_mat((0.62, 0.56, 0.40, 1.0), 0.52, 0.04)

        # Ground platform / sprint lane base.
        self._pl(
            mk_plane("training_plaza", 48.0, 34.0, 2.6),
            tx,
            ty,
            center_z + 0.03,
            self.tx["dirt"],
            dirt_mat,
            "Training Grounds",
            is_platform=False,
        )

        # Sprint lane guide stones.
        for idx in range(7):
            px = tx - 18.0 + (idx * 6.0)
            py = ty - 11.0
            pz = self._th(px, py)
            self._pl(
                mk_box(f"training_lane_marker_{idx}", 0.8, 0.8, 0.18),
                px,
                py,
                pz + 0.09,
                self.tx["stone"],
                stone_mat,
                "Training Grounds",
                is_platform=False,
            )

        # Jump sequence platforms.
        jump_specs = [
            ("training_jump_a", tx - 11.0, ty + 6.0, 1.0, 2.6),
            ("training_jump_b", tx - 5.5, ty + 6.8, 1.5, 2.4),
            ("training_jump_c", tx + 0.5, ty + 7.6, 1.9, 2.3),
        ]
        for name, px, py, h, width in jump_specs:
            pz = self._th(px, py)
            self._pl(
                mk_box(name, width, 2.2, h),
                px,
                py,
                pz + (h * 0.5),
                self.tx["stone"],
                stone_mat,
                "Training Grounds",
            )

        # Vault barriers (low obstacles).
        for idx in range(4):
            px = tx - 12.0 + (idx * 4.2)
            py = ty + 0.2
            pz = self._th(px, py)
            self._pl(
                mk_box(f"training_vault_barrier_{idx}", 2.1, 0.45, 1.05),
                px,
                py,
                pz + 0.52,
                self.tx["stone"],
                stone_mat,
                "Training Grounds",
            )

        # Wallrun wall.
        wall_x = tx + 14.0
        wall_y = ty + 1.8
        wall_z = self._th(wall_x, wall_y)
        self._pl(
            mk_box("training_wallrun_wall", 1.2, 15.0, 6.2),
            wall_x,
            wall_y,
            wall_z + 3.1,
            self.tx["stone"],
            stone_mat,
            "Training Grounds",
        )

        # Climb ledge block.
        ledge_x = tx + 9.0
        ledge_y = ty + 13.0
        ledge_z = self._th(ledge_x, ledge_y)
        self._pl(
            mk_box("training_climb_block", 4.8, 3.2, 3.8),
            ledge_x,
            ledge_y,
            ledge_z + 1.9,
            self.tx["stone"],
            stone_mat,
            "Training Grounds",
        )

        # Decorative perimeter posts so test scenes still feel authored and readable.
        perimeter_posts = [
            (tx - 20.0, ty - 14.0),
            (tx - 20.0, ty + 14.0),
            (tx + 20.0, ty - 14.0),
            (tx + 20.0, ty + 14.0),
        ]
        for idx, (px, py) in enumerate(perimeter_posts):
            pz = self._th(px, py)
            self._pl(
                mk_cyl(f"training_post_{idx}", 0.16, 2.5, 10),
                px,
                py,
                pz + 1.25,
                self.tx["bark"],
                wood_mat,
                "Training Grounds",
                is_platform=False,
            )
            self._pl(
                mk_sphere(f"training_post_lantern_{idx}", 0.22, 8, 10),
                px,
                py,
                pz + 2.35,
                None,
                accent_mat,
                "Training Grounds",
                is_platform=False,
            )

        # Parkour lane: ruined arches + staggered columns for vault/climb/wallrun flow.
        pk_x = tx + 24.0
        pk_y = ty + 9.0
        pk_z = self._th(pk_x, pk_y)
        self._pl(
            mk_plane("parkour_plaza", 18.0, 16.0, 1.9),
            pk_x,
            pk_y,
            pk_z + 0.04,
            self.tx["stone"],
            stone_mat,
            "Forest Parkour Grounds",
            is_platform=False,
        )
        for idx in range(5):
            cx = pk_x - 6.5 + (idx * 3.1)
            cy = pk_y - 4.2 + (idx * 1.35)
            cz = self._th(cx, cy)
            col_h = 2.0 + (idx * 0.75)
            self._pl(
                mk_box(f"parkour_col_{idx}", 1.0, 1.0, col_h),
                cx,
                cy,
                cz + (col_h * 0.5),
                self.tx["stone"],
                stone_mat,
                "Forest Parkour Grounds",
            )
            if idx % 2 == 0:
                self._pl(
                    mk_box(f"parkour_beam_{idx}", 2.8, 0.42, 0.36),
                    cx + 1.35,
                    cy + 1.2,
                    cz + col_h + 0.18,
                    self.tx["bark"],
                    wood_mat,
                    "Forest Parkour Grounds",
                )

        arch_specs = [
            (pk_x - 3.6, pk_y + 5.0, 3.9),
            (pk_x + 3.0, pk_y + 6.6, 4.5),
        ]
        for idx, (ax, ay, ah) in enumerate(arch_specs):
            az = self._th(ax, ay)
            self._pl(
                mk_box(f"parkour_arch_leg_l_{idx}", 0.7, 0.7, ah),
                ax - 1.4,
                ay,
                az + (ah * 0.5),
                self.tx["stone"],
                stone_mat,
                "Forest Parkour Grounds",
            )
            self._pl(
                mk_box(f"parkour_arch_leg_r_{idx}", 0.7, 0.7, ah),
                ax + 1.4,
                ay,
                az + (ah * 0.5),
                self.tx["stone"],
                stone_mat,
                "Forest Parkour Grounds",
            )
            self._pl(
                mk_box(f"parkour_arch_top_{idx}", 3.4, 0.8, 0.5),
                ax,
                ay,
                az + ah + 0.25,
                self.tx["stone"],
                stone_mat,
                "Forest Parkour Grounds",
            )

        # Flight lane: takeoff platform + floating ring markers for traversal testing.
        fl_x = tx - 23.0
        fl_y = ty - 1.0
        fl_z = self._th(fl_x, fl_y)
        self._pl(
            mk_cyl("flight_launch_pad", 4.2, 0.8, 18),
            fl_x,
            fl_y,
            fl_z + 0.4,
            self.tx["stone"],
            stone_mat,
            "Coastal Flight Grounds",
        )
        self._pl(
            mk_box("flight_watch_tower", 2.4, 2.4, 7.8),
            fl_x - 5.2,
            fl_y + 0.8,
            self._th(fl_x - 5.2, fl_y + 0.8) + 3.9,
            self.tx["stone"],
            stone_mat,
            "Coastal Flight Grounds",
        )
        self._pl(
            mk_box("flight_tower_roof", 3.2, 3.2, 0.55),
            fl_x - 5.2,
            fl_y + 0.8,
            self._th(fl_x - 5.2, fl_y + 0.8) + 7.95,
            self.tx["roof"],
            wood_mat,
            "Coastal Flight Grounds",
        )

        ring_specs = [
            (fl_x + 5.0, fl_y + 10.0, fl_z + 7.2, 1.6),
            (fl_x + 12.0, fl_y + 18.0, fl_z + 10.4, 2.0),
            (fl_x + 20.0, fl_y + 13.0, fl_z + 8.8, 1.8),
        ]
        for idx, (rx, ry, rz, rr) in enumerate(ring_specs):
            for seg in range(10):
                ang = (math.tau * seg) / 10.0
                px = rx + (math.cos(ang) * rr)
                py = ry + (math.sin(ang) * rr)
                self._pl(
                    mk_sphere(f"flight_ring_{idx}_{seg}", 0.22, 7, 8),
                    px,
                    py,
                    rz,
                    None,
                    accent_mat,
                    "Coastal Flight Grounds",
                    is_platform=False,
                )

        # Shallow water pool for swim test.
        pool_x = tx - 14.0
        pool_y = ty + 12.0
        pool_z = self._th(pool_x, pool_y) - 1.1
        pool = self._pl(
            mk_plane("training_pool", 11.0, 8.0, 1.6),
            pool_x,
            pool_y,
            pool_z,
            None,
            water_mat,
            "Training Grounds",
            is_platform=False,
        )
        pool.set_transparency(TransparencyAttrib.M_alpha)

        if self.phys:
            p = gc.Platform()
            p.aabb.min = gc.Vec3(pool_x - 5.5, pool_y - 4.0, pool_z - 2.5)
            p.aabb.max = gc.Vec3(pool_x + 5.5, pool_y + 4.0, pool_z + 0.1)
            p.isWater = True
            self.phys.addPlatform(p)

    def _build_dwarven_caves_story_setpiece(self):
        zones = self.layout.get("zones", []) if isinstance(self.layout.get("zones"), list) else []

        def zone_center(zone_id, fallback):
            zid = str(zone_id or "").strip().lower()
            if isinstance(zones, list):
                for row in zones:
                    if not isinstance(row, dict):
                        continue
                    row_id = str(row.get("id", "") or "").strip().lower()
                    center = row.get("center", [])
                    if row_id != zid or not (isinstance(center, list) and len(center) >= 2):
                        continue
                    try:
                        x = float(center[0]); y = float(center[1]); z = float(center[2]) if len(center) >= 3 else 0.0
                        return x, y, z
                    except Exception:
                        continue
            return fallback

        gate_x, gate_y, _ = zone_center("dwarven_caves_gate", (92.0, -6.0, 4.0))
        halls_x, halls_y, _ = zone_center("dwarven_caves_halls", (96.0, -14.0, 2.0))
        throne_x, throne_y, _ = zone_center("dwarven_caves_throne", (102.0, -24.0, 3.0))

        stone_dark = mk_mat((0.36, 0.34, 0.38, 1.0), 0.66, 0.06)
        stone_worn = mk_mat((0.48, 0.45, 0.42, 1.0), 0.74, 0.03)
        iron_dark = mk_mat((0.20, 0.21, 0.24, 1.0), 0.44, 0.52)
        ember = mk_mat((0.78, 0.25, 0.08, 1.0), 0.32, 0.42)
        gem_blue = mk_mat((0.18, 0.46, 0.84, 1.0), 0.14, 0.62)
        gem_red = mk_mat((0.86, 0.18, 0.14, 1.0), 0.18, 0.64)
        gold_mat = mk_mat((0.74, 0.62, 0.18, 1.0), 0.20, 0.72)

        # Gate causeway.
        path_points = [
            (gate_x, gate_y),
            ((gate_x + halls_x) * 0.5, (gate_y + halls_y) * 0.5),
            (halls_x, halls_y),
            ((halls_x + throne_x) * 0.5, (halls_y + throne_y) * 0.5),
            (throne_x, throne_y),
        ]
        for idx in range(len(path_points) - 1):
            ax, ay = path_points[idx]
            bx, by = path_points[idx + 1]
            mx, my = (ax + bx) * 0.5, (ay + by) * 0.5
            ln = math.sqrt(((bx - ax) ** 2) + ((by - ay) ** 2))
            if ln <= 0.2:
                continue
            ang = math.degrees(math.atan2((bx - ax), (by - ay)))
            pz = self._th(mx, my)
            seg = self._pl(
                mk_plane(f"dwarf_path_{idx}", 4.6, ln + 1.2, 1.3),
                mx,
                my,
                pz + 0.06,
                self.tx["stone"],
                stone_worn,
                "Dwarven Caves Gate",
                is_platform=False,
            )
            seg.setH(ang)

        # Main cavern shell around forge halls.
        hall_floor_z = self._th(halls_x, halls_y)
        self._pl(
            mk_cyl("dwarf_hall_floor", 14.0, 0.9, 28),
            halls_x,
            halls_y,
            hall_floor_z + 0.45,
            self.tx["stone"],
            stone_dark,
            "Dwarven Forge Halls",
        )
        self._pl(
            mk_sphere("dwarf_hall_dome", 16.0, 12, 14),
            halls_x,
            halls_y,
            hall_floor_z + 11.0,
            self.tx["stone"],
            mk_mat((0.24, 0.24, 0.28, 0.9), 0.94, 0.0),
            "Dwarven Forge Halls",
            is_platform=False,
        )

        # Treasury sector (left wing).
        treasury_x = halls_x - 14.5
        treasury_y = halls_y - 1.5
        treasury_z = self._th(treasury_x, treasury_y)
        treasury_anchor_node = self._pl(
            mk_box("dwarf_treasury_floor", 12.0, 9.0, 0.8),
            treasury_x, treasury_y, treasury_z + 0.40,
            self.tx["stone"], stone_dark, "Dwarven Treasury Vaults"
        )
        for idx in range(3):
            vx = treasury_x - 3.3 + (idx * 3.3)
            vy = treasury_y + 2.1
            vz = self._th(vx, vy)
            self._pl(
                mk_box(f"dwarf_vault_{idx}", 2.3, 2.1, 2.8),
                vx, vy, vz + 1.4,
                self.tx["stone"], iron_dark, "Dwarven Treasury Vaults"
            )
            self._pl(
                mk_sphere(f"dwarf_treasure_heap_{idx}", 0.72, 8, 9),
                vx, vy - 1.5, vz + 0.70,
                None, gold_mat, "Dwarven Treasury Vaults", is_platform=False
            )
        self._register_story_anchor(
            "dwarven_treasury_cache",
            treasury_anchor_node,
            name="Treasury Vault",
            hint="Inspect treasury cache",
            single_use=True,
            rewards={"xp": 85, "gold": 180},
            event_name="story.dwarven_treasury_opened",
            codex_unlocks=[
                {
                    "section": "events",
                    "id": "dwarven_treasury_opened",
                    "title": "Dwarven Treasury Opened",
                    "details": "A sealed treasury bay yields old coin and records of the stone courts.",
                }
            ],
            location_name="Dwarven Treasury Vaults",
        )

        # Workshop sector (right wing) with anvils and furnaces.
        forge_x = halls_x + 13.8
        forge_y = halls_y - 1.2
        forge_z = self._th(forge_x, forge_y)
        forge_anchor_node = self._pl(
            mk_box("dwarf_forge_floor", 11.0, 9.0, 0.8),
            forge_x, forge_y, forge_z + 0.40,
            self.tx["stone"], stone_dark, "Dwarven Forge Halls"
        )
        for idx in range(4):
            fx = forge_x - 3.4 + (idx * 2.2)
            fy = forge_y + (1.2 if idx % 2 == 0 else -1.4)
            fz = self._th(fx, fy)
            self._pl(
                mk_box(f"dwarf_anvil_{idx}", 1.2, 0.7, 0.9),
                fx, fy, fz + 0.45,
                self.tx["stone"], iron_dark, "Dwarven Forge Halls"
            )
            glow = self._pl(
                mk_cyl(f"dwarf_furnace_glow_{idx}", 0.46, 0.30, 10),
                fx, fy - 1.0, fz + 0.24,
                None, ember, "Dwarven Forge Halls", is_platform=False
            )
            glow.setColorScale(1.0, 0.55, 0.24, 0.94)
        self._register_story_anchor(
            "dwarven_forge_station",
            forge_anchor_node,
            name="Master Forge",
            hint="Examine dwarven forge tools",
            single_use=True,
            rewards={"xp": 75, "gold": 60},
            event_name="story.dwarven_forge_examined",
            codex_unlocks=[
                {
                    "section": "events",
                    "id": "dwarven_forge_examined",
                    "title": "Dwarven Forge Studied",
                    "details": "The forge sector reveals precision craft and ritual metallurgy.",
                }
            ],
            location_name="Dwarven Forge Halls",
        )

        # Bestiary sector with gemstone hybrid creatures.
        beast_x = halls_x
        beast_y = halls_y + 13.2
        beast_z = self._th(beast_x, beast_y)
        bestiary_anchor_node = self._pl(
            mk_box("dwarf_bestiary_floor", 13.0, 8.8, 0.8),
            beast_x, beast_y, beast_z + 0.40,
            self.tx["stone"], stone_dark, "Dwarven Bestiary"
        )
        for idx in range(3):
            cx = beast_x - 4.0 + (idx * 4.0)
            cy = beast_y
            cz = self._th(cx, cy)
            self._pl(
                mk_box(f"dwarf_beast_cage_{idx}", 2.8, 2.6, 2.9),
                cx, cy, cz + 1.45,
                self.tx["stone"], iron_dark, "Dwarven Bestiary"
            )
            self._pl(
                mk_sphere(f"dwarf_hybrid_core_{idx}", 0.62, 8, 9),
                cx, cy, cz + 0.92,
                None, gem_blue if idx % 2 == 0 else gem_red, "Dwarven Bestiary", is_platform=False
            )
            for spike in range(5):
                ang = (math.tau * spike) / 5.0
                sx = cx + (math.cos(ang) * 0.84)
                sy = cy + (math.sin(ang) * 0.84)
                self._pl(
                    mk_cone(f"dwarf_hybrid_spike_{idx}_{spike}", 0.14, 0.45, 7),
                    sx, sy, cz + 1.25,
                    None, gem_blue if idx % 2 == 0 else gem_red, "Dwarven Bestiary", is_platform=False
                )
        self._register_story_anchor(
            "dwarven_bestiary_cage",
            bestiary_anchor_node,
            name="Gemstone Bestiary",
            hint="Inspect gemstone hybrids",
            single_use=True,
            rewards={"xp": 95, "gold": 40},
            event_name="story.dwarven_bestiary_logged",
            codex_unlocks=[
                {
                    "section": "events",
                    "id": "dwarven_bestiary_logged",
                    "title": "Gem Hybrids Catalogued",
                    "details": "Hybrid creatures of crystal core and stone frame are documented in the Codex.",
                },
                {
                    "section": "locations",
                    "id": "dwarven_bestiary",
                    "title": "Dwarven Bestiary",
                    "details": "Containment hall for gemstone-born hybrids beneath the mountain courts.",
                }
            ],
            location_name="Dwarven Bestiary",
        )

        # Central grand throne hall with oversized scale.
        throne_z = self._th(throne_x, throne_y)
        self._pl(
            mk_cyl("dwarf_grand_floor", 18.0, 1.0, 36),
            throne_x, throne_y, throne_z + 0.50,
            self.tx["stone"], stone_worn, "Dwarven Grand Throne"
        )
        for idx in range(12):
            ang = (math.tau * idx) / 12.0
            px = throne_x + (math.cos(ang) * 13.5)
            py = throne_y + (math.sin(ang) * 13.5)
            pz = self._th(px, py)
            self._pl(
                mk_cyl(f"dwarf_grand_col_{idx}", 0.58, 8.5, 12),
                px, py, pz + 4.25,
                self.tx["stone"], stone_dark, "Dwarven Grand Throne"
            )

        throne_base = self._pl(
            mk_box("dwarf_throne_base", 7.5, 4.2, 2.2),
            throne_x, throne_y + 5.2, throne_z + 1.1,
            self.tx["stone"], stone_dark, "Dwarven Grand Throne"
        )
        throne_base.setH(180.0)
        self._pl(
            mk_box("dwarf_throne_seat", 3.2, 1.6, 3.8),
            throne_x, throne_y + 6.1, throne_z + 3.2,
            self.tx["stone"], stone_worn, "Dwarven Grand Throne"
        )

        for idx in range(28):
            ang = (math.tau * idx) / 28.0
            rad = 6.0 + (1.8 if idx % 2 == 0 else 0.0)
            px = throne_x + (math.cos(ang) * rad)
            py = throne_y + (math.sin(ang) * rad)
            pz = self._th(px, py)
            gem_mat = gem_blue if idx % 3 else gem_red
            self._pl(
                mk_sphere(f"dwarf_grand_gem_{idx}", 0.34 + (0.08 if idx % 5 == 0 else 0.0), 7, 8),
                px, py, pz + 0.62,
                None, gem_mat, "Dwarven Grand Throne", is_platform=False
            )
        self._register_story_anchor(
            "dwarven_grand_throne",
            throne_base,
            name="Grand Stone Throne",
            hint="Study the dwarven throne seal",
            single_use=True,
            rewards={"xp": 140, "gold": 220},
            event_name="story.dwarven_throne_attuned",
            codex_unlocks=[
                {
                    "section": "events",
                    "id": "dwarven_throne_attuned",
                    "title": "Throne Seal Attuned",
                    "details": "The central throne imprint confirms the scale of the dwarven sovereign halls.",
                },
                {
                    "section": "locations",
                    "id": "dwarven_grand_throne",
                    "title": "Dwarven Grand Throne",
                    "details": "Central hall whose magnitude eclipses the throne chamber of Sharuan.",
                }
            ],
            location_name="Dwarven Grand Throne",
        )

    def _build_flora_fauna(self):
        bark_mat = mk_mat((0.34, 0.24, 0.16, 1), 0.9, 0.0)
        leaf_mat = mk_mat((0.18, 0.48, 0.20, 1), 0.78, 0.0)
        rng = random.Random(20260223)
        tree_positions = []

        for gx in range(-90, 91, 14):
            for gy in range(-45, 91, 14):
                if gy < -40:
                    continue
                if (gx * gx + (gy - 65) * (gy - 65)) < 520:
                    continue
                if self._distance_to_river(gx, gy) < 5.5:
                    continue
                if rng.random() < 0.34:
                    tree_positions.append(
                        (
                            gx + rng.uniform(-2.8, 2.8),
                            gy + rng.uniform(-2.8, 2.8),
                        )
                    )

        tree_positions.sort(key=lambda p: (p[1], p[0]))
        foliage_tex = None
        for token in (
            "assets/textures/foliage_seamless_texture_5435.jpg",
            "assets/textures/flare.png",
        ):
            try:
                if os.path.exists(token):
                    foliage_tex = self.loader.loadTexture(token)
                    if foliage_tex:
                        break
            except Exception:
                foliage_tex = None

        for idx, (x, y) in enumerate(tree_positions[:72]):
            z = self._th(x, y)
            trunk_h = rng.uniform(2.1, 3.7)
            trunk_r = rng.uniform(0.18, 0.30)
            self._pl(
                mk_cyl(f"trunk_{idx}", trunk_r, trunk_h, 10),
                x, y, z + trunk_h * 0.5,
                self.tx["bark"], bark_mat, "Wild Grove"
            )

            canopy_mode = rng.choice(("cone", "sphere"))
            if canopy_mode == "cone":
                self._pl(
                    mk_cone(f"leaf_cone_{idx}", trunk_h * 0.46, trunk_h * 1.15, 12),
                    x, y, z + trunk_h + trunk_h * 0.50,
                    self.tx["leaf"], leaf_mat, "Wild Grove", is_platform=False
                )
            else:
                self._pl(
                    mk_sphere(f"leaf_sphere_{idx}", trunk_h * 0.42, 8, 10),
                    x, y, z + trunk_h + trunk_h * 0.32,
                    self.tx["leaf"], leaf_mat, "Wild Grove", is_platform=False
                )

            # A small warm leaf highlight helps readability in low light.
            if idx % 6 == 0:
                glow = self._pl(
                    mk_sphere(f"leaf_glow_{idx}", trunk_h * 0.18, 7, 8),
                    x,
                    y,
                    z + trunk_h + trunk_h * 0.42,
                    None,
                    mk_mat((0.98, 0.88, 0.62, 0.58), 0.24, 0.0),
                    "Foliage Glow",
                    is_platform=False,
                )
                glow.set_transparency(TransparencyAttrib.M_alpha)

            # Light shafts through canopy for atmosphere.
            if idx % 8 == 0:
                shaft = self._pl(
                    mk_cone(f"leaf_shaft_{idx}", trunk_h * 0.30, trunk_h * 1.9, 10),
                    x + rng.uniform(-0.5, 0.5),
                    y + rng.uniform(-0.5, 0.5),
                    z + trunk_h + (trunk_h * 0.78),
                    None,
                    mk_mat((0.95, 0.90, 0.70, 0.34), 0.12, 0.0),
                    "Leaf Shaft",
                    is_platform=False,
                )
                shaft.setP(180.0)
                shaft.set_transparency(TransparencyAttrib.M_alpha)
                shaft.setColorScale(1.0, 0.94, 0.76, 0.20)

        # Dense grass band around traversable ground, avoiding river and sea edge.
        grass_rng = random.Random(20260308)
        spec_rng = getattr(self, "_rng", None) or grass_rng
        grass_specs = []
        for _ in range(280):
            x = grass_rng.uniform(-92.0, 92.0)
            y = grass_rng.uniform(-38.0, 88.0)
            if y < -40.0:
                continue
            if self._distance_to_river(x, y) < 4.3:
                continue
            z = self._th(x, y)
            if z < -0.8:
                continue
            # Keep castle foreground cleaner.
            if (x * x + ((y - 65.0) * (y - 65.0))) < 460.0:
                continue
            grass_specs.append(make_grass_tuft_spec(spec_rng, x, y, z))

        if grass_specs:
            try:
                self._spawn_grass_batch(grass_specs, foliage_tex)
            except Exception as exc:
                logger.warning(f"[SharuanWorld] Grass batch failed, falling back to per-tuft nodes: {exc}")
                for grass_idx, spec in enumerate(grass_specs):
                    self._spawn_grass_tuft(
                        grass_idx,
                        spec.get("x", 0.0),
                        spec.get("y", 0.0),
                        spec.get("z", 0.0),
                        foliage_tex,
                        spec=spec,
                    )
