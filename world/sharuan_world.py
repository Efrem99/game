"""Compatibility wrapper for legacy imports from world.sharuan_world."""

import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SharuanWorld = importlib.import_module("src.world.sharuan_world").SharuanWorld

__all__ = ["SharuanWorld"]
