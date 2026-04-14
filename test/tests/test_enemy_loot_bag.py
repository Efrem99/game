import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import EnemyUnit


class _DummyPos:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _DummyRoot:
    def __init__(self, pos):
        self._pos = pos

    def isEmpty(self):
        return False

    def getPos(self, _render):
        return self._pos


class _DummyStoryInteraction:
    def __init__(self):
        self.calls = []

    def register_anchor(self, anchor_id, node, **kwargs):
        self.calls.append(
            {
                "anchor_id": str(anchor_id),
                "node": node,
                "kwargs": dict(kwargs),
            }
        )
        return True


class EnemyLootBagTests(unittest.TestCase):
    def test_dead_enemy_drops_loot_once(self):
        unit = EnemyUnit.__new__(EnemyUnit)
        unit.root = _DummyRoot(_DummyPos(3.0, 4.0, 1.0))
        unit.render = object()
        unit.hp = 0.0
        unit.state = "idle"
        unit.state_time = 0.0
        unit.state_lock = 0.0
        unit.proxy = None
        drop_calls = []
        unit._drop_loot_bag = lambda: drop_calls.append("drop") or True

        EnemyUnit.update(unit, 0.016, _DummyPos(0.0, 0.0, 0.0))
        EnemyUnit.update(unit, 0.016, _DummyPos(0.0, 0.0, 0.0))

        self.assertEqual(["drop"], drop_calls)

    def test_drop_loot_bag_registers_story_anchor_with_rewards(self):
        story_interaction = _DummyStoryInteraction()
        app = types.SimpleNamespace(
            story_interaction=story_interaction,
            world=types.SimpleNamespace(active_location="Training Grounds"),
        )
        bag_node = object()

        unit = EnemyUnit.__new__(EnemyUnit)
        unit.app = app
        unit.render = object()
        unit.root = _DummyRoot(_DummyPos(10.0, 6.0, 2.0))
        unit.id = "goblin_raider_1"
        unit.kind = "goblin"
        unit.name = "Goblin Raider"
        unit.is_boss = False
        unit.cfg = {}
        unit._loot_bag_dropped = False
        unit._loot_bag_anchor_id = ""
        unit._loot_bag_node = None
        unit._spawn_loot_bag_node = lambda _drop_pos: bag_node

        first = EnemyUnit._drop_loot_bag(unit)
        second = EnemyUnit._drop_loot_bag(unit)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(1, len(story_interaction.calls))
        row = story_interaction.calls[0]
        self.assertEqual("enemy_loot_goblin_raider_1", row["anchor_id"])
        self.assertIs(row["node"], bag_node)
        self.assertEqual("Loot Bag", row["kwargs"].get("name"))
        self.assertTrue(bool(row["kwargs"].get("single_use", False)))
        rewards = row["kwargs"].get("rewards")
        self.assertIsInstance(rewards, dict)
        self.assertGreater(int(rewards.get("gold", 0) or 0), 0)
        self.assertGreater(int(rewards.get("xp", 0) or 0), 0)
        self.assertIsInstance(rewards.get("items", []), list)


if __name__ == "__main__":
    unittest.main()
