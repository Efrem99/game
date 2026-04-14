"""Shared helpers for lightweight UI sound playback."""


def play_ui_sfx(app, key, volume=1.0, rate=1.0):
    audio = getattr(app, "audio", None)
    if not audio:
        return False
    try:
        return bool(audio.play_sfx(str(key), volume=float(volume), rate=float(rate)))
    except Exception:
        return False
