"""Helpers to stabilize model appearance under PBR shaders."""

from panda3d.core import LColor, Material, PNMImage, Texture, TextureStage

from utils.logger import logger

try:
    import complexpbr
except Exception:
    complexpbr = None

_WHITE_TEX = None
_DEFAULT_MATERIAL = None


def _call(node, snake_name, camel_name, *args, **kwargs):
    fn = getattr(node, snake_name, None)
    if not callable(fn):
        fn = getattr(node, camel_name, None)
    if not callable(fn):
        raise AttributeError(f"{snake_name}/{camel_name} not found on {type(node)}")
    return fn(*args, **kwargs)


def _white_texture():
    global _WHITE_TEX
    if _WHITE_TEX is not None:
        return _WHITE_TEX

    img = PNMImage(1, 1)
    img.set_xel(0, 0, 1.0, 1.0, 1.0)
    img.add_alpha()
    img.set_alpha(0, 0, 1.0)

    tex = Texture("fallback_white")
    tex.load(img)
    _WHITE_TEX = tex
    return _WHITE_TEX


def _default_material():
    global _DEFAULT_MATERIAL
    if _DEFAULT_MATERIAL is not None:
        return _DEFAULT_MATERIAL

    mat = Material("fallback_model_material")
    mat.set_base_color(LColor(0.86, 0.84, 0.80, 1.0))
    mat.set_roughness(0.68)
    mat.set_metallic(0.0)
    _DEFAULT_MATERIAL = mat
    return _DEFAULT_MATERIAL


def _apply_common_shader_inputs(node):
    defaults = {
        "displacement_scale": 0.0,
        "displacement_map": Texture(),
        "ao": 1.0,
        "shadow_boost": 0.0,
        "specular_factor": 1.0,
        "roughness": 0.62,
        "metallic": 0.0,
    }
    for key, value in defaults.items():
        try:
            _call(node, "set_shader_input", "setShaderInput", key, value, priority=1000)
        except Exception:
            continue


def _fix_dark_color_scale(target):
    try:
        scale = _call(target, "get_color_scale", "getColorScale")
    except Exception:
        return False

    dark_rgb = min(float(scale[0]), float(scale[1]), float(scale[2]))
    if dark_rgb <= 0.001:
        try:
            _call(target, "clear_color_scale", "clearColorScale")
            return True
        except Exception:
            return False
    if dark_rgb < 0.06:
        try:
            _call(target, "set_color_scale", "setColorScale", 1.0, 1.0, 1.0, float(scale[3]))
            return True
        except Exception:
            return False
    return False


def _ensure_geom_visibility(node):
    white_tex = _white_texture()
    fallback_mat = _default_material()
    patched = 0
    default_stage = TextureStage.get_default()

    geom_nodes = [node]
    try:
        geom_nodes.extend(list(node.find_all_matches("**/+GeomNode")))
    except Exception:
        pass

    for geom_np in geom_nodes:
        if _fix_dark_color_scale(geom_np):
            patched += 1

        try:
            has_tex = bool(_call(geom_np, "has_texture", "hasTexture"))
        except Exception:
            has_tex = False

        if not has_tex:
            try:
                geom_np.setTexture(default_stage, white_tex, 1)
                patched += 1
            except Exception:
                pass

        try:
            has_mat = bool(_call(geom_np, "has_material", "hasMaterial"))
        except Exception:
            has_mat = False

        if not has_mat:
            try:
                geom_np.set_material(fallback_mat, 1)
                patched += 1
            except Exception:
                pass
        else:
            try:
                mat = _call(geom_np, "get_material", "getMaterial")
            except Exception:
                mat = None
            if mat:
                try:
                    bc = _call(mat, "get_base_color", "getBaseColor")
                    dark = max(0.0, min(float(bc[0]), float(bc[1]), float(bc[2])))
                    if dark < 0.06:
                        _call(mat, "set_base_color", "setBaseColor", LColor(0.42, 0.40, 0.38, float(bc[3])))
                        geom_np.set_material(mat, 1)
                        patched += 1
                except Exception:
                    pass

    return patched


def _apply_hardware_skinning(node, debug_label):
    if complexpbr is None or not hasattr(complexpbr, "skin"):
        return False
    try:
        complexpbr.skin(node)
        return True
    except Exception as exc:
        logger.debug(f"[Visuals] complexpbr.skin failed for {debug_label}: {exc}")
        return False


def ensure_model_visual_defaults(
    node,
    *,
    apply_skin=False,
    force_two_sided=False,
    debug_label="model",
):
    """Apply safe visual defaults to reduce black/unlit model cases."""
    if node is None:
        return 0
    try:
        if _call(node, "is_empty", "isEmpty"):
            return 0
    except Exception:
        return 0

    _apply_common_shader_inputs(node)

    if force_two_sided:
        try:
            _call(node, "set_two_sided", "setTwoSided", True)
        except Exception:
            pass

    if apply_skin:
        _apply_hardware_skinning(node, debug_label)

    patched = _ensure_geom_visibility(node)
    if patched > 0:
        logger.debug(f"[Visuals] Applied {patched} fallback visual patches to {debug_label}.")
    return patched
