import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player
from managers.vehicle_manager import VehicleManager


class MountKindAliasTests(unittest.TestCase):
    def test_vehicle_manager_normalizes_new_mount_aliases(self):
        manager = VehicleManager.__new__(VehicleManager)
        self.assertEqual("ship", manager._normalize_kind("boat"))
        self.assertEqual("wolf", manager._normalize_kind("dire_wolf"))
        self.assertEqual("stag", manager._normalize_kind("elk"))

    def test_player_mount_anim_kind_uses_horse_fallback_for_new_mounts(self):
        class _Dummy:
            _resolve_mount_anim_kind = Player._resolve_mount_anim_kind

        dummy = _Dummy()
        dummy._mount_anim_kind = "dire_wolf"
        dummy.app = SimpleNamespace(vehicle_mgr=None)
        self.assertEqual("horse", Player._current_mount_anim_kind(dummy))

    def test_player_mount_anim_kind_uses_vehicle_kind_when_cache_empty(self):
        vehicle_mgr = SimpleNamespace(
            is_mounted=True,
            mounted_vehicle=lambda: {"kind": "stag"},
        )
        class _Dummy:
            _resolve_mount_anim_kind = Player._resolve_mount_anim_kind

        dummy = _Dummy()
        dummy._mount_anim_kind = ""
        dummy.app = SimpleNamespace(vehicle_mgr=vehicle_mgr)
        self.assertEqual("horse", Player._current_mount_anim_kind(dummy))


if __name__ == "__main__":
    unittest.main()
