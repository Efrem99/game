"""Root conftest.py — adds src/ to sys.path for all test modules.

Every test file under test/tests/ does its own path injection using
``parents[1]`` (which resolves to ``test/``), but when pytest is invoked
from the project root the working directory differs and those relative
calculations can fail.  This root-level conftest ensures ``src/`` is always
on sys.path regardless of where pytest is invoked from.
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
