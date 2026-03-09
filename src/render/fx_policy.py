"""Shared combat/VFX policy helpers."""

from __future__ import annotations

import os


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


def pick_first_existing_texture_path(candidates=None, exists_fn=None) -> str:
    values = list(candidates or FIRE_SPRITE_TEXTURE_CANDIDATES)
    checker = exists_fn if callable(exists_fn) else os.path.exists
    for path in values:
        token = str(path or "").strip().replace("\\", "/")
        if not token:
            continue
        try:
            if checker(token):
                return token
        except Exception:
            continue
    return ""


def load_optional_texture(loader, candidates=None):
    if not loader:
        return None
    path = pick_first_existing_texture_path(candidates=candidates)
    if not path:
        return None
    try:
        return loader.loadTexture(path)
    except Exception:
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
