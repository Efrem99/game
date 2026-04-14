import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import EnemyUnit


class _Vec3:
    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _RootStub:
    def __init__(self):
        self._pos = _Vec3(0.0, 0.0, 0.0)
        self._hpr = _Vec3(0.0, 0.0, 0.0)

    def isEmpty(self):
        return False

    def setPos(self, value, y=None, z=None):
        if y is None and z is None and hasattr(value, "x"):
            self._pos = _Vec3(value.x, value.y, value.z)
            return
        self._pos = _Vec3(value, y, z)

    def setHpr(self, h, p=None, r=None):
        if p is None and r is None and hasattr(h, "x"):
            self._hpr = _Vec3(h.x, h.y, h.z)
            return
        self._hpr = _Vec3(h, p, r)

    def getPos(self, *_):
        return _Vec3(self._pos.x, self._pos.y, self._pos.z)

    def getHpr(self, *_):
        return _Vec3(self._hpr.x, self._hpr.y, self._hpr.z)


class _AppProbeStub:
    def __init__(self):
        self.calls = []

    def _debug_probe_runtime_node(self, label, node, reference=None):
        self.calls.append((label, node, reference))
        return True


class EnemyRuntimeTransformGuardTests(unittest.TestCase):
    def _make_unit(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.id = "fire_elemental_1"
        unit.root = _RootStub()
        unit.render = object()
        unit.app = _AppProbeStub()
        return unit

    def test_runtime_transform_applies_finite_position_and_heading(self):
        unit = self._make_unit()

        applied = EnemyUnit._commit_runtime_transform(
            unit,
            pos=_Vec3(4.0, 5.0, 6.0),
            heading=135.0,
        )

        self.assertTrue(applied)
        pos = unit.root.getPos()
        hpr = unit.root.getHpr()
        self.assertEqual((4.0, 5.0, 6.0), (pos.x, pos.y, pos.z))
        self.assertEqual((135.0, 0.0, 0.0), (hpr.x, hpr.y, hpr.z))
        self.assertEqual(
            [("enemy_update:fire_elemental_1", unit.root, unit.render)],
            unit.app.calls,
        )

    def test_runtime_transform_rejects_non_finite_values_and_keeps_previous_state(self):
        unit = self._make_unit()
        unit.root.setPos(_Vec3(1.0, 2.0, 3.0))
        unit.root.setHpr(45.0, 0.0, 0.0)

        applied = EnemyUnit._commit_runtime_transform(
            unit,
            pos=_Vec3(math.nan, 5.0, 6.0),
            heading=math.inf,
        )

        self.assertFalse(applied)
        pos = unit.root.getPos()
        hpr = unit.root.getHpr()
        self.assertEqual((1.0, 2.0, 3.0), (pos.x, pos.y, pos.z))
        self.assertEqual((45.0, 0.0, 0.0), (hpr.x, hpr.y, hpr.z))
        self.assertEqual(
            [("enemy_update:fire_elemental_1", unit.root, unit.render)],
            unit.app.calls,
        )


if __name__ == "__main__":
    unittest.main()
