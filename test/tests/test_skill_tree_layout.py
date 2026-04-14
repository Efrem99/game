import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.menu_inventory import build_skill_tree_layout


class SkillTreeLayoutTests(unittest.TestCase):
    def test_build_skill_tree_layout_assigns_dependency_levels_and_edges(self):
        rows = [
            {
                "id": "guard_stance",
                "name": "Guard Stance",
                "branch_name": "Combat",
                "requires": [],
            },
            {
                "id": "power_strike",
                "name": "Power Strike",
                "branch_name": "Combat",
                "requires": ["guard_stance"],
            },
            {
                "id": "whirlwind",
                "name": "Whirlwind",
                "branch_name": "Combat",
                "requires": ["power_strike"],
            },
        ]

        layout = build_skill_tree_layout(rows)

        self.assertEqual(1, len(layout["branches"]))
        branch = layout["branches"][0]
        self.assertEqual("Combat", branch["branch_name"])
        self.assertEqual(
            {"guard_stance": 0, "power_strike": 1, "whirlwind": 2},
            {node["id"]: node["level"] for node in branch["nodes"]},
        )
        self.assertEqual(
            [("guard_stance", "power_strike"), ("power_strike", "whirlwind")],
            branch["edges"],
        )

    def test_build_skill_tree_layout_keeps_multiple_roots_on_same_level(self):
        rows = [
            {"id": "focus_step", "name": "Focus Step", "branch_name": "Mobility", "requires": []},
            {"id": "steady_feet", "name": "Steady Feet", "branch_name": "Mobility", "requires": []},
            {"id": "dash", "name": "Dash", "branch_name": "Mobility", "requires": ["focus_step"]},
        ]

        layout = build_skill_tree_layout(rows)

        branch = layout["branches"][0]
        levels = {node["id"]: node["level"] for node in branch["nodes"]}
        rows_by_id = {node["id"]: node["lane"] for node in branch["nodes"]}
        self.assertEqual(0, levels["focus_step"])
        self.assertEqual(0, levels["steady_feet"])
        self.assertEqual(1, levels["dash"])
        self.assertNotEqual(rows_by_id["focus_step"], rows_by_id["steady_feet"])


if __name__ == "__main__":
    unittest.main()
