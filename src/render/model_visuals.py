"""Helpers to stabilize model appearance under PBR shaders."""

import json
from datetime import datetime, timezone
from pathlib import Path

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


def _is_texture_valid(tex):
    if tex is None:
        return False

    is_empty = getattr(tex, "isEmpty", None)
    if callable(is_empty):
        try:
            return not bool(is_empty())
        except Exception:
            pass

    is_empty_snake = getattr(tex, "is_empty", None)
    if callable(is_empty_snake):
        try:
            return not bool(is_empty_snake())
        except Exception:
            pass

    get_x = getattr(tex, "get_x_size", None) or getattr(tex, "getXSize", None)
    get_y = getattr(tex, "get_y_size", None) or getattr(tex, "getYSize", None)
    if callable(get_x) and callable(get_y):
        try:
            return int(get_x()) > 0 and int(get_y()) > 0
        except Exception:
            pass

    # If Panda does not expose empty/size checks on this build,
    # assume texture is valid rather than replacing it aggressively.
    return True


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


def _fix_dark_vertex_color(target):
    has_color = getattr(target, "has_color", None)
    if not callable(has_color):
        has_color = getattr(target, "hasColor", None)
    if callable(has_color):
        try:
            if not bool(has_color()):
                return False
        except Exception:
            pass

    try:
        color = _call(target, "get_color", "getColor")
    except Exception:
        return False

    dark_rgb = min(float(color[0]), float(color[1]), float(color[2]))
    if dark_rgb < 0.04:
        try:
            _call(target, "set_color", "setColor", 1.0, 1.0, 1.0, float(color[3]))
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
        _apply_common_shader_inputs(geom_np)

        if _fix_dark_color_scale(geom_np):
            patched += 1
        if _fix_dark_vertex_color(geom_np):
            patched += 1

        try:
            has_tex = bool(_call(geom_np, "has_texture", "hasTexture"))
        except Exception:
            has_tex = False

        default_tex = None
        try:
            default_tex = geom_np.getTexture(default_stage)
        except Exception:
            default_tex = None
        has_default_tex = _is_texture_valid(default_tex)

        if not has_tex or not has_default_tex:
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
                        _call(mat, "set_base_color", "setBaseColor", LColor(0.62, 0.60, 0.58, float(bc[3])))
                        geom_np.set_material(mat, 1)
                        patched += 1
                except Exception:
                    pass

    return patched


def _fix_dark_hierarchy(node):
    patched = 0
    all_nodes = [node]
    try:
        all_nodes.extend(list(node.find_all_matches("**")))
    except Exception:
        pass

    for np in all_nodes:
        if _fix_dark_color_scale(np):
            patched += 1
        if _fix_dark_vertex_color(np):
            patched += 1
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

    patched = 0
    patched += _fix_dark_hierarchy(node)
    try:
        patched += _ensure_geom_visibility(node)
    except Exception as exc:
        logger.warning(f"[Visuals] Failed to enforce geom visibility for {debug_label}: {exc}")
    if patched > 0:
        logger.debug(f"[Visuals] Applied {patched} fallback visual patches to {debug_label}.")
    return patched


def audit_node_visual_health(node, *, max_nodes=2500, report_path="logs/scene_visual_audit.json", debug_label="scene"):
    """Collect lightweight visual diagnostics for black/unlit model hunting."""
    if node is None:
        return {"ok": False, "reason": "node_none"}
    issues = {
        "dark_color_scale": [],
        "missing_texture": [],
        "missing_material": [],
    }
    scanned = 0

    try:
        matches = list(node.find_all_matches("**/+GeomNode"))
    except Exception:
        matches = []

    for geom_np in matches:
        scanned += 1
        if scanned > int(max_nodes):
            break
        node_name = ""
        try:
            node_name = geom_np.get_name()
        except Exception:
            node_name = f"geom_{scanned}"

        try:
            color_scale = _call(geom_np, "get_color_scale", "getColorScale")
            dark_rgb = min(float(color_scale[0]), float(color_scale[1]), float(color_scale[2]))
            if dark_rgb < 0.05:
                issues["dark_color_scale"].append(node_name)
        except Exception:
            pass

        has_texture = False
        try:
            has_texture = bool(_call(geom_np, "has_texture", "hasTexture"))
        except Exception:
            has_texture = False
        if not has_texture:
            issues["missing_texture"].append(node_name)

        has_material = False
        try:
            has_material = bool(_call(geom_np, "has_material", "hasMaterial"))
        except Exception:
            has_material = False
        if not has_material:
            issues["missing_material"].append(node_name)

    summary = {
        "label": str(debug_label),
        "scanned_geom_nodes": int(scanned),
        "issues": {
            "dark_color_scale": len(issues["dark_color_scale"]),
            "missing_texture": len(issues["missing_texture"]),
            "missing_material": len(issues["missing_material"]),
        },
        "samples": {
            "dark_color_scale": issues["dark_color_scale"][:60],
            "missing_texture": issues["missing_texture"][:60],
            "missing_material": issues["missing_material"][:60],
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    try:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug(f"[Visuals] Failed to write audit report '{report_path}': {exc}")

    logger.info(
        "[Visuals] Audit '%s': scanned=%d dark=%d missing_tex=%d missing_mat=%d",
        debug_label,
        summary["scanned_geom_nodes"],
        summary["issues"]["dark_color_scale"],
        summary["issues"]["missing_texture"],
        summary["issues"]["missing_material"],
    )
    return summary
