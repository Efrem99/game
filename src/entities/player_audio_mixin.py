"""Player audio helper methods."""

import math

from direct.showbase.ShowBaseGlobal import globalClock


_CONTEXTUAL_STATE_SFX = {
    "vaulting": ("parkour_vault", 0.46, 1.04),
    "climbing": ("parkour_climb", 0.42, 0.96),
    "wallrun": ("parkour_wallrun", 0.48, 1.06),
    "flight_takeoff": ("flight_takeoff", 0.50, 1.00),
    "flight_land": ("flight_land", 0.46, 0.98),
}


class PlayerAudioMixin:
    def _play_sfx(self, sfx_key, volume=1.0, rate=1.0):
        audio = getattr(self.app, "audio", None)
        if not audio:
            return False
        try:
            return bool(audio.play_sfx(sfx_key, volume=volume, rate=rate))
        except Exception:
            return False

    def _footstep_key(self, in_water=False):
        if in_water:
            return "footstep_water"
        loc_name = ""
        world = getattr(self.app, "world", None)
        if world and isinstance(getattr(world, "active_location", None), str):
            loc_name = world.active_location.lower()
        if any(token in loc_name for token in ("castle", "hall", "town", "street")):
            return "footstep_stone"
        if any(token in loc_name for token in ("dock", "bridge", "ship", "wood")):
            return "footstep_wood"
        return "footstep_grass"

    def _update_footsteps(self, dt, moving, running, in_water=False):
        if not moving:
            self._footstep_timer = 0.0
            return
        interval = 0.31 if running else 0.46
        self._footstep_timer += max(0.0, float(dt))
        if self._footstep_timer < interval:
            return
        self._footstep_timer = 0.0
        key = self._footstep_key(in_water=in_water)
        jitter = 0.96 + (0.08 * math.sin(globalClock.getFrameTime() * 7.0))
        self._play_sfx(key, volume=0.72 if running else 0.62, rate=jitter)

    def _contextual_audio_flags(self):
        cs = getattr(self, "cs", None)
        return {
            "in_water": bool(
                getattr(cs, "inWater", False) or getattr(self, "_py_in_water", False)
            ),
            "is_flying": bool(getattr(self, "_is_flying", False)),
        }

    def _play_contextual_water_sfx(self, flags, last_flags):
        if flags["in_water"] and not bool(last_flags.get("in_water", False)):
            self._play_sfx("swim_enter", volume=0.44, rate=0.98)
            return
        if (not flags["in_water"]) and bool(last_flags.get("in_water", False)):
            self._play_sfx("swim_exit", volume=0.40, rate=1.02)

    def _play_contextual_state_change_sfx(self, current_state, last_state, flags, last_flags):
        if current_state == last_state:
            return
        payload = _CONTEXTUAL_STATE_SFX.get(current_state)
        if payload:
            self._play_sfx(payload[0], volume=payload[1], rate=payload[2])
            return
        if (not flags["is_flying"]) and bool(last_flags.get("is_flying", False)):
            self._play_sfx("flight_land", volume=0.44, rate=0.96)

    def _update_contextual_state_sfx(self):
        current_state = str(getattr(self, "_anim_state", "") or "").strip().lower()
        flags = self._contextual_audio_flags()
        last_flags = getattr(self, "_last_contextual_sfx_flags", None)
        if not isinstance(last_flags, dict):
            last_flags = {}

        last_state = str(getattr(self, "_last_contextual_sfx_state", "") or "").strip().lower()
        self._play_contextual_water_sfx(flags, last_flags)
        self._play_contextual_state_change_sfx(current_state, last_state, flags, last_flags)
        self._last_contextual_sfx_state = current_state
        self._last_contextual_sfx_flags = dict(flags)
