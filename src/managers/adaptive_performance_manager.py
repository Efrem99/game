from __future__ import annotations

from typing import Dict

from utils.logger import logger


QUALITY_ORDER = ("low", "medium", "high", "ultra")
ADAPTIVE_MODES = ("quality", "balanced", "performance")


def _normalize_quality(token) -> str:
    value = str(token or "high").strip().lower()
    if value in {"med", "middle"}:
        value = "medium"
    if value not in QUALITY_ORDER:
        value = "high"
    return value


def _normalize_mode(mode) -> str:
    token = str(mode or "balanced").strip().lower()
    if token in {"qual", "hq"}:
        token = "quality"
    if token in {"perf", "speed", "fast"}:
        token = "performance"
    if token not in ADAPTIVE_MODES:
        token = "balanced"
    return token


class AdaptivePerformanceManager:
    """Runtime quality/load balancer that reacts to sustained frame pressure."""

    TARGET_FPS = 60.0
    MAX_LEVEL = 3

    _LOAD_PROFILES: Dict[int, Dict[str, float]] = {
        0: {
            "sky_update_interval": 0.0,
            "influence_update_interval": 0.0,
            "npc_activity_update_interval": 0.0,
            "npc_interaction_update_interval": 0.0,
            "story_interaction_update_interval": 0.0,
            "cutscene_trigger_update_interval": 0.0,
            "npc_logic_update_interval": 0.0,
            "enemy_update_interval": 0.0,
            "particle_upload_interval": 1.0 / 30.0,
            "enemy_fire_particle_budget": 320.0,
            "sim_tick_rate_hz": 15.0,
            "sim_budget_scale": 1.0,
            "world_mesh_cull_distance_scale": 1.0,
            "world_mesh_hlod_distance_scale": 1.0,
            "world_mesh_visibility_update_scale": 1.0,
        },
        1: {
            "sky_update_interval": 1.0 / 45.0,
            "influence_update_interval": 1.0 / 45.0,
            "npc_activity_update_interval": 1.0 / 30.0,
            "npc_interaction_update_interval": 1.0 / 30.0,
            "story_interaction_update_interval": 1.0 / 30.0,
            "cutscene_trigger_update_interval": 1.0 / 30.0,
            "npc_logic_update_interval": 1.0 / 50.0,
            "enemy_update_interval": 1.0 / 48.0,
            "particle_upload_interval": 1.0 / 25.0,
            "enemy_fire_particle_budget": 260.0,
            "sim_tick_rate_hz": 12.0,
            "sim_budget_scale": 0.9,
            "world_mesh_cull_distance_scale": 0.92,
            "world_mesh_hlod_distance_scale": 0.86,
            "world_mesh_visibility_update_scale": 1.10,
        },
        2: {
            "sky_update_interval": 1.0 / 24.0,
            "influence_update_interval": 1.0 / 24.0,
            "npc_activity_update_interval": 1.0 / 20.0,
            "npc_interaction_update_interval": 1.0 / 20.0,
            "story_interaction_update_interval": 1.0 / 20.0,
            "cutscene_trigger_update_interval": 1.0 / 20.0,
            "npc_logic_update_interval": 1.0 / 30.0,
            "enemy_update_interval": 1.0 / 28.0,
            "particle_upload_interval": 1.0 / 20.0,
            "enemy_fire_particle_budget": 200.0,
            "sim_tick_rate_hz": 10.0,
            "sim_budget_scale": 0.75,
            "world_mesh_cull_distance_scale": 0.80,
            "world_mesh_hlod_distance_scale": 0.72,
            "world_mesh_visibility_update_scale": 1.22,
        },
        3: {
            "sky_update_interval": 1.0 / 18.0,
            "influence_update_interval": 1.0 / 18.0,
            "npc_activity_update_interval": 1.0 / 15.0,
            "npc_interaction_update_interval": 1.0 / 15.0,
            "story_interaction_update_interval": 1.0 / 15.0,
            "cutscene_trigger_update_interval": 1.0 / 15.0,
            "npc_logic_update_interval": 1.0 / 20.0,
            "enemy_update_interval": 1.0 / 18.0,
            "particle_upload_interval": 1.0 / 15.0,
            "enemy_fire_particle_budget": 140.0,
            "sim_tick_rate_hz": 8.0,
            "sim_budget_scale": 0.6,
            "world_mesh_cull_distance_scale": 0.68,
            "world_mesh_hlod_distance_scale": 0.58,
            "world_mesh_visibility_update_scale": 1.38,
        },
    }

    _MODE_SETTINGS: Dict[str, Dict[str, object]] = {
        "quality": {
            "thresholds": (55.0, 47.0, 38.0),
            "up_hold_base_sec": 2.4,
            "up_hold_step_sec": 0.35,
            "down_hold_base_sec": 1.1,
            "down_hold_step_sec": 0.15,
            "interval_scale": 0.75,
            "particle_scale": 0.85,
            "sim_tick_scale": 1.10,
            "sim_budget_scale": 1.10,
            "quality_steps": (0, 0, 0, 1),
        },
        "balanced": {
            "thresholds": (58.0, 50.0, 40.0),
            "up_hold_base_sec": 1.5,
            "up_hold_step_sec": 0.35,
            "down_hold_base_sec": 1.5,
            "down_hold_step_sec": 0.20,
            "interval_scale": 1.0,
            "particle_scale": 1.0,
            "sim_tick_scale": 1.0,
            "sim_budget_scale": 1.0,
            "quality_steps": (0, 0, 1, 2),
        },
        "performance": {
            "thresholds": (61.0, 54.0, 46.0),
            "up_hold_base_sec": 0.9,
            "up_hold_step_sec": 0.25,
            "down_hold_base_sec": 2.0,
            "down_hold_step_sec": 0.25,
            "interval_scale": 1.35,
            "particle_scale": 1.35,
            "sim_tick_scale": 0.80,
            "sim_budget_scale": 0.80,
            "quality_steps": (0, 1, 2, 2),
        },
    }

    def __init__(self, app, mode="balanced"):
        self._app = app
        self.current_level = 0
        self.mode = _normalize_mode(mode)
        self._ewma_dt = 1.0 / self.TARGET_FPS
        self._ewma_alpha = 0.02
        self._pressure_time = 0.0
        self._recovery_time = 0.0
        self._base_quality = _normalize_quality(getattr(app, "_gfx_quality", "high"))
        self._applied_quality = self._base_quality
        self._apply_level(0, force=False)

    @property
    def average_fps(self) -> float:
        return 1.0 / max(1e-5, self._ewma_dt)

    def set_mode(self, mode, force_reapply: bool = True) -> str:
        token = _normalize_mode(mode)
        if token == self.mode:
            return self.mode
        self.mode = token
        self._pressure_time = 0.0
        self._recovery_time = 0.0
        if force_reapply:
            self._apply_level(self.current_level, force=True)
        logger.info(f"[AdaptivePerformance] Mode set to '{self.mode}'")
        return self.mode

    def on_quality_changed(self, level, user_initiated: bool = False) -> None:
        token = _normalize_quality(level)
        self._applied_quality = token
        if not user_initiated:
            return
        self._base_quality = token
        self._apply_quality_for_level(self.current_level, force=True)

    def update(self, dt: float, is_playing: bool = True, observed_fps: float | None = None) -> None:
        try:
            dt_val = float(dt or 0.0)
        except Exception:
            return
        if dt_val <= 0.0:
            return

        sample_dt = dt_val
        if observed_fps is not None:
            try:
                fps_val = float(observed_fps or 0.0)
            except Exception:
                fps_val = 0.0
            if fps_val > 0.0:
                sample_dt = 1.0 / max(1e-5, fps_val)

        self._ewma_dt += (sample_dt - self._ewma_dt) * self._ewma_alpha
        settings = self._MODE_SETTINGS.get(self.mode, self._MODE_SETTINGS["balanced"])

        desired_level = self._desired_level_from_fps(self.average_fps)
        if not is_playing:
            desired_level = 0

        if desired_level > self.current_level:
            self._pressure_time += dt_val
            self._recovery_time = 0.0
            hold_sec = float(settings.get("up_hold_base_sec", 1.5)) + (
                float(settings.get("up_hold_step_sec", 0.35)) * float(self.current_level)
            )
            if self._pressure_time >= hold_sec:
                self._pressure_time = 0.0
                self._set_level(self.current_level + 1)
            return

        if desired_level < self.current_level:
            self._recovery_time += dt_val
            self._pressure_time = 0.0
            hold_sec = float(settings.get("down_hold_base_sec", 1.5)) + (
                float(settings.get("down_hold_step_sec", 0.20))
                * float(max(0, self.current_level - 1))
            )
            if self._recovery_time >= hold_sec:
                self._recovery_time = 0.0
                self._set_level(self.current_level - 1)
            return

        self._pressure_time = 0.0
        self._recovery_time = 0.0

    def debug_snapshot(self) -> dict:
        return {
            "mode": self.mode,
            "level": int(self.current_level),
            "average_fps": float(self.average_fps),
            "base_quality": self._base_quality,
            "effective_quality": self._applied_quality,
        }

    def _desired_level_from_fps(self, fps: float) -> int:
        settings = self._MODE_SETTINGS.get(self.mode, self._MODE_SETTINGS["balanced"])
        thresholds = settings.get("thresholds", (58.0, 50.0, 40.0))
        level0 = float(thresholds[0])
        level1 = float(thresholds[1])
        level2 = float(thresholds[2])
        if fps >= level0:
            return 0
        if fps >= level1:
            return 1
        if fps >= level2:
            return 2
        return 3

    def _set_level(self, level: int) -> None:
        clamped = max(0, min(self.MAX_LEVEL, int(level)))
        if clamped == self.current_level:
            return
        self._apply_level(clamped, force=False)

    def _profile_for_mode_level(self, level: int) -> dict:
        settings = self._MODE_SETTINGS.get(self.mode, self._MODE_SETTINGS["balanced"])
        base_profile = dict(self._LOAD_PROFILES.get(level, self._LOAD_PROFILES[0]))
        out = dict(base_profile)

        interval_scale = float(settings.get("interval_scale", 1.0))
        particle_scale = float(settings.get("particle_scale", interval_scale))
        sim_tick_scale = float(settings.get("sim_tick_scale", 1.0))
        sim_budget_scale = float(settings.get("sim_budget_scale", 1.0))

        for key in (
            "sky_update_interval",
            "influence_update_interval",
            "npc_activity_update_interval",
            "npc_interaction_update_interval",
            "story_interaction_update_interval",
            "cutscene_trigger_update_interval",
            "npc_logic_update_interval",
            "enemy_update_interval",
        ):
            out[key] = max(0.0, float(base_profile.get(key, 0.0) or 0.0) * interval_scale)

        out["particle_upload_interval"] = max(
            0.0,
            float(base_profile.get("particle_upload_interval", 1.0 / 30.0) or 1.0 / 30.0)
            * particle_scale,
        )
        base_enemy_budget = float(base_profile.get("enemy_fire_particle_budget", 220.0) or 220.0)
        out["enemy_fire_particle_budget"] = max(
            32.0,
            min(2048.0, round(base_enemy_budget / max(0.1, particle_scale))),
        )
        out["sim_tick_rate_hz"] = max(
            4.0,
            min(
                60.0,
                float(base_profile.get("sim_tick_rate_hz", 15.0) or 15.0) * sim_tick_scale,
            ),
        )
        out["sim_budget_scale"] = max(
            0.25,
            min(
                2.0,
                float(base_profile.get("sim_budget_scale", 1.0) or 1.0) * sim_budget_scale,
            ),
        )
        return out

    def _apply_level(self, level: int, force: bool = False) -> None:
        clamped = max(0, min(self.MAX_LEVEL, int(level)))
        previous = self.current_level
        self.current_level = clamped
        profile = self._profile_for_mode_level(self.current_level)

        app = self._app
        if hasattr(app, "set_runtime_load_profile"):
            try:
                app.set_runtime_load_profile(profile, level=self.current_level)
            except Exception as exc:
                logger.debug(f"[AdaptivePerformance] Failed to apply runtime profile: {exc}")
        sim_tier_mgr = getattr(app, "sim_tier_mgr", None)
        if sim_tier_mgr and hasattr(sim_tier_mgr, "set_runtime_profile"):
            try:
                sim_tier_mgr.set_runtime_profile(
                    tick_rate_hz=profile.get("sim_tick_rate_hz", None),
                    budget_scale=profile.get("sim_budget_scale", None),
                )
            except Exception as exc:
                logger.debug(f"[AdaptivePerformance] Sim tier profile failed: {exc}")

        self._apply_quality_for_level(self.current_level, force=force)

        if self.current_level != previous:
            logger.info(
                f"[AdaptivePerformance] [{self.mode}] Level {previous} -> {self.current_level} "
                f"(avg_fps={self.average_fps:.1f}, quality={self._applied_quality})"
            )

    def _apply_quality_for_level(self, level: int, force: bool = False) -> None:
        desired = self._quality_for_level(level)
        if not force and desired == self._applied_quality:
            return

        app = self._app
        if hasattr(app, "apply_graphics_quality"):
            try:
                app.apply_graphics_quality(desired, persist=False)
            except Exception as exc:
                logger.debug(f"[AdaptivePerformance] Failed to apply graphics quality: {exc}")
                return
        self._applied_quality = _normalize_quality(getattr(app, "_gfx_quality", desired))

    def _quality_for_level(self, level: int) -> str:
        base = _normalize_quality(self._base_quality)
        base_idx = QUALITY_ORDER.index(base)
        settings = self._MODE_SETTINGS.get(self.mode, self._MODE_SETTINGS["balanced"])
        quality_steps = settings.get("quality_steps", (0, 0, 1, 2))
        if isinstance(quality_steps, (list, tuple)) and quality_steps:
            step_down = int(quality_steps[min(len(quality_steps) - 1, max(0, int(level)))])
        else:
            step_down = 0

        if base_idx <= QUALITY_ORDER.index("medium"):
            floor_idx = base_idx
        else:
            floor_idx = QUALITY_ORDER.index("medium")

        idx = max(floor_idx, base_idx - step_down)
        idx = max(0, min(len(QUALITY_ORDER) - 1, idx))
        return QUALITY_ORDER[idx]
