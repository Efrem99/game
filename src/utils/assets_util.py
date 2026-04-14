import math
import os
from panda3d.core import PNMImage, Texture, SamplerState

def _noise(x, y, s=0):
    n = int(x * 73 + y * 179 + s * 31) & 0xFFFF
    n = (n << 13) ^ n
    return 1.0 - ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7FFFFFFF) / 1073741824.0

def _snoise(x, y, s=0):
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    a, b = _noise(ix, iy, s), _noise(ix+1, iy, s)
    c, d = _noise(ix, iy+1, s), _noise(ix+1, iy+1, s)
    return a + fx*(b-a) + fy*(c-a) + fx*fy*(a-b-c+d)

def _fbm(x, y, oct=4, s=0):
    v, a, f = 0.0, 1.0, 1.0
    for _ in range(oct):
        v += _snoise(x*f, y*f, s)*a; a *= 0.5; f *= 2.0
    return v

def _clamp(v): return max(0.0, min(1.0, v))

def make_tex(name, sz, fn, anisotropy=4):
    """
    Creates a texture procedurally. Uses a disk cache in cache/panda3d/procedural
    to avoid expensive Python pixel loops on subsequent launches.
    """
    cache_dir = os.path.join("cache", "panda3d", "procedural")
    try:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{name}_{sz}.png")
    except Exception:
        cache_path = None

    img = PNMImage(sz, sz)
    loaded_from_cache = False
    
    if cache_path and os.path.exists(cache_path):
        try:
            if img.read(cache_path):
                loaded_from_cache = True
        except Exception:
            pass

    if not loaded_from_cache:
        for py in range(sz):
            for px in range(sz):
                r, g, b = fn(px/sz, py/sz)
                img.set_xel(px, py, _clamp(r), _clamp(g), _clamp(b))
        if cache_path:
            try:
                img.write(cache_path)
            except Exception:
                pass

    t = Texture(name)
    t.load(img)
    t.set_wrap_u(SamplerState.WM_repeat)
    t.set_wrap_v(SamplerState.WM_repeat)
    t.set_minfilter(SamplerState.FT_linear_mipmap_linear)
    t.set_magfilter(SamplerState.FT_linear)
    try:
        aniso = max(1, min(16, int(anisotropy or 4)))
    except Exception:
        aniso = 4
    t.set_anisotropic_degree(aniso)
    return t

def make_pbr_tex_set(name, sz, albedo_fn, normal_fn=None, rough_fn=None, anisotropy=4):
    albedo = make_tex(f"{name}_albedo", sz, albedo_fn, anisotropy=anisotropy)
    if normal_fn:
        norm = make_tex(f"{name}_normal", sz, normal_fn, anisotropy=anisotropy)
    else:
        norm = make_tex(f"{name}_normal", sz, lambda u,v: (0.5, 0.5, 1.0), anisotropy=anisotropy)
    if rough_fn:
        rough = make_tex(f"{name}_rough", sz, rough_fn, anisotropy=anisotropy)
    else:
        rough = make_tex(f"{name}_rough", sz, lambda u,v: (0.8, 0.8, 0.8), anisotropy=anisotropy)
    return {"albedo": albedo, "normal": norm, "rough": rough}
