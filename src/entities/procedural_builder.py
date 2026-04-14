"""Procedural geometry builders — canonical source is world.procedural_builder.

This module re-exports everything from the canonical module so that any code
importing from ``entities.procedural_builder`` continues to work without change.
"""

from world.procedural_builder import (  # noqa: F401
    mk_box,
    mk_cyl,
    mk_cone,
    mk_sphere,
    mk_plane,
    mk_terrain,
    mk_mat,
    sample_polyline_points,
)

__all__ = [
    "mk_box",
    "mk_cyl",
    "mk_cone",
    "mk_sphere",
    "mk_plane",
    "mk_terrain",
    "mk_mat",
    "sample_polyline_points",
]
