"""Event-driven time scaling manager (slow-mo/bullet-time channels)."""

from direct.showbase.ShowBaseGlobal import globalClock


class TimeFxManager:
    def __init__(self, app):
        self.app = app
        self._events = []
        self._scales = {
            "world": 1.0,
            "player": 1.0,
            "enemies": 1.0,
            "physics": 1.0,
            "particles": 1.0,
        }

    def _now(self):
        return float(globalClock.getFrameTime())

    def trigger(self, kind="combat", duration=0.25, scales=None):
        default = {
            "world": 0.40,
            "player": 0.82,
            "enemies": 0.35,
            "physics": 0.46,
            "particles": 0.25,
        }
        if str(kind or "").strip().lower() in {"micro_hit", "combo_tick"}:
            default = {
                "world": 0.55,
                "player": 0.90,
                "enemies": 0.52,
                "physics": 0.65,
                "particles": 0.45,
            }
            duration = 0.12 if duration is None else duration
        elif str(kind or "").strip().lower() in {"perfect_dodge", "parry"}:
            default = {
                "world": 0.32,
                "player": 0.86,
                "enemies": 0.26,
                "physics": 0.40,
                "particles": 0.22,
            }
            duration = 0.22 if duration is None else duration
        elif str(kind or "").strip().lower() in {"death", "hard_fall"}:
            default = {
                "world": 0.24,
                "player": 0.70,
                "enemies": 0.20,
                "physics": 0.30,
                "particles": 0.14,
            }
            duration = 0.45 if duration is None else duration

        row = {
            "kind": str(kind or "slowmo"),
            "start": self._now(),
            "duration": max(0.05, min(2.5, float(duration or 0.25))),
            "scales": dict(default),
        }
        if isinstance(scales, dict):
            for key, value in scales.items():
                if key in row["scales"]:
                    try:
                        row["scales"][key] = max(0.05, min(1.0, float(value)))
                    except Exception:
                        continue
        self._events.append(row)

    def update(self, dt):
        _ = dt
        now = self._now()
        self._events = [e for e in self._events if now <= (float(e["start"]) + float(e["duration"]))]

        # If multiple events overlap, apply strongest slow-down per channel.
        channels = {k: 1.0 for k in self._scales.keys()}
        for event in self._events:
            t = (now - float(event["start"])) / max(1e-4, float(event["duration"]))
            if t < 0.0 or t > 1.0:
                continue
            # Smooth recovery to real-time.
            ease = t * t * (3.0 - (2.0 * t))
            for ch, base_scale in event.get("scales", {}).items():
                if ch not in channels:
                    continue
                target = float(base_scale) + ((1.0 - float(base_scale)) * ease)
                channels[ch] = min(channels[ch], max(0.05, min(1.0, target)))

        self._scales.update(channels)

    def scaled_dt(self, channel, dt):
        token = str(channel or "world").strip().lower()
        scale = float(self._scales.get(token, 1.0))
        return max(0.0, float(dt) * max(0.05, min(1.0, scale)))

    def get_scales(self):
        return dict(self._scales)
