import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from render.fx_policy import enforce_particle_budget, scale_particle_budget_for_fps


class _Node:
    def __init__(self):
        self.removed = False

    def removeNode(self):
        self.removed = True

    def isEmpty(self):
        return False


class ParticleBudgetPolicyTests(unittest.TestCase):
    def test_enforce_particle_budget_keeps_latest_entries(self):
        nodes = [_Node(), _Node(), _Node(), _Node()]
        rows = [{"node": n, "marker": i} for i, n in enumerate(nodes)]

        trimmed = enforce_particle_budget(rows, 2)

        self.assertEqual(2, trimmed)
        self.assertEqual([2, 3], [row["marker"] for row in rows])
        self.assertTrue(nodes[0].removed)
        self.assertTrue(nodes[1].removed)
        self.assertFalse(nodes[2].removed)
        self.assertFalse(nodes[3].removed)

    def test_enforce_particle_budget_noop_when_under_limit(self):
        nodes = [_Node(), _Node()]
        rows = [{"node": n} for n in nodes]

        trimmed = enforce_particle_budget(rows, 4)

        self.assertEqual(0, trimmed)
        self.assertEqual(2, len(rows))
        self.assertFalse(nodes[0].removed)
        self.assertFalse(nodes[1].removed)

    def test_scale_particle_budget_keeps_base_when_fps_in_band(self):
        self.assertEqual(200, scale_particle_budget_for_fps(200, 45.0, min_fps=30.0, max_fps=60.0))

    def test_scale_particle_budget_reduces_under_min_fps(self):
        reduced = scale_particle_budget_for_fps(200, 20.0, min_fps=30.0, max_fps=60.0)
        self.assertLess(reduced, 200)
        self.assertGreaterEqual(reduced, 32)


if __name__ == "__main__":
    unittest.main()
