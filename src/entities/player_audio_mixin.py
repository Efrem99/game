"""Player audio helper methods."""

import math

from direct.showbase.ShowBaseGlobal import globalClock


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
