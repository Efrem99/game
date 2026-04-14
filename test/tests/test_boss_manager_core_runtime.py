import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import BossManager


class _Vec3Like:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _RuntimeHint:
    def __init__(self):
        self.id = 1
        self.desiredState = "chase"
        self.desiredHeading = 15.0
        self.targetDistance = 6.5
        self.engagedUntil = 0.0
        self.actorPos = _Vec3Like(1.5, 2.0, 3.0)
        self.moving = True


class _FakeCoreRuntime:
    def __init__(self):
        self.calls = []

    def updateUnits(self, units, context):
        self.calls.append((list(units), context))
        return [_RuntimeHint()]


class _JumpingRuntimeHint(_RuntimeHint):
    def __init__(self):
        super().__init__()
        self.actorPos = _Vec3Like(5000.0, -4000.0, 1200.0)
        self.desiredHeading = 108000.0


class _EnemyUnitStub:
    def __init__(self):
        self.id = "enemy_a"
        self.exported = 0
        self.applied = []
        self.update_calls = []

    def export_runtime_unit(self):
        self.exported += 1
        return SimpleNamespace(
            id=1,
            actorPos=_Vec3Like(1.0, 2.0, 3.0),
            runSpeed=4.0,
            phaseSpeedMul=1.0,
            state="idle",
        )

    def apply_runtime_unit(self, runtime_unit):
        self.applied.append(runtime_unit)

    def update(self, dt, player_pos, runtime_hint=None):
        self.update_calls.append((float(dt), player_pos, runtime_hint))


class BossManagerCoreRuntimeTests(unittest.TestCase):
    def test_update_routes_runtime_hints_through_core_batch_when_available(self):
        manager = BossManager.__new__(BossManager)
        manager.app = SimpleNamespace(render=object())
        manager.units = [_EnemyUnitStub()]
        manager._core_runtime = _FakeCoreRuntime()

        player_pos = _Vec3Like(1.0, 2.0, 3.0)

        BossManager.update(manager, 0.25, player_pos)

        self.assertEqual(1, manager.units[0].exported)
        self.assertEqual(1, len(manager._core_runtime.calls))
        self.assertEqual(1, len(manager.units[0].applied))
        self.assertEqual(1, len(manager.units[0].update_calls))
        self.assertIsInstance(manager.units[0].update_calls[0][2], _RuntimeHint)

    def test_update_rejects_runtime_hints_that_jump_far_beyond_expected_step(self):
        manager = BossManager.__new__(BossManager)
        manager.app = SimpleNamespace(render=object())
        manager.units = [_EnemyUnitStub()]
        manager._core_runtime = _FakeCoreRuntime()
        manager._core_runtime.updateUnits = lambda units, context: [_JumpingRuntimeHint()]

        player_pos = _Vec3Like(1.0, 2.0, 3.0)

        BossManager.update(manager, 0.25, player_pos)

        self.assertEqual(1, manager.units[0].exported)
        self.assertEqual([], manager.units[0].applied)
        self.assertEqual(1, len(manager.units[0].update_calls))
        self.assertIsNone(manager.units[0].update_calls[0][2])


if __name__ == "__main__":
    unittest.main()
