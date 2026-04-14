import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_movement_mixin import PlayerMovementMixin


class _VehicleAnimDummy:
    _update_vehicle_control = PlayerMovementMixin._update_vehicle_control

    def __init__(self, mounted_kind="ship", moved=True):
        self.app = SimpleNamespace(
            vehicle_mgr=SimpleNamespace(
                is_mounted=True,
                update_mounted=lambda player, dt, mx, my, running, cam_yaw: bool(moved),
                mounted_vehicle=lambda: {"kind": mounted_kind},
            )
        )
        self._is_flying = False
        self._anim_state = "idle"
        self._state_lock_until = 0.0
        self._set_calls = []
        self._blend_ticks = []

    def _set_flight_fx(self, enabled):
        self._flight_fx = bool(enabled)

    def _set_weapon_drawn(self, enabled, reset_timer=False):
        self._weapon_drawn = bool(enabled)
        self._weapon_reset = bool(reset_timer)

    def _get_action(self, action):
        return False

    def _run_animation_state_machine(self):
        vehicle = self.app.vehicle_mgr.mounted_vehicle()
        kind = str(vehicle.get("kind", "") or "").strip().lower()
        if kind in {"ship", "boat"}:
            self._anim_state = "mounted_ship_move"
        else:
            self._anim_state = "mounted_move"

    def _set_anim(self, state_name, loop=True, blend_time=None, force=False):
        self._set_calls.append((str(state_name), bool(loop)))
        self._anim_state = str(state_name)
        return True

    def _tick_anim_blend(self, dt):
        self._blend_ticks.append(float(dt))


class VehicleAnimationStateTests(unittest.TestCase):
    def test_ship_mount_control_keeps_ship_move_state(self):
        actor = _VehicleAnimDummy(mounted_kind="ship", moved=True)

        actor._update_vehicle_control(0.016, 0.0, 0.0, 1.0)

        self.assertEqual("mounted_ship_move", actor._anim_state)
        self.assertEqual(("mounted_ship_move", True), actor._set_calls[-1])

    def test_ship_mount_control_keeps_ship_idle_state(self):
        actor = _VehicleAnimDummy(mounted_kind="boat", moved=False)

        actor._update_vehicle_control(0.016, 0.0, 0.0, 0.0)

        self.assertEqual("mounted_ship_idle", actor._anim_state)
        self.assertEqual(("mounted_ship_idle", True), actor._set_calls[-1])

    def test_land_mount_control_keeps_generic_mounted_move(self):
        actor = _VehicleAnimDummy(mounted_kind="horse", moved=True)

        actor._update_vehicle_control(0.016, 0.0, 1.0, 0.0)

        self.assertEqual("mounted_move", actor._anim_state)
        self.assertEqual(("mounted_move", True), actor._set_calls[-1])


if __name__ == "__main__":
    unittest.main()
