import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.shop_ui import ShopUI


class _ShopBackendDummy:
    _load_default_shop = ShopUI._load_default_shop

    def __init__(self):
        self.app = SimpleNamespace(
            data_mgr=SimpleNamespace(
                items={
                    "iron_sword": {
                        "id": "iron_sword",
                        "name": "Iron Sword",
                        "type": "weapon",
                        "description": "A sturdy starter blade.",
                    }
                }
            )
        )


class ShopUIBackendBridgeTests(unittest.TestCase):
    def test_default_shop_prefers_backend_items_when_disk_scan_is_unavailable(self):
        dummy = _ShopBackendDummy()

        with patch("ui.shop_ui.os.path.isdir", return_value=False):
            items = dummy._load_default_shop()

        self.assertEqual(1, len(items))
        self.assertEqual("iron_sword", items[0]["id"])
        self.assertEqual(50, items[0]["price"])


if __name__ == "__main__":
    unittest.main()
