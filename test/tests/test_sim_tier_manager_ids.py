import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from world.sim_tier_manager import SimTierManager


class SimTierManagerIdTests(unittest.TestCase):
    def test_register_coerces_string_entity_id_to_stable_int_key(self):
        with patch("world.sim_tier_manager.HAS_CORE", False):
            mgr = SimTierManager(app=None)

        proxy = object()
        mgr.register("merchant_general", proxy)

        keys = list(mgr._entity_registry.keys())
        self.assertEqual(1, len(keys))
        self.assertIsInstance(keys[0], int)
        self.assertIs(mgr._entity_registry[keys[0]], proxy)

    def test_unregister_accepts_original_string_entity_id(self):
        with patch("world.sim_tier_manager.HAS_CORE", False):
            mgr = SimTierManager(app=None)

        mgr.register("merchant_general", object())
        mgr.unregister("merchant_general")

        self.assertEqual({}, mgr._entity_registry)


if __name__ == "__main__":
    unittest.main()
