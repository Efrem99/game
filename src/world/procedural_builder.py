"""Procedural geometry builders extracted for clean architecture."""
import math
from panda3d.core import (
    GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomVertexRewriter,
    GeomTriangles, Geom, GeomNode, Material, LColor
)

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

class DataHeightmap:
    """Storage for grid-based height data to support sculpting."""
    def __init__(self, size, res, data=None):
        self.size = size
        self.res = res
        self.grid = data if data else [[0.0 for _ in range(res + 1)] for _ in range(res + 1)]

    def get_height(self, x, y):
        hs = self.size / 2
        ix = (x + hs) / (self.size / self.res)
        iy = (y + hs) / (self.size / self.res)
        idx_x = max(0, min(self.res, int(ix)))
        idx_y = max(0, min(self.res, int(iy)))
        return self.grid[idx_y][idx_x]

    def set_height(self, x, y, val):
        hs = self.size / 2
        ix = (x + hs) / (self.size / self.res)
        iy = (y + hs) / (self.size / self.res)
        idx_x = max(0, min(self.res, int(ix)))
        idx_y = max(0, min(self.res, int(iy)))
        self.grid[idx_y][idx_x] = val

def mk_terrain(nm, sz, res, hfn, data_heightmap=None):
    fmt = GeomVertexFormat.get_v3n3t2()
    vd = GeomVertexData(nm, fmt, Geom.UH_static)
    vw, nw, tw = GeomVertexWriter(vd,'vertex'), GeomVertexWriter(vd,'normal'), GeomVertexWriter(vd,'texcoord')
    tr = GeomTriangles(Geom.UH_static)
    hs=sz/2; step=sz/res; heights=[]
    for iy in range(res+1):
        row=[]
        for ix in range(res+1):
            x,y = -hs+ix*step, -hs+iy*step
            z = data_heightmap.grid[iy][ix] if data_heightmap else hfn(x,y)
            row.append(z)
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
    c = list(bc)
    while len(c) < 4:
        c.append(1.0)
    m=Material(); m.set_base_color(LColor(*c)); m.set_roughness(rough); m.set_metallic(metal); return m

def sample_polyline_points(points, spacing=3.0):
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
        if not out:
            out.append((ax, ay))
            last = (ax, ay)
        seg_dist = 0.0
        while seg_dist + step <= ln:
            seg_dist += step
            t = seg_dist / ln
            nx = ax + dx * t
            ny = ay + dy * t
            out.append((nx, ny))
            last = (nx, ny)
        rem = ln - seg_dist
        if last is not None:
            ldx = bx - last[0]; ldy = by - last[1]
            if math.sqrt((ldx * ldx) + (ldy * ldy)) > step * 0.5:
                out.append((bx, by))
                last = (bx, by)
    return out

def update_terrain_mesh(node, sz, res, data_heightmap):
    """Updates an existing terrain mesh vertex data from a heightmap."""
    if not node or not data_heightmap: return
    geom = node.get_geom(0)
    vdata = geom.modify_vertex_data()
    vw = GeomVertexRewriter(vdata, 'vertex')
    nw = GeomVertexRewriter(vdata, 'normal')
    
    step = sz / res
    hs = sz / 2
    grid = data_heightmap.grid

    # Update Positions
    for iy in range(res + 1):
        for ix in range(res + 1):
            vw.set_row(iy * (res + 1) + ix)
            x, y = -hs + ix * step, -hs + iy * step
            vw.set_data3(x, y, grid[iy][ix])

    # Update Normals
    for iy in range(res + 1):
        for ix in range(res + 1):
            nw.set_row(iy * (res + 1) + ix)
            zl = grid[iy][max(0, ix - 1)]
            zr = grid[iy][min(res, ix + 1)]
            zd = grid[max(0, iy - 1)][ix]
            zu = grid[min(res, iy + 1)][ix]
            nx, ny, nz = (zl - zr) / (2 * step), (zd - zu) / (2 * step), 1.0
            ln = math.sqrt(nx * nx + ny * ny + nz * nz)
            nw.set_data3(nx / ln, ny / ln, nz / ln)
