import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.shop_manager import ShopManager


class _Backend:
    def __init__(self, recursive=None):
        self._recursive = dict(recursive or {})

    def load_recursive(self, rel_dir):
        return dict(self._recursive.get(str(rel_dir), {}))


class ShopManagerBackendBridgeTests(unittest.TestCase):
    def test_loads_merchant_inventory_from_backend_recursive_data(self):
        backend = _Backend(
            recursive={
                "shops": {
                    "merchant_general": {
                        "merchant_id": "merchant_general",
                        "merchant_name": "Merchant Aldric",
                        "items": [{"id": "iron_sword"}],
                    }
                }
            }
        )
        app = SimpleNamespace(
            data_mgr=SimpleNamespace(backend=backend, data_dir=ROOT / "data"),
            project_root=str(ROOT),
        )

        manager = ShopManager(app)

        self.assertIn("merchant_general", manager._merchant_inventories)
        self.assertEqual(
            "Merchant Aldric",
            manager._merchant_inventories["merchant_general"]["name"],
        )


if __name__ == "__main__":
    unittest.main()
