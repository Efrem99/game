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

from utils.core_runtime import gc, HAS_CORE
from direct.showbase.ShowBaseGlobal import globalClock
from .procedural_builder import (
    mk_box, mk_cyl, mk_cone, mk_sphere, mk_plane, mk_terrain, mk_mat, 
    sample_polyline_points, DataHeightmap, update_terrain_mesh
)
from panda3d.core import (
    Vec3, LColor, CardMaker,
    GeomNode, Geom, GeomTriangles, GeomVertexFormat,
    GeomVertexData, GeomVertexWriter, GeomVertexRewriter,
    TransparencyAttrib, Texture, TextureStage, Material, Shader, PointLight, SamplerState, PNMImage
)

from utils.assets_util import _fbm, make_pbr_tex_set
from utils.asset_pathing import prefer_bam_path
from utils.logger import logger
from render.fx_policy import load_optional_texture, make_soft_disc_texture
from render.model_visuals import ensure_model_visual_defaults
from .location_meshes import normalize_location_mesh_entries
from managers.runtime_data_access import load_data_file


TRAINING_GROUNDS_CENTER = (18.0, 24.0)
TRAINING_GROUNDS_RADIUS = 30.0
TRAINING_PLAZA_HALF_EXTENTS = (24.0, 17.0)
# Keep the swim probe visibly separate from the brown training-plaza placeholder lane.
TRAINING_POOL_CENTER = (6.0, 46.0)
TRAINING_POOL_HALF_EXTENTS = (5.5, 4.0)
TRAINING_POOL_SURFACE_OFFSET = 1.1
TRAINING_POOL_PLAYER_Z_OFFSET = 0.95


def should_enable_world_shader(has_core, env=None):
    """
    Keep world lighting shader enabled by default for stable visuals.
    Explicit env switches still allow forcing on/off for diagnostics.
    """
    env_map = os.environ if env is None else env
    force = str(env_map.get("XBOT_FORCE_WORLD_SHADER", "0") or "").strip().lower()
    if force in {"1", "true", "yes", "on"}:
        return True
    disable = str(env_map.get("XBOT_DISABLE_WORLD_SHADER", "0") or "").strip().lower()
    if disable in {"1", "true", "yes", "on"}:
        return False
    return True


def should_batch_location_meshes(entry_count, enabled=True, min_count=3):
    if not bool(enabled):
        return False
    try:
        count = max(0, int(entry_count))
    except Exception:
        count = 0
    try:
        threshold = max(1, int(min_count))
    except Exception:
        threshold = 3
    return count >= threshold


def should_hide_location_mesh_by_distance(
    distance,
    currently_hidden,
    cull_distance=170.0,
    hysteresis=18.0,
):
    try:
        dist = max(0.0, float(distance))
    except Exception:
        dist = 0.0
    try:
        cutoff = max(5.0, float(cull_distance))
    except Exception:
        cutoff = 170.0
    try:
        hyst = max(0.0, float(hysteresis))
    except Exception:
        hyst = 18.0
    half = hyst * 0.5
    hide_threshold = cutoff + half
    show_threshold = max(0.0, cutoff - half)
    if bool(currently_hidden):
        return dist > show_threshold
    return dist > hide_threshold


def should_use_location_mesh_hlod(
    distance,
    currently_using_hlod,
    hlod_distance=110.0,
    hysteresis=24.0,
):
    try:
        dist = max(0.0, float(distance))
    except Exception:
        dist = 0.0
    try:
        cutoff = max(15.0, float(hlod_distance))
    except Exception:
        cutoff = 110.0
    try:
        hyst = max(0.0, float(hysteresis))
    except Exception:
        hyst = 24.0
    half = hyst * 0.5
    enter_threshold = cutoff + half
    exit_threshold = max(0.0, cutoff - half)
    if bool(currently_using_hlod):
        return dist > exit_threshold
    return dist > enter_threshold


def _normalize_location_token(token):
    raw = str(token or "").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")


def resolve_ultimate_sandbox_features(token):
    default = {"sun", "traversal", "water", "vfx", "scenery", "stairs", "story", "npcs"}
    raw = str(token or "").strip().lower()
    if raw in {"", "full", "all", "default"}:
        return set(default)
    if raw in {"minimal", "base", "base_only"}:
        return set()
    out = set()
    for part in raw.replace(";", ",").split(","):
        item = str(part or "").strip().lower()
        if item:
            out.add(item)
    return out


def build_training_flight_gate_plan(training_center=TRAINING_GROUNDS_CENTER):
    try:
        tx = float(training_center[0])
        ty = float(training_center[1])
    except Exception:
        tx, ty = TRAINING_GROUNDS_CENTER
    fl_x = tx - 23.0
    fl_y = ty - 1.0
    gate_specs = [
        (fl_x + 5.0, fl_y + 10.0, 7.2, 1.6),
        (fl_x + 12.0, fl_y + 18.0, 10.4, 2.0),
        (fl_x + 20.0, fl_y + 13.0, 8.8, 1.8),
    ]
    rows = []
    for idx, (gx, gy, gz, radius) in enumerate(gate_specs):
        opening_half_w = max(1.4, radius * 1.05)
        opening_half_h = max(1.8, radius * 1.10)
        post_w = 0.42
        beam_h = 0.34
        rows.extend(
            [
                {
                    "id": f"flight_gate_{idx}_left_post",
                    "shape": "box",
                    "size": (post_w, 0.42, (opening_half_h * 2.0) + beam_h),
                    "pos": (gx - opening_half_w - (post_w * 0.5), gy, gz),
                    "material": "wood",
                },
                {
                    "id": f"flight_gate_{idx}_right_post",
                    "shape": "box",
                    "size": (post_w, 0.42, (opening_half_h * 2.0) + beam_h),
                    "pos": (gx + opening_half_w + (post_w * 0.5), gy, gz),
                    "material": "wood",
                },
                {
                    "id": f"flight_gate_{idx}_top_beam",
                    "shape": "box",
                    "size": ((opening_half_w * 2.0) + (post_w * 2.0), 0.48, beam_h),
                    "pos": (gx, gy, gz + opening_half_h + (beam_h * 0.5)),
                    "material": "accent",
                },
            ]
        )
    return rows


def resolve_location_mesh_cull_profile(
    active_location,
    base_distance=170.0,
    base_hysteresis=18.0,
    base_interval=0.25,
    profiles=None,
):
    try:
        distance = max(20.0, float(base_distance))
    except Exception:
        distance = 170.0
    try:
        hysteresis = max(0.0, float(base_hysteresis))
    except Exception:
        hysteresis = 18.0
    try:
        interval = max(0.05, float(base_interval))
    except Exception:
        interval = 0.25

    rows = profiles if isinstance(profiles, dict) else {}
    loc_key = _normalize_location_token(active_location)
    row = rows.get(loc_key, {}) if loc_key else {}
    if not isinstance(row, dict):
        row = {}

    if "distance" in row:
        try:
            distance = max(20.0, float(row.get("distance")))
        except Exception:
            pass
    if "hysteresis" in row:
        try:
            hysteresis = max(0.0, float(row.get("hysteresis")))
        except Exception:
            pass
    if "interval" in row:
        try:
            interval = max(0.05, float(row.get("interval")))
        except Exception:
            pass

    return {
        "distance": float(distance),
        "hysteresis": float(hysteresis),
        "interval": float(interval),
    }


def resolve_location_mesh_hlod_profile(
    active_location,
    enabled=True,
    base_distance=110.0,
    base_hysteresis=24.0,
    profiles=None,
):
    hlod_enabled = bool(enabled)
    try:
        distance = max(15.0, float(base_distance))
    except Exception:
        distance = 110.0
    try:
        hysteresis = max(0.0, float(base_hysteresis))
    except Exception:
        hysteresis = 24.0

    rows = profiles if isinstance(profiles, dict) else {}
    loc_key = _normalize_location_token(active_location)
    row = rows.get(loc_key, {}) if loc_key else {}
    if not isinstance(row, dict):
        row = {}

    if "enabled" in row:
        hlod_enabled = bool(row.get("enabled"))
    if "distance" in row:
        try:
            distance = max(15.0, float(row.get("distance")))
        except Exception:
            pass
    if "hysteresis" in row:
        try:
            hysteresis = max(0.0, float(row.get("hysteresis")))
        except Exception:
            pass
    return {
        "enabled": bool(hlod_enabled),
        "distance": float(distance),
        "hysteresis": float(hysteresis),
    }


def resolve_world_model_perf_profile(model_path, loc_name=""):
    token = str(model_path or "").strip().replace("\\", "/").lower()
    loc_token = str(loc_name or "").strip().lower()
    if not token:
        return {
            "family": "",
            "cull_distance": 0.0,
            "hysteresis": 0.0,
            "lod_profile": "",
            "lod_stage": "",
            "hi_res_candidate": False,
        }
    if any(marker in token for marker in ("tree_stump", "stump")):
        return {
            "family": "stump",
            "cull_distance": 110.0,
            "hysteresis": 16.0,
            "lod_profile": "stump_low",
            "lod_stage": "low",
            "hi_res_candidate": False,
        }
    if any(marker in token for marker in ("tree", "pine_", "oak_", "birch_", "willow_")):
        return {
            "family": "tree",
            "cull_distance": 155.0 if "wild grove" in loc_token else 145.0,
            "hysteresis": 20.0,
            "lod_profile": "tree_placeholder",
            "lod_stage": "low",
            "hi_res_candidate": True,
        }
    if any(marker in token for marker in ("bush", "plant", "fern", "shrub")):
        return {
            "family": "foliage",
            "cull_distance": 96.0,
            "hysteresis": 14.0,
            "lod_profile": "foliage_placeholder",
            "lod_stage": "low",
            "hi_res_candidate": True,
        }
    return {
        "family": "",
        "cull_distance": 0.0,
        "hysteresis": 0.0,
        "lod_profile": "",
        "lod_stage": "",
        "hi_res_candidate": False,
    }


def _as_xyz_tuple(value):
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        try:
            return (float(value.x), float(value.y), float(value.z))
        except Exception:
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            return None
    return None


def normalize_location_door_entries(rows):
    payload = rows if isinstance(rows, list) else []
    out = []
    for idx, row in enumerate(payload):
        if not isinstance(row, dict):
            continue
        center = _as_xyz_tuple(row.get("center", row.get("pos")))
        if center is None:
            continue
        target_name = str(row.get("to", row.get("target", row.get("location", ""))) or "").strip()
        if not target_name:
            continue
        source_name = str(row.get("from", row.get("source", "")) or "").strip()
        try:
            radius = max(0.6, float(row.get("radius", 2.2) or 2.2))
        except Exception:
            radius = 2.2
        door_id = str(row.get("id", f"door_{idx}") or f"door_{idx}").strip().lower()
        if not door_id:
            door_id = f"door_{idx}"
        model_path = str(row.get("model", "") or "").strip().replace("\\", "/")
        try:
            heading = float(row.get("heading", row.get("h", 0.0)) or 0.0)
        except Exception:
            heading = 0.0
        try:
            door_scale = max(0.1, float(row.get("scale", 1.0) or 1.0))
        except Exception:
            door_scale = 1.0
        out.append(
            {
                "id": door_id,
                "from": source_name,
                "to": target_name,
                "from_token": _normalize_location_token(source_name),
                "to_token": _normalize_location_token(target_name),
                "center": center,
                "radius": float(radius),
                "model": model_path,
                "heading": float(heading),
                "scale": float(door_scale),
            }
        )
    return out


def resolve_location_door_transition(player_pos, active_location, door_rows):
    pos = _as_xyz_tuple(player_pos)
    if pos is None:
        return None
    active_token = _normalize_location_token(active_location)
    rows = door_rows if isinstance(door_rows, list) else []
    best = None
    best_dist_sq = None
    px, py, pz = pos
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_token = str(row.get("from_token", "") or "").strip().lower()
        if source_token and source_token != active_token:
            continue
        center = _as_xyz_tuple(row.get("center"))
        if center is None:
            continue
        cx, cy, cz = center
        radius = max(0.6, float(row.get("radius", 2.2) or 2.2))
        dx = px - cx
        dy = py - cy
        dz = pz - cz
        dist_sq = (dx * dx) + (dy * dy) + (dz * dz)
        if dist_sq > (radius * radius):
            continue
        if best is None or best_dist_sq is None or dist_sq < best_dist_sq:
            best = row
            best_dist_sq = dist_sq
    return best

# ─── Mesh builders ─────────────────────────────────────────────────
def build_castle_interior_prop_plan(room_id):
    token = str(room_id or "").strip().lower()
    if token == "prince_chamber":
        return [
            {"id": "room_rug", "kind": "box", "size": (3.4, 2.2, 0.10), "pos": (0.0, 0.2, 0.06), "tex": "roof", "mat": "trim"},
            {"id": "bed_frame", "kind": "box", "size": (2.6, 1.4, 0.52), "pos": (-2.0, 1.6, 0.28), "tex": "bark", "mat": "trim"},
            {"id": "bed_headboard", "kind": "box", "size": (2.6, 0.22, 1.1), "pos": (-2.0, 2.28, 0.76), "tex": "bark", "mat": "wall"},
            {"id": "writing_desk", "kind": "box", "size": (1.8, 0.9, 0.82), "pos": (2.1, 1.8, 0.44), "tex": "bark", "mat": "trim"},
            {"id": "wardrobe", "kind": "box", "size": (1.3, 0.8, 2.05), "pos": (2.4, -1.7, 1.06), "tex": "bark", "mat": "wall"},
        ]
    if token == "world_map_gallery":
        return [
            {"id": "room_rug", "kind": "box", "size": (3.8, 2.4, 0.10), "pos": (0.0, 0.0, 0.06), "tex": "roof", "mat": "trim"},
            {"id": "map_table", "kind": "box", "size": (2.9, 1.7, 0.76), "pos": (0.0, 0.8, 0.40), "tex": "bark", "mat": "trim"},
            {"id": "map_wall_frame_l", "kind": "plane", "size": (2.4, 1.4), "pos": (-3.7, 0.6, 2.1), "tex": "dirt", "mat": "gold", "h": 90.0},
            {"id": "map_wall_frame_r", "kind": "plane", "size": (2.4, 1.4), "pos": (3.7, 0.6, 2.1), "tex": "dirt", "mat": "gold", "h": -90.0},
            {"id": "scroll_shelf", "kind": "box", "size": (2.4, 0.6, 1.9), "pos": (0.0, -2.2, 1.0), "tex": "bark", "mat": "wall"},
        ]
    if token == "royal_laundry":
        return [
            {"id": "linen_rack_l", "kind": "box", "size": (1.8, 0.7, 1.8), "pos": (-2.1, 1.6, 0.95), "tex": "bark", "mat": "wall"},
            {"id": "linen_rack_r", "kind": "box", "size": (1.8, 0.7, 1.8), "pos": (2.1, 1.6, 0.95), "tex": "bark", "mat": "wall"},
            {"id": "wash_table", "kind": "box", "size": (2.6, 1.2, 0.86), "pos": (0.0, -0.6, 0.45), "tex": "stone", "mat": "floor"},
            {"id": "wash_basin", "kind": "cyl", "size": (0.42, 0.24, 12), "pos": (0.0, -0.6, 0.98), "tex": "stone", "mat": "trim"},
            {"id": "soap_bucket", "kind": "cyl", "size": (0.22, 0.34, 10), "pos": (1.4, -1.9, 0.20), "tex": "stone", "mat": "trim"},
        ]
    if token == "throne_hall":
        return [
            {"id": "carpet_run", "kind": "box", "size": (3.1, 7.6, 0.12), "pos": (0.0, 0.9, 0.07), "tex": "roof", "mat": "gold"},
            {"id": "chandelier_ring", "kind": "cyl", "size": (1.45, 0.16, 16), "pos": (0.0, 0.4, 4.65), "tex": "stone", "mat": "gold"},
            {"id": "guest_bench_l", "kind": "box", "size": (2.8, 0.8, 0.86), "pos": (-3.9, -1.8, 0.46), "tex": "bark", "mat": "trim"},
            {"id": "guest_bench_r", "kind": "box", "size": (2.8, 0.8, 0.86), "pos": (3.9, -1.8, 0.46), "tex": "bark", "mat": "trim"},
            {"id": "banner_l", "kind": "plane", "size": (1.2, 2.3), "pos": (-5.2, 2.6, 2.9), "tex": "roof", "mat": "gold", "h": 90.0},
            {"id": "banner_r", "kind": "plane", "size": (1.2, 2.3), "pos": (5.2, 2.6, 2.9), "tex": "roof", "mat": "gold", "h": -90.0},
        ]
    return []



def _rotate_xy(x, y, heading_deg):
    angle = math.radians(float(heading_deg))
    ca = math.cos(angle)
    sa = math.sin(angle)
    return (float(x) * ca) - (float(y) * sa), (float(x) * sa) + (float(y) * ca)


def make_grass_tuft_spec(rng, x, y, z):
    """Build a deterministic tuft descriptor for batch grass generation."""
    stream = rng if hasattr(rng, "uniform") else random.Random()
    return {
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "tint": float(stream.uniform(0.88, 1.06)),
        "blade_h": float(stream.uniform(1.2, 2.3)),
        "blade_w": float(stream.uniform(0.48, 0.76)),
        "heading": float(stream.uniform(-180.0, 180.0)),
        "tip_scale": float(stream.uniform(0.22, 0.52)),
        "lean": float(stream.uniform(0.02, 0.24)),
        "lean_heading": float(stream.uniform(-180.0, 180.0)),
        "stiffness": float(stream.uniform(0.60, 1.00)),
    }


def estimate_grass_tuft_count(radius, density_scale=1.0, quality="medium", max_budget=1600):
    """Estimate tuft count for circular grass patches with a quality-aware budget cap."""
    try:
        zone_radius = max(0.0, float(radius))
    except Exception:
        zone_radius = 0.0
    try:
        density = max(0.1, float(density_scale))
    except Exception:
        density = 1.0
    token = str(quality or "medium").strip().lower()
    quality_mult = {
        "low": 0.60,
        "medium": 0.95,
        "high": 1.30,
        "ultra": 1.75,
    }.get(token, 0.95)
    area = math.pi * zone_radius * zone_radius
    estimate = int(area * 0.045 * density * quality_mult)
    estimate = max(16, estimate)
    return min(int(max_budget), estimate)


def compose_grass_batch_rows(spec_rows):
    """Compose crossed-card grass rows (vertices) and triangle indices."""
    rows = []
    triangles = []

    def add_card(px, py, pz, half_w, blade_h, heading_deg, tint, stiffness, tip_scale, lean, lean_heading):
        base_index = len(rows)
        hx, hy = _rotate_xy(half_w, 0.0, heading_deg)
        top_half_w = max(0.01, half_w * max(0.05, float(tip_scale)))
        thx, thy = _rotate_xy(top_half_w, 0.0, heading_deg)
        lx, ly = _rotate_xy(float(lean), 0.0, lean_heading)
        nx, ny = _rotate_xy(0.0, -1.0, heading_deg)
        normal = (float(nx), float(ny), 0.0)
        color = (float(tint), float(tint), float(tint), float(stiffness))

        # Order is BL, BR, TR, TL so index layout stays stable for tests and batching.
        vertices = (
            (float(px - hx), float(py - hy), float(pz)),
            (float(px + hx), float(py + hy), float(pz)),
            (float(px + thx + lx), float(py + thy + ly), float(pz + blade_h)),
            (float(px - thx + lx), float(py - thy + ly), float(pz + blade_h)),
        )
        uvs = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        for vertex, uv in zip(vertices, uvs):
            rows.append(
                {
                    "vertex": tuple(float(v) for v in vertex),
                    "normal": normal,
                    "color": color,
                    "uv": uv,
                }
            )

        triangles.append((base_index + 0, base_index + 1, base_index + 2))
        triangles.append((base_index + 0, base_index + 2, base_index + 3))

    for row in (spec_rows if isinstance(spec_rows, list) else []):
        if not isinstance(row, dict):
            continue
        try:
            px = float(row.get("x", 0.0) or 0.0)
            py = float(row.get("y", 0.0) or 0.0)
            pz = float(row.get("z", 0.0) or 0.0)
            blade_h = max(0.01, float(row.get("blade_h", 1.2) or 1.2))
            blade_w = max(0.01, float(row.get("blade_w", 0.6) or 0.6))
            heading = float(row.get("heading", 0.0) or 0.0)
            tint = float(row.get("tint", 1.0) or 1.0)
            stiffness = float(row.get("stiffness", 0.8) or 0.8)
            tip_scale = max(0.05, float(row.get("tip_scale", 0.34) or 0.34))
            lean = float(row.get("lean", 0.0) or 0.0)
            lean_heading = float(row.get("lean_heading", heading) or heading)
        except Exception:
            continue

        half_w = blade_w * 0.5
        add_card(px, py, pz, half_w, blade_h, heading, tint, stiffness, tip_scale, lean, lean_heading)
        add_card(px, py, pz, half_w, blade_h, heading + 90.0, tint, stiffness, tip_scale, lean, lean_heading)

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
        self.world_type = "overworld" # Default
        if not isinstance(self.layout, dict):
            self.layout = {}

        terrain_cfg = self.layout.get("terrain", {}) if isinstance(self.layout.get("terrain"), dict) else {}
        self.terrain_size = float(terrain_cfg.get("size", 200.0) or 200.0)
        self.terrain_res = int(terrain_cfg.get("resolution", 72) or 72)
        self.castle_hill_cfg = terrain_cfg.get("castle_hill", {}) if isinstance(terrain_cfg.get("castle_hill"), dict) else {}
        self.sea_cfg = terrain_cfg.get("sea", {}) if isinstance(terrain_cfg.get("sea"), dict) else {}
        self.hills_cfg = terrain_cfg.get("hills", {}) if isinstance(terrain_cfg.get("hills"), dict) else {}
        self.river_cfg = self.layout.get("river", {}) if isinstance(self.layout.get("river"), dict) else {}
        # Level Editor 2.0 State (SQLite + Msgpack)
        self.terrain_data = DataHeightmap(self.terrain_size, self.terrain_res)
        for iy in range(self.terrain_res + 1):
            for ix in range(self.terrain_res + 1):
                px = -self.terrain_size / 2 + ix * (self.terrain_size / self.terrain_res)
                py = -self.terrain_size / 2 + iy * (self.terrain_size / self.terrain_res)
                self.terrain_data.grid[iy][ix] = self._th(px, py)
        self._terrain_node = None
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
        self._location_doors = normalize_location_door_entries(
            self.layout.get("location_doors", [])
        )
        self._door_controlled_location_tokens = set()
        for row in self._location_doors:
            if not isinstance(row, dict):
                continue
            source_token = str(row.get("from_token", "") or "").strip().lower()
            target_token = str(row.get("to_token", "") or "").strip().lower()
            if source_token:
                self._door_controlled_location_tokens.add(source_token)
            if target_token:
                self._door_controlled_location_tokens.add(target_token)
        self._active_door_overlap = ""
        self.active_location = None
        self.colliders = [] # Python-only fallback AABB list
        self._water_surfaces = []
        self._ambient_fire_props = []
        self._ambient_fire_tex = None
        self._castle_lights = []
        # Stable RNG for procedural decoration jitter (grass, decals, micro-variation).
        self._rng = random.Random(20260308)
        self._chest_nodes = []
        self._location_mesh_nodes = []
        self._location_mesh_cluster_nodes = {}
        self._location_mesh_cluster_centers = {}
        self._location_mesh_cluster_modes = {}
        self._location_mesh_hlod_roots = {}
        self._terrain_shader_targets = []
        self._terrain_shader_cursed_blend = 0.0
        perf_cfg = (
            self.layout.get("performance", {})
            if isinstance(self.layout.get("performance"), dict)
            else {}
        )
        self._batch_location_meshes_enabled = bool(perf_cfg.get("batch_location_meshes", True))
        try:
            self._batch_location_meshes_min_count = max(
                1, int(perf_cfg.get("batch_location_meshes_min_count", 3) or 3)
            )
        except Exception:
            self._batch_location_meshes_min_count = 3
        self._location_mesh_culling_enabled = bool(perf_cfg.get("cull_location_meshes", True))
        self._location_mesh_hlod_enabled = bool(perf_cfg.get("location_mesh_hlod_enabled", True))
        raw_location_profiles = (
            perf_cfg.get("location_mesh_cull_profiles", {})
            if isinstance(perf_cfg.get("location_mesh_cull_profiles"), dict)
            else {}
        )
        self._location_mesh_cull_profiles = {}
        for raw_key, raw_row in raw_location_profiles.items():
            key = _normalize_location_token(raw_key)
            if not key or not isinstance(raw_row, dict):
                continue
            self._location_mesh_cull_profiles[key] = dict(raw_row)
        raw_hlod_profiles = (
            perf_cfg.get("location_mesh_hlod_profiles", {})
            if isinstance(perf_cfg.get("location_mesh_hlod_profiles"), dict)
            else {}
        )
        self._location_mesh_hlod_profiles = {}
        for raw_key, raw_row in raw_hlod_profiles.items():
            key = _normalize_location_token(raw_key)
            if not key or not isinstance(raw_row, dict):
                continue
            self._location_mesh_hlod_profiles[key] = dict(raw_row)
        try:
            self._location_mesh_cull_distance = max(
                20.0, float(perf_cfg.get("location_mesh_cull_distance", 170.0) or 170.0)
            )
        except Exception:
            self._location_mesh_cull_distance = 170.0
        try:
            self._location_mesh_cull_hysteresis = max(
                0.0, float(perf_cfg.get("location_mesh_cull_hysteresis", 18.0) or 18.0)
            )
        except Exception:
            self._location_mesh_cull_hysteresis = 18.0
        try:
            default_hlod_distance = min(
                self._location_mesh_cull_distance - 12.0,
                float(perf_cfg.get("location_mesh_hlod_distance", 118.0) or 118.0),
            )
            self._location_mesh_hlod_distance = max(15.0, float(default_hlod_distance))
        except Exception:
            self._location_mesh_hlod_distance = 118.0
        try:
            self._location_mesh_hlod_hysteresis = max(
                0.0, float(perf_cfg.get("location_mesh_hlod_hysteresis", 22.0) or 22.0)
            )
        except Exception:
            self._location_mesh_hlod_hysteresis = 22.0
        try:
            self._location_mesh_cull_update_interval = max(
                0.05, float(perf_cfg.get("location_mesh_cull_update_interval", 0.25) or 0.25)
            )
        except Exception:
            self._location_mesh_cull_update_interval = 0.25
        self._location_mesh_cull_accum = 0.0
        self._location_mesh_runtime_cull_scale = 1.0
        self._location_mesh_runtime_hlod_scale = 1.0
        self._location_mesh_runtime_update_scale = 1.0
        self._location_mesh_runtime_level = 0
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
        
        # --- VOID SANDBOX DETECTION ---
        is_sandbox = (str(getattr(app, "_test_profile", "")).lower() == "ultimate_sandbox" or 
                    str(getattr(app, "_test_location_raw", "")).lower() == "ultimate_sandbox")
        
        if is_sandbox:
            self.world_type = "ultimate_sandbox"
            self.active_location = "ultimate_sandbox"
            # Prevent Old Forest override by making sandbox a real location
            self.locations.append({"name": "ultimate_sandbox", "pos": [0.0, 0.0, 5.0], "radius": 1000.0})

            self._gen_steps = [
                (0.2, self._init_textures, "Waking up the void..."),
                (1.0, self._build_ultimate_sandbox, "Forging the Ultimate Sandbox..."),
            ]
        else:
            self._gen_steps = [

            (0.10, self._init_textures, "Generating procedural materials..."),
            (0.24, self._build_terrain, "Drafting Sharuan terrain..."),
            (0.34, self._build_sea, "Simulating sea and water bodies..."),
            (0.36, self._enhance_water_surfaces, "Enhancing water shading..."),
            (0.42, self._build_river, "Mapping river paths..."),
            (0.44, self._build_bridge, "Constructing Sharuan stone bridge..."),
            (0.54, self._build_castle, "Constructing Castle Sharuan..."),
            (0.565, self._build_location_doors, "Placing location transition doors..."),
            (0.59, self._build_location_meshes, "Streaming handcrafted location meshes..."),
            (0.63, self._build_city_wall, "Erecting city fortifications..."),
            (0.72, self._build_districts, "Laying out city districts..."),
            (0.80, self._build_port_town, "Building port and market district..."),
            (0.86, self._build_center, "Designing town center..."),
            (0.90, self._build_movement_training_ground, "Preparing movement training grounds..."),
            (0.92, self._build_ultimate_sandbox, "Building Ultimate Sandbox Grounds..."),
            (0.94, self._build_scenery, "Adding scenery and decorations..."),
            (0.955, self._build_treasure_chests, "Placing treasure chests across locations..."),
            (0.97, self._build_dwarven_caves_story_setpiece, "Carving dwarven cave sectors..."),
            (0.985, self._place_zone_props, "Scattering zone props..."),
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
        payload = {}
        data_mgr = getattr(getattr(self, "app", None), "data_mgr", None)
        getter = getattr(data_mgr, "get_location_meshes_config", None)
        if callable(getter):
            try:
                value = getter()
                if isinstance(value, dict):
                    payload = value
            except Exception as exc:
                logger.warning(f"[World] Failed to read location meshes from DataManager: {exc}")
        if not payload and getattr(self, "app", None) is not None:
            payload = load_data_file(self.app, "world/location_meshes.json", default={})

        file_rows = normalize_location_mesh_entries(payload)
        if file_rows:
            merged.extend(file_rows)
        return merged

    def _collect_world_model_paths(self, category, names=None):
        token = str(category or "").strip().lower()
        if not token:
            return []
        base_dir = Path("assets/models/world") / token
        if not base_dir.exists():
            return []
        out = []
        seen = set()
        candidates = []
        if isinstance(names, list) and names:
            for raw in names:
                item = str(raw or "").strip()
                if item:
                    candidates.append(base_dir / item)
        else:
            candidates.extend(sorted(base_dir.glob("*.glb")))
        for path in candidates:
            try:
                src = prefer_bam_path(path.as_posix())
            except Exception:
                src = path.as_posix().replace("\\", "/")
            key = src.lower()
            if key in seen:
                continue
            if not Path(src).exists():
                continue
            seen.add(key)
            out.append(src)
        return out

    def _spawn_world_model(
        self,
        model_path,
        x,
        y,
        z,
        *,
        scale=1.0,
        h=0.0,
        p=0.0,
        r=0.0,
        loc_name="",
        is_platform=False,
        is_wallrun=False,
        tint=None,
    ):
        raw = str(model_path or "").strip().replace("\\", "/")
        if not raw:
            return None
        resolved = prefer_bam_path(raw)
        if not resolved or not Path(resolved).exists():
            return None

        # ── Instance cache: load each unique model once, reuse via instanceTo ──
        if not hasattr(self, "_model_cache"):
            self._model_cache = {}

        cache_key = resolved.lower()
        cached = self._model_cache.get(cache_key)
        if cached is not None and not cached.isEmpty():
            # Create a lightweight wrapper node and instance the cached geometry into it
            node = self.render.attachNewNode(f"inst_{Path(resolved).stem}")
            cached.instanceTo(node)
        else:
            try:
                node = self.loader.loadModel(resolved)
            except Exception as exc:
                logger.debug(f"[World] Failed to load world model '{resolved}': {exc}")
                return None
            if not node or node.isEmpty():
                return None
            # Store as hidden template for instancing
            self._model_cache[cache_key] = node.copyTo(self.render)
            self._model_cache[cache_key].hide()
            self._model_cache[cache_key].setName(f"tpl_{Path(resolved).stem}")

        # Defensive check for position
        try:
            fx, fy, fz = float(x), float(y), float(z)
            if any(math.isnan(v) or math.isinf(v) for v in (fx, fy, fz)):
                logger.warning(f"[World] Suppressed NaN/Inf world model pos: {fx, fy, fz}")
                fx, fy, fz = 0.0, 0.0, 0.0
        except Exception:
            fx, fy, fz = 0.0, 0.0, 0.0

        node.reparentTo(self.render)
        node.setPos(fx, fy, fz)
        node.setHpr(float(h), float(p), float(r))

        if isinstance(scale, (tuple, list)) and len(scale) >= 3:
            try:
                s1, s2, s3 = float(scale[0]), float(scale[1]), float(scale[2])
                if any(math.isnan(v) or math.isinf(v) for v in (s1, s2, s3)):
                    s1, s2, s3 = 1.0, 1.0, 1.0
                node.setScale(s1, s2, s3)
            except Exception:
                node.setScale(1.0)
        else:
            try:
                s = float(scale or 1.0)
                if math.isnan(s) or math.isinf(s):
                    s = 1.0
                node.setScale(max(0.01, s))
            except Exception:
                node.setScale(1.0)
        if isinstance(tint, (tuple, list)) and len(tint) >= 3:
            try:
                node.setColorScale(*tint)
            except Exception:
                pass
        if getattr(self, "terrain_shader", None):
            node.set_shader(self.terrain_shader, priority=100)
            self._register_terrain_shader_target(node)
        ensure_model_visual_defaults(
            node,
            apply_skin=False,
            force_two_sided=True,
            debug_label=f"world_model:{Path(resolved).name}",
        )
        self._attach_world_model_fx(node, resolved)
        if loc_name:
            node.set_tag("info", str(loc_name))
        if is_platform:
            self._add_platform_from_bounds(node.get_tight_bounds(), is_wallrun=bool(is_wallrun))
        return node

    def _world_model_fx_profile(self, model_path):
        token = str(model_path or "").strip().replace("\\", "/").lower()
        if not token:
            return None
        if "forge_fire" in token:
            return {
                "kind": "fire_prop",
                "base_scale": 0.44,
                "z_offset": 0.42,
                "alpha": 0.92,
            }
        if "fireplace" in token:
            return {
                "kind": "fire_prop",
                "base_scale": 0.58,
                "z_offset": 0.54,
                "alpha": 0.88,
            }
        if any(marker in token for marker in ("camp_fire", "campfire", "bonfire")):
            return {
                "kind": "fire_prop",
                "base_scale": 0.52,
                "z_offset": 0.38,
                "alpha": 0.90,
            }
        return None

    def _fire_prop_texture(self):
        tex = getattr(self, "_ambient_fire_tex", None)
        if tex:
            return tex
        tex = load_optional_texture(
            getattr(self, "loader", None),
            candidates=["assets/textures/flare.png"],
            require_alpha=True,
            fallback_texture=lambda: make_soft_disc_texture(
                tex_name="ambient_fire_prop_sprite",
                size=160,
                warm=True,
            ),
        )
        self._ambient_fire_tex = tex
        return tex

    def _attach_world_model_fx(self, node, model_path):
        profile = self._world_model_fx_profile(model_path)
        if not isinstance(profile, dict) or not node:
            return None
        try:
            if hasattr(node, "isEmpty") and node.isEmpty():
                return None
        except Exception:
            pass

        root = node.attachNewNode("ambient_fire_fx")
        if hasattr(root, "setTag"):
            root.setTag("fx_role", "fire_prop")
        if hasattr(root, "setPos"):
            root.setPos(0.0, 0.0, float(profile.get("z_offset", 0.4) or 0.4))

        tex = self._fire_prop_texture()
        base_scale = max(0.12, float(profile.get("base_scale", 0.48) or 0.48))
        alpha = max(0.1, min(1.0, float(profile.get("alpha", 0.9) or 0.9)))
        specs = (
            ("flame_core", 0.00, base_scale * 1.00, (1.0, 0.72, 0.30, alpha)),
            ("flame_outer", 18.0, base_scale * 1.18, (1.0, 0.46, 0.16, alpha * 0.82)),
            ("ember_glow", -22.0, base_scale * 0.68, (1.0, 0.34, 0.08, alpha * 0.64)),
        )

        rows = self._ambient_fire_props if isinstance(getattr(self, "_ambient_fire_props", None), list) else []
        self._ambient_fire_props = rows
        for idx, (name, roll, scale, color) in enumerate(specs):
            cm = CardMaker(f"{Path(str(model_path or '')).stem}_{name}")
            cm.setFrame(-0.5, 0.5, 0.0, 1.0)
            flame = root.attachNewNode(cm.generate())
            if hasattr(flame, "setTransparency"):
                flame.setTransparency(TransparencyAttrib.MAlpha)
            if hasattr(flame, "setDepthWrite"):
                flame.setDepthWrite(False)
            if hasattr(flame, "setDepthTest"):
                flame.setDepthTest(False)
            if hasattr(flame, "setTwoSided"):
                flame.setTwoSided(True)
            if hasattr(flame, "setLightOff"):
                flame.setLightOff(1)
            if hasattr(flame, "setShaderOff"):
                flame.setShaderOff(1002)
            if hasattr(flame, "setBillboardPointEye"):
                flame.setBillboardPointEye()
            if hasattr(flame, "setBin"):
                flame.setBin("transparent", 28 + idx)
            if tex and hasattr(flame, "setTexture"):
                try:
                    flame.setTexture(tex, 1)
                except Exception:
                    pass
            if hasattr(flame, "setPos"):
                flame.setPos(0.0, 0.0, 0.03 * idx)
            if hasattr(flame, "setScale"):
                flame.setScale(scale, 1.0, scale * 1.6)
            if hasattr(flame, "setR"):
                flame.setR(roll)
            if hasattr(flame, "setColorScale"):
                flame.setColorScale(*color)
            rows.append(
                {
                    "node": flame,
                    "phase": idx * 0.85,
                    "base_scale": scale,
                    "base_alpha": color[3],
                    "color": color[:3],
                    "roll": roll,
                    "lift": 0.03 * idx,
                    "sway": 0.018 + (idx * 0.008),
                    "pulse": 3.0 + (idx * 0.55),
                }
            )
        return root

    def _animate_fire_props(self, t):
        rows = self._ambient_fire_props if isinstance(getattr(self, "_ambient_fire_props", None), list) else []
        if not rows:
            return
        alive = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            node = row.get("node")
            if not node:
                continue
            try:
                if hasattr(node, "isEmpty") and node.isEmpty():
                    continue
            except Exception:
                pass

            phase = float(row.get("phase", 0.0) or 0.0)
            pulse_speed = float(row.get("pulse", 3.0) or 3.0)
            pulse = 0.88 + (0.16 * math.sin((t * pulse_speed) + phase))
            drift = math.sin((t * (pulse_speed * 0.64)) + phase) * float(row.get("sway", 0.02) or 0.02)
            lift = float(row.get("lift", 0.0) or 0.0) + (0.012 * math.sin((t * 2.1) + phase))
            scale = max(0.05, float(row.get("base_scale", 0.3) or 0.3) * pulse)
            rgb = row.get("color", (1.0, 0.6, 0.2))
            alpha = max(0.12, min(1.0, float(row.get("base_alpha", 0.8) or 0.8) * (0.82 + (0.20 * math.sin((t * 4.0) + phase)))))

            if hasattr(node, "setPos"):
                node.setPos(drift, 0.0, lift)
            if hasattr(node, "setScale"):
                node.setScale(scale, 1.0, scale * 1.65)
            if hasattr(node, "setR"):
                node.setR(float(row.get("roll", 0.0) or 0.0) + (6.0 * math.sin((t * 1.8) + phase)))
            if hasattr(node, "setColorScale"):
                node.setColorScale(float(rgb[0]), float(rgb[1]), float(rgb[2]), alpha)
            alive.append(row)
        self._ambient_fire_props = alive

    def _build_location_doors(self):
        rows = self._location_doors if isinstance(self._location_doors, list) else []
        if not rows:
            return

        trim_mat = mk_mat((0.54, 0.49, 0.42, 1.0), 0.54, 0.00)
        lintel_mat = mk_mat((0.45, 0.30, 0.20, 1.0), 0.78, 0.03)
        marker_mat = mk_mat((0.96, 0.84, 0.56, 0.34), 0.20, 0.00)

        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            center = _as_xyz_tuple(row.get("center"))
            if center is None:
                continue
            x, y, z = center
            heading = float(row.get("heading", 0.0) or 0.0)
            loc_name = f"Door: {row.get('to', 'Location')}"
            built = False
            model_path = str(row.get("model", "") or "").strip()
            if model_path:
                model_node = self._spawn_world_model(
                    model_path,
                    x,
                    y,
                    z,
                    scale=float(row.get("scale", 1.0) or 1.0),
                    h=heading,
                    loc_name=loc_name,
                    is_platform=False,
                    is_wallrun=False,
                )
                built = bool(model_node)
                if built:
                    row["node"] = model_node
            if not built:
                post_l = self._pl(
                    mk_box(f"door_post_l_{idx}", 0.42, 0.36, 4.2),
                    x - 1.12,
                    y,
                    z + 2.1,
                    self.tx["stone"],
                    trim_mat,
                    loc_name,
                    is_platform=False,
                    is_wallrun=False,
                )
                post_l.setH(heading)
                post_r = self._pl(
                    mk_box(f"door_post_r_{idx}", 0.42, 0.36, 4.2),
                    x + 1.12,
                    y,
                    z + 2.1,
                    self.tx["stone"],
                    trim_mat,
                    loc_name,
                    is_platform=False,
                    is_wallrun=False,
                )
                post_r.setH(heading)
                lintel = self._pl(
                    mk_box(f"door_lintel_{idx}", 2.7, 0.34, 0.45),
                    x,
                    y,
                    z + 4.05,
                    self.tx["bark"],
                    lintel_mat,
                    loc_name,
                    is_platform=False,
                    is_wallrun=False,
                )
                lintel.setH(heading)
                marker = self._pl(
                    mk_plane(f"door_marker_{idx}", 1.8, 2.9, 1.0),
                    x,
                    y + 0.05,
                    z + 2.0,
                    None,
                    marker_mat,
                    loc_name,
                    is_platform=False,
                    is_wallrun=False,
                )
                marker.setH(heading)
                marker.set_transparency(TransparencyAttrib.M_alpha)
                marker.setColorScale(1.0, 0.88, 0.62, 0.26)
                vfx = getattr(self.app, "magic_vfx", None)
                if vfx:
                    vfx.spawn_portal_vfx(Vec3(x, y + 0.1, z + 2.0))
                row["node"] = lintel

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
        now = globalClock.getFrameTime()
        self._animate_water(now)
        self._animate_fire_props(now)
        zone_location = None
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
                    zone_location = loc["name"]

        next_location = zone_location
        door_hit = resolve_location_door_transition(
            player_pos,
            self.active_location,
            self._location_doors,
        )
        if isinstance(door_hit, dict):
            door_id = str(door_hit.get("id", "") or "").strip().lower()
            if door_id and self._active_door_overlap != door_id:
                next_location = str(door_hit.get("to", "") or "").strip() or zone_location
            self._active_door_overlap = door_id
        else:
            self._active_door_overlap = ""
            current_token = _normalize_location_token(self.active_location)
            zone_token = _normalize_location_token(zone_location)
            if (
                zone_token
                and zone_token != current_token
                and (
                    zone_token in self._door_controlled_location_tokens
                    or current_token in self._door_controlled_location_tokens
                )
            ):
                next_location = self.active_location

        if self.active_location != next_location and next_location:
            logger.info(f"[World] Entered: {next_location}")
        self.active_location = next_location
        self._update_location_mesh_visibility(player_pos, globalClock.getDt())

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
        quality = str(getattr(self.data_mgr, "graphics_settings", {}).get("quality", "low") or "low").strip().lower()
        if quality == "low":
            S = 128
            anisotropy = 4
        elif quality in {"med", "middle", "medium"}:
            S = 192
            anisotropy = 6
        elif quality == "ultra":
            S = 320
            anisotropy = 12
        else:
            S = 256
            anisotropy = 8
        self._grass_anisotropy = int(max(2, anisotropy))
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

        # Water PBR - tighter ripples and stronger shoreline readability.
        def gn_water_alb(u, v):
            n0 = _fbm((u * 2.4) + 17.0, (v * 2.2) + 9.0, 3, 83)
            n1 = _fbm((u * 7.0) + 31.0, (v * 6.8) + 47.0, 2, 91)
            lum = max(0.0, min(1.0, 0.42 + (n0 * 0.20) + (n1 * 0.16)))
            return (
                0.05 + (lum * 0.16),
                0.20 + (lum * 0.30),
                0.34 + (lum * 0.40),
            )

        def gn_water_norm(u, v):
            n1 = _fbm(u * 20.0, v * 20.0, 3, 101)
            n2 = _fbm((u + 0.006) * 20.0, v * 20.0, 3, 101)
            n3 = _fbm(u * 20.0, (v + 0.006) * 20.0, 3, 101)
            return 0.5 + ((n1 - n2) * 4.2), 0.5 + ((n1 - n3) * 4.2), 1.0

        def gn_water_rough(u, v):
            n = _fbm((u * 5.5) + 3.0, (v * 5.0) + 11.0, 3, 61)
            rv = 0.18 + (n * 0.12)
            return rv, rv, rv

        # Magic Grid PBR (for Sandbox)
        def gn_grid_alb(u,v):
            su=math.sin(u*60); sv=math.sin(v*60)
            edge = 1.0 if abs(su)>0.97 or abs(sv)>0.97 else 0.0
            n=_fbm(u*8,v*8,4,88); b=0.12+n*0.04
            return b+edge*0.5, b+edge*0.35, b+edge*0.8
        def gn_grid_rough(u,v):
            su=math.sin(u*60); sv=math.sin(v*60)
            edge = 1.0 if abs(su)>0.97 or abs(sv)>0.97 else 0.0
            return 0.2 if edge > 0.5 else 0.75, 0.2 if edge > 0.5 else 0.75, 0.2 if edge > 0.5 else 0.75

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

        water_tex_size = max(96, min(256, int(S * 0.58)))
        self.tx = {
            'grass': make_pbr_tex_set('grass', S, gn_grass_alb, gn_grass_norm, gn_grass_rough, anisotropy=anisotropy),
            'stone': make_pbr_tex_set('stone', S, gn_stone_alb, gn_stone_norm, lambda u,v: (0.35, 0.35, 0.35), anisotropy=anisotropy),
            'roof':  make_pbr_tex_set('roof',  S, gn_roof_alb, anisotropy=anisotropy),
            'bark':  make_pbr_tex_set('bark',  S, gn_bark_alb, None, lambda u,v: (0.85, 0.85, 0.85), anisotropy=anisotropy),
            'leaf':  make_pbr_tex_set('leaf',  S, gn_leaf_alb, None, lambda u,v: (0.75, 0.75, 0.75), anisotropy=anisotropy),
            'dirt':  make_pbr_tex_set('dirt',  S, lambda u,v: (0.45, 0.38, 0.30), anisotropy=anisotropy),
            'water': make_pbr_tex_set('water', water_tex_size, gn_water_alb, gn_water_norm, gn_water_rough, anisotropy=max(6, anisotropy)),
            'magic_grid': make_pbr_tex_set('magic_grid', S, gn_grid_alb, None, gn_grid_rough, anisotropy=anisotropy),
        }

    def _th(self, x, y):
        # Ultimate Sandbox special case
        if getattr(self, "world_type", "") == "ultimate_sandbox":
            return 5.0

        # Defensive check for input
        try:
            x, y = float(x), float(y)
            if any(math.isnan(v) or math.isinf(v) for v in (x, y)):
                return 0.0
        except Exception:
            return 0.0

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
        res = mtn + sea + rv + noise + hills
        import math
        if math.isnan(res) or math.isinf(res):
            return 0.0
        return float(res)

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
                    is_wallrun=False,
                )
                decal.setH(rng.uniform(-180.0, 180.0))
                decal.setColorScale(0.92, 0.84, 0.72, 0.56)
                decal.set_transparency(TransparencyAttrib.M_alpha)

    def _scatter_points(
        self,
        *,
        count,
        x_range,
        y_range,
        min_spacing=3.5,
        rng=None,
        max_tries_per_point=46,
        accept_fn=None,
    ):
        total = max(0, int(count or 0))
        if total <= 0:
            return []
        xr = x_range if (isinstance(x_range, (list, tuple)) and len(x_range) >= 2) else (-1.0, 1.0)
        yr = y_range if (isinstance(y_range, (list, tuple)) and len(y_range) >= 2) else (-1.0, 1.0)
        x0, x1 = float(min(xr[0], xr[1])), float(max(xr[0], xr[1]))
        y0, y1 = float(min(yr[0], yr[1])), float(max(yr[0], yr[1]))
        spacing = max(0.0, float(min_spacing or 0.0))
        spacing_sq = spacing * spacing
        tries = max(8, int(max_tries_per_point or 0))
        rng = rng if rng else random.Random(1337)
        points = []

        for _ in range(total):
            placed = False
            for _attempt in range(tries):
                px = rng.uniform(x0, x1)
                py = rng.uniform(y0, y1)
                if callable(accept_fn):
                    try:
                        if not bool(accept_fn(px, py)):
                            continue
                    except Exception:
                        continue
                if spacing_sq > 0.0:
                    blocked = False
                    for ox, oy in points:
                        dx = px - ox
                        dy = py - oy
                        if ((dx * dx) + (dy * dy)) < spacing_sq:
                            blocked = True
                            break
                    if blocked:
                        continue
                points.append((px, py))
                placed = True
                break
            if not placed and callable(accept_fn):
                # Last-resort fallback to keep density stable in strict zones.
                for _attempt in range(max(3, tries // 2)):
                    px = rng.uniform(x0, x1)
                    py = rng.uniform(y0, y1)
                    try:
                        if bool(accept_fn(px, py)):
                            points.append((px, py))
                            break
                    except Exception:
                        continue
        return points

    def _spawn_gpu_grass(self, x, y, z, extent, density, tex):
        """Constructs a thick field of grass using high-density geometry and wind-sway shaders."""
        from panda3d.core import GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Geom, GeomNode, TransparencyAttrib, Shader

        total_blades = int((extent * extent) * max(0.05, float(density)))
        quality = str(getattr(self.data_mgr, "graphics_settings", {}).get("quality", "high") or "high").strip().lower()
        if quality == "low":
            total_blades = int(total_blades * 0.70)
        elif quality in {"med", "middle", "medium"}:
            total_blades = int(total_blades * 0.88)
        elif quality == "ultra":
            total_blades = int(total_blades * 1.18)
        total_blades = max(24, min(2400, total_blades))
        if total_blades <= 0:
            return None

        fmt = GeomVertexFormat.getV3n3c4t2()
        vdata = GeomVertexData("gpu_grass", fmt, Geom.UHStatic)
        vwriter = GeomVertexWriter(vdata, "vertex")
        nwriter = GeomVertexWriter(vdata, "normal")
        cwriter = GeomVertexWriter(vdata, "color")
        twriter = GeomVertexWriter(vdata, "texcoord")
        
        triangles = GeomTriangles(Geom.UHStatic)
        base_v = 0
        biome = self.data_mgr.get_biome("plains")
        grass_col = biome.get("grass_color", [0.18, 0.52, 0.10])
        base_r = float(grass_col[0]) if isinstance(grass_col, list) and len(grass_col) >= 3 else 0.18
        base_g = float(grass_col[1]) if isinstance(grass_col, list) and len(grass_col) >= 3 else 0.52
        base_b = float(grass_col[2]) if isinstance(grass_col, list) and len(grass_col) >= 3 else 0.10

        def add_card(px, py, pz, half_w, height, rot, stiffness, tint):
            nonlocal base_v
            s_rot = math.sin(rot)
            c_rot = math.cos(rot)
            v0x = -half_w * c_rot
            v0y = -half_w * s_rot
            v1x = half_w * c_rot
            v1y = half_w * s_rot
            cr = max(0.0, min(1.0, base_r * (0.78 + (0.34 * tint))))
            cg = max(0.0, min(1.0, base_g * (0.82 + (0.42 * tint))))
            cb = max(0.0, min(1.0, base_b * (0.76 + (0.28 * tint))))
            
            # Add subtle brown/yellow highlights for aging grass
            if tint > 0.85:
                cr *= 1.1; cg *= 0.95; cb *= 0.85
            elif tint < 0.2:
                cg *= 1.2 # extra lush green for low-stiff blades

            vwriter.addData3(px + v0x, py + v0y, pz)
            nwriter.addData3(s_rot, -c_rot, 0)
            cwriter.addData4(cr, cg, cb, stiffness)
            twriter.addData2(0, 0)

            vwriter.addData3(px + v1x, py + v1y, pz)
            nwriter.addData3(s_rot, -c_rot, 0)
            cwriter.addData4(cr, cg, cb, stiffness)
            twriter.addData2(1, 0)

            # Randomize blade height and add tapering
            h_mod = height * (0.94 + (0.12 * tint))
            vwriter.addData3(px + v0x * 0.45, py + v0y * 0.45, pz + h_mod)
            nwriter.addData3(s_rot, -c_rot, 0)
            cwriter.addData4(cr, cg, cb, stiffness)
            twriter.addData2(0, 1)

            vwriter.addData3(px + v1x * 0.45, py + v1y * 0.45, pz + h_mod)
            nwriter.addData3(s_rot, -c_rot, 0)
            cwriter.addData4(cr, cg, cb, stiffness)
            twriter.addData2(1, 1)

            triangles.addVertices(base_v + 0, base_v + 1, base_v + 2)
            triangles.addVertices(base_v + 1, base_v + 3, base_v + 2)
            base_v += 4

        rng = random.Random(int(x + y * 1337))
        sea_y = float(self.sea_cfg.get("start_y", -50.0) or -50.0)
        for _ in range(total_blades):
            ox = rng.uniform(-extent, extent)
            oy = rng.uniform(-extent, extent)
            dist_sq = (ox * ox) + (oy * oy)
            if dist_sq > (extent * extent):
                continue

            px = x + ox
            py = y + oy
            if py <= (sea_y + 1.8):
                continue
            if self._distance_to_river(px, py) < 2.4:
                continue
            # Kremor exclusion: No grass in the desolate zone
            dk_sq = (px - 76)**2 + (py - 12)**2
            if dk_sq < 1764.0: # 42 units radius
                continue
            pz = float(self._th(px, py))
            if pz < -0.45:
                continue

            blade_h = rng.uniform(0.44, 1.10)
            blade_w = rng.uniform(0.08, 0.19)
            half_w = blade_w * 0.5
            base_rot = rng.uniform(0.0, math.tau)
            stiffness = rng.uniform(0.6, 1.0)
            tint = rng.uniform(0.86, 1.14)

            # Two crossed cards per tuft for fuller grass without oversized X cards.
            add_card(px, py, pz, half_w, blade_h, base_rot, stiffness, tint)
            add_card(
                px,
                py,
                pz,
                half_w * rng.uniform(0.85, 1.10),
                blade_h * rng.uniform(0.86, 1.08),
                base_rot + (math.pi * 0.5) + rng.uniform(-0.18, 0.18),
                stiffness * rng.uniform(0.92, 1.06),
                tint * rng.uniform(0.94, 1.08),
            )

        geom = Geom(vdata)
        geom.addPrimitive(triangles)
        node = GeomNode("grass_patch")
        node.addGeom(geom)

        root = self.render.attachNewNode(node)
        root.setTransparency(TransparencyAttrib.M_alpha)
        root.setTwoSided(True)
        if tex:
            root.setTexture(tex, 1)

        # Compile Wind Shader
        vert_shader = """
        #version 130
        uniform mat4 p3d_ModelViewProjectionMatrix;
        uniform float osg_FrameTime;
        in vec4 p3d_Vertex;
        in vec3 p3d_Normal;
        in vec4 p3d_Color;
        in vec2 p3d_MultiTexCoord0;
        out vec2 texcoord;
        out vec4 color;
        
        void main() {
            vec4 pos = p3d_Vertex;
            // UV Y used as height mask, color A as stiffness
            float height_factor = p3d_MultiTexCoord0.y; 
            float stiffness = p3d_Color.a;
            
            // Wind function
            float windX = sin(pos.x * 0.5 + osg_FrameTime * 2.0) * cos(pos.y * 0.3 + osg_FrameTime);
            float windY = cos(pos.y * 0.4 + osg_FrameTime * 1.5) * sin(pos.x * 0.2 + osg_FrameTime * 1.2);
            
            // Apply sway
            pos.x += windX * height_factor * stiffness * 0.6;
            pos.y += windY * height_factor * stiffness * 0.6;
            
            gl_Position = p3d_ModelViewProjectionMatrix * pos;
            texcoord = p3d_MultiTexCoord0;
            color = vec4(p3d_Color.rgb, 1.0);
        }
        """
        
        frag_shader = """
        #version 130
        uniform sampler2D p3d_Texture0;
        in vec2 texcoord;
        in vec4 color;
        out vec4 p3d_FragColor;
        
        void main() {
            vec4 tex = texture(p3d_Texture0, texcoord);
            if(tex.a < 0.22) discard;
            float alpha = smoothstep(0.22, 0.80, tex.a);
            p3d_FragColor = vec4(color.rgb * tex.rgb, alpha);
        }
        """

        shader = Shader.make(Shader.SL_GLSL, vert_shader, frag_shader)
        root.setShader(shader)
        return root

    def _attach_scene_node(self, geom):
        copier = getattr(geom, "copy_to", None)
        if callable(copier):
            try:
                return copier(self.render)
            except Exception:
                pass
        copier = getattr(geom, "copyTo", None)
        if callable(copier):
            try:
                return copier(self.render)
            except Exception:
                pass
        return self.render.attach_new_node(geom)

    def _iter_terrain_shader_targets(self):
        compact = []
        for node in list(getattr(self, "_terrain_shader_targets", []) or []):
            if node is None:
                continue
            try:
                if node.isEmpty():
                    continue
            except Exception:
                continue
            compact.append(node)
        self._terrain_shader_targets = compact
        return list(compact)

    def _register_terrain_shader_target(self, node):
        if not getattr(self, "terrain_shader", None):
            return
        if node is None:
            return
        try:
            if node.isEmpty():
                return
        except Exception:
            return
        self._terrain_shader_targets.append(node)
        try:
            node.set_shader_input(
                "cursed_blend",
                float(getattr(self, "_terrain_shader_cursed_blend", 0.0) or 0.0),
            )
        except Exception:
            logger.debug("[SharuanWorld] Failed to seed cursed_blend on terrain shader target.")

    def sync_environment_shader_inputs(self, cursed_blend=0.0):
        try:
            blend = float(cursed_blend or 0.0)
            if math.isnan(blend) or math.isinf(blend):
                blend = 0.0
        except Exception:
            blend = 0.0
        self._terrain_shader_cursed_blend = blend
        for node in self._iter_terrain_shader_targets():
            try:
                node.set_shader_input("cursed_blend", blend)
            except Exception:
                logger.debug("[SharuanWorld] Failed to sync cursed_blend on terrain shader target.")

    def _pl(self, geom, x, y, z, tx_set=None, mat=None, loc_name=None, is_platform=True, is_wallrun=False):
        np = self._attach_scene_node(geom)
        # Defensive check for position
        try:
            fx, fy, fz = float(x), float(y), float(z)
            if any(math.isnan(v) or math.isinf(v) for v in (fx, fy, fz)):
                fx, fy, fz = 0.0, 0.0, 0.0
        except Exception:
            fx, fy, fz = 0.0, 0.0, 0.0
        np.set_pos(fx, fy, fz)
        # Level Editor 2.0 Tags (Strict SQLite + Msgpack)
        eid = "obj_" + str(id(np))
        if hasattr(geom, "getName"):
            eid = str(geom.getName())
        np.set_tag('entity_id', eid)
        np.set_tag('type', 'primitive')

        if getattr(self, "terrain_shader", None):
            np.set_shader(self.terrain_shader, priority=100)
            self._register_terrain_shader_target(np)

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

        if mat:
            try:
                np.set_material(mat, 1)
            except Exception:
                pass

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
                    p.isWallRun = bool(is_wallrun)
                    self.phys.addPlatform(p)
                else:
                    self.colliders.append({
                        'min_x': bounds[0].x, 'min_y': bounds[0].y, 'min_z': bounds[0].z,
                        'max_x': bounds[1].x, 'max_y': bounds[1].y, 'max_z': bounds[1].z
                    })
        return np

    def _build_location_meshes(self):
        self._location_mesh_nodes = []
        self._location_mesh_cluster_nodes = {}
        self._location_mesh_cluster_centers = {}
        self._location_mesh_cluster_modes = {}
        rows = self._location_meshes_cfg if isinstance(self._location_meshes_cfg, list) else []
        if not rows:
            return

        cluster_accum = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            model_path = prefer_bam_path(str(row.get("model", "") or "").strip().replace("\\", "/"))
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
            is_wallrun = bool(row.get("is_wallrun", False))
            batch_static = bool(row.get("batch_static", True))
            never_cull = bool(row.get("never_cull", False))
            hlod_enabled = bool(row.get("hlod_enabled", True))
            cluster_token = _normalize_location_token(
                row.get("hlod_group")
                or row.get("location")
                or row.get("zone")
                or mesh_id
            ) or _normalize_location_token(mesh_id)

            node.reparentTo(self.render)
            try:
                fx, fy, fz = float(pos[0]), float(pos[1]), float(pos[2])
                if any(math.isnan(v) or math.isinf(v) for v in (fx, fy, fz)):
                    fx, fy, fz = 0.0, 0.0, 0.0
                node.setPos(fx, fy, fz)
            except Exception:
                node.setPos(0.0, 0.0, 0.0)

            try:
                fh, fp, fr = float(hpr[0]), float(hpr[1]), float(hpr[2])
                if any(math.isnan(v) or math.isinf(v) for v in (fh, fp, fr)):
                    fh, fp, fr = 0.0, 0.0, 0.0
                node.setHpr(fh, fp, fr)
            except Exception:
                node.setHpr(0.0, 0.0, 0.0)

            try:
                fs1, fs2, fs3 = float(scale[0]), float(scale[1]), float(scale[2])
                if any(math.isnan(v) or math.isinf(v) for v in (fs1, fs2, fs3)):
                    fs1, fs2, fs3 = 1.0, 1.0, 1.0
                node.setScale(fs1, fs2, fs3)
            except Exception:
                node.setScale(1.0)
            node.setTag("info", label)
            node.setTag("mesh_id", mesh_id)
            node.setTag("entity_id", mesh_id)
            node.setTag("type", "location_mesh")
            node.setTag("batch_static", "1" if batch_static else "0")
            node.setTag("never_cull", "1" if never_cull else "0")
            node.setTag("hlod_enabled", "1" if hlod_enabled else "0")
            node.setTag("hlod_group", cluster_token)
            self._attach_world_model_fx(node, model_path)

            if is_platform:
                try:
                    bounds = node.getTightBounds()
                    if bounds:
                        self._add_platform_from_bounds(bounds, is_wallrun=is_wallrun)
                except Exception:
                    pass
            self._location_mesh_nodes.append(node)
            self._location_mesh_cluster_nodes.setdefault(cluster_token, []).append(node)
            accum = cluster_accum.get(cluster_token, (0.0, 0.0, 0.0, 0))
            cluster_accum[cluster_token] = (
                accum[0] + float(node.getX(self.render)),
                accum[1] + float(node.getY(self.render)),
                accum[2] + float(node.getZ(self.render)),
                accum[3] + 1,
            )

        for cluster_token, accum in cluster_accum.items():
            count = max(1, int(accum[3] or 1))
            self._location_mesh_cluster_centers[cluster_token] = Vec3(
                accum[0] / count,
                accum[1] / count,
                accum[2] / count,
            )

        nodes = self._location_mesh_nodes if isinstance(self._location_mesh_nodes, list) else []
        if not should_batch_location_meshes(
            len(nodes),
            enabled=self._batch_location_meshes_enabled,
            min_count=self._batch_location_meshes_min_count,
        ):
            return
        optimized = 0
        for node in nodes:
            if not node or node.isEmpty():
                continue
            try:
                if str(node.getTag("batch_static") or "1") != "1":
                    continue
            except Exception:
                pass
            try:
                node.clearModelNodes()
            except Exception:
                pass
            try:
                node.flattenMedium()
                optimized += 1
            except Exception:
                continue
        if optimized > 0:
            logger.info(f"[World] Batched static location meshes: {optimized}")
        self._rebuild_location_mesh_hlod_roots()

    def _rebuild_location_mesh_hlod_roots(self):
        roots = getattr(self, "_location_mesh_hlod_roots", {})
        if isinstance(roots, dict):
            for root in roots.values():
                if not root or root.isEmpty():
                    continue
                try:
                    root.removeNode()
                except Exception:
                    pass
        self._location_mesh_hlod_roots = {}

        if not bool(getattr(self, "_location_mesh_hlod_enabled", True)):
            return

        clusters = (
            self._location_mesh_cluster_nodes
            if isinstance(getattr(self, "_location_mesh_cluster_nodes", None), dict)
            else {}
        )
        built = 0
        for cluster_token, nodes in clusters.items():
            if not cluster_token or not isinstance(nodes, list):
                continue
            static_nodes = []
            for node in nodes:
                if not node or node.isEmpty():
                    continue
                try:
                    if str(node.getTag("batch_static") or "1") != "1":
                        continue
                    if str(node.getTag("hlod_enabled") or "1") != "1":
                        continue
                except Exception:
                    continue
                static_nodes.append(node)
            if len(static_nodes) < 2:
                continue

            root = self.render.attachNewNode(f"location_hlod_{cluster_token}")
            root.hide()
            root.setTag("hlod_root", "1")
            root.setTag("hlod_group", cluster_token)
            root.setTag("never_cull", "1")
            try:
                center = self._location_mesh_cluster_centers.get(cluster_token)
                if center is not None:
                    root.setPos(center)
            except Exception:
                pass

            for node in static_nodes:
                try:
                    clone = node.copyTo(root)
                    clone.setPos(node.getPos(self.render) - root.getPos(self.render))
                    clone.setHpr(node.getHpr(self.render))
                    clone.setScale(node.getScale(self.render))
                    clone.clearModelNodes()
                except Exception:
                    continue
            try:
                root.clearModelNodes()
            except Exception:
                pass
            try:
                root.flattenMedium()
            except Exception:
                pass
            self._location_mesh_hlod_roots[cluster_token] = root
            built += 1

        if built > 0:
            logger.info(f"[WorldPerf] Built location-mesh HLOD clusters: {built}")

    def set_runtime_performance_profile(self, profile=None, level=0):
        cfg = profile if isinstance(profile, dict) else {}
        try:
            runtime_level = max(0, min(3, int(level or 0)))
        except Exception:
            runtime_level = 0
        default_scales = {
            0: (1.00, 1.00, 1.00),
            1: (0.92, 0.86, 1.10),
            2: (0.80, 0.72, 1.22),
            3: (0.68, 0.58, 1.38),
        }
        cull_scale, hlod_scale, update_scale = default_scales.get(runtime_level, default_scales[0])
        try:
            cull_scale = float(cfg.get("world_mesh_cull_distance_scale", cull_scale) or cull_scale)
        except Exception:
            pass
        try:
            hlod_scale = float(cfg.get("world_mesh_hlod_distance_scale", hlod_scale) or hlod_scale)
        except Exception:
            pass
        try:
            update_scale = float(cfg.get("world_mesh_visibility_update_scale", update_scale) or update_scale)
        except Exception:
            pass
        self._location_mesh_runtime_level = runtime_level
        self._location_mesh_runtime_cull_scale = max(0.35, min(1.25, cull_scale))
        self._location_mesh_runtime_hlod_scale = max(0.25, min(1.25, hlod_scale))
        self._location_mesh_runtime_update_scale = max(0.75, min(3.0, update_scale))
        logger.info(
            "[WorldPerf] Applied mesh runtime profile: "
            f"level={self._location_mesh_runtime_level} "
            f"cull_scale={self._location_mesh_runtime_cull_scale:.2f} "
            f"hlod_scale={self._location_mesh_runtime_hlod_scale:.2f} "
            f"update_scale={self._location_mesh_runtime_update_scale:.2f}"
        )

    def _update_location_mesh_visibility(self, player_pos, dt):
        if not self._location_mesh_culling_enabled:
            return
        if not isinstance(self._location_mesh_nodes, list) or not self._location_mesh_nodes:
            return
        profile = resolve_location_mesh_cull_profile(
            active_location=self.active_location,
            base_distance=self._location_mesh_cull_distance,
            base_hysteresis=self._location_mesh_cull_hysteresis,
            base_interval=self._location_mesh_cull_update_interval,
            profiles=self._location_mesh_cull_profiles,
        )
        cull_distance = float(profile.get("distance", self._location_mesh_cull_distance))
        hysteresis = float(profile.get("hysteresis", self._location_mesh_cull_hysteresis))
        update_interval = float(profile.get("interval", self._location_mesh_cull_update_interval))
        cull_distance *= max(0.35, float(getattr(self, "_location_mesh_runtime_cull_scale", 1.0) or 1.0))
        update_interval *= max(0.75, float(getattr(self, "_location_mesh_runtime_update_scale", 1.0) or 1.0))
        hlod_profile = resolve_location_mesh_hlod_profile(
            active_location=self.active_location,
            enabled=self._location_mesh_hlod_enabled,
            base_distance=self._location_mesh_hlod_distance,
            base_hysteresis=self._location_mesh_hlod_hysteresis,
            profiles=self._location_mesh_hlod_profiles,
        )
        hlod_distance = float(hlod_profile.get("distance", self._location_mesh_hlod_distance))
        hlod_distance *= max(0.25, float(getattr(self, "_location_mesh_runtime_hlod_scale", 1.0) or 1.0))
        hlod_hysteresis = float(hlod_profile.get("hysteresis", self._location_mesh_hlod_hysteresis))
        hlod_enabled = bool(hlod_profile.get("enabled", self._location_mesh_hlod_enabled))
        hlod_distance = min(max(15.0, hlod_distance), max(15.0, cull_distance - 5.0))
        self._location_mesh_cull_accum += max(0.0, float(dt or 0.0))
        if self._location_mesh_cull_accum < update_interval:
            return
        self._location_mesh_cull_accum = 0.0
        if player_pos is None:
            return

        cluster_modes = (
            self._location_mesh_cluster_modes
            if isinstance(getattr(self, "_location_mesh_cluster_modes", None), dict)
            else {}
        )
        cluster_centers = (
            self._location_mesh_cluster_centers
            if isinstance(getattr(self, "_location_mesh_cluster_centers", None), dict)
            else {}
        )
        hlod_roots = (
            self._location_mesh_hlod_roots
            if isinstance(getattr(self, "_location_mesh_hlod_roots", None), dict)
            else {}
        )
        for cluster_token, center in cluster_centers.items():
            try:
                cluster_dist = float((center - player_pos).length())
            except Exception:
                continue
            current_mode = str(cluster_modes.get(cluster_token, "full") or "full")
            hide_cluster = should_hide_location_mesh_by_distance(
                distance=cluster_dist,
                currently_hidden=(current_mode == "hidden"),
                cull_distance=cull_distance,
                hysteresis=hysteresis,
            )
            if hide_cluster:
                next_mode = "hidden"
            else:
                root = hlod_roots.get(cluster_token)
                use_hlod = bool(hlod_enabled and root and not root.isEmpty())
                if use_hlod and should_use_location_mesh_hlod(
                    distance=cluster_dist,
                    currently_using_hlod=(current_mode == "hlod"),
                    hlod_distance=hlod_distance,
                    hysteresis=hlod_hysteresis,
                ):
                    next_mode = "hlod"
                else:
                    next_mode = "full"
            cluster_modes[cluster_token] = next_mode
            root = hlod_roots.get(cluster_token)
            if root and not root.isEmpty():
                try:
                    if next_mode == "hlod":
                        root.show()
                    else:
                        root.hide()
                except Exception:
                    pass
        self._location_mesh_cluster_modes = cluster_modes

        for node in self._location_mesh_nodes:
            if not node or node.isEmpty():
                continue
            try:
                if str(node.getTag("never_cull") or "") == "1":
                    continue
            except Exception:
                pass
            try:
                dist = float((node.getPos(self.render) - player_pos).length())
            except Exception:
                continue
            try:
                currently_hidden = bool(node.isHidden())
            except Exception:
                currently_hidden = False
            try:
                cluster_token = str(node.getTag("hlod_group") or "").strip().lower()
            except Exception:
                cluster_token = ""
            cluster_mode = str(cluster_modes.get(cluster_token, "") or "")
            if cluster_mode == "hidden":
                if not currently_hidden:
                    try:
                        node.hide()
                    except Exception:
                        pass
                continue
            if cluster_mode == "hlod":
                try:
                    if str(node.getTag("hlod_enabled") or "1") == "1":
                        if not currently_hidden:
                            try:
                                node.hide()
                            except Exception:
                                pass
                        continue
                except Exception:
                    pass
            should_hide = should_hide_location_mesh_by_distance(
                distance=dist,
                currently_hidden=currently_hidden,
                cull_distance=cull_distance,
                hysteresis=hysteresis,
            )
            if should_hide and not currently_hidden:
                try:
                    node.hide()
                except Exception:
                    pass
            elif (not should_hide) and currently_hidden:
                try:
                    node.show()
                except Exception:
                    pass

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

    def _grass_blade_texture(self, size=256):
        if hasattr(self, "_cached_grass_blade_tex"):
            return self._cached_grass_blade_tex

        # Prefer authored alpha textures if they exist.
        alpha_candidates = (
            "assets/textures/grass_blade_alpha.png",
            "assets/textures/grass_cards_alpha.png",
            "assets/textures/foliage_alpha.png",
        )
        for token in alpha_candidates:
            try:
                if not os.path.exists(token):
                    continue
                tex = self.loader.loadTexture(token)
                if not tex:
                    continue
                tex.set_wrap_u(SamplerState.WM_clamp)
                tex.set_wrap_v(SamplerState.WM_clamp)
                tex.set_minfilter(SamplerState.FT_linear_mipmap_linear)
                tex.set_magfilter(SamplerState.FT_linear)
                tex.set_anisotropic_degree(max(4, int(getattr(self, "_grass_anisotropy", 8))))
                self._cached_grass_blade_tex = tex
                return tex
            except Exception:
                continue

        # Runtime fallback with alpha to prevent "cross-card" rectangles.
        side = max(64, int(size))
        img = PNMImage(side, side, 4)
        img.fill(0.0, 0.0, 0.0)
        try:
            img.alpha_fill(0.0)
        except Exception:
            img.alphaFill(0.0)
        centers = [0.18, 0.35, 0.53, 0.72, 0.87]

        for y in range(side):
            v = y / max(1.0, float(side - 1))
            for x in range(side):
                u = x / max(1.0, float(side - 1))
                best_alpha = 0.0
                best_rgb = (0.0, 0.0, 0.0)
                for idx, center in enumerate(centers):
                    bend = (1.0 - v) * (0.05 * math.sin((v * 7.5) + (idx * 1.6)))
                    c = center + bend
                    half_w = 0.008 + ((1.0 - v) ** 1.55) * (0.078 - (abs(center - 0.5) * 0.02))
                    d = abs(u - c)
                    if d > half_w:
                        continue
                    edge = max(0.0, 1.0 - (d / max(1e-5, half_w)))
                    alpha = (edge ** 1.85) * (v ** 0.70)
                    alpha *= 0.76 + (0.24 * (math.sin((u * 46.0) + (v * 17.0)) ** 2))
                    if alpha <= best_alpha:
                        continue
                    hue_shift = idx / max(1.0, float(len(centers) - 1))
                    best_alpha = alpha
                    best_rgb = (
                        0.14 + (0.05 * (1.0 - v)) + (0.02 * hue_shift),
                        0.36 + (0.42 * v) + (0.04 * hue_shift),
                        0.08 + (0.10 * v),
                    )
                if best_alpha > 0.0:
                    img.set_xel_a(
                        x,
                        y,
                        max(0.0, min(1.0, best_rgb[0])),
                        max(0.0, min(1.0, best_rgb[1])),
                        max(0.0, min(1.0, best_rgb[2])),
                        max(0.0, min(1.0, best_alpha)),
                    )

        tex = Texture("proc_grass_blade_alpha")
        tex.load(img)
        tex.set_wrap_u(SamplerState.WM_clamp)
        tex.set_wrap_v(SamplerState.WM_clamp)
        tex.set_minfilter(SamplerState.FT_linear_mipmap_linear)
        tex.set_magfilter(SamplerState.FT_linear)
        tex.set_anisotropic_degree(max(4, int(getattr(self, "_grass_anisotropy", 8))))
        self._cached_grass_blade_tex = tex
        return tex

    def _register_story_anchor(self, anchor_id, node, **kwargs):
        manager = getattr(self.app, "story_interaction", None)
        if not manager or not hasattr(manager, "register_anchor"):
            return False
        try:
            return bool(manager.register_anchor(anchor_id, node, **kwargs))
        except Exception:
            return False

    def _leafy_tree_model_paths(self):
        leafy = self._collect_world_model_paths(
            "trees",
            ["oak_tree_1.glb", "oak_tree_2.glb", "oak_tree_3.glb", "birch_tree_1.glb", "willow_tree_1.glb"],
        )
        if leafy:
            return leafy
        return self._collect_world_model_paths(
            "trees",
            ["common_tree_1.glb", "common_tree_2.glb", "common_tree_3.glb"],
        )

    def _ultimate_sandbox_tree_model_paths(self):
        scenic = self._collect_world_model_paths(
            "trees",
            ["pine_tree_2.glb", "oak_tree_1.glb", "birch_tree_1.glb", "willow_tree_1.glb"],
        )
        if scenic:
            return scenic
        return self._leafy_tree_model_paths()

    def _ultimate_sandbox_portal_anchor_kwargs(self):
        return {
            "name": "Void Portal (Center)",
            "hint": "Teleport to Origin",
            "single_use": False,
            "event_name": "portal_jump",
            "event_payload": {"target": "ultimate_sandbox", "kind": "void"},
        }

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

    def _build_castle_stable(
        self,
        stable_id,
        x,
        y,
        base_z,
        wall_mat,
        roof_mat,
        wood_mat,
        loc_name="Castle Courtyard",
    ):
        width = 8.4
        depth = 4.6
        height = 2.9
        body = self._pl(
            mk_box(f"{stable_id}_body", width, depth, height),
            x,
            y,
            base_z + (height * 0.5),
            self.tx["stone"],
            wall_mat,
            loc_name,
        )

        roof_left = self._pl(
            mk_box(f"{stable_id}_roof_left", width + 0.5, depth * 0.62, 0.18),
            x,
            y - 0.42,
            base_z + height + 0.56,
            self.tx["roof"],
            roof_mat,
            loc_name,
            is_platform=False,
        )
        roof_left.setP(24.0)
        roof_right = self._pl(
            mk_box(f"{stable_id}_roof_right", width + 0.5, depth * 0.62, 0.18),
            x,
            y + 0.42,
            base_z + height + 0.56,
            self.tx["roof"],
            roof_mat,
            loc_name,
            is_platform=False,
        )
        roof_right.setP(-24.0)

        front_y = y - (depth * 0.5) + 0.06
        self._pl(
            mk_box(f"{stable_id}_entrance_beam", width - 0.4, 0.14, 0.20),
            x,
            front_y,
            base_z + 2.0,
            self.tx["bark"],
            wood_mat,
            loc_name,
            is_platform=False,
        )
        for idx, px in enumerate((-3.2, -1.1, 1.1, 3.2)):
            self._pl(
                mk_box(f"{stable_id}_pillar_{idx}", 0.22, 0.22, 2.1),
                x + px,
                front_y,
                base_z + 1.05,
                self.tx["bark"],
                wood_mat,
                loc_name,
                is_platform=False,
            )
            hay = self._pl(
                mk_box(f"{stable_id}_hay_{idx}", 1.2, 0.82, 0.44),
                x + px,
                y + 0.8,
                base_z + 0.22,
                None,
                mk_mat((0.76, 0.66, 0.34, 0.94), 0.48, 0.0),
                loc_name,
                is_platform=False,
            )
            hay.setTransparency(TransparencyAttrib.M_alpha)

        for idx, px in enumerate((-2.2, 0.0, 2.2)):
            self._pl(
                mk_box(f"{stable_id}_stall_divider_{idx}", 0.12, 2.1, 1.5),
                x + px,
                y + 0.2,
                base_z + 0.75,
                self.tx["bark"],
                wood_mat,
                loc_name,
                is_platform=False,
            )

        return body

    def _build_terrain(self):
        t = mk_terrain('terrain', self.terrain_size, self.terrain_res, self._th, self.terrain_data)
        m = mk_mat((0.25,0.45,0.15,1), 1.0, 0.0)
        np = self._pl(t, 0, 0, 0, self.tx['grass'], m, 'Sharuan Plains', is_platform=False)
        self._terrain_node = np
        np.set_tag('type', 'terrain')
        np.set_shader_input("bend_weight", 0.25) # Give it some bend from wind/magic
        quality = str(getattr(self.data_mgr, "graphics_settings", {}).get("quality", "high") or "high").strip().lower()
        tex_scale = 10.0
        if quality == "low":
            tex_scale = 9.0
        elif quality in {"med", "middle", "medium"}:
            tex_scale = 11.5
        elif quality == "ultra":
            tex_scale = 15.0
        else:
            tex_scale = 13.0
        # Tile all texture stages for terrain coverage
        for ts in [TextureStage.get_default()]:
            np.set_tex_scale(ts, tex_scale, tex_scale)
        # Also scale normal and roughness if applied
        children_ts = np.findAllTextureStages()
        for ts in children_ts:
            np.set_tex_scale(ts, tex_scale, tex_scale)

    # ------------------------------------------------------------------
    # Level Editor 2.0 Runtime API
    # ------------------------------------------------------------------

    def update_terrain_collision(self, data_heightmap=None):
        """
        Rebuild the terrain's collision geometry to match the current
        DataHeightmap after sculpting.  We use a mesh-based collision node
        so that it works even without the Bullet physics extension.
        """
        dh = data_heightmap or getattr(self, "terrain_data", None)
        if not dh or not self._terrain_node:
            return
        try:
            from panda3d.core import CollisionNode, CollisionPolygon, Point3
            # Remove old terrain collision node if any
            old_col = self._terrain_node.find("terrain_collision")
            if old_col and not old_col.is_empty():
                old_col.remove_node()

            col_node = CollisionNode("terrain_collision")
            col_node.setFromCollideMask(0)
            col_node.setIntoCollideMask(0x1)

            res = dh.res
            sz = dh.size
            hs = sz / 2
            step = sz / res
            grid = dh.grid

            # Build collision triangles from the heightmap grid
            for iy in range(res):
                for ix in range(res):
                    x0, y0 = -hs + ix * step, -hs + iy * step
                    x1, y1 = x0 + step, y0 + step
                    z00 = grid[iy][ix]
                    z10 = grid[iy][ix + 1]
                    z01 = grid[iy + 1][ix]
                    z11 = grid[iy + 1][ix + 1]
                    col_node.add_solid(CollisionPolygon(
                        Point3(x0, y0, z00),
                        Point3(x1, y0, z10),
                        Point3(x1, y1, z11),
                        Point3(x0, y1, z01),
                    ))

            self._terrain_node.attach_new_node(col_node)
            logger.debug("[SharuanWorld] Terrain collision updated.")
        except Exception as e:
            logger.warning(f"[SharuanWorld] Terrain collision update failed: {e}")

    def spawn_entity(self, data: dict):
        """
        Spawn a new world object in response to an EditorManager spawn_request.
        Delegates to HazardManager for hazard zone registration.
        """
        from managers.hazard_manager import HAZARD_PRESETS
        from world.procedural_builder import mk_box, mk_sphere, mk_cyl, mk_mat
        import uuid

        obj_type = str(data.get("type", "rock"))
        pos = data.get("pos", [0.0, 0.0, 0.0])
        entity_id = f"spawned_{obj_type}_{uuid.uuid4().hex[:6]}"

        shape_map = {
            "rock": (mk_sphere, [entity_id, 0.8, 8, 8], (0.45, 0.42, 0.38, 1)),
            "barrel": (mk_cyl, [entity_id, 0.4, 0.9, 12], (0.55, 0.35, 0.18, 1)),
            "tree_trunk": (mk_cyl, [entity_id, 0.25, 3.0, 8], (0.38, 0.25, 0.14, 1)),
            "chest": (mk_box, [entity_id, 0.8, 0.6, 0.6], (0.72, 0.58, 0.18, 1)),
            "lava_pool": (mk_box, [entity_id, 4.0, 4.0, 0.15], (1.0, 0.28, 0.0, 0.88)),
            "swamp_pool": (mk_box, [entity_id, 4.0, 4.0, 0.15], (0.18, 0.36, 0.10, 0.82)),
            "water_pool": (mk_box, [entity_id, 4.0, 4.0, 0.15], (0.18, 0.50, 0.82, 0.68)),
            "fire_area": (mk_box, [entity_id, 3.0, 3.0, 0.10], (1.0, 0.50, 0.0, 0.75)),
            "poison_cloud": (mk_box, [entity_id, 3.5, 3.5, 0.10], (0.4, 0.8, 0.2, 0.55)),
            "blizzard_zone": (mk_box, [entity_id, 4.5, 4.5, 0.10], (0.65, 0.88, 1.0, 0.60)),
        }

        fn, args, color = shape_map.get(obj_type, (mk_box, [entity_id, 1, 1, 1], (0.6, 0.6, 0.6, 1)))
        nd = fn(*args)
        np = self.render.attach_new_node(nd)
        np.set_pos(pos[0], pos[1], pos[2])
        np.set_tag("entity_id", entity_id)
        np.set_tag("type", obj_type)
        np.set_tag("interactive", "1")
        np.node().set_into_collide_mask(0x1)
        np.set_material(mk_mat(bc=color), 1)

        # Register as hazard if applicable
        hazard_mgr = getattr(self.app, "hazard_manager", None)
        if hazard_mgr and obj_type in HAZARD_PRESETS:
            hazard_mgr.register_zone(entity_id, obj_type, pos, radius=3.0)

        logger.info(f"[SharuanWorld] Spawned '{obj_type}' ({entity_id}) at {pos}")

    def trigger_vfx(self, spell_id: str, pos):
        """Fire a spell's VFX at a world position (called by EditorManager for Magic VFX tests)."""
        if not spell_id or pos is None:
            return
        try:
            from panda3d.core import Point3
            target = Point3(float(pos[0]), float(pos[1]), float(pos[2]))
            spell_mgr = (getattr(self.app, "spell_manager", None)
                         or getattr(self.app, "ability_mgr", None))
            if spell_mgr:
                if hasattr(spell_mgr, "cast_at_point"):
                    spell_mgr.cast_at_point(spell_id, target)
                elif hasattr(spell_mgr, "trigger_spell"):
                    spell_mgr.trigger_spell(spell_id, target)
                logger.info(f"[SharuanWorld] VFX triggered: '{spell_id}' at {pos}")
            else:
                logger.warning("[SharuanWorld] No spell manager found for VFX test.")
        except Exception as e:
            logger.error(f"[SharuanWorld] VFX trigger failed: {e}")

    def _build_sea(self):
        wm = mk_mat((0.10, 0.27, 0.44, 0.84), 0.08, 0.22)
        sea_y = float(self.sea_cfg.get("start_y", -50.0) or -50.0)
        sea_level = float(self.sea_cfg.get("level", -1.5) or -1.5)
        sea = mk_plane('sea', self.terrain_size, 72, 4)
        np = self._pl(sea, 0, sea_y - 30.0, sea_level, self.tx.get("water"), wm, 'Southern Sea', is_platform=False)
        np.set_transparency(TransparencyAttrib.M_alpha)
        np.setColorScale(0.34, 0.58, 0.84, 0.80)
        try:
            for ts in np.findAllTextureStages():
                np.set_tex_scale(ts, 18.0, 18.0)
        except Exception:
            pass
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
            np = self._pl(seg, mx, my, self._th(mx,my)-0.3, self.tx.get("water"), wm, 'River Aran', is_platform=False)
            np.set_h(ang)
            np.set_transparency(TransparencyAttrib.M_alpha)
            np.setColorScale(0.40, 0.66, 0.90, 0.74)
            try:
                for ts in np.findAllTextureStages():
                    np.set_tex_scale(ts, 5.0 + (seg_t * 1.5), 3.2)
            except Exception:
                pass
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

        def place_room_props(room_id, center_x, center_y, room_z, label):
            mat_map = {
                "floor": floor_mat,
                "wall": wall_mat,
                "trim": trim_mat,
                "gold": gold_mat,
            }
            for spec in build_castle_interior_prop_plan(room_id):
                if not isinstance(spec, dict):
                    continue
                prop_id = str(spec.get("id", "prop") or "prop").strip().lower()
                kind = str(spec.get("kind", "box") or "box").strip().lower()
                size = spec.get("size", ())
                pos = spec.get("pos", ())
                if not (isinstance(pos, (list, tuple)) and len(pos) >= 3):
                    continue
                px = center_x + float(pos[0])
                py = center_y + float(pos[1])
                pz = room_z + float(pos[2])

                if kind == "box" and isinstance(size, (list, tuple)) and len(size) >= 3:
                    geom = mk_box(f"{room_id}_{prop_id}", float(size[0]), float(size[1]), float(size[2]))
                elif kind == "cyl" and isinstance(size, (list, tuple)) and len(size) >= 3:
                    geom = mk_cyl(f"{room_id}_{prop_id}", float(size[0]), float(size[1]), int(size[2]))
                elif kind == "sphere" and isinstance(size, (list, tuple)) and len(size) >= 3:
                    geom = mk_sphere(f"{room_id}_{prop_id}", float(size[0]), int(size[1]), int(size[2]))
                elif kind == "plane" and isinstance(size, (list, tuple)) and len(size) >= 2:
                    geom = mk_plane(f"{room_id}_{prop_id}", float(size[0]), float(size[1]), 1.0)
                else:
                    continue

                tex_key = str(spec.get("tex", "stone") or "stone").strip().lower()
                mat_key = str(spec.get("mat", "trim") or "trim").strip().lower()
                tex = self.tx.get(tex_key, self.tx.get("stone"))
                mat = mat_map.get(mat_key, trim_mat)
                prop = self._pl(
                    geom,
                    px,
                    py,
                    pz,
                    tex,
                    mat,
                    label,
                    is_platform=False,
                )
                try:
                    heading = float(spec.get("h", 0.0) or 0.0)
                except Exception:
                    heading = 0.0
                if abs(heading) > 0.01:
                    prop.setH(heading)
                if kind == "plane":
                    prop.setTransparency(TransparencyAttrib.M_alpha)
                    prop.setColorScale(1.0, 1.0, 1.0, 0.95)

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
        place_room_props("prince_chamber", prince_x, prince_y, prince_z, "Prince Chamber")
        place_room_props("world_map_gallery", map_x, map_y, map_z, "World Map Gallery")
        place_room_props("royal_laundry", laundry_x, laundry_y, laundry_z, "Royal Laundry")
        place_room_props("throne_hall", throne_x, throne_y, throne_z, "Throne Hall")

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

        # Use new GLB building models where available, fall back to procedural
        building_models = self._collect_world_model_paths("buildings")
        building_type_map = {
            0: "medieval_tavern",     # main tavern
            1: "medieval_shop",       # general store
            2: "medieval_house_1",
            3: "medieval_blacksmith",
            4: "medieval_house_2",
            5: "medieval_house_1",
            6: "medieval_tower",      # guard tower
            7: "medieval_house_2",
            8: "medieval_shop",
            9: "medieval_house_1",
            10: "medieval_house_2",
            11: "medieval_house_1",
        }

        for idx, (x, y) in enumerate(district_points):
            base_z = self._th(x, y)
            # Try GLB model first
            wanted = building_type_map.get(idx, "medieval_house_1")
            glb_match = None
            for p in building_models:
                if wanted in p:
                    glb_match = p
                    break
            if glb_match:
                heading = (idx * 30.0) % 360.0  # Varied rotation
                self._spawn_world_model(
                    glb_match, x, y, base_z,
                    scale=1.0, h=heading, loc_name="City District", is_platform=True,
                )
            else:
                # Fallback to procedural
                width = 5.0 + (idx % 3) * 0.8
                depth = 4.4 + ((idx + 1) % 3) * 0.7
                height = 3.5 + (idx % 2) * 0.6
                self._build_timber_house(
                    f"house_{idx}",
                    x, y, base_z,
                    width, depth, height,
                    wall_mat, roof_mat, wood_mat,
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
                building_type = str(row.get("type", "house") or "house").strip().lower()
                if building_type in {"stable", "stables", "horse_stable", "courtyard_stable"}:
                    self._build_castle_stable(
                        f"castle_stable_{idx}",
                        x,
                        y,
                        bz,
                        wall_mat,
                        roof_mat,
                        wood_mat,
                        "Castle Courtyard",
                    )
                    continue
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

    def _build_port_moored_boat(
        self,
        boat_id,
        x,
        y,
        water_z,
        heading,
        hull_len,
        hull_beam,
        mast_h,
        wood_mat,
    ):
        hull_len = max(3.2, float(hull_len))
        hull_beam = max(1.0, float(hull_beam))
        mast_h = max(1.8, float(mast_h))

        hull = self._pl(
            mk_sphere(f"{boat_id}_hull_mid", 0.56, 10, 14),
            x,
            y,
            water_z + 0.14,
            self.tx["bark"],
            wood_mat,
            "Port Docks",
            is_platform=False,
        )
        hull.setScale(hull_len * 0.42, hull_beam * 0.64, 0.56)
        hull.setH(heading)

        bow = self._pl(
            mk_cone(f"{boat_id}_bow", hull_beam * 0.34, hull_beam * 0.96, 12),
            x + (math.sin(math.radians(heading)) * (hull_len * 0.48)),
            y + (math.cos(math.radians(heading)) * (hull_len * 0.48)),
            water_z + 0.24,
            self.tx["bark"],
            wood_mat,
            "Port Docks",
            is_platform=False,
        )
        bow.setH(heading)
        bow.setP(90.0)

        stern = self._pl(
            mk_cone(f"{boat_id}_stern", hull_beam * 0.30, hull_beam * 0.82, 12),
            x - (math.sin(math.radians(heading)) * (hull_len * 0.46)),
            y - (math.cos(math.radians(heading)) * (hull_len * 0.46)),
            water_z + 0.26,
            self.tx["bark"],
            mk_mat((0.24, 0.16, 0.10, 1.0), 0.82, 0.02),
            "Port Docks",
            is_platform=False,
        )
        stern.setH(heading + 180.0)
        stern.setP(90.0)

        deck = self._pl(
            mk_box(f"{boat_id}_deck", hull_len * 0.84, hull_beam * 0.72, 0.10),
            x,
            y,
            water_z + 0.58,
            self.tx["bark"],
            mk_mat((0.50, 0.36, 0.22, 1.0), 0.76, 0.03),
            "Port Docks",
            is_platform=False,
        )
        deck.setH(heading)

        mast = self._pl(
            mk_cyl(f"{boat_id}_mast", 0.08, mast_h, 10),
            x + (math.sin(math.radians(heading)) * 0.18),
            y + (math.cos(math.radians(heading)) * 0.18),
            water_z + (0.62 + (mast_h * 0.5)),
            self.tx["bark"],
            wood_mat,
            "Port Docks",
            is_platform=False,
        )
        mast.setH(heading)

        yard = self._pl(
            mk_cyl(f"{boat_id}_yard", 0.04, hull_beam * 1.42, 10),
            x + (math.sin(math.radians(heading)) * 0.22),
            y + (math.cos(math.radians(heading)) * 0.22),
            water_z + (0.62 + (mast_h * 0.66)),
            self.tx["bark"],
            wood_mat,
            "Port Docks",
            is_platform=False,
        )
        yard.setH(heading + 90.0)
        yard.setP(90.0)

        sail = self._pl(
            mk_box(f"{boat_id}_sail", 0.04, hull_beam * 0.96, mast_h * 0.56),
            x + (math.sin(math.radians(heading)) * 0.30),
            y + (math.cos(math.radians(heading)) * 0.30),
            water_z + (0.62 + (mast_h * 0.52)),
            None,
            mk_mat((0.88, 0.84, 0.74, 0.86), 0.52, 0.0),
            "Port Docks",
            is_platform=False,
        )
        sail.setH(heading)
        sail.setTransparency(TransparencyAttrib.M_alpha)

        lantern = self._pl(
            mk_sphere(f"{boat_id}_lantern", 0.09, 7, 8),
            x - (math.sin(math.radians(heading)) * (hull_len * 0.40)),
            y - (math.cos(math.radians(heading)) * (hull_len * 0.40)),
            water_z + 0.88,
            None,
            mk_mat((0.95, 0.78, 0.34, 0.92), 0.12, 0.0),
            "Port Docks",
            is_platform=False,
        )
        lantern.setTransparency(TransparencyAttrib.M_alpha)
        lantern.setColorScale(1.0, 0.86, 0.54, 0.82)

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
                rope = self._pl(
                    mk_cyl(f"port_dock_rope_{idx}", 0.03, max(1.8, sx - 0.5), 6),
                    px,
                    py + (sy * 0.5) - 0.35,
                    pz + 0.44,
                    None,
                    mk_mat((0.34, 0.28, 0.20, 0.82), 0.86, 0.0),
                    "Port Docks",
                    is_platform=False,
                )
                rope.setH(90.0)
                rope.setP(90.0)
                rope.setTransparency(TransparencyAttrib.M_alpha)

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

        boat_rows = port_cfg.get("moored_boats", [])
        if not isinstance(boat_rows, list) or not boat_rows:
            boat_rows = [
                {"pos": [cx - 10.0, cy - 10.5], "heading": 12.0, "hull_len": 4.8, "hull_beam": 1.4, "mast_h": 2.6},
                {"pos": [cx - 2.5, cy - 13.3], "heading": -14.0, "hull_len": 5.0, "hull_beam": 1.5, "mast_h": 2.8},
                {"pos": [cx + 5.0, cy - 10.5], "heading": 12.0, "hull_len": 4.9, "hull_beam": 1.4, "mast_h": 2.6},
                {"pos": [cx + 12.5, cy - 13.3], "heading": -14.0, "hull_len": 5.1, "hull_beam": 1.5, "mast_h": 2.9},
            ]

        for bidx, row in enumerate(boat_rows):
            if not isinstance(row, dict):
                continue
            pos = row.get("pos", [])
            if not (isinstance(pos, list) and len(pos) >= 2):
                continue
            try:
                bx = float(pos[0]); by = float(pos[1])
                heading = float(row.get("heading", 0.0) or 0.0)
                hull_len = float(row.get("hull_len", 4.8) or 4.8)
                hull_beam = float(row.get("hull_beam", 1.4) or 1.4)
                mast_h = float(row.get("mast_h", 2.6) or 2.6)
            except Exception:
                continue
            water_z = self.sample_water_height(bx, by)
            self._build_port_moored_boat(
                f"port_boat_{bidx}",
                bx,
                by,
                water_z,
                heading,
                hull_len,
                hull_beam,
                mast_h,
                wood_mat,
            )

        lantern_rows = port_cfg.get("harbor_lanterns", [])
        if isinstance(lantern_rows, list):
            for lidx, row in enumerate(lantern_rows):
                if not isinstance(row, dict):
                    continue
                pos = row.get("pos", [])
                if not (isinstance(pos, list) and len(pos) >= 2):
                    continue
                try:
                    lx = float(pos[0]); ly = float(pos[1])
                except Exception:
                    continue
                lz = self._th(lx, ly)
                self._pl(
                    mk_cyl(f"port_lantern_post_{lidx}", 0.09, 2.2, 9),
                    lx,
                    ly,
                    lz + 1.1,
                    self.tx["bark"],
                    wood_mat,
                    "Port Docks",
                    is_platform=False,
                )
                glow = self._pl(
                    mk_sphere(f"port_lantern_glow_{lidx}", 0.14, 7, 8),
                    lx,
                    ly,
                    lz + 2.35,
                    None,
                    mk_mat((0.96, 0.82, 0.42, 0.88), 0.12, 0.0),
                    "Port Docks",
                    is_platform=False,
                )
                glow.setTransparency(TransparencyAttrib.M_alpha)
                glow.setColorScale(1.0, 0.88, 0.56, 0.78)

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
        stone_model_pool = self._collect_world_model_paths(
            "props",
            ["stone_1.glb", "stone_2.glb", "stone_3.glb"],
        )
        ambient_prop_pool = self._collect_world_model_paths(
            "props",
            [
                "bush_1.glb",
                "bush_2.glb",
                "bush_3.glb",
                "plant_1.glb",
                "plant_2.glb",
                "mushroom_group_1.glb",
            ],
        )

        # --- Smarter boulder distribution with spacing/exclusion logic ---
        def _boulder_accept(px, py):
            if py < -42.0:
                return False
            if self._distance_to_river(px, py) < 5.8:
                return False
            if (px * px + py * py) < 260.0:
                return False
            if abs(px) < 6.0 and -6.0 <= py <= 54.0:
                return False
            if self._th(px, py) < -1.0:
                return False
            return True

        boulder_positions = self._scatter_points(
            count=24,
            x_range=(-60.0, 62.0),
            y_range=(-34.0, 72.0),
            min_spacing=11.2,
            rng=rng,
            max_tries_per_point=72,
            accept_fn=_boulder_accept,
        )
        for i, (bx, by) in enumerate(boulder_positions):
            bz = self._th(bx, by)
            if stone_model_pool:
                model_path = stone_model_pool[i % len(stone_model_pool)]
                model = self._spawn_world_model(
                    model_path,
                    bx,
                    by,
                    bz + 0.02,
                    scale=rng.uniform(1.2, 2.9),
                    h=rng.uniform(-180.0, 180.0),
                    loc_name="Sharuan Plains",
                    is_platform=False,
                )
                if model:
                    continue
            r = rng.uniform(0.48, 1.35)
            squash = rng.uniform(0.78, 1.08)
            core = self._pl(
                mk_sphere(f"boulder_{i}", r, 9, 12),
                bx, by, bz + (r * 0.34),
                self.tx["stone"], stone_mat, "Sharuan Plains"
            )
            core.setScale(1.0, 1.0, squash)
            if i % 3 == 0:
                cap = self._pl(
                    mk_sphere(f"boulder_cap_{i}", r * 0.42, 7, 9),
                    bx + rng.uniform(-0.24, 0.24),
                    by + rng.uniform(-0.24, 0.24),
                    bz + (r * 0.82),
                    self.tx["stone"],
                    mk_mat((0.56, 0.54, 0.50, 1.0), 0.46, 0.0),
                    "Sharuan Plains",
                    is_platform=False,
                )
                cap.setColorScale(1.0, 1.0, 1.0, 0.92)

        if ambient_prop_pool:
            def _prop_accept(px, py):
                if self._distance_to_river(px, py) < 3.8:
                    return False
                if self._th(px, py) < -0.6:
                    return False
                if abs(px) < 5.0 and -4.0 <= py <= 58.0:
                    return False
                return True

            ambient_points = self._scatter_points(
                count=58,
                x_range=(-72.0, 84.0),
                y_range=(-32.0, 76.0),
                min_spacing=4.2,
                rng=random.Random(420420),
                max_tries_per_point=72,
                accept_fn=_prop_accept,
            )
            for idx, (px, py) in enumerate(ambient_points):
                pz = self._th(px, py)
                model_path = ambient_prop_pool[idx % len(ambient_prop_pool)]
                node = self._spawn_world_model(
                    model_path,
                    px,
                    py,
                    pz + 0.02,
                    scale=rng.uniform(0.86, 1.44),
                    h=rng.uniform(-180.0, 180.0),
                    loc_name="Wild Props",
                    is_platform=False,
                )
                if not node:
                    continue

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
        clutter_rng = random.Random(42013)
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
            # Smarter clutter placement around stalls: weighted props with local spacing.
            clutter_offsets = [(-1.6, 1.2), (-0.4, 1.4), (0.8, 1.2), (1.7, 1.0), (-1.5, -1.3), (1.5, -1.3)]
            clutter_rng.shuffle(clutter_offsets)
            used = []
            placed = 0
            for ox, oy in clutter_offsets:
                if placed >= 3:
                    break
                if any(((ox - ux) ** 2 + (oy - uy) ** 2) < 0.55 for ux, uy in used):
                    continue
                px = sx + ox + clutter_rng.uniform(-0.12, 0.12)
                py = sy + oy + clutter_rng.uniform(-0.12, 0.12)
                pz = self._th(px, py)
                token = "crate" if clutter_rng.random() < 0.56 else "barrel"
                if token == "crate":
                    self._pl(
                        mk_box(f"stall_crate_{i}_{placed}", 0.58, 0.58, 0.46),
                        px,
                        py,
                        pz + 0.24,
                        self.tx["bark"],
                        mk_mat((0.42, 0.31, 0.20, 1.0), 0.80, 0.02),
                        "Market Square",
                        is_platform=False,
                    )
                else:
                    self._pl(
                        mk_cyl(f"stall_barrel_{i}_{placed}", 0.30, 0.62, 10),
                        px,
                        py,
                        pz + 0.31,
                        self.tx["bark"],
                        mk_mat((0.36, 0.28, 0.18, 1.0), 0.82, 0.03),
                        "Market Square",
                        is_platform=False,
                    )
                used.append((ox, oy))
                placed += 1

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

        # Adrian's cage landmark inside Kremor.
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
                    self.tx["stone"], stone_mat, "Kremor Cage Clearing", is_platform=False
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
                    self.tx["stone"], stone_mat, "Kremor Cage Clearing", is_platform=False
                )
                door.setH(-24.0)
            except Exception:
                pass

        # Kremor Obsidian Palace (Centerpiece)
        try:
            px, py = 76.0, 12.0
            pz = self._th(px, py)
            obsidian_mat = mk_mat((0.05, 0.04, 0.08, 1.0), 0.95, 0.2) # Very dark, glossy
            # Main Keep
            self._pl(
                mk_box("obsidian_palace_keep", 18.0, 18.0, 24.0),
                px, py, pz + 12.0,
                self.tx["stone"], obsidian_mat, "Kremor Obsidian Palace"
            )
            # Towers
            for ox, oy in [(-10, -10), (10, -10), (10, 10), (-10, 10)]:
                self._pl(
                    mk_cyl(f"obsidian_tower_{ox}_{oy}", 3.5, 32.0, 8),
                    px + ox, py + oy, pz + 16.0,
                    self.tx["stone"], obsidian_mat, "Kremor Obsidian Palace"
                )
            # Spikes/Pinnacles
            for ox, oy in [(-6, 0), (6, 0), (0, -6), (0, 6)]:
                self._pl(
                    mk_cone(f"obsidian_spike_{ox}_{oy}", 1.5, 8.0, 6),
                    px + ox, py + oy, pz + 24.0,
                    self.tx["stone"], obsidian_mat, "Kremor Obsidian Palace"
                )
        except Exception as e:
            logger.warning(f"[SharuanWorld] Failed to build Obsidian Palace: {e}")

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
        tx, ty = TRAINING_GROUNDS_CENTER
        center_z = self._th(tx, ty)
        stone_mat = mk_mat((0.52, 0.49, 0.45, 1.0), 0.72, 0.02)
        dirt_mat = mk_mat((0.42, 0.35, 0.26, 1.0), 0.88, 0.0)
        water_mat = mk_mat((0.12, 0.30, 0.50, 0.82), 0.15, 0.18)
        wood_mat = mk_mat((0.32, 0.22, 0.14, 1.0), 0.78, 0.0)
        accent_mat = mk_mat((0.62, 0.56, 0.40, 1.0), 0.52, 0.04)
        plaza_half_w, plaza_half_h = TRAINING_PLAZA_HALF_EXTENTS

        # Ground platform / sprint lane base.
        self._pl(
            mk_plane("training_plaza", plaza_half_w * 2.0, plaza_half_h * 2.0, 2.6),
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

        # Stealth + climb lane: narrow alleys, cover blocks, and climb towers.
        st_x = tx + 54.0
        st_y = ty + 0.5
        st_z = self._th(st_x, st_y)
        self._pl(
            mk_plane("stealth_climb_plaza", 24.0, 16.0, 2.0),
            st_x,
            st_y,
            st_z + 0.03,
            self.tx["stone"],
            stone_mat,
            "Stealth Climb Grounds",
            is_platform=False,
        )

        # Side walls forming a stealth corridor.
        for idx, offset in enumerate((-7.2, 7.2)):
            wx = st_x + offset
            wy = st_y + 0.5
            wz = self._th(wx, wy)
            self._pl(
                mk_box(f"stealth_wall_{idx}", 1.0, 14.4, 5.8),
                wx,
                wy,
                wz + 2.9,
                self.tx["stone"],
                stone_mat,
                "Stealth Climb Grounds",
            )

        # Cover blocks for crouch and stealth weaving.
        cover_specs = [
            (st_x - 2.0, st_y - 5.0, 2.8, 1.3),
            (st_x + 2.8, st_y - 2.6, 3.0, 1.5),
            (st_x - 1.6, st_y + 1.2, 2.6, 1.4),
            (st_x + 3.4, st_y + 4.0, 3.2, 1.6),
        ]
        for idx, (cx, cy, cw, ch) in enumerate(cover_specs):
            cz = self._th(cx, cy)
            self._pl(
                mk_box(f"stealth_cover_{idx}", cw, 1.0, ch),
                cx,
                cy,
                cz + (ch * 0.5),
                self.tx["stone"],
                stone_mat,
                "Stealth Climb Grounds",
            )

        # Climb towers and catwalk for repeated climb jumps.
        tower_specs = [
            (st_x - 5.0, st_y + 6.0, 5.4),
            (st_x + 5.2, st_y + 6.2, 6.1),
        ]
        for idx, (cx, cy, th) in enumerate(tower_specs):
            cz = self._th(cx, cy)
            self._pl(
                mk_box(f"stealth_tower_{idx}", 2.8, 2.8, th),
                cx,
                cy,
                cz + (th * 0.5),
                self.tx["stone"],
                stone_mat,
                "Stealth Climb Grounds",
            )

        bridge_z = max(self._th(st_x - 5.0, st_y + 6.0), self._th(st_x + 5.2, st_y + 6.2)) + 5.9
        self._pl(
            mk_box("stealth_catwalk", 10.8, 1.1, 0.35),
            st_x + 0.1,
            st_y + 6.1,
            bridge_z,
            self.tx["bark"],
            wood_mat,
            "Stealth Climb Grounds",
        )

        # Minimal jump posts for clean parkour readout in capture.
        for idx in range(4):
            jx = st_x - 3.0 + (idx * 2.1)
            jy = st_y + 9.5
            jz = self._th(jx, jy)
            post_h = 1.4 + (idx * 0.75)
            self._pl(
                mk_box(f"stealth_jump_post_{idx}", 0.9, 0.9, post_h),
                jx,
                jy,
                jz + (post_h * 0.5),
                self.tx["stone"],
                stone_mat,
                "Stealth Climb Grounds",
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

        for row in build_training_flight_gate_plan((tx, ty)):
            sx, sy, sz = row.get("size", (1.0, 1.0, 1.0))
            px, py, pz = row.get("pos", (0.0, 0.0, 0.0))
            material = accent_mat if row.get("material") == "accent" else wood_mat
            self._pl(
                mk_box(str(row.get("id", "flight_gate")), float(sx), float(sy), float(sz)),
                px,
                py,
                pz,
                self.tx["bark"],
                material,
                "Coastal Flight Grounds",
                is_platform=False,
            )

        # Shallow water pool for swim test.
        pool_x, pool_y = TRAINING_POOL_CENTER
        pool_half_w, pool_half_h = TRAINING_POOL_HALF_EXTENTS
        pool_z = self._th(pool_x, pool_y) - TRAINING_POOL_SURFACE_OFFSET
        pool = self._pl(
            mk_plane("training_pool", pool_half_w * 2.0, pool_half_h * 2.0, 1.6),
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
            p.aabb.min = gc.Vec3(pool_x - pool_half_w, pool_y - pool_half_h, pool_z - 2.5)
            p.aabb.max = gc.Vec3(pool_x + pool_half_w, pool_y + pool_half_h, pool_z + 0.1)
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
                    if row_id != zid:
                        continue
                    try:
                        x = float(center[0]); y = float(center[1]); z = float(center[2]) if len(center) >= 3 else 0.0
                        return x, y, z
                    except Exception:
                        pass
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
        soot_dark = mk_mat((0.10, 0.10, 0.12, 1.0), 0.86, 0.0)

        def spawn_torch(tid, x, y, z, location_name):
            self._pl(
                mk_cyl(f"dwarf_torch_pole_{tid}", 0.10, 2.2, 8),
                x, y, z + 1.10,
                self.tx["stone"], iron_dark, location_name
            )
            flame = self._pl(
                mk_cone(f"dwarf_torch_flame_{tid}", 0.22, 0.55, 8),
                x, y + 0.06, z + 2.45,
                None, ember, location_name, is_platform=False
            )
            flame.setColorScale(1.0, 0.56, 0.22, 0.90)
            flame.set_transparency(TransparencyAttrib.M_alpha)
            try:
                point = PointLight(f"dwarf_torch_light_{tid}")
                point.setColor((0.95, 0.66, 0.36, 1.0))
                point.setAttenuation((1.0, 0.065, 0.006))
                point_np = self.render.attachNewNode(point)
                point_np.setPos(x, y, z + 2.25)
                self.render.setLight(point_np)
            except Exception:
                pass

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
        hall_dome = self._pl(
            mk_sphere("dwarf_hall_dome", 16.0, 12, 14),
            halls_x,
            halls_y,
            hall_floor_z + 11.0,
            self.tx["stone"],
            mk_mat((0.24, 0.24, 0.28, 0.9), 0.94, 0.0),
            "Dwarven Forge Halls",
            is_platform=False,
        )
        hall_dome.setTwoSided(True)

        # Cave roof shells block sky and keep the zone visually subterranean.
        cave_canopies = [
            ("gate", gate_x, gate_y, 12.5, 8.6, "Dwarven Caves Gate"),
            ("halls", halls_x, halls_y, 18.0, 11.2, "Dwarven Forge Halls"),
            ("throne", throne_x, throne_y, 16.0, 10.4, "Dwarven Grand Throne"),
        ]
        for cid, cx, cy, radius, z_off, loc_name in cave_canopies:
            floor_z = self._th(cx, cy)
            canopy = self._pl(
                mk_sphere(f"dwarf_cave_canopy_{cid}", radius, 14, 16),
                cx,
                cy,
                floor_z + z_off,
                self.tx["stone"],
                soot_dark,
                loc_name,
                is_platform=False,
            )
            canopy.setTwoSided(True)
            canopy.setColorScale(0.62, 0.62, 0.66, 0.96)
            cap = self._pl(
                mk_cyl(f"dwarf_cave_cap_{cid}", radius * 0.82, 0.70, 20),
                cx,
                cy,
                floor_z + z_off + (radius * 0.56),
                self.tx["stone"],
                soot_dark,
                loc_name,
                is_platform=False,
            )
            cap.setTwoSided(True)

        # Torch route: keeps caves readable and visibly subterranean.
        torch_points = [
            ("gate_l", gate_x - 2.8, gate_y + 1.6, self._th(gate_x - 2.8, gate_y + 1.6), "Dwarven Caves Gate"),
            ("gate_r", gate_x + 2.8, gate_y + 1.6, self._th(gate_x + 2.8, gate_y + 1.6), "Dwarven Caves Gate"),
            ("halls_l", halls_x - 4.6, halls_y - 2.2, self._th(halls_x - 4.6, halls_y - 2.2), "Dwarven Forge Halls"),
            ("halls_r", halls_x + 4.6, halls_y - 2.2, self._th(halls_x + 4.6, halls_y - 2.2), "Dwarven Forge Halls"),
            ("throne_l", throne_x - 5.1, throne_y + 0.6, self._th(throne_x - 5.1, throne_y + 0.6), "Dwarven Grand Throne"),
            ("throne_r", throne_x + 5.1, throne_y + 0.6, self._th(throne_x + 5.1, throne_y + 0.6), "Dwarven Grand Throne"),
        ]
        for tid, tx, ty, tz, loc_name in torch_points:
            spawn_torch(tid, tx, ty, tz, loc_name)

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

    def _is_in_kremor(self, x, y):
        # Kremor center is (84, -12), radius 32
        dx = x - 84.0
        dy = y - (-12.0)
        return (dx * dx + dy * dy) < (32.0 * 32.0)

    def _build_flora_fauna(self):
        bark_mat = mk_mat((0.33, 0.24, 0.16, 1.0), 0.86, 0.02)
        bark_dark = mk_mat((0.26, 0.19, 0.12, 1.0), 0.92, 0.00)
        leaf_oak = mk_mat((0.19, 0.45, 0.20, 1.0), 0.78, 0.00)
        leaf_pine = mk_mat((0.14, 0.36, 0.16, 1.0), 0.86, 0.00)
        leaf_birch = mk_mat((0.31, 0.56, 0.27, 1.0), 0.70, 0.00)
        rng = random.Random(20260223)

        tree_profiles = [
            {"name": "oak", "leaf": leaf_oak, "canopy_scale": 1.0, "spire": False},
            {"name": "pine", "leaf": leaf_pine, "canopy_scale": 0.82, "spire": True},
            {"name": "birch", "leaf": leaf_birch, "canopy_scale": 0.92, "spire": False},
        ]
        broadleaf_models = self._leafy_tree_model_paths()
        pine_models = self._collect_world_model_paths(
            "trees",
            ["pine_tree_1.glb", "pine_tree_2.glb", "pine_tree_3.glb"],
        )
        dead_models = self._collect_world_model_paths(
            "trees",
            ["dead_tree_1.glb", "dead_tree_2.glb"],
        )
        stump_models = self._collect_world_model_paths(
            "trees",
            ["tree_stump_1.glb", "tree_stump_2.glb"],
        )
        undergrowth_models = self._collect_world_model_paths(
            "props",
            ["bush_1.glb", "bush_2.glb", "bush_3.glb", "plant_1.glb", "plant_2.glb"],
        )

        def _tree_accept(px, py):
            if py < -40.0:
                return False
            if self._distance_to_river(px, py) < 5.2:
                return False
            if self._th(px, py) < -0.8:
                return False
            if abs(px) < 5.4 and -4.0 <= py <= 54.0:
                return False
            if self._is_in_kremor(px, py):
                return False
            return True

        quality = str(getattr(self.data_mgr, "graphics_settings", {}).get("quality", "high") or "high").strip().lower()
        tree_budget = 86
        if quality == "low":
            tree_budget = 52
        elif quality in {"med", "middle", "medium"}:
            tree_budget = 68
        elif quality == "ultra":
            tree_budget = 108
        tree_scatter_count = max(tree_budget + 20, int(tree_budget * 1.24))

        tree_positions = self._scatter_points(
            count=tree_scatter_count,
            x_range=(-90.0, 90.0),
            y_range=(-38.0, 90.0),
            min_spacing=8.2,
            rng=rng,
            max_tries_per_point=84,
            accept_fn=_tree_accept,
        )
        tree_positions.sort(key=lambda p: (p[1], p[0]))
        foliage_tex = self._grass_blade_texture(256)

        for idx, (x, y) in enumerate(tree_positions[:tree_budget]):
            z = self._th(x, y)
            profile = tree_profiles[idx % len(tree_profiles)]
            tree_model_pool = broadleaf_models
            if profile["name"] == "pine":
                tree_model_pool = pine_models if pine_models else broadleaf_models
            elif idx % 11 == 0 and dead_models:
                tree_model_pool = dead_models
            if tree_model_pool:
                model_path = tree_model_pool[idx % len(tree_model_pool)]
                base_scale = 1.08 if profile["name"] == "pine" else 0.98
                tree_node = self._spawn_world_model(
                    model_path,
                    x,
                    y,
                    z + 0.02,
                    scale=base_scale * rng.uniform(0.88, 1.28),
                    h=rng.uniform(-180.0, 180.0),
                    loc_name="Wild Grove",
                    is_platform=False,
                )
                if tree_node:
                    tint = rng.uniform(0.94, 1.08)
                    try:
                        tree_node.setColorScale(tint * 1.02, tint, tint * 0.96, 1.0)
                    except Exception:
                        pass
                    if undergrowth_models and idx % 2 == 0:
                        for uidx in range(2):
                            ux = x + rng.uniform(-1.6, 1.6)
                            uy = y + rng.uniform(-1.6, 1.6)
                            uz = self._th(ux, uy)
                            u_path = undergrowth_models[(idx + uidx) % len(undergrowth_models)]
                            self._spawn_world_model(
                                u_path,
                                ux,
                                uy,
                                uz + 0.02,
                                scale=rng.uniform(0.72, 1.18),
                                h=rng.uniform(-180.0, 180.0),
                                loc_name="Wild Grove",
                                is_platform=False,
                            )
                    if stump_models and idx % 6 == 0:
                        s_path = stump_models[idx % len(stump_models)]
                        sx = x + rng.uniform(-1.2, 1.2)
                        sy = y + rng.uniform(-1.2, 1.2)
                        sz = self._th(sx, sy)
                        self._spawn_world_model(
                            s_path,
                            sx,
                            sy,
                            sz + 0.02,
                            scale=rng.uniform(0.86, 1.22),
                            h=rng.uniform(-180.0, 180.0),
                            loc_name="Wild Grove",
                            is_platform=False,
                        )

        def _grass_accept(px, py):
            if py < -40.0:
                return False
            if self._distance_to_river(px, py) < 2.6:
                return False
            if self._th(px, py) < -0.4:
                return False
            if abs(px) < 5.2 and -8.0 <= py <= 56.0:
                return False
            if self._is_in_kremor(px, py):
                return False
            return True

        grass_patch_count = 18
        grass_density = 0.94
        if quality == "low":
            grass_patch_count = 10
            grass_density = 0.62
        elif quality in {"med", "middle", "medium"}:
            grass_patch_count = 14
            grass_density = 0.80
        elif quality == "ultra":
            grass_patch_count = 24
            grass_density = 1.12

        grass_points = self._scatter_points(
            count=grass_patch_count,
            x_range=(-88.0, 88.0),
            y_range=(-36.0, 90.0),
            min_spacing=14.0,
            rng=random.Random(20260229),
            max_tries_per_point=96,
            accept_fn=_grass_accept,
        )
        for gx, gy in grass_points:
            extent = rng.uniform(12.0, 19.5)
            density = grass_density * rng.uniform(0.85, 1.24)
            self._spawn_gpu_grass(gx, gy, 0.0, extent, density=density, tex=foliage_tex)

    # ------------------------------------------------------------------ #
    #  _enhance_water_surfaces                                             #
    # ------------------------------------------------------------------ #
    def _enhance_water_surfaces(self):
        """Apply enhanced colors/animation params to previously built water surfaces.

        Reads water_config.json for color/wave overrides and applies them to
        the _water_surfaces list that _build_sea already populated.
        """
        wcfg = {}
        try:
            wcfg_attr = getattr(getattr(self, "app", None), "data_mgr", None)
            if wcfg_attr:
                wcfg = getattr(wcfg_attr, "water_config", {}) or {}
        except Exception:
            wcfg = {}
        if not isinstance(wcfg, dict):
            wcfg = {}

        if not wcfg and getattr(self, "app", None) is not None:
            wcfg = load_data_file(self.app, "water_config.json", default={})
        if not isinstance(wcfg, dict):
            wcfg = {}

        shallow = wcfg.get("color", {}).get("shallow", [0.24, 0.55, 0.82, 0.62])
        mid = wcfg.get("color", {}).get("mid", [0.14, 0.38, 0.66, 0.72])
        deep = wcfg.get("color", {}).get("deep", [0.06, 0.18, 0.46, 0.84])
        river_col = wcfg.get("color", {}).get("river", [0.18, 0.46, 0.72, 0.58])
        foam_col = wcfg.get("color", {}).get("river_foam", [0.72, 0.84, 0.92, 0.38])
        wave_h = float(wcfg.get("wave_height", 0.22))
        wave_speed = float(wcfg.get("wave_speed", 0.65))

        for surf in getattr(self, "_water_surfaces", []):
            kind = str(surf.get("kind", "") or "")
            node = surf.get("node")
            if not node or node.isEmpty():
                continue
            try:
                if kind == "sea":
                    sea_col = [
                        (float(shallow[0]) * 0.45) + (float(mid[0]) * 0.35) + (float(deep[0]) * 0.20),
                        (float(shallow[1]) * 0.45) + (float(mid[1]) * 0.35) + (float(deep[1]) * 0.20),
                        (float(shallow[2]) * 0.45) + (float(mid[2]) * 0.35) + (float(deep[2]) * 0.20),
                        max(0.60, min(0.92, (float(shallow[3]) * 0.55) + (float(deep[3]) * 0.45))),
                    ]
                    node.setColorScale(*sea_col)
                    surf["amp"] = wave_h * 1.05
                    surf["speed"] = wave_speed * 0.8
                elif kind == "sea_foam":
                    node.setColorScale(*foam_col)
                    surf["amp"] = wave_h * 0.22
                    surf["speed"] = wave_speed * 1.8
                elif kind == "river":
                    node.setColorScale(*river_col)
                    surf["amp"] = wave_h * 0.4
                    surf["speed"] = wave_speed * 1.2
                elif kind == "river_foam":
                    node.setColorScale(*foam_col)
                    surf["amp"] = wave_h * 0.14
                    surf["speed"] = wave_speed * 2.0
            except Exception:
                pass

        # Add second river-foam pass for readability
        if not hasattr(self, "_river_foam_added"):
            self._river_foam_added = True
            wm_foam = mk_mat(
                (float(foam_col[0]), float(foam_col[1]), float(foam_col[2]), float(foam_col[3])),
                0.10, 0.0
            )
            for i in range(len(self.RIVER) - 1):
                ax, ay = self.RIVER[i]; bx, by = self.RIVER[i + 1]
                mx, my = (ax + bx) / 2, (ay + by) / 2
                dx, dy = bx - ax, by - ay
                ln = math.sqrt(dx * dx + dy * dy)
                ang = math.degrees(math.atan2(dx, dy))
                seg_t = i / max(1, len(self.RIVER) - 1)
                w0 = float(self.river_cfg.get("width_start", 3.0) or 3.0)
                w1 = float(self.river_cfg.get("width_end", 6.0) or 6.0)
                w = (w0 + ((w1 - w0) * seg_t)) * 1.55
                base_z = self._th(mx, my) - 0.28
                foam_np = self._pl(
                    mk_plane(f"river_foam_{i}", w, ln * 0.9, 4.0),
                    mx, my, base_z + 0.05,
                    None, wm_foam, "River Aran", is_platform=False,
                )
                foam_np.set_h(ang)
                foam_np.set_transparency(TransparencyAttrib.M_alpha)
                self._water_surfaces.append({
                    "kind": "river_foam",
                    "node": foam_np,
                    "base_z": base_z + 0.05,
                    "amp": wave_h * 0.12,
                    "speed": wave_speed * 2.2,
                    "phase": i * 0.62,
                })

        logger.info("[SharuanWorld] Water surfaces enhanced.")

    # ------------------------------------------------------------------ #
    #  _build_bridge                                                       #
    # ------------------------------------------------------------------ #
    def _build_bridge(self):
        """Construct a procedural stone arch bridge over the river.

        Bridge position is read from layout.json story_landmarks.sharuan_bridge.
        """
        landmarks = self.layout.get("story_landmarks", {}) if isinstance(self.layout.get("story_landmarks"), dict) else {}
        bridge_cfg = landmarks.get("sharuan_bridge", {}) if isinstance(landmarks.get("sharuan_bridge"), dict) else {}

        center = bridge_cfg.get("center", [-22.0, 20.0])
        cx = float(center[0]) if isinstance(center, list) and len(center) >= 2 else -22.0
        cy = float(center[1]) if isinstance(center, list) and len(center) >= 2 else 20.0
        length = float(bridge_cfg.get("length", 10.0))
        width = float(bridge_cfg.get("width", 3.2))
        arch_count = int(bridge_cfg.get("arch_count", 3))
        bz = self._th(cx, cy) - 0.2

        stone_mat = mk_mat((0.54, 0.52, 0.48, 1.0), 0.88, 0.04)
        stone_dark = mk_mat((0.38, 0.36, 0.34, 1.0), 0.82, 0.03)
        mortar_mat = mk_mat((0.64, 0.62, 0.58, 1.0), 0.80, 0.04)

        # Deck planks / stone slab
        deck = self._pl(
            mk_box("bridge_deck", width, length, 0.28),
            cx, cy, bz + 0.14,
            None, mortar_mat, "Sharuan Forest Bridge", is_platform=True,
        )
        _ = deck  # suppress lint

        # Walkway surface (slightly lighter)
        walk_mat = mk_mat((0.68, 0.66, 0.60, 1.0), 0.76, 0.05)
        self._pl(
            mk_box("bridge_walkway", width - 0.4, length - 0.2, 0.06),
            cx, cy, bz + 0.30,
            None, walk_mat, "Sharuan Forest Bridge", is_platform=False,
        )

        # Arches — each arch is a pair of pillars + arch keystone box
        seg_length = length / max(1, arch_count)
        pillar_h = 2.6
        keystone_h = 0.55

        for i in range(arch_count):
            arch_y = cy - (length * 0.5) + (seg_length * (i + 0.5))
            arch_pz = bz - pillar_h * 0.5

            # Left pillar
            self._pl(
                mk_cyl(f"bridge_pillar_L{i}", 0.30, pillar_h, 8),
                cx - width * 0.48, arch_y, arch_pz,
                None, stone_dark, "Sharuan Forest Bridge", is_platform=True,
            )
            # Right pillar
            self._pl(
                mk_cyl(f"bridge_pillar_R{i}", 0.30, pillar_h, 8),
                cx + width * 0.48, arch_y, arch_pz,
                None, stone_dark, "Sharuan Forest Bridge", is_platform=True,
            )
            # Arch keystone (box bridging pillars)
            self._pl(
                mk_box(f"bridge_arch_{i}", width, 0.60, keystone_h),
                cx, arch_y, bz - 0.06,
                None, stone_mat, "Sharuan Forest Bridge", is_platform=True,
            )

        # Railings — left & right rows of railing posts
        post_count = max(4, int(length / 1.4))
        post_spacing = length / max(1, post_count - 1)
        railing_h = float(bridge_cfg.get("railing_height", 0.90))
        for i in range(post_count):
            py = cy - (length * 0.5) + (i * post_spacing)
            # Left railing post
            self._pl(
                mk_box(f"bridge_rail_post_L{i}", 0.12, 0.12, railing_h),
                cx - width * 0.52, py, bz + 0.28 + railing_h * 0.5,
                None, stone_dark, "Sharuan Forest Bridge", is_platform=False,
            )
            # Right railing post
            self._pl(
                mk_box(f"bridge_rail_post_R{i}", 0.12, 0.12, railing_h),
                cx + width * 0.52, py, bz + 0.28 + railing_h * 0.5,
                None, stone_dark, "Sharuan Forest Bridge", is_platform=False,
            )

        # Top rails (horizontal bars)
        self._pl(
            mk_box("bridge_top_rail_L", 0.10, length, 0.10),
            cx - width * 0.52, cy, bz + 0.28 + railing_h,
            None, mortar_mat, "Sharuan Forest Bridge", is_platform=False,
        )
        self._pl(
            mk_box("bridge_top_rail_R", 0.10, length, 0.10),
            cx + width * 0.52, cy, bz + 0.28 + railing_h,
            None, mortar_mat, "Sharuan Forest Bridge", is_platform=False,
        )

        # Physics collision for the deck
        if self.phys:
            try:
                p = gc.Platform()
                p.aabb.min = gc.Vec3(cx - width, cy - length * 0.5, bz - 0.2)
                p.aabb.max = gc.Vec3(cx + width, cy + length * 0.5, bz + 0.36)
                self.phys.addPlatform(p)
            except Exception:
                pass

        logger.info(f"[SharuanWorld] Bridge built at ({cx:.1f}, {cy:.1f}) length={length:.1f} arches={arch_count}")

    # ------------------------------------------------------------------ #
    #  _place_zone_props                                                   #
    # ------------------------------------------------------------------ #
    def _place_zone_props(self):
        """Scatter data-driven props in zones defined in prop_rules.json.

        Reads prop_rules.json (data/world/prop_rules.json), resolves each zone
        center and radius from layout.json zones list, and distributes props
        using seeded random inside each zone circle while respecting min_spacing.
        Falls back gracefully if no prop model files exist (uses procedural boxes).
        """
        rules = {}
        data_mgr = getattr(getattr(self, "app", None), "data_mgr", None)
        getter = getattr(data_mgr, "get_prop_rules_config", None)
        if callable(getter):
            try:
                value = getter()
                if isinstance(value, dict):
                    rules = value
            except Exception as exc:
                logger.warning(f"[SharuanWorld] Не удалось прочитать prop_rules через DataManager: {exc}")
        if not rules and getattr(self, "app", None) is not None:
            rules = load_data_file(self.app, "world/prop_rules.json", default={})
        if not isinstance(rules, dict) or not rules:
            return

        zones_data = self.layout.get("zones", []) if isinstance(self.layout.get("zones"), list) else []

        def zone_circle(zone_id):
            zid = str(zone_id or "").strip().lower()
            for row in zones_data:
                if not isinstance(row, dict):
                    continue
                rid = str(row.get("id", "") or "").strip().lower()
                if rid != zid:
                    continue
                center = row.get("center", [])
                radius = float(row.get("radius", 20.0) or 20.0)
                if isinstance(center, list) and len(center) >= 2:
                    try:
                        return float(center[0]), float(center[1]), radius
                    except Exception:
                        pass
            return None

        fallback_mat = mk_mat((0.44, 0.40, 0.36, 1.0), 0.80, 0.04)
        water_level = -0.4
        total_placed = 0
        GLOBAL_PROP_CAP = 200  # Hard limit to prevent OOM

        zone_entries = rules.get("zones", []) if isinstance(rules, dict) else []
        for zone_rule in zone_entries:
            if total_placed >= GLOBAL_PROP_CAP:
                break
            if not isinstance(zone_rule, dict):
                continue
            zone_id = str(zone_rule.get("zone_id", "") or "").strip()
            if not zone_id:
                continue
            circle = zone_circle(zone_id)
            if circle is None:
                continue
            cx_z, cy_z, radius = circle
            props = zone_rule.get("props", [])
            if not isinstance(props, list):
                continue

            for prop_def in props:
                if total_placed >= GLOBAL_PROP_CAP:
                    break
                if not isinstance(prop_def, dict):
                    continue
                density = float(prop_def.get("density", 0.0) or 0.0)
                min_spacing = float(prop_def.get("min_spacing", 4.0) or 4.0)
                seed = int(prop_def.get("seed", 1000) or 1000)
                prop_type = str(prop_def.get("type", "") or "").strip()
                scale_min = float(prop_def.get("scale_min", 1.0) or 1.0)
                scale_max = float(prop_def.get("scale_max", 1.0) or 1.0)
                y_align = bool(prop_def.get("y_align", True))
                model_path = str(prop_def.get("model", "") or "").strip()

                # Estimate prop count from zone area * density, capped per-type
                area = math.pi * radius * radius
                count = min(30, max(0, int(area * density * 0.08)))
                if count == 0:
                    continue

                rng = random.Random(seed + hash(zone_id))
                placed_positions = []
                location_label = str(zone_rule.get("biome", zone_id)).replace("_", " ").title()

                for _ in range(count * 8):  # oversample, skip collisions
                    if len(placed_positions) >= count:
                        break
                    angle = rng.uniform(0, math.tau)
                    dist = rng.uniform(0, radius * 0.95)
                    px = cx_z + math.cos(angle) * dist
                    py = cy_z + math.sin(angle) * dist
                    pz = self._th(px, py)

                    # Skip underwater positions
                    if pz < water_level:
                        continue

                    # Respect min spacing
                    too_close = any(
                        math.sqrt((px - ox) ** 2 + (py - oy) ** 2) < min_spacing
                        for ox, oy in placed_positions
                    )
                    if too_close:
                        continue

                    # Attempt to load actual model first
                    scale = rng.uniform(scale_min, scale_max)
                    h_rot = rng.uniform(0, 360) if not y_align else rng.uniform(-15, 15)
                    spawned = False

                    if model_path:
                        norm_path = prefer_bam_path(model_path) if callable(prefer_bam_path) else model_path
                        if Path(norm_path).exists():
                            try:
                                tint = prop_def.get("tint")
                                spawned = bool(self._spawn_world_model(
                                    norm_path, px, py, pz,
                                    scale=scale, h=h_rot,
                                    loc_name=location_label,
                                    tint=tint
                                ))
                            except Exception:
                                spawned = False

                    if not spawned:
                        # Fallback: tiny procedural marker (invisible but world-consistent)
                        size = scale * 0.3
                        self._pl(
                            mk_box(f"prop_{prop_type}_{len(placed_positions)}", size, size, size * 2.0),
                            px, py, pz + size,
                            None, fallback_mat, location_label, is_platform=False,
                        )
                        spawned = True

                    if spawned:
                        placed_positions.append((px, py))
                        total_placed += 1

        logger.info(f"[SharuanWorld] Zone props placed: {total_placed} total across {len(zone_entries)} zones.")

    
    
    
    
    
    



    
    
    
    
    
    def _build_ultimate_sandbox(self):
        """Isolated Void Sandbox: Beautiful testing grounds at (0,0,5)."""
        if str(self.active_location).lower() != "ultimate_sandbox":
            return

        tx, ty, tz = 0.0, 0.0, 5.0
        features = resolve_ultimate_sandbox_features(os.environ.get("XBOT_SANDBOX_BUILD_FEATURES", "full"))
        
        stone_mat = mk_mat((0.48, 0.46, 0.44, 1.0), 0.72, 0.04)
        dirt_mat = mk_mat((0.38, 0.32, 0.24, 1.0), 0.90, 0.0)
        water_mat = mk_mat((0.12, 0.32, 0.52, 0.78), 0.10, 0.20)
        wood_mat = mk_mat((0.28, 0.18, 0.10, 1.0), 0.82, 0.0)
        accent_mat = mk_mat((0.8, 0.6, 0.2, 1.0), 0.3, 0.6)
        magic_mat = mk_mat((0.3, 0.1, 0.9, 0.8), 0.1, 0.9)
        
        from panda3d.core import TransparencyAttrib, Vec3, DirectionalLight, LColor
        import random, math
        rng = random.Random(42)
        
        # 0. Add a Sun light to the void (Beautiful lighting)
        if "sun" in features:
            sun = DirectionalLight("sandbox_sun")
            sun.set_color((1.1, 1.0, 0.9, 1))
            sun_np = self.render.attach_new_node(sun)
            sun_np.set_hpr(45, -60, 0)
            self.render.set_light(sun_np)
            
            from panda3d.core import AmbientLight
            alight = AmbientLight("sandbox_ambient")
            alight.set_color((0.6, 0.62, 0.65, 1)) # Boosted ambient light
            alight_np = self.render.attach_new_node(alight)
            self.render.set_light(alight_np)
            
            # Provide an emissive sky dome so complexpbr's realtime IBL has something to reflect!
            # Without this, shadowed areas are pitch black because ambient bounce light is zero.
            void_sky = self._pl(
                mk_sphere("sandbox_sky", 300.0, 16, 16),
                tx, ty, tz,
                None, None, "Ultimate Sandbox", is_platform=False
            )
            void_sky.setTwoSided(True)
            void_sky.setColorScale(0.12, 0.16, 0.22, 1.0) # Moody dark blue ambient
            void_sky.setLightOff(1)
            void_sky.setShaderOff(1)
        
        # 1. Isolated High-Fidelity Base
        # Use two layers to kill Z-fighting and add depth
        self._pl(
            mk_box("sandbox_void_deep", 200.0, 200.0, 4.0),
            tx, ty, tz - 2.5,
            self.tx.get("stone"), stone_mat, "Ultimate Sandbox",
            is_platform=False
        )
        self._pl(
            mk_box("sandbox_void_base", 182.0, 182.0, 1.2),
            tx, ty, tz - 0.55,
            self.tx.get("magic_grid"), stone_mat, "Ultimate Sandbox",
            is_platform=True
        )
        
        # 2. Parkour Zone (Floating Cubes)
        if "traversal" in features:
            for i in range(12):
                h = 1.0 + (i * 0.8)
                self._pl(
                    mk_box(f"sandbox_cube_{i}", 4.0, 4.0, h),
                    tx + 25.0 + (i * 6.0), ty + (5.0 if i % 2 == 0 else -5.0),
                    tz + (h * 0.5),
                    self.tx.get("stone"), stone_mat, "Ultimate Sandbox"
                )

            # 3. Wallrun & Climbing Area
            self._pl(mk_box("sandbox_wallrun", 1.5, 60.0, 16.0), tx-35.0, ty, tz+8.0, self.tx.get("stone"), stone_mat, "Ultimate Sandbox", is_wallrun=True)
            self._pl(mk_box("sandbox_climb_tower", 10.0, 10.0, 30.0), tx-20.0, ty-50.0, tz+15.0, self.tx.get("stone"), stone_mat, "Ultimate Sandbox")

        if "water" in features:
            # 4. Swimming / Diving Pool
            self._pl(mk_box("pool_frame", 50.0, 40.0, 6.0), tx, ty+50.0, tz-3.0, None, stone_mat, "Ultimate Sandbox")
            water = self._pl(mk_plane("sandbox_water", 48.0, 38.0), tx, ty+50.0, tz-0.1, None, water_mat, "Ultimate Sandbox", is_platform=False)
            water.setTransparency(TransparencyAttrib.MAlpha)

        if "vfx" in features:
            # 5. Interactive Portals & VFX
            portal_start = self._pl(mk_cyl("portal_center", 3.0, 0.2, 16), tx-15, ty-15, tz+0.1, None, magic_mat, "Ultimate Sandbox")
            self._register_story_anchor("portal_c", portal_start, **self._ultimate_sandbox_portal_anchor_kwargs())

            for vx, vy, vtype in [(10, 10, "fire"), (-10, -10, "spark")]:
                fountain = self._pl(mk_box(f"vfx_fountain_{vtype}", 0.8, 0.8, 0.4), tx+vx, ty+vy, tz+0.2, None, accent_mat, "Ultimate Sandbox")
                fountain.set_tag("vfx_test", vtype)

        if "scenery" in features:
            # 6. Scenery (Trees / Vegetation)
            models = self._ultimate_sandbox_tree_model_paths()
            pts = self._scatter_points(count=15, x_range=(-80, 80), y_range=(-80, 80), rng=rng)
            for mx, my in pts:
                if math.sqrt(mx*mx + my*my) < 25:
                    continue
                mdl = rng.choice(models)
                try:
                    self._pl(self.loader.load_model(mdl), mx, my, tz, None, None, "Ultimate Sandbox", False)
                except Exception:
                    pass

            # 7. Heavy Rocks (Large, Textured, Randomized)
            stone_tex = self.tx.get("stone")
            for i in range(12):
                rx = rng.uniform(-70, 70)
                ry = rng.uniform(-70, 70)
                if math.sqrt(rx*rx + ry*ry) < 18: continue
                
                scale = rng.uniform(2.5, 6.0)
                rock = self._pl(
                    mk_sphere(f"sandbox_rock_{i}", 1.0, 8, 8),
                    rx, ry, tz + (scale * 0.4),
                    stone_tex, stone_mat, "Ultimate Sandbox",
                    is_platform=True
                )
                rock.setScale(scale, scale * rng.uniform(0.7, 1.3), scale * rng.uniform(0.5, 0.9))
                rock.setHpr(rng.uniform(0, 360), rng.uniform(-20, 20), rng.uniform(-20, 20))

            for i in range(15):
                 dx, dy = rng.uniform(-70, 70), rng.uniform(-70, 70)
                 self._pl(mk_plane(f"decal_{i}", 5, 5), dx, dy, tz+0.02, None, mk_mat((0.2,0.5,0.2, 0.6)), "Ultimate Sandbox", False)

        if "stairs" in features:
            # 7. Stairs
            for i in range(12):
                self._pl(mk_box(f"sandbox_step_{i}", 3.5, 3.5, 0.8), 25, -25 + (i*4), tz + (i*1.5), None, accent_mat, "Ultimate Sandbox")

        if "story" in features:
            # 8. Interactive Objects (Loot/Lore)
            chest = self._pl(mk_box("sandbox_chest_void", 1.6, 1.0, 1.1), tx+12, ty+12, tz+0.55, self.tx.get("wood"), wood_mat, "Ultimate Sandbox")
            self._register_story_anchor("sandbox_chest_v", chest, name="Void Treasure", hint="Loot Chest")

            book = self._pl(mk_box("sandbox_book_void", 0.6, 0.8, 0.15), tx-12, ty+12, tz+0.05, None, mk_mat((0.15,0.3,0.9)), "Ultimate Sandbox")
            self._register_story_anchor("sandbox_book_v", book, name="Void Chronicles", hint="Read Insights")

        if "npcs" in features:
            # 9. Test NPC (Dialogue & TTS test)
            npc_payload = {
                "name": "Sandbox Guide",
                "role": "Guide",
                "pos": [tx + 5, ty + 5, tz],
                "appearance": {
                    "scale": 1.0,
                    "model": "assets/models/xbot/Xbot.glb",
                    "skin_color": [0.3, 0.4, 0.8],
                    "armor_type": "plate"
                },
                "dialogue": "guard_dialogue"
            }
            if hasattr(self.app, "npc_mgr"):
                # self.app.npc_mgr._spawn_single("sandbox_guide", npc_payload)

                # 10. Test Merchant
                merchant_payload = {
                    "name": "Merchant Aldric",
                    "role": "Merchant",
                    "pos": [tx - 5, ty + 5, tz],
                    "appearance": {
                        "scale": 1.0,
                        "model": "assets/models/xbot/Xbot.glb",
                        "skin_color": [0.8, 0.6, 0.4],
                        "armor_type": "leather",
                        "weapon_type": "none",
                        "shield_type": "none"
                    },
                    "dialogue": "merchant"
                }
                self.app.npc_mgr._spawn_single("merchant_general", merchant_payload)


        from utils.logger import logger
        logger.info(f"[SharuanWorld] Isolated Void Sandbox (Feature-Complete) built at ({tx}, {ty}, {tz})")

# --- REGION DEFINITION: Kremor (Cursed Forest) ---
# The 'SharuanWorld' class serves as the Overworld Generator for all contiguous landmass regions,
# including the kingdom of Sharuan and the outlying cursed forests of Kremor.

