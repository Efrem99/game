import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.core_runtime import HAS_CORE, gc


class EnemyRuntimeCoreTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HAS_CORE, "Compiled game_core.pyd is required for enemy runtime core tests")
        self.system = gc.EnemyRuntimeSystem()

    def _make_context(self, *, dt=1.0, game_time=10.0, player_pos=None):
        ctx = gc.EnemyRuntimeContext()
        ctx.dt = float(dt)
        ctx.gameTime = float(game_time)
        player = player_pos or (0.0, 8.0, 0.0)
        ctx.playerPos = gc.Vec3(float(player[0]), float(player[1]), float(player[2]))
        return ctx

    def _make_unit(self):
        unit = gc.EnemyRuntimeUnit()
        unit.id = 1
        unit.kind = "goblin"
        unit.alive = True
        unit.actorPos = gc.Vec3(0.0, 0.0, 0.0)
        unit.currentHeading = 180.0
        unit.runSpeed = 4.0
        unit.attackRange = 2.5
        unit.aggroRange = 16.0
        unit.disengageHold = 4.0
        unit.engagedUntil = 0.0
        unit.isEngaged = False
        unit.state = "idle"
        unit.stateLock = 0.0
        unit.attackCooldown = 0.0
        unit.phaseSpeedMul = 1.0
        unit.groundZ = 0.0
        unit.groundOffset = 1.2
        unit.hoverHeight = 1.2
        return unit

    def test_mid_range_enemy_enters_chase_and_moves_toward_player(self):
        unit = self._make_unit()
        ctx = self._make_context(dt=0.5, game_time=12.0, player_pos=(0.0, 8.0, 0.0))

        result = self.system.updateUnits([unit], ctx)[0]

        self.assertTrue(result.isEngaged)
        self.assertEqual("chase", result.desiredState)
        self.assertTrue(result.moving)
        self.assertGreater(result.actorPos.y, 0.0)
        self.assertAlmostEqual(115.0, result.desiredHeading, places=4)
        self.assertGreater(result.targetDistance, 2.5)

    def test_close_range_enemy_requests_attack_telegraph_without_moving(self):
        unit = self._make_unit()
        ctx = self._make_context(dt=0.25, game_time=12.0, player_pos=(0.0, 1.5, 0.0))

        result = self.system.updateUnits([unit], ctx)[0]

        self.assertTrue(result.isEngaged)
        self.assertEqual("telegraph", result.desiredState)
        self.assertFalse(result.moving)
        self.assertAlmostEqual(0.0, result.actorPos.x, places=5)
        self.assertAlmostEqual(0.0, result.actorPos.y, places=5)
        self.assertLess(result.targetDistance, 2.5)


if __name__ == "__main__":
    unittest.main()
