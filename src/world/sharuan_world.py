"""
SharuanWorld - Refactored Sharuan Map
Handles procedural generation, PBR materials, and world entities.
Wires generated geometry into C++ physics.
"""
import math
import random
from panda3d.core import (
    Vec3, LColor,
    GeomNode, Geom, GeomTriangles, GeomVertexFormat,
    GeomVertexData, GeomVertexWriter, GeomVertexRewriter,
    TransparencyAttrib, Texture, TextureStage, Material, Shader
)

try:
    import game_core as gc
    HAS_CORE = True
except ImportError:
    gc = None
    HAS_CORE = False

from utils.assets_util import _fbm, make_pbr_tex_set

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

class SharuanWorld:
    RIVER = [(30,65),(25,55),(20,45),(15,38),(10,32),(5,25),(0,18),(-5,10),
             (-8,2),(-10,-5),(-10,-15),(-8,-25),(-5,-35),(-3,-45),(0,-55),(0,-70)]

    def __init__(self, app):
        self.app = app
        self.render = app.render
        self.loader = app.loader
        self.phys = app.phys if HAS_CORE else None
        self.data_mgr = app.data_mgr

        self.locations = self.data_mgr.world_config.get("locations", [])
        self.active_location = None
        self.colliders = [] # Python-only fallback AABB list

        try:
            self.terrain_shader = Shader.load(
                Shader.SL_GLSL,
                "shaders/simple_pbr.vert",
                "shaders/simple_pbr.frag"
            )
        except Exception as e:
            from utils.logger import logger
            logger.error(f"Failed to load terrain fallback shader: {e}")
            self.terrain_shader = None

        self.tx = {}
        self._gen_steps = [
            (0.1, self._init_textures, "Generating procedural materials..."),
            (0.25, self._build_terrain, "Drafting Sharuan terrain..."),
            (0.35, self._build_sea, "Simulating sea and water bodies..."),
            (0.42, self._build_river, "Mapping river paths..."),
            (0.55, self._build_castle, "Constructing Castle Sharuan..."),
            (0.65, self._build_city_wall, "Erecting city fortifications..."),
            (0.75, self._build_districts, "Laying out city districts..."),
            (0.82, self._build_center, "Designing town center..."),
            (0.86, self._build_movement_training_ground, "Preparing movement training grounds..."),
            (0.90, self._build_scenery, "Adding scenery and decorations..."),
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

    def update(self, player_pos):
        # Check for location triggers
        for loc in self.locations:
            lp = loc['pos']
            dist = (player_pos - Vec3(lp[0], lp[1], lp[2])).length()
            if dist < loc['radius']:
                if self.active_location != loc['name']:
                    self.active_location = loc['name']
                    print(f"[World] Entered: {self.active_location}")
                return
        self.active_location = None

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
        md = math.sqrt(x*x + (y-65)*(y-65))
        mtn = 26.0 * math.exp(-(md*md) / (2*25*25))
        if md < 10: mtn = max(mtn, 23.0 + (10-md)*0.1)
        sea = min(0.0, (y + 50) * 0.5) if y < -50 else 0.0
        rv = 0.0
        for i in range(len(self.RIVER)-1):
            ax,ay = self.RIVER[i]; bx,by = self.RIVER[i+1]
            dx,dy = bx-ax, by-ay; ln = math.sqrt(dx*dx+dy*dy)
            if ln < 0.1: continue
            t = max(0, min(1, ((x-ax)*dx+(y-ay)*dy)/(ln*ln)))
            px,py = ax+t*dx, ay+t*dy; dd = math.sqrt((x-px)**2+(y-py)**2)
            w = 2.5 + (1.0 - t) * 1.5
            if dd < w: rv = min(rv, -1.5 * (1.0 - dd/w))
        noise = _fbm(x*0.05, y*0.05, 3, 100) * 1.2
        hills = _fbm(x*0.03, y*0.03, 2, 200) * 2.0
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

    def _build_terrain(self):
        t = mk_terrain('terrain', 200, 72, self._th)
        m = mk_mat((0.25,0.45,0.15,1), 1.0, 0.0)
        np = self._pl(t, 0, 0, 0, self.tx['grass'], m, 'Sharuan Plains', is_platform=False)
        # Tile all texture stages for terrain coverage
        for ts in [TextureStage.get_default()]:
            np.set_tex_scale(ts, 10, 10)
        # Also scale normal and roughness if applied
        children_ts = np.findAllTextureStages()
        for ts in children_ts:
            np.set_tex_scale(ts, 10, 10)

    def _build_sea(self):
        wm = mk_mat((0.15,0.35,0.55,0.85), 0.1, 0.2)
        sea = mk_plane('sea', 200, 60, 4)
        np = self._pl(sea, 0, -80, -1.5, None, wm, 'Southern Sea', is_platform=False)
        np.set_transparency(TransparencyAttrib.M_alpha)
        if self.phys:
            p = gc.Platform()
            p.aabb.min = gc.Vec3(-100, -110, -10)
            p.aabb.max = gc.Vec3(100, -50, -1.5)
            p.isWater = True
            self.phys.addPlatform(p)

    def _build_river(self):
        wm = mk_mat((0.12,0.30,0.50,0.8), 0.15, 0.15)
        for i in range(len(self.RIVER)-1):
            ax,ay = self.RIVER[i]; bx,by = self.RIVER[i+1]
            mx,my = (ax+bx)/2, (ay+by)/2
            dx,dy = bx-ax, by-ay; ln = math.sqrt(dx*dx+dy*dy)
            ang = math.degrees(math.atan2(dx, dy))
            w = 3.0 + i * 0.2
            seg = mk_plane(f'riv{i}', w, ln, 1)
            np = self._pl(seg, mx, my, self._th(mx,my)-0.3, None, wm, 'River Aran', is_platform=False)
            np.set_h(ang)
            np.set_transparency(TransparencyAttrib.M_alpha)
            if self.phys:
                p = gc.Platform()
                p.aabb.min = gc.Vec3(mx-w, my-ln*0.5, -5)
                p.aabb.max = gc.Vec3(mx+w, my+ln*0.5, 0)
                p.isWater = True
                self.phys.addPlatform(p)

    def _build_castle(self):
        sm = mk_mat((0.6,0.58,0.55,1), 0.9, 0.05)
        cx, cy = 0, 65; bz = self._th(cx, cy)
        self._pl(mk_box('keep',6,6,10), cx,cy, bz+4.5, self.tx['stone'], sm, 'Castle Keep')
        for tx,ty in [(-5,-5),(5,-5),(-5,5),(5,5)]:
            tz = self._th(cx+tx, cy+ty)
            self._pl(mk_cyl('tw',1.8,12,16), cx+tx,cy+ty, tz+5.5, self.tx['stone'], sm, 'Guard Tower')

    def _build_city_wall(self):
        sm = mk_mat((0.50,0.47,0.43,1), 0.9, 0.05)
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
            self._pl(
                mk_box(f"house_{idx}", width, depth, height),
                x, y, base_z + height * 0.5,
                self.tx["stone"], wall_mat, "City District"
            )
            self._pl(
                mk_cone(f"roof_{idx}", max(width, depth) * 0.45, 2.6, 10),
                x, y, base_z + height + 1.0,
                self.tx["roof"], roof_mat, "City District", is_platform=False
            )

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

    def _build_movement_training_ground(self):
        """Dedicated test arena for movement tutorial and animation state validation."""
        tx, ty = 18.0, 24.0
        center_z = self._th(tx, ty)
        stone_mat = mk_mat((0.52, 0.49, 0.45, 1.0), 0.72, 0.02)
        dirt_mat = mk_mat((0.42, 0.35, 0.26, 1.0), 0.88, 0.0)
        water_mat = mk_mat((0.12, 0.30, 0.50, 0.82), 0.15, 0.18)

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

        for idx, (x, y) in enumerate(tree_positions[:36]):
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
