"""Shared access to the optional compiled C++ core.

Import this module before Panda3D-heavy modules when possible. On this
machine, importing `game_core` after Panda can crash the process, while an
early import is stable.
"""

gc = None
HAS_CORE = False
CORE_IMPORT_ERROR = None

try:
    import game_core as gc

    HAS_CORE = True
except ImportError as exc:
    CORE_IMPORT_ERROR = exc
