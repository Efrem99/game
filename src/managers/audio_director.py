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
                self._current.setVolume(target)
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
            snd.setVolume(target if self._current is None else 0.0)
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
                    self._current.setVolume(max(0.0, (1.0 - t) * self._fade_out_from))
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
                    self._current.setVolume(max(0.0, t * self._current_target))
                except Exception:
                    pass
                if t >= 1.0:
                    self._fading_in = False
                    self._fade_t = 0.0
                return

            if self._current and not self._fading_out:
                try:
                    self._current.setVolume(self._current_target)
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
                self._current.setVolume(max(0.0, (1.0 - t) * self._current_target))
                self._next.setVolume(max(0.0, t * self._next_target))
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
        self._crossfade_time = max(0.05, float(cfg.get("crossfade_time", 1.5) or 1.5))
        self._combat_hold_time = max(0.25, float(cfg.get("combat_hold_time", 4.0) or 4.0))
        self._boss_hold_time = max(0.5, float(cfg.get("boss_hold_time", 6.0) or 6.0))
        self._music_no_overlap = bool(cfg.get("music_no_overlap", True))
        self._ambient_no_overlap = bool(cfg.get("ambient_no_overlap", True))
        self._ambient_enabled = bool(cfg.get("ambient_enabled", True))
        self._sfx_polyphony = max(1, int(cfg.get("sfx_polyphony", 4) or 4))
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

        if self._is_boss_context(location_key):
            return "boss", biome_key, location_key, "boss_presence"

        combat_active = self._is_combat_active()
        if combat_active:
            return "combat", biome_key, location_key, "combat"

        loc_music = self._location_music.get(location_key)
        if isinstance(loc_music, str) and loc_music.strip():
            return _norm_key(loc_music), biome_key, location_key, f"location:{location_key}"

        return "overworld", biome_key, location_key, "overworld_default"

    def _pick_gameplay_ambient(self, biome_key, location_key):
        loc_ambient = self._location_ambient.get(location_key)
        if isinstance(loc_ambient, str) and loc_ambient.strip():
            key = _norm_key(loc_ambient)
        else:
            bio = self._biome_ambient.get(biome_key)
            key = _norm_key(bio) if isinstance(bio, str) else _norm_key(biome_key)

        if self._player_in_water():
            key = "water"
        elif self._player_is_flying():
            key = "wind"
        return key

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

    def update(self, dt):
        self._music_channel.set_fade_time(self._crossfade_time)
        self._ambient_channel.set_fade_time(max(0.05, self._crossfade_time * 0.8))
        self._music_channel.set_allow_overlap(not self._music_no_overlap)
        self._ambient_channel.set_allow_overlap(not self._ambient_no_overlap)

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
