"""Runtime audio routing for music, ambient loops, and event SFX."""

import os
import random
import re

from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import AudioSound

from utils.logger import logger


def _norm_key(value):
    token = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    return token.strip("_")


def _clamp01(value):
    try:
        fval = float(value)
    except Exception:
        fval = 1.0
    if fval < 0.0:
        return 0.0
    if fval > 1.0:
        return 1.0
    return fval


class _LoopChannel:
    def __init__(self, app, label, fade_time=1.6, use_music=True):
        self.app = app
        self.label = label
        self.use_music = bool(use_music)
        self.fade_time = max(0.01, float(fade_time))
        self.allow_overlap = True
        self._current = None
        self._current_path = None
        self._current_key = None
        self._current_target = 1.0
        self._next = None
        self._next_path = None
        self._next_key = None
        self._next_target = 1.0
        self._queued = None
        self._fading_out = False
        self._fading_in = False
        self._fade_out_from = 1.0
        self._fade_t = 0.0
        self._master_gain = 1.0

    def set_master_gain(self, gain):
        self._master_gain = _clamp01(gain)

    def _effective(self, value):
        return _clamp01(float(value) * float(self._master_gain))

    def set_fade_time(self, seconds):
        self.fade_time = max(0.01, float(seconds or 0.01))

    def set_allow_overlap(self, enabled):
        self.allow_overlap = bool(enabled)

    def _load_loop_sound(self, path):
        try:
            if self.use_music:
                snd = self.app.loader.loadMusic(path)
            else:
                snd = self.app.loader.loadSfx(path)
        except Exception as exc:
            logger.warning(f"[Audio] Failed to load {self.label} track '{path}': {exc}")
            return None

        if not snd:
            logger.warning(f"[Audio] Missing {self.label} track '{path}'")
            return None
        return snd

    def stop(self):
        for snd in (self._current, self._next):
            if snd:
                try:
                    snd.stop()
                except Exception:
                    pass
        self._current = None
        self._current_path = None
        self._current_key = None
        self._next = None
        self._next_path = None
        self._next_key = None
        self._queued = None
        self._fading_out = False
        self._fading_in = False
        self._fade_out_from = 1.0
        self._fade_t = 0.0

    def switch_to(self, track_key, path, volume):
        target = _clamp01(volume)
        if not path:
            self.stop()
            return False

        if self._current and self._current_path == path and self._next is None:
            self._current_key = track_key
            self._current_target = target
            try:
                self._current.setVolume(self._effective(target))
            except Exception:
                pass
            return True

        if not self.allow_overlap:
            self._next = None
            self._next_path = None
            self._next_key = None
            self._next_target = 1.0

            if self._current is None:
                snd = self._load_loop_sound(path)
                if not snd:
                    return False
                try:
                    snd.setLoop(True)
                    snd.setVolume(0.0)
                    snd.play()
                except Exception as exc:
                    logger.warning(f"[Audio] Failed to play {self.label} track '{path}': {exc}")
                    return False
                self._current = snd
                self._current_path = path
                self._current_key = track_key
                self._current_target = target
                self._fading_in = True
                self._fading_out = False
                self._fade_t = 0.0
                return True

            self._queued = (track_key, path, target)
            if not self._fading_out:
                self._fading_out = True
                self._fading_in = False
                self._fade_t = 0.0
                try:
                    self._fade_out_from = float(self._current.getVolume())
                except Exception:
                    self._fade_out_from = float(self._current_target)
            return True

        if self._next and self._next_path == path:
            self._next_key = track_key
            self._next_target = target
            return True

        snd = self._load_loop_sound(path)
        if not snd:
            return False

        try:
            snd.setLoop(True)
            snd.setVolume(self._effective(target) if self._current is None else 0.0)
            snd.play()
        except Exception as exc:
            logger.warning(f"[Audio] Failed to play {self.label} track '{path}': {exc}")
            return False

        if self._current is None:
            self._current = snd
            self._current_path = path
            self._current_key = track_key
            self._current_target = target
            self._next = None
            self._next_path = None
            self._next_key = None
            self._fade_t = 0.0
            return True

        if self._next:
            try:
                self._next.stop()
            except Exception:
                pass

        self._next = snd
        self._next_path = path
        self._next_key = track_key
        self._next_target = target
        self._fade_t = 0.0
        return True

    def update(self, dt):
        if not self.allow_overlap:
            if self._fading_out and self._current:
                self._fade_t += max(0.0, float(dt))
                t = min(1.0, self._fade_t / self.fade_time)
                try:
                    self._current.setVolume(self._effective(max(0.0, (1.0 - t) * self._fade_out_from)))
                except Exception:
                    pass
                if t >= 1.0:
                    try:
                        self._current.stop()
                    except Exception:
                        pass
                    self._current = None
                    self._current_path = None
                    self._current_key = None
                    self._current_target = 1.0
                    self._fading_out = False
                    self._fade_t = 0.0

            if self._current is None and self._queued:
                key, path, target = self._queued
                self._queued = None
                snd = self._load_loop_sound(path)
                if snd:
                    try:
                        snd.setLoop(True)
                        snd.setVolume(0.0)
                        snd.play()
                        self._current = snd
                        self._current_path = path
                        self._current_key = key
                        self._current_target = target
                        self._fading_in = True
                        self._fade_t = 0.0
                    except Exception:
                        self._fading_in = False
                        self._current = None

            if self._fading_in and self._current:
                self._fade_t += max(0.0, float(dt))
                t = min(1.0, self._fade_t / self.fade_time)
                try:
                    self._current.setVolume(self._effective(max(0.0, t * self._current_target)))
                except Exception:
                    pass
                if t >= 1.0:
                    self._fading_in = False
                    self._fade_t = 0.0
                return

            if self._current and not self._fading_out:
                try:
                    self._current.setVolume(self._effective(self._current_target))
                except Exception:
                    pass
            return

        if not self._current and self._next:
            self._current = self._next
            self._current_path = self._next_path
            self._current_key = self._next_key
            self._current_target = self._next_target
            self._next = None
            self._next_path = None
            self._next_key = None
            self._fade_t = 0.0
            return

        if self._current and self._next:
            self._fade_t += max(0.0, float(dt))
            t = min(1.0, self._fade_t / self.fade_time)
            try:
                self._current.setVolume(self._effective(max(0.0, (1.0 - t) * self._current_target)))
                self._next.setVolume(self._effective(max(0.0, t * self._next_target)))
            except Exception:
                pass

            if t >= 1.0:
                try:
                    self._current.stop()
                except Exception:
                    pass
                self._current = self._next
                self._current_path = self._next_path
                self._current_key = self._next_key
                self._current_target = self._next_target
                self._next = None
                self._next_path = None
                self._next_key = None
                self._fade_t = 0.0


class AudioDirector:
    def __init__(self, app):
        self.app = app
        self._rng = random.Random()
        self._missing_paths = set()
        self._sfx_pool = {}
        self._combat_until = 0.0
        self._boss_until = 0.0
        self._last_route_signature = None
        self._route_override = None

        cfg = getattr(self.app.data_mgr, "sound_config", None)
        if not isinstance(cfg, dict):
            cfg = {}
        self._cfg = cfg

        self._music = cfg.get("music", {}) if isinstance(cfg.get("music"), dict) else {}
        self._ambient = cfg.get("ambient", {}) if isinstance(cfg.get("ambient"), dict) else {}
        self._sfx = cfg.get("sfx", {}) if isinstance(cfg.get("sfx"), dict) else {}
        self._location_music = {
            _norm_key(k): v
            for k, v in (cfg.get("location_music", {}) or {}).items()
        }
        self._location_ambient = {
            _norm_key(k): v
            for k, v in (cfg.get("location_ambient", {}) or {}).items()
        }
        self._biome_ambient = {
            _norm_key(k): v
            for k, v in (cfg.get("biome_ambient", {}) or {}).items()
        }
        self._context_music = {
            _norm_key(k): _norm_key(v)
            for k, v in (cfg.get("context_music", {}) or {}).items()
            if str(v or "").strip()
        }
        self._context_ambient = {
            _norm_key(k): _norm_key(v)
            for k, v in (cfg.get("context_ambient", {}) or {}).items()
            if str(v or "").strip()
        }
        self._crossfade_time = max(0.05, float(cfg.get("crossfade_time", 1.5) or 1.5))
        self._combat_hold_time = max(0.25, float(cfg.get("combat_hold_time", 4.0) or 4.0))
        self._boss_hold_time = max(0.5, float(cfg.get("boss_hold_time", 6.0) or 6.0))
        self._music_no_overlap = bool(cfg.get("music_no_overlap", True))
        self._ambient_no_overlap = bool(cfg.get("ambient_no_overlap", True))
        self._ambient_enabled = bool(cfg.get("ambient_enabled", True))
        self._sfx_polyphony = max(1, int(cfg.get("sfx_polyphony", 4) or 4))
        self._sfx_global_limit = max(1, int(cfg.get("sfx_global_limit", 24) or 24))
        mixer_cfg = cfg.get("mixer", {}) if isinstance(cfg.get("mixer"), dict) else {}
        self._mix_dialog_music_duck = _clamp01(mixer_cfg.get("dialog_music_duck", 0.55))
        self._mix_dialog_ambient_duck = _clamp01(mixer_cfg.get("dialog_ambient_duck", 0.45))
        self._mix_boss_ambient_duck = _clamp01(mixer_cfg.get("boss_ambient_duck", 0.62))
        self._mix_combat_ambient_duck = _clamp01(mixer_cfg.get("combat_ambient_duck", 0.80))
        self._mix_ui_music_duck = _clamp01(mixer_cfg.get("ui_music_duck", 0.72))
        self._mix_voice_music_duck = _clamp01(mixer_cfg.get("voice_music_duck", 0.22))
        self._mix_voice_ambient_duck = _clamp01(mixer_cfg.get("voice_ambient_duck", 0.20))
        self._voices_path = str(cfg.get("voices_path", "data/audio/voices") or "data/audio/voices").strip()
        self._voice_volume = _clamp01(cfg.get("voice_volume", 0.88))
        self._active_voice = []
        voice_playback_cfg = cfg.get("voice_playback", {}) if isinstance(cfg.get("voice_playback"), dict) else {}
        self._voice_rate_jitter = max(0.0, min(0.25, float(voice_playback_cfg.get("rate_jitter", 0.018) or 0.018)))
        self._voice_volume_jitter = max(0.0, min(0.20, float(voice_playback_cfg.get("volume_jitter", 0.025) or 0.025)))
        self._voice_playrate_min = max(0.5, min(1.75, float(voice_playback_cfg.get("playrate_min", 0.86) or 0.86)))
        self._voice_playrate_max = max(self._voice_playrate_min, min(1.75, float(voice_playback_cfg.get("playrate_max", 1.14) or 1.14)))
        hybrid_cfg = cfg.get("voice_hybrid", {}) if isinstance(cfg.get("voice_hybrid"), dict) else {}
        self._voice_shadow_enabled = bool(hybrid_cfg.get("shadow_enabled", True))
        self._voice_shadow_volume = _clamp01(hybrid_cfg.get("shadow_volume", 0.52))
        self._voice_shadow_rate = max(0.5, min(1.75, float(hybrid_cfg.get("shadow_rate", 0.90) or 0.90)))
        self._voice_growl_volume = _clamp01(hybrid_cfg.get("growl_volume", 0.34))
        self._voice_growl_rate = max(0.5, min(1.75, float(hybrid_cfg.get("growl_rate", 0.86) or 0.86)))
        self._voice_growl_suffix = str(hybrid_cfg.get("growl_suffix", "_growl") or "_growl").strip()
        self._voice_growl_spike_chance = max(0.0, min(1.0, float(hybrid_cfg.get("growl_spike_chance", 0.0) or 0.0)))
        self._voice_resonance_volume = _clamp01(hybrid_cfg.get("resonance_volume", 0.0))
        self._voice_resonance_rate = max(0.5, min(1.75, float(hybrid_cfg.get("resonance_rate", 0.72) or 0.72)))
        self._voice_resonance_key = str(hybrid_cfg.get("resonance_key", "") or "").strip()
        raw_voice_emotions = cfg.get("voice_emotions", {}) if isinstance(cfg.get("voice_emotions"), dict) else {}
        self._voice_emotions = self._build_voice_emotion_profiles(raw_voice_emotions)
        self._voice_emotion = "default"
        self._voice_emotion_intensity = 1.0
        corruption_cfg = cfg.get("world_corruption", {}) if isinstance(cfg.get("world_corruption"), dict) else {}
        self._world_corruption_music_duck = _clamp01(corruption_cfg.get("music_duck", 0.0))
        self._world_corruption_ambient_duck = _clamp01(corruption_cfg.get("ambient_duck", 0.0))
        self._world_corruption_shadow_boost = max(0.0, float(corruption_cfg.get("voice_shadow_boost", 0.0) or 0.0))
        self._world_corruption_growl_boost = max(0.0, float(corruption_cfg.get("voice_growl_boost", 0.0) or 0.0))
        self._world_corruption_resonance_boost = max(0.0, float(corruption_cfg.get("voice_resonance_boost", 0.0) or 0.0))
        self._world_corruption_lerp_speed = max(0.05, min(16.0, float(corruption_cfg.get("lerp_speed", 3.0) or 3.0)))
        self._world_corruption = _clamp01(corruption_cfg.get("initial", 0.0))
        self._world_corruption_target = float(self._world_corruption)
        raw_cooldowns = cfg.get("sfx_cooldowns", {})
        self._sfx_cooldowns = {}
        if isinstance(raw_cooldowns, dict):
            for key, value in raw_cooldowns.items():
                norm_key = _norm_key(key)
                if not norm_key:
                    continue
                try:
                    seconds = max(0.0, float(value))
                except Exception:
                    continue
                self._sfx_cooldowns[norm_key] = seconds
        self._sfx_last_play = {}
        self._priority_cfg = self._build_priority_config(cfg.get("priority", {}))

        self._music_channel = _LoopChannel(
            self.app,
            "music",
            fade_time=self._crossfade_time,
            use_music=True,
        )
        self._ambient_channel = _LoopChannel(
            self.app,
            "ambient",
            fade_time=max(0.05, self._crossfade_time * 0.8),
            use_music=False,
        )
        self._bind_event_bus()

    def _cleanup_voice_instances(self):
        alive = []
        for snd in list(self._active_voice):
            if not snd:
                continue
            try:
                if snd.status() == AudioSound.PLAYING:
                    alive.append(snd)
            except Exception:
                continue
        self._active_voice = alive

    def _voice_delivery(self, base_volume, base_rate=1.0):
        volume = _clamp01(base_volume)
        rate = max(0.5, min(1.75, float(base_rate or 1.0)))
        if self._voice_volume_jitter > 0.0:
            volume = _clamp01(volume + self._rng.uniform(-self._voice_volume_jitter, self._voice_volume_jitter))
        if self._voice_rate_jitter > 0.0:
            rate += self._rng.uniform(-self._voice_rate_jitter, self._voice_rate_jitter)
        rate = max(self._voice_playrate_min, min(self._voice_playrate_max, rate))
        return volume, rate

    def _float_or(self, value, default):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _build_voice_emotion_profiles(self, payload):
        base = {
            "main": 1.0,
            "shadow": float(self._voice_shadow_volume),
            "growl": float(self._voice_growl_volume),
            "resonance": float(self._voice_resonance_volume),
            "rate": 1.0,
        }
        out = {"default": dict(base)}
        if not isinstance(payload, dict):
            return out
        for raw_key, raw_profile in payload.items():
            token = _norm_key(raw_key)
            if not token:
                continue
            row = dict(base)
            if isinstance(raw_profile, dict):
                row["main"] = self._float_or(raw_profile.get("main", row["main"]), row["main"])
                row["shadow"] = self._float_or(raw_profile.get("shadow", row["shadow"]), row["shadow"])
                row["growl"] = self._float_or(raw_profile.get("growl", row["growl"]), row["growl"])
                row["resonance"] = self._float_or(raw_profile.get("resonance", row["resonance"]), row["resonance"])
                row["rate"] = self._float_or(raw_profile.get("rate", row["rate"]), row["rate"])
            out[token] = row
        if "default" not in out:
            out["default"] = dict(base)
        return out

    def set_voice_emotion(self, emotion, intensity=1.0):
        token = _norm_key(emotion) or "default"
        if token not in self._voice_emotions:
            token = "default"
        self._voice_emotion = token
        self._voice_emotion_intensity = _clamp01(intensity)
        return token

    def get_voice_emotion(self):
        return str(self._voice_emotion or "default"), float(self._voice_emotion_intensity)

    def set_world_corruption(self, value, immediate=False):
        self._world_corruption_target = _clamp01(value)
        if immediate:
            self._world_corruption = float(self._world_corruption_target)
        return float(self._world_corruption_target)

    def get_world_corruption(self):
        return _clamp01(self._world_corruption)

    def _update_world_corruption(self, dt):
        dt = max(0.0, float(dt or 0.0))
        if dt <= 0.0:
            return
        current = float(self._world_corruption)
        target = float(self._world_corruption_target)
        if abs(target - current) <= 1e-6:
            self._world_corruption = target
            return
        alpha = min(1.0, dt * float(self._world_corruption_lerp_speed))
        self._world_corruption = current + (target - current) * alpha

    def _resolve_voice_profile(self, emotion=None, intensity=1.0, corruption=None):
        base = dict(self._voice_emotions.get("default", {}))
        token = _norm_key(emotion) if emotion else _norm_key(self._voice_emotion)
        if not token:
            token = "default"
        profile = self._voice_emotions.get(token, self._voice_emotions.get("default", {}))
        mix = _clamp01(intensity if emotion is not None else self._voice_emotion_intensity)
        out = {}
        for key in ("main", "shadow", "growl", "resonance", "rate"):
            a = self._float_or(base.get(key, 1.0), 1.0)
            b = self._float_or(profile.get(key, a), a)
            out[key] = a + (b - a) * mix
        cor = self.get_world_corruption() if corruption is None else _clamp01(corruption)
        out["shadow"] *= 1.0 + cor * float(self._world_corruption_shadow_boost)
        out["growl"] *= 1.0 + cor * float(self._world_corruption_growl_boost)
        out["resonance"] *= 1.0 + cor * float(self._world_corruption_resonance_boost)
        out["main"] = max(0.0, out["main"])
        out["shadow"] = max(0.0, out["shadow"])
        out["growl"] = max(0.0, out["growl"])
        out["resonance"] = max(0.0, out["resonance"])
        out["rate"] = max(0.5, min(1.75, out["rate"]))
        return out

    def _auto_growl_key(self, voice_key):
        token = str(voice_key or "").strip().replace("\\", "/")
        if not token or token.lower().endswith((".ogg", ".mp3", ".wav")):
            return ""
        suffix = str(self._voice_growl_suffix or "").strip()
        if not suffix:
            return ""
        return f"{token}{suffix}"

    def play_hybrid_voice_key(
        self,
        voice_key,
        *,
        growl_key=None,
        volume=1.0,
        rate=1.0,
        emotion=None,
        emotion_intensity=1.0,
        corruption=None,
        resonance_key=None,
    ):
        key = str(voice_key or "").strip()
        if not key:
            return False
        profile = self._resolve_voice_profile(
            emotion=emotion,
            intensity=emotion_intensity,
            corruption=corruption,
        )
        base_volume = max(0.0, float(volume or 0.0))
        base_rate = max(0.5, min(1.75, float(rate or 1.0)))
        played_any = False

        main_rate = max(0.5, min(1.75, base_rate * float(profile["rate"])))
        if self.play_voice_key(
            key,
            volume=base_volume * float(profile["main"]),
            rate=main_rate,
        ):
            played_any = True

        if self._voice_shadow_enabled and float(profile["shadow"]) > 0.0001:
            if self.play_voice_key(
                key,
                volume=base_volume * float(profile["shadow"]),
                rate=max(0.5, min(1.75, main_rate * float(self._voice_shadow_rate))),
            ):
                played_any = True

        growl_token = str(growl_key or "").strip() or self._auto_growl_key(key)
        if growl_token and float(profile["growl"]) > 0.0001:
            growl_rate = max(0.5, min(1.75, main_rate * float(self._voice_growl_rate)))
            growl_volume = base_volume * float(profile["growl"])
            if self.play_voice_key(
                growl_token,
                volume=growl_volume,
                rate=growl_rate,
            ):
                played_any = True
                if self._voice_growl_spike_chance > 0.0 and self._rng.random() < self._voice_growl_spike_chance:
                    self.play_voice_key(
                        growl_token,
                        volume=growl_volume * 0.68,
                        rate=max(0.5, min(1.75, growl_rate * 0.97)),
                    )

        resonance_token = str(resonance_key or "").strip()
        if not resonance_token:
            resonance_token = str(self._voice_resonance_key or "").strip()
        if not resonance_token:
            resonance_token = growl_token
        if resonance_token and float(profile["resonance"]) > 0.0001:
            if self.play_voice_key(
                resonance_token,
                volume=base_volume * float(profile["resonance"]),
                rate=max(0.5, min(1.75, main_rate * float(self._voice_resonance_rate))),
            ):
                played_any = True

        return played_any

    def _int_priority(self, value, default):
        try:
            out = int(value)
        except Exception:
            out = int(default)
        return max(-999, min(999, out))

    def _build_priority_config(self, payload):
        music = {
            "default": 10,
            "location": 44,
            "context": 64,
            "combat": 86,
            "boss": 96,
            "override": 120,
        }
        ambient = {
            "default": 12,
            "biome": 28,
            "location": 46,
            "context": 62,
            "water": 86,
            "flight": 78,
            "override": 110,
        }
        music_context = {}
        ambient_context = {}
        if isinstance(payload, dict):
            row_music = payload.get("music", {})
            if isinstance(row_music, dict):
                for key, value in row_music.items():
                    token = _norm_key(key)
                    if token:
                        music[token] = self._int_priority(value, music.get(token, 10))
            row_ambient = payload.get("ambient", {})
            if isinstance(row_ambient, dict):
                for key, value in row_ambient.items():
                    token = _norm_key(key)
                    if token:
                        ambient[token] = self._int_priority(value, ambient.get(token, 12))
            row_music_ctx = payload.get("music_context", {})
            if isinstance(row_music_ctx, dict):
                for key, value in row_music_ctx.items():
                    token = _norm_key(key)
                    if token:
                        music_context[token] = self._int_priority(value, music.get("context", 64))
            row_ambient_ctx = payload.get("ambient_context", {})
            if isinstance(row_ambient_ctx, dict):
                for key, value in row_ambient_ctx.items():
                    token = _norm_key(key)
                    if token:
                        ambient_context[token] = self._int_priority(value, ambient.get("context", 62))
        return {
            "music": music,
            "ambient": ambient,
            "music_context": music_context,
            "ambient_context": ambient_context,
        }

    def _prio(self, family, key, fallback):
        cfg = self._priority_cfg.get(family, {})
        if not isinstance(cfg, dict):
            return self._int_priority(fallback, fallback)
        return self._int_priority(cfg.get(_norm_key(key), fallback), fallback)

    def _bind_event_bus(self):
        bus = getattr(self.app, "event_bus", None)
        if not bus or not hasattr(bus, "subscribe"):
            return
        try:
            bus.subscribe("audio.sfx.play", self._on_event_sfx, priority=70)
            bus.subscribe("audio.voice.play", self._on_event_voice, priority=72)
            bus.subscribe("audio.voice.emotion", self._on_event_voice_emotion, priority=73)
            bus.subscribe("audio.corruption.set", self._on_event_corruption_set, priority=73)
            bus.subscribe("audio.route.override", self._on_event_route_override, priority=76)
            bus.subscribe("audio.route.clear", self._on_event_route_clear, priority=76)
        except Exception as exc:
            logger.debug(f"[Audio] Event bus bind failed: {exc}")

    def _on_event_sfx(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.play_sfx(
            payload.get("key", ""),
            volume=payload.get("volume", 1.0),
            rate=payload.get("rate", 1.0),
        )

    def _on_event_voice(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        key = str(payload.get("key", "") or "").strip()
        path = str(payload.get("path", "") or "").strip()
        hybrid = bool(payload.get("hybrid", False))
        growl_key = str(payload.get("growl_key", "") or "").strip()
        emotion = str(payload.get("emotion", "") or "").strip()
        resonance_key = str(payload.get("resonance_key", "") or "").strip()
        corruption_value = payload.get("corruption", None)
        if key and (hybrid or growl_key or emotion or resonance_key or (corruption_value is not None)):
            self.play_hybrid_voice_key(
                key,
                growl_key=growl_key,
                volume=payload.get("volume", 1.0),
                rate=payload.get("rate", 1.0),
                emotion=emotion or None,
                emotion_intensity=payload.get("emotion_intensity", 1.0),
                corruption=corruption_value,
                resonance_key=resonance_key or None,
            )
            return
        if key:
            self.play_voice_key(key, volume=payload.get("volume", 1.0), rate=payload.get("rate", 1.0))
        elif path:
            self.play_voice_path(path, volume=payload.get("volume", 1.0), rate=payload.get("rate", 1.0))

    def _on_event_voice_emotion(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.set_voice_emotion(
            payload.get("emotion", "default"),
            intensity=payload.get("intensity", 1.0),
        )

    def _on_event_corruption_set(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.set_world_corruption(
            payload.get("value", 0.0),
            immediate=bool(payload.get("immediate", False)),
        )

    def _on_event_route_override(self, event_name, payload):
        _ = event_name
        if not isinstance(payload, dict):
            return
        self.request_route_override(
            music_key=payload.get("music_key"),
            ambient_key=payload.get("ambient_key"),
            priority=payload.get("priority", self._prio("music", "override", 120)),
            hold_seconds=payload.get("hold_seconds", 0.0),
            owner=payload.get("owner", "event_bus"),
        )

    def _on_event_route_clear(self, event_name, payload):
        _ = event_name
        _ = payload
        self.clear_route_override()

    def request_route_override(self, music_key=None, ambient_key=None, priority=120, hold_seconds=0.0, owner="runtime"):
        now = globalClock.getFrameTime()
        token_music = _norm_key(music_key) if music_key else ""
        token_ambient = _norm_key(ambient_key) if ambient_key else ""
        if not token_music and not token_ambient:
            return False
        duration = float(hold_seconds or 0.0)
        target_until = now + duration if duration > 0.0 else (now + 86400.0)
        prio = self._int_priority(priority, self._prio("music", "override", 120))
        if isinstance(self._route_override, dict):
            active_until = float(self._route_override.get("until", -9999.0))
            old_prio = int(self._route_override.get("priority", -999))
            if now < active_until and prio < old_prio:
                return False
        self._route_override = {
            "music_key": token_music,
            "ambient_key": token_ambient,
            "priority": prio,
            "until": target_until,
            "owner": str(owner or "runtime"),
        }
        return True

    def clear_route_override(self):
        self._route_override = None

    def _active_sfx_count(self):
        total = 0
        for pool in self._sfx_pool.values():
            if not isinstance(pool, list):
                continue
            for snd in pool:
                try:
                    if snd.status() == AudioSound.PLAYING:
                        total += 1
                except Exception:
                    continue
        return total

    def _resolve_path(self, path):
        if not isinstance(path, str) or not path.strip():
            return None

        raw = path.strip().replace("\\", "/")
        if os.path.isabs(raw):
            if os.path.exists(raw):
                return raw
            return None

        root = getattr(self.app, "project_root", os.getcwd())
        candidate = os.path.join(root, raw)
        if os.path.exists(candidate):
            return raw

        alt = os.path.join(root, "data", "audio", os.path.basename(raw))
        if os.path.exists(alt):
            return os.path.relpath(alt, root).replace("\\", "/")
        return None

    def _resolve_spec(self, spec):
        if isinstance(spec, str):
            return self._resolve_path(spec), 1.0

        if isinstance(spec, list):
            candidates = list(spec)
            self._rng.shuffle(candidates)
            for item in candidates:
                path, vol = self._resolve_spec(item)
                if path:
                    return path, vol
            return None, 1.0

        if isinstance(spec, dict):
            base_vol = _clamp01(spec.get("volume", 1.0))
            options = spec.get("options")
            if isinstance(options, list) and options:
                path, child_vol = self._resolve_spec(options)
                if path:
                    return path, _clamp01(base_vol * child_vol)
            path_value = spec.get("path") or spec.get("file") or spec.get("src")
            path = self._resolve_path(path_value)
            if path:
                return path, base_vol
            return None, base_vol

        return None, 1.0

    def _warn_missing_once(self, label):
        if label in self._missing_paths:
            return
        self._missing_paths.add(label)
        logger.warning(f"[Audio] Missing audio source: {label}")

    def _resolve_named(self, mapping, key, fallback_key=None):
        if not isinstance(mapping, dict):
            return None, 1.0

        spec = None
        if key and key in mapping:
            spec = mapping.get(key)
        elif fallback_key and fallback_key in mapping:
            spec = mapping.get(fallback_key)
        elif "default" in mapping:
            spec = mapping.get("default")

        path, vol = self._resolve_spec(spec)
        if spec is not None and not path:
            self._warn_missing_once(f"{key or fallback_key}")
        return path, vol

    def play_sfx(self, sfx_key, volume=1.0, rate=1.0):
        key = _norm_key(sfx_key)
        if not key:
            return False
        now = globalClock.getFrameTime()
        cooldown = float(self._sfx_cooldowns.get(key, self._sfx_cooldowns.get("default", 0.0)))
        if cooldown > 0.0:
            last_play = float(self._sfx_last_play.get(key, -9999.0))
            if (now - last_play) < cooldown:
                return False
        spec = self._sfx.get(key)
        path, base_vol = self._resolve_spec(spec)
        if not path:
            self._warn_missing_once(f"sfx:{key}")
            return False

        if self._active_sfx_count() >= self._sfx_global_limit:
            return False

        snd = self._acquire_sfx_instance(path)
        if not snd:
            return False

        final_vol = _clamp01(base_vol * float(volume))
        play_rate = max(0.5, min(1.75, float(rate)))
        try:
            snd.setVolume(final_vol)
            snd.setPlayRate(play_rate)
            snd.play()
            self._sfx_last_play[key] = now
            return True
        except Exception as exc:
            logger.warning(f"[Audio] Failed to play SFX '{key}' ({path}): {exc}")
            return False

    def _acquire_sfx_instance(self, path):
        pool = self._sfx_pool.setdefault(path, [])

        for snd in pool:
            try:
                if snd.status() != AudioSound.PLAYING:
                    return snd
            except Exception:
                return snd

        if len(pool) < self._sfx_polyphony:
            try:
                snd = self.app.loader.loadSfx(path)
            except Exception as exc:
                logger.warning(f"[Audio] Failed to load SFX '{path}': {exc}")
                return None
            if not snd:
                self._warn_missing_once(path)
                return None
            pool.append(snd)
            return snd

        idx = self._rng.randrange(len(pool))
        return pool[idx] if pool else None

    def _is_combat_active(self):
        now = globalClock.getFrameTime()
        active = False
        player = getattr(self.app, "player", None)
        if player:
            if hasattr(player, "get_hud_combat_event"):
                try:
                    if player.get_hud_combat_event():
                        active = True
                except Exception:
                    pass
            combat = getattr(player, "combat", None)
            if combat and hasattr(combat, "isAttacking"):
                try:
                    if combat.isAttacking():
                        active = True
                except Exception:
                    pass
        if active:
            self._combat_until = now + self._combat_hold_time
        return now < self._combat_until

    def _location_key(self):
        world = getattr(self.app, "world", None)
        if world and isinstance(getattr(world, "active_location", None), str):
            return _norm_key(world.active_location)
        return ""

    def _infer_biome_key(self, location_key):
        if any(token in location_key for token in ("cave", "vault", "forge", "crypt", "catacomb", "throne")):
            return "caves"
        if "dock" in location_key or "sea" in location_key or "river" in location_key:
            return "sea"
        if "mount" in location_key or "peak" in location_key:
            return "mountain"

        player = getattr(self.app, "player", None)
        if player and getattr(player, "actor", None):
            try:
                pos = player.actor.getPos()
                if pos.y < -40.0:
                    return "sea"
                if pos.z > 30.0:
                    return "mountain"
            except Exception:
                pass
        return "plains"

    def _runtime_context_tags(self, location_key):
        tags = []
        low = str(location_key or "").lower()
        cave_like = any(token in low for token in ("cave", "vault", "forge", "crypt", "catacomb", "throne"))
        if "dock" in low or "port" in low:
            tags.append("docks")
            tags.append("town")
        if "coast" in low or "sea" in low or "shore" in low:
            tags.append("coast")
        if "forest" in low or "grove" in low:
            tags.append("forest")
        if cave_like:
            tags.append("caves")
        if (not cave_like) and any(token in low for token in ("interior", "chamber", "hall", "gallery", "laundry")):
            tags.append("interior")
        if "castle" in low or "keep" in low:
            tags.append("castle")
        if "training" in low:
            tags.append("tutorial")

        player = getattr(self.app, "player", None)
        if player:
            if bool(getattr(player, "_is_flying", False)):
                tags.append("flight")
            cs = getattr(player, "cs", None)
            if cs and getattr(cs, "inWater", False):
                tags.append("water")
            vm = getattr(self.app, "vehicle_mgr", None)
            if vm and bool(getattr(vm, "is_mounted", False)):
                kind = ""
                mounted = vm.mounted_vehicle() if hasattr(vm, "mounted_vehicle") else None
                if isinstance(mounted, dict):
                    kind = _norm_key(mounted.get("kind", ""))
                if kind:
                    tags.append(f"mounted_{kind}")
                tags.append("mounted")
            if getattr(player, "_was_wallrun", False):
                tags.append("parkour")
            brain = getattr(player, "brain", None)
            if brain and isinstance(getattr(brain, "mental", None), dict):
                fear = float(brain.mental.get("fear", 0.0) or 0.0)
                if fear >= 0.72:
                    tags.append("panic")
            if cs and hasattr(cs, "health") and hasattr(cs, "maxHealth"):
                try:
                    hp_ratio = float(cs.health) / max(1.0, float(cs.maxHealth))
                    if hp_ratio <= 0.35:
                        tags.append("injured")
                except Exception:
                    pass

        if self._is_boss_context(location_key):
            tags.insert(0, "boss")
        elif self._is_combat_active():
            tags.insert(0, "combat")
        return tags

    def _pick_context_music(self, location_key):
        best_token = None
        best_tag = ""
        best_priority = -999
        for tag in self._runtime_context_tags(location_key):
            token = _norm_key(self._context_music.get(_norm_key(tag), ""))
            if token:
                prio = self._int_priority(
                    self._priority_cfg.get("music_context", {}).get(_norm_key(tag), self._prio("music", "context", 64)),
                    self._prio("music", "context", 64),
                )
                if prio > best_priority:
                    best_priority = prio
                    best_token = token
                    best_tag = str(tag)
        if best_token:
            return best_token, f"context:{best_tag}", int(best_priority)
        return None, "", -999

    def _pick_context_ambient(self, location_key):
        best_token = None
        best_priority = -999
        for tag in self._runtime_context_tags(location_key):
            token = _norm_key(self._context_ambient.get(_norm_key(tag), ""))
            if token:
                prio = self._int_priority(
                    self._priority_cfg.get("ambient_context", {}).get(_norm_key(tag), self._prio("ambient", "context", 62)),
                    self._prio("ambient", "context", 62),
                )
                if prio > best_priority:
                    best_priority = prio
                    best_token = token
        return best_token, int(best_priority)

    def _player_in_water(self):
        player = getattr(self.app, "player", None)
        cs = getattr(player, "cs", None) if player else None
        return bool(cs and getattr(cs, "inWater", False))

    def _player_is_flying(self):
        player = getattr(self.app, "player", None)
        return bool(player and getattr(player, "_is_flying", False))

    def _is_boss_context(self, location_key):
        player = getattr(self.app, "player", None)
        if not player:
            return False
        now = globalClock.getFrameTime()

        boss_mgr = getattr(self.app, "boss_manager", None)
        if boss_mgr and hasattr(boss_mgr, "any_engaged"):
            try:
                if boss_mgr.any_engaged():
                    self._boss_until = max(self._boss_until, now + self._boss_hold_time)
                    return True
            except Exception:
                pass

        dragon = getattr(self.app, "dragon_boss", None)
        if dragon and bool(getattr(dragon, "is_engaged", False)):
            self._boss_until = max(self._boss_until, now + self._boss_hold_time)
            return True

        try:
            enemies = list(getattr(player, "enemies", []) or [])
        except Exception:
            enemies = []

        for enemy in enemies:
            tokens = []
            if isinstance(enemy, dict):
                for field in ("type", "kind", "id", "name", "tag"):
                    val = enemy.get(field)
                    if val:
                        tokens.append(str(val))
            else:
                for field in ("type", "kind", "id", "name", "tag"):
                    if hasattr(enemy, field):
                        val = getattr(enemy, field)
                        if val:
                            tokens.append(str(val))
            if "boss" in " ".join(tokens).lower():
                self._boss_until = max(self._boss_until, now + self._boss_hold_time)
                return True

        if "boss" in str(location_key or "").lower():
            self._boss_until = max(self._boss_until, now + self._boss_hold_time)
            return True
        return now < self._boss_until

    def _pick_gameplay_music(self):
        location_key = self._location_key()
        biome_key = self._infer_biome_key(location_key)
        candidates = []

        candidates.append(
            ("overworld", self._prio("music", "default", 10), "overworld_default")
        )

        loc_music = self._location_music.get(location_key)
        if isinstance(loc_music, str) and loc_music.strip():
            candidates.append(
                (_norm_key(loc_music), self._prio("music", "location", 44), f"location:{location_key}")
            )

        context_music, context_reason, context_prio = self._pick_context_music(location_key)
        if context_music:
            candidates.append((context_music, context_prio, context_reason))

        if self._is_combat_active():
            candidates.append(("combat", self._prio("music", "combat", 86), "combat"))
        if self._is_boss_context(location_key):
            candidates.append(("boss", self._prio("music", "boss", 96), "boss_presence"))

        now = globalClock.getFrameTime()
        override = self._route_override if isinstance(self._route_override, dict) else None
        if override:
            if now > float(override.get("until", -9999.0)):
                self._route_override = None
            else:
                music_key = _norm_key(override.get("music_key", ""))
                if music_key:
                    candidates.append((music_key, int(override.get("priority", 120)), f"override:{override.get('owner', '')}"))

        best = max(candidates, key=lambda row: int(row[1])) if candidates else ("overworld", 10, "overworld_default")
        return best[0], biome_key, location_key, best[2]

    def _pick_gameplay_ambient(self, biome_key, location_key):
        candidates = []
        candidates.append(("plains", self._prio("ambient", "default", 12)))

        bio = self._biome_ambient.get(biome_key)
        biome_token = _norm_key(bio) if isinstance(bio, str) else _norm_key(biome_key)
        if biome_token:
            candidates.append((biome_token, self._prio("ambient", "biome", 28)))

        loc_ambient = self._location_ambient.get(location_key)
        if isinstance(loc_ambient, str) and loc_ambient.strip():
            candidates.append((_norm_key(loc_ambient), self._prio("ambient", "location", 46)))

        context_ambient, context_prio = self._pick_context_ambient(location_key)
        if context_ambient:
            candidates.append((context_ambient, context_prio))

        if self._player_in_water():
            candidates.append(("water", self._prio("ambient", "water", 86)))
        elif self._player_is_flying():
            candidates.append(("wind", self._prio("ambient", "flight", 78)))

        override = self._route_override if isinstance(self._route_override, dict) else None
        now = globalClock.getFrameTime()
        if override and now <= float(override.get("until", -9999.0)):
            ambient_key = _norm_key(override.get("ambient_key", ""))
            if ambient_key:
                candidates.append((ambient_key, int(override.get("priority", 110))))

        best = max(candidates, key=lambda row: int(row[1])) if candidates else ("plains", 12)
        return best[0]

    def _choose_targets(self):
        state_mgr = getattr(self.app, "state_mgr", None)
        state = getattr(state_mgr, "current_state", None)
        gs = getattr(self.app, "GameState", None)

        if gs and state in (gs.MAIN_MENU, gs.LOADING):
            return "menu", None, "menu_or_loading"

        if gs and state in (gs.PLAYING, gs.PAUSED, gs.INVENTORY, gs.DIALOG):
            music_key, biome_key, location_key, reason = self._pick_gameplay_music()
            ambient_key = self._pick_gameplay_ambient(biome_key, location_key)
            return music_key, ambient_key, reason

        return "menu", None, "fallback_menu"

    def _log_audio_route(self, music_key, ambient_key, reason):
        signature = (str(music_key or ""), str(ambient_key or ""), str(reason or ""))
        if signature == self._last_route_signature:
            return
        self._last_route_signature = signature
        logger.info(
            f"[Audio] Route -> music='{music_key}' ambient='{ambient_key}' reason='{reason}'"
        )

    def _compute_mix_gains(self):
        music_gain = 1.0
        ambient_gain = 1.0

        state_mgr = getattr(self.app, "state_mgr", None)
        state = getattr(state_mgr, "current_state", None)
        gs = getattr(self.app, "GameState", None)
        if gs and state in {gs.PAUSED, gs.INVENTORY}:
            music_gain *= self._mix_ui_music_duck

        if gs and state == gs.DIALOG:
            music_gain *= self._mix_dialog_music_duck
            ambient_gain *= self._mix_dialog_ambient_duck

        location_key = self._location_key()
        if self._is_boss_context(location_key):
            ambient_gain *= self._mix_boss_ambient_duck
        elif self._is_combat_active():
            ambient_gain *= self._mix_combat_ambient_duck
        self._cleanup_voice_instances()
        if self._active_voice:
            music_gain *= self._mix_voice_music_duck
            ambient_gain *= self._mix_voice_ambient_duck

        corruption = self.get_world_corruption()
        if corruption > 0.0:
            music_gain *= max(0.0, 1.0 - corruption * float(self._world_corruption_music_duck))
            ambient_gain *= max(0.0, 1.0 - corruption * float(self._world_corruption_ambient_duck))

        return _clamp01(music_gain), _clamp01(ambient_gain)

    def play_voice_path(self, path, volume=1.0, rate=1.0):
        resolved = self._resolve_path(path)
        if not resolved:
            self._warn_missing_once(f"voice:{path}")
            return False
        try:
            snd = self.app.loader.loadSfx(resolved)
        except Exception as exc:
            logger.warning(f"[Audio] Failed to load voice clip '{path}': {exc}")
            return False
        if not snd:
            self._warn_missing_once(f"voice:{path}")
            return False
        try:
            final_volume, final_rate = self._voice_delivery(float(volume) * self._voice_volume, base_rate=rate)
            snd.setVolume(final_volume)
            try:
                snd.setPlayRate(final_rate)
            except Exception:
                pass
            snd.play()
            self._active_voice.append(snd)
            return True
        except Exception as exc:
            logger.warning(f"[Audio] Failed to play voice clip '{path}': {exc}")
            return False

    def play_voice_key(self, voice_key, volume=1.0, rate=1.0):
        token = str(voice_key or "").strip().replace("\\", "/")
        if not token:
            return False
        base = str(self._voices_path or "data/audio/voices").strip().replace("\\", "/")
        low = token.lower()
        if low.endswith((".ogg", ".mp3", ".wav")):
            candidate = token
            if not token.startswith(base):
                candidate = f"{base}/{token}"
            return self.play_voice_path(candidate, volume=volume, rate=rate)
        for ext in (".ogg", ".mp3", ".wav"):
            candidate = f"{base}/{token}{ext}"
            if self.play_voice_path(candidate, volume=volume, rate=rate):
                return True
        return False

    def warmup_cache(self, include_sfx=True, sfx_limit=14):
        """Preload key audio clips to avoid first-play hitching after lazy world boot."""
        warmed = 0
        seen_music = set()
        seen_sfx = set()

        def _prime_loop(mapping, use_music):
            nonlocal warmed
            if not isinstance(mapping, dict):
                return
            for spec in mapping.values():
                path, _ = self._resolve_spec(spec)
                if not path:
                    continue
                if path in seen_music:
                    continue
                seen_music.add(path)
                try:
                    snd = self.app.loader.loadMusic(path) if use_music else self.app.loader.loadSfx(path)
                except Exception:
                    snd = None
                if snd:
                    warmed += 1

        _prime_loop(self._music, use_music=True)
        _prime_loop(self._ambient, use_music=False)

        if include_sfx:
            remaining = max(0, int(sfx_limit or 0))
            for spec in self._sfx.values():
                if remaining <= 0:
                    break
                path, _ = self._resolve_spec(spec)
                if not path or path in seen_sfx:
                    continue
                seen_sfx.add(path)
                pool = self._sfx_pool.setdefault(path, [])
                if pool:
                    remaining -= 1
                    continue
                try:
                    snd = self.app.loader.loadSfx(path)
                except Exception:
                    snd = None
                if snd:
                    pool.append(snd)
                    warmed += 1
                    remaining -= 1
        return warmed

    def update(self, dt):
        self._update_world_corruption(dt)
        self._music_channel.set_fade_time(self._crossfade_time)
        self._ambient_channel.set_fade_time(max(0.05, self._crossfade_time * 0.8))
        self._music_channel.set_allow_overlap(not self._music_no_overlap)
        self._ambient_channel.set_allow_overlap(not self._ambient_no_overlap)
        music_gain, ambient_gain = self._compute_mix_gains()
        self._music_channel.set_master_gain(music_gain)
        self._ambient_channel.set_master_gain(ambient_gain)

        music_key, ambient_key, reason = self._choose_targets()
        self._log_audio_route(music_key, ambient_key, reason)
        music_path, music_vol = self._resolve_named(self._music, music_key, fallback_key="overworld")
        if music_path:
            self._music_channel.switch_to(music_key, music_path, music_vol)
        else:
            self._music_channel.stop()

        if self._ambient_enabled and ambient_key:
            amb_path, amb_vol = self._resolve_named(self._ambient, ambient_key, fallback_key="plains")
            if amb_path:
                self._ambient_channel.switch_to(ambient_key, amb_path, amb_vol)
            else:
                self._ambient_channel.stop()
        else:
            self._ambient_channel.stop()

        self._music_channel.update(dt)
        self._ambient_channel.update(dt)
