"""Data-driven cutscene triggers for events and world zones."""

import math

from utils.logger import logger


class CutsceneTriggerManager:
    def __init__(self, app):
        self.app = app
        self._events = []
        self._zones = []
        self._fired_once = set()
        self._cooldowns = {}
        self._zone_inside = {}
        self._last_location = ""
        self._default_cooldown = 0.0
        self._load_config()

    def _now(self):
        try:
            from direct.showbase.ShowBaseGlobal import globalClock

            return float(globalClock.getFrameTime())
        except Exception:
            return 0.0

    def _norm(self, value):
        return str(value or "").strip().lower()

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safe_vec3(self, value):
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            try:
                return (float(value[0]), float(value[1]), float(value[2]))
            except Exception:
                return None
        return None

    def _load_config(self):
        cfg = getattr(getattr(self.app, "data_mgr", None), "cutscene_triggers", None)
        if not isinstance(cfg, dict):
            return
        settings = cfg.get("settings", {})
        if isinstance(settings, dict):
            self._default_cooldown = max(
                0.0, self._safe_float(settings.get("default_cooldown", 0.0), 0.0)
            )

        event_triggers = cfg.get("event_triggers", [])
        if isinstance(event_triggers, list):
            for item in event_triggers:
                if isinstance(item, dict):
                    self._events.append(dict(item))

        zone_triggers = cfg.get("zone_triggers", [])
        if isinstance(zone_triggers, list):
            for item in zone_triggers:
                if isinstance(item, dict):
                    self._zones.append(dict(item))

        logger.info(
            f"[CutsceneTriggers] Loaded event_triggers={len(self._events)} zone_triggers={len(self._zones)}"
        )

    def _trigger_id(self, trigger, fallback):
        token = self._norm(trigger.get("id"))
        return token if token else str(fallback)

    def _trigger_cooldown(self, trigger):
        return max(
            0.0,
            self._safe_float(
                trigger.get("cooldown", self._default_cooldown), self._default_cooldown
            ),
        )

    def _can_fire(self, trigger_id, trigger):
        if bool(trigger.get("once", False)) and trigger_id in self._fired_once:
            return False
        now = self._now()
        next_time = float(self._cooldowns.get(trigger_id, -99999.0))
        return now >= next_time

    def _mark_fired(self, trigger_id, trigger):
        if bool(trigger.get("once", False)):
            self._fired_once.add(trigger_id)
        cd = self._trigger_cooldown(trigger)
        if cd > 0.0:
            self._cooldowns[trigger_id] = self._now() + cd

    def _matches_event(self, trigger, event_name, payload):
        ev = self._norm(trigger.get("event"))
        if ev != self._norm(event_name):
            return False

        if "location" in trigger:
            expected = self._norm(trigger.get("location"))
            got = self._norm((payload or {}).get("location"))
            if expected and got != expected:
                return False

        if "quest_id" in trigger:
            expected = self._norm(trigger.get("quest_id"))
            got = self._norm((payload or {}).get("quest_id"))
            if expected and got != expected:
                return False

        if "mode" in trigger:
            expected = self._norm(trigger.get("mode"))
            got = self._norm((payload or {}).get("mode"))
            if expected and got != expected:
                return False

        if "phase" in trigger:
            expected = self._norm(trigger.get("phase"))
            got = self._norm((payload or {}).get("phase"))
            if expected and got != expected:
                return False
        return True

    def _shot_from_trigger(self, trigger):
        shot = trigger.get("shot", trigger)
        if not isinstance(shot, dict):
            shot = {}
        trigger_id = self._trigger_id(trigger, "trigger")
        return {
            "name": str(shot.get("name") or trigger.get("id") or "shot"),
            "duration": self._safe_float(shot.get("duration", 1.25), 1.25),
            "profile": str(shot.get("profile", "exploration") or "exploration"),
            "side": self._safe_float(shot.get("side", 0.0), 0.0),
            "yaw_bias_deg": self._safe_float(shot.get("yaw_bias_deg", 0.0), 0.0),
            "priority": int(self._safe_float(shot.get("priority", 68), 68)),
            "owner": str(shot.get("owner") or f"cutscene:{trigger_id}"),
        }

    def _play_shot(self, trigger):
        shot = self._shot_from_trigger(trigger)
        player = getattr(self.app, "player", None)
        if not player or not getattr(player, "actor", None):
            return False
        try:
            return bool(
                self.app.play_camera_shot(
                    name=shot["name"],
                    duration=shot["duration"],
                    profile=shot["profile"],
                    side=shot["side"],
                    yaw_bias_deg=shot["yaw_bias_deg"],
                    priority=shot["priority"],
                    owner=shot["owner"],
                )
            )
        except Exception as exc:
            logger.debug(f"[CutsceneTriggers] Failed to play shot '{shot['name']}': {exc}")
            return False

    def emit(self, event_name, payload=None):
        payload = payload or {}
        for idx, trigger in enumerate(self._events):
            if not self._matches_event(trigger, event_name, payload):
                continue
            trigger_id = self._trigger_id(trigger, f"event_{idx}")
            if not self._can_fire(trigger_id, trigger):
                continue
            fired = self._play_shot(trigger)
            if fired:
                self._mark_fired(trigger_id, trigger)
                logger.info(
                    f"[CutsceneTriggers] Fired event trigger '{trigger_id}' on '{event_name}'"
                )

    def _match_zone(self, zone, location_name):
        expected_location = self._norm(zone.get("location"))
        if expected_location and expected_location != self._norm(location_name):
            return False
        return True

    def _zone_inside_check(self, zone, player_pos):
        center = self._safe_vec3(zone.get("center"))
        if not center:
            return False
        radius = max(0.1, self._safe_float(zone.get("radius", 1.0), 1.0))

        dx = float(player_pos.x) - center[0]
        dy = float(player_pos.y) - center[1]
        dz = float(player_pos.z) - center[2]
        dist = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
        return dist <= radius

    def update(self, player_pos, location_name=None):
        if player_pos is None:
            return

        loc_token = self._norm(location_name)
        if loc_token and loc_token != self._last_location:
            self.emit("location_enter", {"location": location_name})
        self._last_location = loc_token

        for idx, zone in enumerate(self._zones):
            zone_id = self._trigger_id(zone, f"zone_{idx}")
            if not self._match_zone(zone, location_name):
                self._zone_inside[zone_id] = False
                continue

            inside = self._zone_inside_check(zone, player_pos)
            prev_inside = bool(self._zone_inside.get(zone_id, False))
            self._zone_inside[zone_id] = inside

            if inside and (not prev_inside):
                if not self._can_fire(zone_id, zone):
                    continue
                fired = self._play_shot(zone.get("on_enter", zone))
                if fired:
                    self._mark_fired(zone_id, zone)
                    logger.info(f"[CutsceneTriggers] Zone enter trigger fired: {zone_id}")
