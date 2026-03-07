"""Runtime stealth evaluator for player visibility/noise and NPC detection scaling."""

from __future__ import annotations

import math


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


class StealthManager:
    def __init__(self, app):
        self.app = app
        self._last_pos = None
        self._last_speed = 0.0
        self._state = self._empty_state()

    def _empty_state(self):
        return {
            "active": False,
            "is_crouched": False,
            "is_hidden": False,
            "state": "exposed",
            "stealth_level": 0.0,
            "noise": 1.0,
            "exposure": 1.0,
            "speed": 0.0,
            "detection_radius_mult": 1.0,
            "awareness_gain_mult": 1.0,
            "awareness_decay_mult": 1.0,
            "context_override": "",
            "hint": "",
        }

    def _estimate_speed(self, player, dt):
        cs = getattr(player, "cs", None)
        if cs is not None:
            try:
                vx = float(getattr(cs.velocity, "x", 0.0) or 0.0)
                vy = float(getattr(cs.velocity, "y", 0.0) or 0.0)
                speed = math.sqrt((vx * vx) + (vy * vy))
                self._last_speed = speed
                return speed
            except Exception:
                pass

        actor = getattr(player, "actor", None)
        if not actor:
            return float(self._last_speed)
        try:
            now = actor.getPos(self.app.render)
        except Exception:
            try:
                now = actor.getPos()
            except Exception:
                return float(self._last_speed)

        if self._last_pos is None:
            self._last_pos = now
            return float(self._last_speed)

        step = now - self._last_pos
        self._last_pos = now
        dt_safe = max(1e-3, float(dt or 0.0))
        speed = float(math.sqrt((step.x * step.x) + (step.y * step.y)) / dt_safe)
        self._last_speed = speed
        return speed

    def update(self, dt, player, world_state=None, motion_plan=None):
        if not player:
            self._state = self._empty_state()
            return dict(self._state)

        ws = world_state if isinstance(world_state, dict) else {}
        state = self._empty_state()
        state["active"] = True

        speed = max(0.0, float(self._estimate_speed(player, dt)))
        speed_norm = _clamp(speed / 9.0)
        state["speed"] = speed

        cs = getattr(player, "cs", None)
        in_water = bool(cs and getattr(cs, "inWater", False))
        is_flying = bool(getattr(player, "_is_flying", False))
        is_mounted = False
        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if vehicle_mgr and getattr(vehicle_mgr, "is_mounted", False):
            is_mounted = True

        anim_state = str(getattr(player, "_anim_state", "") or "").strip().lower()
        combat_now = anim_state in {
            "attacking",
            "attack_light",
            "attack_heavy",
            "casting",
            "dodging",
            "blocking",
            "staggered",
        }

        try:
            running = bool(player._get_action("run"))  # noqa: SLF001
        except Exception:
            running = False
        is_crouched = bool(getattr(player, "_stealth_crouch", False))
        if is_mounted or is_flying:
            is_crouched = False

        visibility = _clamp(ws.get("visibility", 1.0), 0.08, 1.0)
        is_night = bool(ws.get("is_night", False))
        weather = str(ws.get("weather", "") or "").strip().lower()
        weather_cover = 0.0
        if weather in {"rainy", "stormy"}:
            weather_cover = 0.16
        elif weather in {"overcast", "foggy"}:
            weather_cover = 0.08

        exposure = 0.26
        exposure += visibility * 0.50
        exposure += speed_norm * 0.40
        exposure += 0.24 if running else 0.0
        exposure += 0.08 if in_water else 0.0
        exposure += 0.22 if combat_now else 0.0
        exposure += 0.22 if is_flying else 0.0
        exposure += 0.16 if is_mounted else 0.0
        exposure -= 0.32 if is_crouched else 0.0
        exposure -= 0.10 if is_night else 0.0
        exposure -= weather_cover
        exposure = _clamp(exposure)

        noise = 0.08
        noise += speed_norm * 0.45
        noise += 0.28 if running else 0.0
        noise += 0.18 if in_water else 0.0
        noise += 0.24 if combat_now else 0.0
        noise -= 0.24 if is_crouched else 0.0
        noise = _clamp(noise)

        stealth_level = 1.0 - max(exposure * 0.78, noise * 0.66)
        stealth_level = _clamp(stealth_level)

        # Let movement utility slightly bias stealth profile, so cautious gait helps concealment.
        if isinstance(motion_plan, dict):
            motion = motion_plan.get("motion_plan", {})
            if isinstance(motion, dict):
                try:
                    gait = float(motion.get("gait_speed_mult", 1.0) or 1.0)
                except Exception:
                    gait = 1.0
                if gait < 0.95:
                    stealth_level = _clamp(stealth_level + ((0.95 - gait) * 0.18))

        if stealth_level >= 0.72:
            state_name = "hidden"
            hint = self.app.data_mgr.t("hud.stealth_hidden", "Hidden")
        elif stealth_level >= 0.42:
            state_name = "cautious"
            hint = self.app.data_mgr.t("hud.stealth_cautious", "Cautious")
        else:
            state_name = "exposed"
            hint = self.app.data_mgr.t("hud.stealth_exposed", "Exposed")

        detect_mult = 1.35 - (stealth_level * 0.86) + (noise * 0.18)
        detect_mult = max(0.48, min(1.45, detect_mult))
        gain_mult = max(0.35, min(1.50, 1.20 - (stealth_level * 0.82) + (noise * 0.32)))
        decay_mult = max(0.60, min(1.80, 0.85 + (stealth_level * 0.72) - (noise * 0.20)))

        state.update(
            {
                "is_crouched": bool(is_crouched),
                "is_hidden": bool(state_name == "hidden"),
                "state": state_name,
                "stealth_level": float(stealth_level),
                "noise": float(noise),
                "exposure": float(exposure),
                "detection_radius_mult": float(detect_mult),
                "awareness_gain_mult": float(gain_mult),
                "awareness_decay_mult": float(decay_mult),
                "context_override": "stealth" if (is_crouched and state_name != "exposed" and not combat_now) else "",
                "hint": str(hint),
            }
        )
        self._state = state
        return dict(self._state)

    def get_state(self):
        return dict(self._state)

