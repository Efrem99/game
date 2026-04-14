"""Shared combat/VFX policy helpers."""

from __future__ import annotations

import math
import os

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from panda3d.core import PNMImage, SamplerState, Texture
except Exception:
    PNMImage = None
    SamplerState = None
    Texture = None


FIRE_SPRITE_TEXTURE_CANDIDATES = (
    "assets/textures/flare.png",
    "assets/textures/skills/fire.png",
    "assets/textures/skills/fireball.png",
)
DEFAULT_MELEE_WHEEL_TOKEN = "sword"
MELEE_WHEEL_TOKENS = (
    "sword",
    "weapon",
    "weapon_sword",
    "melee",
    "fencing",
)


def is_melee_wheel_token(label) -> bool:
    token = str(label or "").strip().lower()
    if not token:
        return True
    compact = "".join(ch for ch in token if ch.isalnum() or ch == "_")
    return compact in MELEE_WHEEL_TOKENS


def should_cast_selected_spell(light_pressed: bool, selected_label, explicit_cast: bool = False) -> bool:
    """Cast on light-attack only when the selected wheel slot is a spell."""
    if bool(explicit_cast):
        return True
    return bool(light_pressed) and (not is_melee_wheel_token(selected_label))


def image_path_has_alpha(path) -> bool:
    token = str(path or "").strip().replace("\\", "/")
    if not token or Image is None:
        return False
    try:
        with Image.open(token) as img:
            if "A" in img.getbands():
                return True
            if "transparency" in img.info:
                return True
    except Exception:
        return False
    return False


def make_soft_disc_texture(tex_name="fx_soft_disc", size=128, warm=False):
    if PNMImage is None or Texture is None or SamplerState is None:
        return None
    side = max(16, int(size or 128))
    img = PNMImage(side, side, 4)
    half = max(1.0, side * 0.5)
    for y in range(side):
        ny = (y - half) / half
        for x in range(side):
            nx = (x - half) / half
            dist = math.sqrt((nx * nx) + (ny * ny))
            edge = max(0.0, 1.0 - dist)
            alpha = edge ** 2.2
            if warm:
                r = 0.95 + (alpha * 0.05)
                g = 0.80 + (alpha * 0.16)
                b = 0.56 + (alpha * 0.30)
            else:
                r = 0.72 + (alpha * 0.18)
                g = 0.82 + (alpha * 0.14)
                b = 1.00
            img.set_xel_a(x, y, min(1.0, r), min(1.0, g), min(1.0, b), alpha)
    tex = Texture(str(tex_name or "fx_soft_disc"))
    tex.load(img)
    tex.set_wrap_u(SamplerState.WM_clamp)
    tex.set_wrap_v(SamplerState.WM_clamp)
    return tex


def pick_first_existing_texture_path(
    candidates=None,
    exists_fn=None,
    require_alpha=False,
    alpha_ok_fn=None,
) -> str:
    values = list(candidates or FIRE_SPRITE_TEXTURE_CANDIDATES)
    checker = exists_fn if callable(exists_fn) else os.path.exists
    alpha_checker = alpha_ok_fn if callable(alpha_ok_fn) else image_path_has_alpha
    for path in values:
        token = str(path or "").strip().replace("\\", "/")
        if not token:
            continue
        try:
            if not checker(token):
                continue
        except Exception:
            continue
        if require_alpha:
            try:
                if not alpha_checker(token):
                    continue
            except Exception:
                continue
        return token
    return ""


def load_optional_texture(
    loader,
    candidates=None,
    exists_fn=None,
    require_alpha=False,
    alpha_ok_fn=None,
    fallback_texture=None,
):
    if not loader and not callable(fallback_texture):
        return None
    path = pick_first_existing_texture_path(
        candidates=candidates,
        exists_fn=exists_fn,
        require_alpha=require_alpha,
        alpha_ok_fn=alpha_ok_fn,
    )
    if path and loader:
        try:
            return loader.loadTexture(path)
        except Exception:
            pass
    if callable(fallback_texture):
        try:
            return fallback_texture()
        except Exception:
            return None
    return None


def can_spawn_particle_fire(particles) -> bool:
    if not particles:
        return False
    method = getattr(particles, "spawnFireball", None)
    return callable(method)


def _extract_xyz(pos):
    if pos is None:
        return 0.0, 0.0, 0.0
    try:
        x = float(getattr(pos, "x", 0.0))
    except Exception:
        x = 0.0
    try:
        y = float(getattr(pos, "y", 0.0))
    except Exception:
        y = 0.0
    try:
        z = float(getattr(pos, "z", 0.0))
    except Exception:
        z = 0.0
    return x, y, z


def spawn_fireball_burst(particles, pos, bursts=1, vec3_factory=None) -> int:
    if not can_spawn_particle_fire(particles):
        return 0
    try:
        total = max(0, int(bursts))
    except Exception:
        total = 0
    if total <= 0:
        return 0

    x, y, z = _extract_xyz(pos)
    spawned = 0
    maker = vec3_factory if callable(vec3_factory) else None
    for _ in range(total):
        payload = maker(x, y, z) if maker else pos
        try:
            particles.spawnFireball(payload)
            spawned += 1
        except Exception:
            continue
    return spawned


def enforce_particle_budget(particle_rows, max_particles) -> int:
    """Trim oldest particle rows to keep list size within a runtime budget."""
    if not isinstance(particle_rows, list):
        return 0
    try:
        limit = max(0, int(max_particles))
    except Exception:
        limit = 0

    overflow = len(particle_rows) - limit
    if overflow <= 0:
        return 0

    to_remove = particle_rows[:overflow]
    del particle_rows[:overflow]
    for row in to_remove:
        node = row.get("node") if isinstance(row, dict) else None
        if not node:
            continue
        try:
            is_empty = bool(node.isEmpty()) if hasattr(node, "isEmpty") else False
        except Exception:
            is_empty = False
        if is_empty:
            continue
        try:
            node.removeNode()
        except Exception:
            pass
    return overflow


def scale_particle_budget_for_fps(
    base_budget,
    average_fps,
    min_fps=30.0,
    max_fps=60.0,
    min_scale=0.35,
):
    """Scale particle budget down when FPS drops below the minimum target."""
    try:
        base = max(32, int(base_budget))
    except Exception:
        base = 32
    try:
        fps = float(average_fps)
    except Exception:
        fps = float(max_fps)
    try:
        floor = max(1.0, float(min_fps))
    except Exception:
        floor = 30.0
    try:
        _ = max(float(max_fps), floor)
    except Exception:
        pass
    try:
        floor_scale = max(0.05, min(1.0, float(min_scale)))
    except Exception:
        floor_scale = 0.35

    if fps >= floor:
        return base

    ratio = max(0.0, min(1.0, fps / floor))
    scale = max(floor_scale, ratio)
    return max(32, int(round(base * scale)))
