import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.core_runtime import HAS_CORE, gc


class NPCRuntimeCoreTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HAS_CORE, "Compiled game_core.pyd is required for NPC runtime core tests")
        self.system = gc.NpcRuntimeSystem()

    def _make_context(self, *, dt=1.0, weather="", phase="", is_night=False, visibility=1.0):
        ctx = gc.NpcRuntimeContext()
        ctx.dt = float(dt)
        ctx.weather = str(weather)
        ctx.phase = str(phase)
        ctx.isNight = bool(is_night)
        ctx.visibility = float(visibility)
        return ctx

    def _make_unit(self):
        unit = gc.NpcRuntimeUnit()
        unit.id = 1
        unit.home = gc.Vec3(0.0, 0.0, 0.0)
        unit.target = gc.Vec3(0.0, 0.0, 0.0)
        unit.actorPos = gc.Vec3(0.0, 0.0, 0.0)
        unit.baseWalkSpeed = 1.5
        unit.walkSpeed = 1.5
        unit.baseWanderRadius = 3.0
        unit.wanderRadius = 3.0
        unit.baseIdleMin = 1.5
        unit.baseIdleMax = 4.2
        unit.idleMin = 1.5
        unit.idleMax = 4.2
        unit.idleTimer = 1.0
        unit.suspicion = 0.0
        unit.alerted = False
        unit.detectedPlayer = False
        unit.role = "villager"
        unit.activity = "idle"
        unit.anim = "idle"
        unit.actionRoll = 1.0
        unit.targetAngle = 0.0
        unit.targetDistance01 = 0.0
        unit.idleReset01 = 0.5
        return unit

    def test_civilian_shelter_motion_is_forced_home_and_slowed_by_storm_night(self):
        unit = self._make_unit()
        unit.home = gc.Vec3(0.0, 0.0, 0.0)
        unit.target = gc.Vec3(5.0, 0.0, 0.0)
        unit.actorPos = gc.Vec3(3.0, 0.0, 0.0)
        unit.baseWalkSpeed = 2.0
        unit.walkSpeed = 2.0
        unit.baseWanderRadius = 4.0
        unit.wanderRadius = 4.0
        unit.baseIdleMin = 1.0
        unit.baseIdleMax = 4.0
        unit.idleMin = 1.0
        unit.idleMax = 4.0
        unit.activity = "shelter"
        ctx = self._make_context(dt=1.0, weather="stormy", phase="night", is_night=True)

        result = self.system.updateUnits([unit], ctx)[0]

        self.assertLess(result.walkSpeed, 2.0)
        self.assertLess(result.wanderRadius, 4.0)
        self.assertGreater(result.idleMin, 1.0)
        self.assertAlmostEqual(0.0, result.target.x, places=5)
        self.assertAlmostEqual(0.0, result.target.y, places=5)
        self.assertTrue(result.moving)
        self.assertEqual("walk", result.desiredAnim)
        self.assertLess(result.actorPos.x, 3.0)

    def test_patrol_unit_can_pick_new_target_and_start_moving_in_same_frame(self):
        unit = self._make_unit()
        unit.role = "gate guard"
        unit.activity = "patrol"
        unit.baseWalkSpeed = 1.5
        unit.baseWanderRadius = 5.0
        unit.actionRoll = 0.0
        unit.targetAngle = 0.0
        unit.targetDistance01 = 1.0
        ctx = self._make_context(dt=1.0, weather="clear", phase="day", is_night=False)

        result = self.system.updateUnits([unit], ctx)[0]

        self.assertTrue(result.targetChanged)
        self.assertTrue(result.moving)
        self.assertEqual("walk", result.desiredAnim)
        self.assertGreater(result.target.x, 4.9)
        self.assertAlmostEqual(0.0, result.target.y, places=5)
        self.assertAlmostEqual(90.0, result.desiredHeading, places=4)
        self.assertGreater(result.actorPos.x, 0.0)

    def test_idle_expiry_picks_new_target_but_waits_until_next_frame_to_move(self):
        unit = self._make_unit()
        unit.activity = "idle"
        unit.idleTimer = 0.1
        unit.targetAngle = math.pi / 2.0
        unit.targetDistance01 = 0.5
        unit.idleReset01 = 0.25
        ctx = self._make_context(dt=0.5, weather="clear", phase="day", is_night=False)

        result = self.system.updateUnits([unit], ctx)[0]

        self.assertTrue(result.targetChanged)
        self.assertFalse(result.moving)
        self.assertEqual("idle", result.desiredAnim)
        self.assertAlmostEqual(0.0, result.actorPos.x, places=5)
        self.assertAlmostEqual(0.0, result.actorPos.y, places=5)
        self.assertGreater(result.target.y, 0.0)
        self.assertGreaterEqual(result.idleTimer, result.idleMin)
        self.assertLessEqual(result.idleTimer, result.idleMax)


if __name__ == "__main__":
    unittest.main()
