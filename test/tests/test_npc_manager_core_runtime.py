import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.npc_manager import NPCManager


class _Vec3Like:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _FakeActor:
    def __init__(self):
        self.pos = _Vec3Like(0.0, 0.0, 0.0)
        self.h = None
        self.play_rates = {}
        self.looped = []
        self.played = []

    def getPos(self, _render=None):
        return _Vec3Like(self.pos.x, self.pos.y, self.pos.z)

    def setPos(self, *args):
        if len(args) == 1 and hasattr(args[0], "x"):
            value = args[0]
            self.pos = _Vec3Like(value.x, value.y, value.z)
            return
        self.pos = _Vec3Like(float(args[0]), float(args[1]), float(args[2]))

    def setH(self, value):
        self.h = float(value)

    def setPlayRate(self, rate, clip):
        self.play_rates[str(clip)] = float(rate)

    def getAnimNames(self):
        return ["idle", "walk"]

    def loop(self, clip):
        self.looped.append(str(clip))

    def play(self, clip):
        self.played.append(str(clip))


class _FakeCoreRuntime:
    def __init__(self):
        self.calls = []

    def updateUnits(self, units, context):
        self.calls.append((units, context))
        updated = []
        for unit in units:
            unit.actorPos = type(unit.actorPos)(1.25, 0.0, 0.0)
            unit.desiredHeading = 90.0
            unit.desiredPlayRate = 1.1
            unit.desiredAnim = "walk"
            unit.walkSpeed = 1.65
            unit.idleMin = 1.0
            unit.idleMax = 2.0
            unit.idleTimer = 1.4
            unit.moving = True
            unit.targetChanged = False
            updated.append(unit)
        return updated


class NPCManagerCoreRuntimeTests(unittest.TestCase):
    def test_update_uses_core_runtime_batch_when_available(self):
        app = SimpleNamespace(render=object())
        manager = NPCManager(app)
        actor = _FakeActor()
        core_runtime = _FakeCoreRuntime()
        manager._core_runtime = core_runtime
        manager._update_player_detection = lambda *args, **kwargs: None
        manager._update_activity_state = lambda *args, **kwargs: None
        manager._update_dracolid_visual = lambda *args, **kwargs: None
        manager._ground_height = lambda x, y, fallback=0.0: float(fallback)
        manager.units = [
            {
                "id": "npc_a",
                "actor": actor,
                "home": _Vec3Like(0.0, 0.0, 0.0),
                "target": _Vec3Like(3.0, 0.0, 0.0),
                "base_wander_radius": 3.0,
                "wander_radius": 3.0,
                "base_walk_speed": 1.5,
                "walk_speed": 1.5,
                "base_idle_min": 1.0,
                "base_idle_max": 2.0,
                "idle_min": 1.0,
                "idle_max": 2.0,
                "idle_timer": 0.5,
                "role": "villager",
                "activity": "idle",
                "anim": "idle",
                "suspicion": 0.0,
                "alerted": False,
            }
        ]

        manager.update(1.0, world_state={"weather": "clear", "phase": "day"}, stealth_state={})

        self.assertEqual(1, len(core_runtime.calls))
        self.assertAlmostEqual(1.25, actor.pos.x, places=5)
        self.assertAlmostEqual(90.0, actor.h, places=5)
        self.assertEqual("walk", manager.units[0]["anim"])
        self.assertAlmostEqual(1.1, actor.play_rates["walk"], places=5)


if __name__ == "__main__":
    unittest.main()
