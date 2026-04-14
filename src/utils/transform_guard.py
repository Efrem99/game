"""Transform Guard - Numerical validation wrappers for Panda3D NodePath transforms."""

import math
from panda3d.core import Vec3, LMatrix4f
from utils.logger import logger

def is_finite(val):
    """Checks if a value or collection of values is finite."""
    if isinstance(val, (int, float)):
        return math.isfinite(val)
    try:
        for x in val:
            if not math.isfinite(x):
                return False
    except TypeError:
        return math.isfinite(val)
    return True

def safe_set_pos(np, x, y=None, z=None):
    """Sets position with finiteness validation."""
    if y is None and z is None:
        # Vec3 or LPoint3
        if is_finite(x):
            np.setPos(x)
        else:
            logger.warning(f"[TransformGuard] Rejected non-finite Pos {x} for {np}")
    else:
        # separate components
        if is_finite(x) and is_finite(y) and is_finite(z):
            np.setPos(x, y, z)
        else:
            logger.warning(f"[TransformGuard] Rejected non-finite Pos ({x}, {y}, {z}) for {np}")

def safe_set_hpr(np, h, p=None, r=None):
    """Sets HPR with finiteness validation."""
    if p is None and r is None:
        if is_finite(h):
            np.setHpr(h)
    else:
        if is_finite(h) and is_finite(p) and is_finite(r):
            np.setHpr(h, p, r)

def safe_set_scale(np, sx, sy=None, sz=None):
    """Sets scale with finiteness validation and zero-guarding."""
    if sy is None and sz is None:
        # Uniform or Vec3
        if is_finite(sx):
            # Guard against exact zero if it would cause matrix singularity issues
            # though setScale(0) is allowed in Panda, it's often a sign of corruption in our engine
            np.setScale(sx)
    else:
        if is_finite(sx) and is_finite(sy) and is_finite(sz):
            np.setScale(sx, sy, sz)

def safe_look_at(np, target, up=Vec3.up()):
    """safe lookAt with distance/finite check."""
    try:
        pos = np.getPos()
        if isinstance(target, Vec3):
            tpos = target
        else:
            tpos = target.getPos(np.getParent())
        
        diff = tpos - pos
        if diff.length_squared() > 1e-6 and is_finite(diff):
            np.lookAt(target, up)
    except Exception:
        pass
