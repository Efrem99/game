from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.interval.IntervalGlobal import Sequence, Wait, Func, LerpColorScaleInterval
from panda3d.core import (
    WindowProperties, AmbientLight, DirectionalLight,
    Vec3, Vec4, LPoint3, LColor, Fog, AntialiasAttrib,
    Texture, SamplerState, TexturePool, TransparencyAttrib, PNMImage, MouseButton, InputDevice, ClockObject,
    loadPrcFileData
)
import complexpbr
import math
import os
from utils.logger import logger

# Global Panda3D Configuration
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_RUNTIME_TEST_BOOT = bool(str(os.environ.get("XBOT_TEST_PROFILE", "")).strip()) or (
    str(os.environ.get("XBOT_VIDEO_BOT", "")).strip().lower() in {"1", "true", "yes", "on"}
)
_PANDA_CACHE_DIR = os.path.join(_PROJECT_ROOT, "cache", "panda3d")
try:
    os.makedirs(_PANDA_CACHE_DIR, exist_ok=True)
except Exception:
    _PANDA_CACHE_DIR = ""

loadPrcFileData("", "window-type normal")
loadPrcFileData("", "window-title King Wizard")
if os.path.exists("assets/textures/king_wizard.ico"):
    loadPrcFileData("", "icon-filename assets/textures/king_wizard.ico")
elif os.path.exists("assets/textures/kw_logo.png"):
    loadPrcFileData("", "icon-filename assets/textures/kw_logo.png")
loadPrcFileData("", "win-size 1280 720")
loadPrcFileData("", "win-origin 100 100")
loadPrcFileData("", "background-color 0.2 0.3 0.5")
loadPrcFileData("", "show-frame-rate-meter #t")
loadPrcFileData("", "sync-video #t")
loadPrcFileData("", "framebuffer-multisample #t")
loadPrcFileData("", "multisamples 4")
if _PANDA_CACHE_DIR:
    loadPrcFileData("", f"model-cache-dir {_PANDA_CACHE_DIR.replace('\\', '/')}")
if _RUNTIME_TEST_BOOT:
    # Runtime test sessions should be deterministic and avoid cache rename stalls.
    loadPrcFileData("", "model-cache-models #f")
    loadPrcFileData("", "model-cache-textures #f")
    loadPrcFileData("", "model-cache-compressed-textures #f")
# loadPrcFileData("", "threading-model /Cull") # Removed for stability

try:
    import game_core as gc
    HAS_CORE = True
    logger.info("Successfully loaded game_core.pyd")
except ImportError:
    logger.warning("game_core.pyd not found. Running in Python-only mode (limited logic).")
    gc = None
    HAS_CORE = False

from world.sharuan_world import SharuanWorld
from world.influence_manager import InfluenceManager
from world.sim_tier_manager import SimTierManager
from entities.boss_manager import BossManager
from entities.companion_unit import CompanionUnit
from entities.player import Player
from managers.data_manager import DataManager
from managers.audio_director import AudioDirector
from managers.camera_director import CameraDirector
from managers.cutscene_trigger_manager import CutsceneTriggerManager
from managers.event_bus import EventBus
from managers.npc_activity_director import NPCActivityDirector
from managers.state_manager import StateManager, GameState
from managers.quest_manager import QuestManager
from managers.save_manager import SaveManager
from managers.sky_manager import SkyManager
from managers.time_fx_manager import TimeFxManager
from managers.vehicle_manager import VehicleManager
from managers.npc_manager import NPCManager
from managers.movement_tutorial_manager import MovementTutorialManager
from managers.dialog_cinematic_manager import DialogCinematicManager
from managers.npc_interaction_manager import NPCInteractionManager
from managers.story_interaction_manager import StoryInteractionManager
from managers.skill_tree_manager import SkillTreeManager
from managers.stealth_manager import StealthManager
from render.magic_vfx import MagicVFXSystem
from render.fx_policy import scale_particle_budget_for_fps
from render.model_visuals import ensure_model_visual_defaults, audit_node_visual_health
from ui.menu_main import MainMenu
from ui.menu_pause import PauseMenu
from ui.menu_inventory import InventoryUI
from ui.loading_screen import LoadingScreen
from ui.ui_intro import IntroUI
from ui.hud_overlay import HUDOverlay
from managers.preload_manager import PreloadManager
from managers.asset_bundle_manager import AssetBundleManager
from managers.adaptive_performance_manager import AdaptivePerformanceManager
from utils.video_bot_plan import (
    build_video_bot_events,
    resolve_action_binding,
    resolve_video_bot_plan_name,
)

class XBotApp(ShowBase):
    GameState = GameState # Shortcut

    def __init__(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._windowed_size = (1280, 720)
        self._windowed_origin = (100, 100)
        self._is_fullscreen = False
        self._last_fs_toggle_time = -999.0
        self._test_profile = str(os.environ.get("XBOT_TEST_PROFILE", "")).strip().lower()
        self._test_location_raw = str(os.environ.get("XBOT_TEST_LOCATION", "")).strip()
        self._test_scenario_raw = str(os.environ.get("XBOT_TEST_SCENARIO", "")).strip()
        self._cursed_blend = 0.0
        self._auto_start_requested = str(os.environ.get("XBOT_AUTO_START", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._video_bot_enabled = str(os.environ.get("XBOT_VIDEO_BOT", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._video_bot_capture_input = self._video_bot_enabled and str(
            os.environ.get("XBOT_VIDEO_BOT_CAPTURE_INPUT", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}
        self._video_bot_visibility_boost = self._video_bot_enabled and str(
            os.environ.get("XBOT_VIDEO_VISIBILITY_BOOST", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}
        self._video_bot_loop_plan = self._video_bot_enabled and str(
            os.environ.get("XBOT_VIDEO_BOT_LOOP_PLAN", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}
        try:
            self._video_bot_loop_gap_sec = float(
                os.environ.get("XBOT_VIDEO_BOT_LOOP_GAP_SEC", "0.45") or 0.45
            )
        except Exception:
            self._video_bot_loop_gap_sec = 0.45
        self._video_bot_loop_gap_sec = max(0.0, min(4.0, self._video_bot_loop_gap_sec))
        self._video_bot_force_aggro_mobs = str(
            os.environ.get("XBOT_FORCE_AGGRO_MOBS", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._video_bot_plan_raw = str(os.environ.get("XBOT_VIDEO_BOT_PLAN", "")).strip()
        self._video_bot_plan_name = "ground"
        self._video_bot_plan = []
        self._video_bot_elapsed = 0.0
        self._video_bot_event_idx = 0
        self._video_bot_hold_actions = {}
        self._video_bot_forced_flags = {}
        self._video_bot_bindings = {}
        self._video_bot_warned_actions = set()
        self._video_bot_done = False
        self._video_bot_cursor_pos = (0.0, 0.0)
        self._video_bot_cursor_target = (0.0, 0.0)
        self._video_bot_cursor_visible = False
        self._video_bot_visibility_refresh_at = 0.0
        self._video_bot_cursor_visible_until = 0.0
        self._video_bot_cursor_click_until = 0.0
        self._video_bot_started = False
        self._video_bot_start_delay_sec = 1.1
        self._video_bot_start_ready_at = 0.0
        self._video_bot_last_real_time = 0.0
        self._video_bot_cycle_count = 0
        self._cutscene_triggers_enabled = True
        self._gamepad_device = None
        self._gp_deadzone = 0.18
        self._gp_axes = {
            "move_x": 0.0,
            "move_y": 0.0,
            "look_x": 0.0,
            "look_y": 0.0,
        }

        # Force a window to open
        logger.info("Calling ShowBase.__init__...")
        super().__init__()

        if not self.win:
            logger.error("Failed to create graphics window!")
            return

        logger.info(f"Graphics pipe successfully opened. Window handle: {self.win}")
        self._configure_fps_band(min_fps=30.0, max_fps=60.0)

        # Standardize Window Visibility
        self._setup_window(initial=True)

        # -- Graphics & Aesthetics --
        logger.info("Configuring graphics and aesthetics...")
        self.setBackgroundColor(0, 0, 0)
        self.render.setAntialias(AntialiasAttrib.MMultisample, 2) # Reduced for stability

        # Camera Defaults — 0 yaw = camera directly behind player (north)
        self._cam_yaw = 0.0
        self._cam_pitch = -20.0
        self._cam_dist = 22.0
        self._cam_zoom_offset = 0.0
        self._cam_angles_cache = (self._cam_yaw, self._cam_pitch)
        self._cam_yaw_rad = math.radians(self._cam_yaw)
        self._cam_pitch_rad = math.radians(self._cam_pitch)
        self._cam_mouse_sens = 150.0
        self._cam_invert_y = False
        self._gfx_quality = "Medium"
        self._advanced_rendering = (
            str(os.environ.get("XBOT_DISABLE_POSTFX", "0") or "").strip().lower()
            not in {"1", "true", "yes", "on"}
        )
        self._screenspace_ready = False

        # Advanced complexpbr Rendering
        logger.info("Initializing complexpbr shaders and screenspace effects...")

        shaders_dir = os.path.join(self.project_root, "shaders")
        try:
            os.makedirs(shaders_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not access shaders directory '{shaders_dir}': {e}")

        from panda3d.core import getModelPath
        # Ensure root is in model path for relative shader loading
        getModelPath().appendDirectory(self.project_root)

        self.render.set_shader_input("displacement_scale", 0.0)
        self.render.set_shader_input("displacement_map", Texture())

        if self._advanced_rendering:
            complexpbr.apply_shader(
                self.render,
                intensity=1.0,
                default_lighting=False,
                custom_dir="shaders/"
            )
        else:
            logger.info("[Render] PostFX disabled via XBOT_DISABLE_POSTFX.")

        # Avoid "Could not find appropriate DisplayRegion to filter" error
        if self._advanced_rendering:
            # self._safe_screenspace_init()  # Moved to main loop/finalize for reliability
            pass # Screenspace init is now delayed to _update task
        else:
            self._screenspace_ready = False
            self._remove_screenspace_nodes()

        # Global fallback inputs for complexpbr 0.6.0+ stability
        fallbacks = {
            "displacement_scale": 0.0,
            "displacement_map": Texture(),
            "specular_factor": 1.0,
            "ao": 1.0,
            "shadow_boost": 0.0,
        }

        # Apply to all relevant root nodes to ensure shader inheritance stability
        for scene_root in [self.render, self.camera, self.render2d, self.aspect2d, self.pixel2d]:
            for name, val in fallbacks.items():
                scene_root.set_shader_input(name, val, priority=1000)

        # EXPLICITLY disable shaders on UI roots to prevent PBR leaks
        self.aspect2d.set_shader_off(1001)
        self.render2d.set_shader_off(1001)

        # -- Lights --
        self._alight = AmbientLight("alight")
        self._alight.setColor(Vec4(0.4, 0.4, 0.5, 1))
        self._alnp = self.render.attachNewNode(self._alight)
        self.render.setLight(self._alnp)

        self._dlight = DirectionalLight("dlight")
        self._dlight.setColor(Vec4(0.8, 0.8, 0.7, 1))
        self._dlnp = self.render.attachNewNode(self._dlight)
        self._dlnp.setHpr(45, -60, 0)
        self.render.setLight(self._dlnp)

        # We exclusively apply complexpbr.skin() to animated actors later,
        # not to the static root render graph.

        # Configure post-processing on the screen quad
        if self._advanced_rendering and hasattr(self, 'screen_quad'):
            logger.debug("Configuring complexpbr post-processing inputs.")
            self.screen_quad.set_shader_input("bloom_intensity", 0.62)
            for name, val in fallbacks.items():
                self.screen_quad.set_shader_input(name, val, priority=1000)

        # -- Managers --
        self.data_mgr = DataManager()
        self.event_bus = EventBus()
        self.apply_graphics_quality(
            self.data_mgr.graphics_settings.get("quality", "High"),
            persist=False,
        )
        camera_cfg = (
            self.data_mgr.graphics_settings.get("camera", {})
            if isinstance(self.data_mgr.graphics_settings, dict)
            else {}
        )
        if not isinstance(camera_cfg, dict):
            camera_cfg = {}
        try:
            self._cam_mouse_sens = max(40.0, min(320.0, float(camera_cfg.get("mouse_sensitivity", 150.0) or 150.0)))
        except Exception:
            self._cam_mouse_sens = 150.0
        self._cam_invert_y = bool(camera_cfg.get("invert_y", False))
        self.sky_mgr = SkyManager(self)

        # Apply Saved Audio Settings Early
        try:
            m_vol = self.data_mgr.audio_settings.get("music", 0.8)
            s_vol = self.data_mgr.audio_settings.get("sfx", 1.0)
            self.musicManager.setVolume(m_vol)
            if self.sfxManagerList:
                self.sfxManagerList[0].setVolume(s_vol)
        except Exception as e:
            logger.debug(f"Could not apply startup audio settings: {e}")

        self.audio = AudioDirector(self)
        self.audio_director = self.audio  # Compatibility alias for managers that use explicit name.
        self.camera_director = CameraDirector(self)
        self.time_fx = TimeFxManager(self)
        self.cutscene_triggers = CutsceneTriggerManager(self)

        self.profile = {
            "xp": 0,
            "gold": 0,
            "items": {},
            "skills": {"points": 4, "unlocked": {}},
            "skill_points": 4,
            "codex": {
                "locations": [],
                "characters": [],
                "factions": [],
                "npcs": [],
                "enemies": [],
                "tutorial": [],
                "events": [],
            },
        }
        self._ensure_codex_profile()
        self.state_mgr = StateManager(self)
        self.quest_mgr = QuestManager(self, self.data_mgr.quests)
        self.preload_mgr = PreloadManager(self)
        self.asset_bundle_mgr = AssetBundleManager(self)
        self.save_mgr = SaveManager(self)
        self.vehicle_mgr = VehicleManager(self)
        self.npc_mgr = NPCManager(self)
        self.npc_activity_director = NPCActivityDirector(self)
        self.skill_tree_mgr = SkillTreeManager(self)
        self.stealth_mgr = StealthManager(self)
        self.movement_tutorial = MovementTutorialManager(self)
        self._tutorial_quest_id = "movement_tutorial"
        self._tutorial_core_complete_sent = False
        self._tutorial_full_complete_sent = False
        self._tutorial_flow_blocked_by_opening = False
        self._opening_memory_pkg = {}
        self._opening_memory_started = False
        self._opening_memory_finished = False
        self._opening_banner_queue = []
        self._opening_banner_cursor = 0
        self._opening_banner_delay_left = 0.0
        self._opening_banner_time_left = 0.0
        self._opening_banner_elapsed = 0.0
        self._opening_banner_current = None
        self._opening_banner_active = False
        self._autosave_interval = 45.0
        self._last_autosave_time = 0.0
        self._autosave_flash_until = 0.0
        self._aim_target_info = None
        self._lock_target_kind = ""
        self._lock_target_id = ""
        self._aim_highlight_node = None
        self._aim_highlight_prev_color = None
        self._last_codex_location = ""
        self._stealth_state_cache = {}

        # -- UI --
        self.main_menu = MainMenu(self)
        self.pause_menu = PauseMenu(self)
        self.inventory_ui = InventoryUI(self)
        self.loading_screen = LoadingScreen(self)
        self.hud = HUDOverlay(self)
        self.hud.hide()

        from managers.dialogue_manager import DialogueManager
        self.dialogue_mgr = DialogueManager(self)

        # -- Start Preloading (Deferred till user starts the game) --
        # We save memory during the intro/menu by delaying asset loading.

        # -- Core Engine Systems (C++) --
        self._init_core_systems()
        self._last_particle_count = 0
        self._particle_upload_interval = 1.0 / 30.0
        self._particle_upload_accum = 0.0
        self._enemy_fire_particle_budget = 320
        self._enemy_fire_particle_budget_live = 320
        self._runtime_load_level = 0
        self._runtime_update_intervals = {}
        self._runtime_update_accum = {}
        self._world_state_cache = {}
        self._diag_log_interval_sec = 5.0
        self._last_diag_log_time = -999.0
        self._boss_update_fail_count = 0
        self._boss_update_last_log_time = -999.0

        # -- World & Player (Deferred) --
        self.world = None
        self.player = None
        self.boss_manager = None
        self.dragon_boss = None
        self.influence_mgr = InfluenceManager(self.render)
        self.sim_tier_mgr = SimTierManager(self)
        adaptive_mode = "balanced"
        cfg = getattr(self, "data_mgr", None)
        if cfg and isinstance(getattr(cfg, "graphics_settings", {}), dict):
            adaptive_mode = str(cfg.graphics_settings.get("adaptive_mode", adaptive_mode) or adaptive_mode)
        adaptive_mode = str(os.environ.get("XBOT_ADAPTIVE_MODE", adaptive_mode) or adaptive_mode).strip().lower()
        self.adaptive_perf_mgr = AdaptivePerformanceManager(self, mode=adaptive_mode)
        self._adaptive_mode = getattr(self.adaptive_perf_mgr, "mode", "balanced")
        self.dialog_cinematic = DialogCinematicManager(self)
        self.npc_interaction = NPCInteractionManager(self)
        self.story_interaction = StoryInteractionManager(self)

        # -- Start Intro --
        logger.info("Starting cinematic intro (8.7s expected)...")
        self.intro = IntroUI(self, on_complete=self._on_intro_done)
        self.intro.start()

        # -- Tasks --
        self.taskMgr.add(self._update, "main_update")
        self.taskMgr.add(self._heartbeat, "heartbeat_task")
        self.taskMgr.add(self._cursor_task, "ui_cursor_task")
        self.taskMgr.add(self._autosave_task, "autosave_task")
        self.accept("f11", self._request_fullscreen_toggle)
        self.accept("alt-enter", self._request_fullscreen_toggle)
        self.accept("f10", self._request_fullscreen_toggle)
        self._dev_location_idx = 0
        self.accept("f9", self._dev_transition_next)
        self.accept("window-event", self._on_window_event)
        self.accept("connect-device", self._on_input_device_change)
        self.accept("disconnect-device", self._on_input_device_change)
        self.accept("escape", self._on_escape_pressed)
        self.accept("f5", self._save_slot_hotkey, [1])
        self.accept("f6", self._save_slot_hotkey, [2])
        self.accept("f7", self._save_slot_hotkey, [3])
        self.accept("shift-f5", self._load_slot_hotkey, [1])
        self.accept("shift-f6", self._load_slot_hotkey, [2])
        self.accept("shift-f7", self._load_slot_hotkey, [3])
        self.accept("f8", self._restart_main_tutorial_hotkey)
        self.accept("shift-f8", self._restart_full_tutorial_hotkey)

        self.accept("wheel_up", self._zoom_camera, [-2.0])
        self.accept("wheel_down", self._zoom_camera, [2.0])
        self._setup_gamepad_input()
        self._setup_video_bot()

    def _zoom_camera(self, delta):
        if self._video_bot_input_locked():
            return
        if self.state_mgr.is_playing():
            self._cam_zoom_offset = getattr(self, "_cam_zoom_offset", 0.0) + delta
            self._cam_dist = max(5.0, min(50.0, self._cam_dist + delta))

    def _configure_fps_band(self, min_fps=30.0, max_fps=60.0):
        try:
            min_token = float(min_fps or 30.0)
        except Exception:
            min_token = 30.0
        try:
            max_token = float(max_fps or 60.0)
        except Exception:
            max_token = 60.0
        min_token = max(20.0, min(60.0, min_token))
        max_token = max(min_token, min(240.0, max_token))

        self._fps_target_min = min_token
        self._fps_target_max = max_token
        self._fps_sample_accum = 0.0
        self._fps_last_avg = max_token

        clock = getattr(self, "clock", None)
        if not clock:
            return
        try:
            clock.setMode(ClockObject.MLimited)
            clock.setFrameRate(float(self._fps_target_max))
            clock.setMaxDt(1.0 / max(1.0, float(self._fps_target_min)))
        except Exception as exc:
            logger.debug(f"[FPSBand] Failed to configure FPS band: {exc}")

    def _clear_gamepad_axes(self):
        self._gp_axes["move_x"] = 0.0
        self._gp_axes["move_y"] = 0.0
        self._gp_axes["look_x"] = 0.0
        self._gp_axes["look_y"] = 0.0

    def _apply_axis_deadzone(self, value):
        try:
            v = float(value or 0.0)
        except Exception:
            return 0.0
        d = max(0.01, min(0.4, float(getattr(self, "_gp_deadzone", 0.18) or 0.18)))
        a = abs(v)
        if a <= d:
            return 0.0
        return math.copysign((a - d) / max(1e-6, (1.0 - d)), v)

    def _axis_value(self, device, axis):
        if not device:
            return 0.0
        try:
            axis_node = device.findAxis(axis)
            if axis_node:
                return float(axis_node.value)
        except Exception:
            pass
        return 0.0

    def _setup_gamepad_input(self):
        self._attach_primary_gamepad()

    def _on_input_device_change(self, *_args):
        self._attach_primary_gamepad()

    def _attach_primary_gamepad(self):
        devices = []
        try:
            devices = self.devices.getDevices(InputDevice.DeviceClass.gamepad)
        except Exception:
            devices = []

        target = None
        for dev in devices:
            try:
                if dev and dev.isConnected():
                    target = dev
                    break
            except Exception:
                continue

        current = getattr(self, "_gamepad_device", None)
        if current and target and current == target:
            return

        if current:
            try:
                self.detachInputDevice(current)
            except Exception:
                pass
            self._gamepad_device = None

        if target:
            try:
                self.attachInputDevice(target, prefix="gamepad")
                self._gamepad_device = target
                logger.info(f"[Input] Gamepad attached: {target}")
            except Exception as exc:
                self._gamepad_device = None
                logger.debug(f"[Input] Failed to attach gamepad: {exc}")
                self._clear_gamepad_axes()
                return
        else:
            self._clear_gamepad_axes()

    def _sample_gamepad_axes(self):
        device = getattr(self, "_gamepad_device", None)
        if not device:
            self._attach_primary_gamepad()
            device = getattr(self, "_gamepad_device", None)
        if not device:
            self._clear_gamepad_axes()
            return
        try:
            if not device.isConnected():
                self._attach_primary_gamepad()
                device = getattr(self, "_gamepad_device", None)
        except Exception:
            self._attach_primary_gamepad()
            device = getattr(self, "_gamepad_device", None)
        if not device:
            self._clear_gamepad_axes()
            return

        lx = self._axis_value(device, InputDevice.Axis.left_x)
        ly = self._axis_value(device, InputDevice.Axis.left_y)
        rx = self._axis_value(device, InputDevice.Axis.right_x)
        ry = self._axis_value(device, InputDevice.Axis.right_y)

        self._gp_axes["move_x"] = self._apply_axis_deadzone(lx)
        self._gp_axes["move_y"] = -self._apply_axis_deadzone(ly)
        self._gp_axes["look_x"] = self._apply_axis_deadzone(rx)
        self._gp_axes["look_y"] = -self._apply_axis_deadzone(ry)

    def _remove_screenspace_nodes(self):
        try:
            for child in self.render.getChildren():
                if "screendisplay" in child.getName().lower():
                    child.removeNode()
        except Exception:
            pass
        try:
            for child in self.render2d.getChildren():
                if "screendisplay" in child.getName().lower():
                    child.removeNode()
        except Exception:
            pass

    def _safe_screenspace_init(self):
        if not bool(getattr(self, "_advanced_rendering", True)):
            self._screenspace_ready = False
            self._remove_screenspace_nodes()
            return False
        self._remove_screenspace_nodes()
        try:
            if self.win and self.win.getActiveDisplayRegions():
                complexpbr.screenspace_init()
                self._screenspace_ready = True
                return True
        except Exception as exc:
            logger.warning(f"[Render] screenspace init failed, keeping base shader only: {exc}")
        self._screenspace_ready = False
        return False

    def _apply_lighting_from_settings(self, quality_token):
        cfg = {}
        if hasattr(self, "data_mgr") and isinstance(getattr(self.data_mgr, "graphics_settings", {}), dict):
            cfg = self.data_mgr.graphics_settings
        lighting = cfg.get("lighting", {}) if isinstance(cfg, dict) else {}
        if not isinstance(lighting, dict):
            lighting = {}

        sun = lighting.get("sun", {}) if isinstance(lighting.get("sun"), dict) else {}
        ambient = lighting.get("ambient", {}) if isinstance(lighting.get("ambient"), dict) else {}

        q_mult = {"low": 0.90, "medium": 0.97, "high": 1.0, "ultra": 1.06}
        light_mult = q_mult.get(str(quality_token), 1.0)

        sun_color = sun.get("color", [1.0, 0.95, 0.9])
        amb_color = ambient.get("color", [0.3, 0.3, 0.35])
        try:
            sun_intensity = float(sun.get("intensity", 1.2) or 1.2) * light_mult
        except Exception:
            sun_intensity = 1.2 * light_mult
        try:
            amb_intensity = float(ambient.get("intensity", 0.5) or 0.5) * (0.9 + (0.1 * light_mult))
        except Exception:
            amb_intensity = 0.5
        if not bool(getattr(self, "_video_bot_visibility_boost", False)):
            # Keep world readability stable even when users previously forced "Low".
            sun_intensity = max(1.06, sun_intensity)
            amb_intensity = max(0.44, amb_intensity)
        if bool(getattr(self, "_video_bot_visibility_boost", False)):
            sun_intensity = max(1.20, sun_intensity)
            amb_intensity = max(0.58, amb_intensity)

        if hasattr(self, "_dlight") and self._dlight:
            try:
                self._dlight.setColor(
                    Vec4(
                        float(sun_color[0]) * sun_intensity,
                        float(sun_color[1]) * sun_intensity,
                        float(sun_color[2]) * sun_intensity,
                        1.0,
                    )
                )
            except Exception:
                pass
            direction = sun.get("direction", [1, -2, -2])
            if isinstance(direction, (list, tuple)) and len(direction) >= 3 and hasattr(self, "_dlnp"):
                try:
                    dx, dy, dz = float(direction[0]), float(direction[1]), float(direction[2])
                    heading = math.degrees(math.atan2(dx, dy))
                    pitch = math.degrees(math.atan2(dz, max(0.001, math.sqrt((dx * dx) + (dy * dy)))))
                    self._dlnp.setHpr(heading, pitch, 0.0)
                except Exception:
                    pass

        if hasattr(self, "_alight") and self._alight:
            try:
                self._alight.setColor(
                    Vec4(
                        float(amb_color[0]) * amb_intensity,
                        float(amb_color[1]) * amb_intensity,
                        float(amb_color[2]) * amb_intensity,
                        1.0,
                    )
                )
            except Exception:
                pass

        shadow_boost = {"low": 0.0, "medium": 0.08, "high": 0.14, "ultra": 0.22}.get(str(quality_token), 0.1)
        try:
            self.render.set_shader_input("shadow_boost", shadow_boost, priority=1000)
        except Exception:
            pass
        if bool(getattr(self, "_video_bot_visibility_boost", False)):
            try:
                self.render.clearFog()
            except Exception:
                pass
            try:
                self.render.set_shader_input("shadow_boost", max(0.26, float(shadow_boost)), priority=1001)
            except Exception:
                pass
            try:
                self.render.setColorScale(1.0, 1.0, 1.0, 1.0)
            except Exception:
                pass
        else:
            try:
                self.render.setColorScale(1.0, 1.0, 1.0, 1.0)
            except Exception:
                pass

    def set_runtime_load_profile(self, profile, level=0):
        cfg = profile if isinstance(profile, dict) else {}
        self._runtime_load_level = max(0, min(3, int(level or 0)))

        interval_map = {
            "sky_update_interval": "sky",
            "influence_update_interval": "influence",
            "npc_activity_update_interval": "npc_activity",
            "npc_interaction_update_interval": "npc_interaction",
            "story_interaction_update_interval": "story_interaction",
            "cutscene_trigger_update_interval": "cutscene_triggers",
            "npc_logic_update_interval": "npc_logic",
            "enemy_update_interval": "enemy_logic",
        }
        intervals = (
            self._runtime_update_intervals
            if isinstance(getattr(self, "_runtime_update_intervals", None), dict)
            else {}
        )
        accum = (
            self._runtime_update_accum
            if isinstance(getattr(self, "_runtime_update_accum", None), dict)
            else {}
        )

        for profile_key, runtime_key in interval_map.items():
            try:
                interval = max(0.0, min(0.30, float(cfg.get(profile_key, 0.0) or 0.0)))
            except Exception:
                interval = 0.0
            if abs(float(intervals.get(runtime_key, 0.0) or 0.0) - interval) > 1e-6:
                accum[runtime_key] = 0.0
            intervals[runtime_key] = interval

        self._runtime_update_intervals = intervals
        self._runtime_update_accum = accum

        if "particle_upload_interval" in cfg:
            try:
                self._particle_upload_interval = max(
                    1.0 / 120.0,
                    min(1.0 / 6.0, float(cfg.get("particle_upload_interval", 1.0 / 30.0))),
                )
            except Exception:
                self._particle_upload_interval = 1.0 / 30.0
        if "enemy_fire_particle_budget" in cfg:
            try:
                self._enemy_fire_particle_budget = max(
                    32,
                    min(2048, int(round(float(cfg.get("enemy_fire_particle_budget", 320) or 320)))),
                )
            except Exception:
                self._enemy_fire_particle_budget = 320
            self._enemy_fire_particle_budget_live = self._enemy_fire_particle_budget

        stm = getattr(self, "sim_tier_mgr", None)
        if stm and hasattr(stm, "set_runtime_profile"):
            try:
                stm.set_runtime_profile(
                    tick_rate_hz=cfg.get("sim_tick_rate_hz", None),
                    budget_scale=cfg.get("sim_budget_scale", None),
                )
            except Exception as exc:
                logger.debug(f"[RuntimeProfile] Sim-tier runtime profile failed: {exc}")

    def set_adaptive_graphics_mode(self, mode, persist=True):
        perf_mgr = getattr(self, "adaptive_perf_mgr", None)
        token = "balanced"
        if perf_mgr and hasattr(perf_mgr, "set_mode"):
            try:
                token = str(perf_mgr.set_mode(mode, force_reapply=True) or "balanced")
            except Exception as exc:
                logger.debug(f"[AdaptivePerformance] Mode switch failed: {exc}")
                token = str(getattr(perf_mgr, "mode", "balanced") or "balanced")
        self._adaptive_mode = token

        cfg = getattr(self, "data_mgr", None)
        if persist and cfg and isinstance(getattr(cfg, "graphics_settings", {}), dict):
            cfg.graphics_settings["adaptive_mode"] = token
            cfg.save_settings("graphics_settings.json", cfg.graphics_settings)
        return token

    def _runtime_take_dt(self, key, dt):
        intervals = getattr(self, "_runtime_update_intervals", {})
        accum_map = getattr(self, "_runtime_update_accum", {})
        if not isinstance(intervals, dict) or not isinstance(accum_map, dict):
            return max(0.0, float(dt or 0.0))

        try:
            interval = max(0.0, float(intervals.get(key, 0.0) or 0.0))
        except Exception:
            interval = 0.0
        dt_val = max(0.0, float(dt or 0.0))
        if interval <= 0.0:
            return dt_val

        accum = float(accum_map.get(key, 0.0) or 0.0) + dt_val
        if accum + 1e-9 < interval:
            accum_map[key] = accum
            return 0.0

        accum_map[key] = 0.0
        return accum

    def _iter_loaded_textures(self):
        seen = set()
        collections = []
        for fetcher in ("findAllTextures", "find_all_textures"):
            fn = getattr(TexturePool, fetcher, None)
            if callable(fn):
                try:
                    collections.append(fn())
                except Exception:
                    continue

        for collection in collections:
            if collection is None:
                continue
            try:
                texture_rows = list(collection)
            except Exception:
                continue
            for tex in texture_rows:
                if tex is None:
                    continue
                marker = id(tex)
                if marker in seen:
                    continue
                seen.add(marker)
                yield tex

    def _apply_texture_sampler_defaults(self, quality_token):
        token = str(quality_token or "high").strip().lower()
        aniso_target = {"low": 2, "medium": 4, "high": 8, "ultra": 12}.get(token, 8)
        min_filter = getattr(SamplerState, "FT_linear_mipmap_linear", None)
        if min_filter is None:
            min_filter = getattr(Texture, "FTLinearMipmapLinear", None)
        mag_filter = getattr(SamplerState, "FT_linear", None)
        if mag_filter is None:
            mag_filter = getattr(Texture, "FTLinear", None)

        tuned = 0
        for tex in self._iter_loaded_textures():
            try:
                if hasattr(tex, "isEmpty") and tex.isEmpty():
                    continue
            except Exception:
                pass

            touched = False
            if min_filter is not None:
                setter = getattr(tex, "setMinfilter", None) or getattr(tex, "set_minfilter", None)
                if callable(setter):
                    try:
                        setter(min_filter)
                        touched = True
                    except Exception:
                        pass
            if mag_filter is not None:
                setter = getattr(tex, "setMagfilter", None) or getattr(tex, "set_magfilter", None)
                if callable(setter):
                    try:
                        setter(mag_filter)
                        touched = True
                    except Exception:
                        pass
            aniso_setter = getattr(tex, "setAnisotropicDegree", None) or getattr(tex, "set_anisotropic_degree", None)
            if callable(aniso_setter):
                try:
                    aniso_setter(int(aniso_target))
                    touched = True
                except Exception:
                    pass
            if touched:
                tuned += 1
        return tuned

    def apply_graphics_quality(self, level, persist=True):
        token = str(level or "high").strip().lower()
        if token in {"med", "middle"}:
            token = "medium"
        if token not in {"low", "medium", "high", "ultra"}:
            token = "high"

        aa = {"low": 0, "medium": 2, "high": 4, "ultra": 8}.get(token, 4)
        if aa == 0:
            self.render.setAntialias(0)
        else:
            self.render.setAntialias(AntialiasAttrib.MMultisample, aa)

        # Toggle heavy screenspace pass.
        if token in {"medium", "high", "ultra"} and getattr(self, "_advanced_rendering", True):
            self._safe_screenspace_init()
        else:
            self._screenspace_ready = False
            self._remove_screenspace_nodes()

        bloom_intensity = 0.50
        bloom_threshold = 0.66
        exposure = 1.16
        cfg = getattr(self, "data_mgr", None)
        if cfg and isinstance(getattr(cfg, "graphics_settings", {}), dict):
            pbr_cfg = cfg.graphics_settings.get("pbr", {})
            if isinstance(pbr_cfg, dict):
                try:
                    exposure = float(pbr_cfg.get("exposure", exposure) or exposure)
                except Exception:
                    exposure = 1.16
            pp = cfg.graphics_settings.get("post_processing", {})
            if isinstance(pp, dict):
                bloom = pp.get("bloom", {})
                if isinstance(bloom, dict):
                    try:
                        bloom_intensity = float(bloom.get("intensity", bloom_intensity) or bloom_intensity)
                    except Exception:
                        bloom_intensity = 0.50
                    try:
                        bloom_threshold = float(bloom.get("threshold", bloom_threshold) or bloom_threshold)
                    except Exception:
                        bloom_threshold = 0.66
        bloom_scale = {"low": 0.86, "medium": 0.95, "high": 1.0, "ultra": 1.05}.get(token, 1.0)
        bloom_intensity *= bloom_scale
        bloom_intensity = max(0.14, min(0.74, float(bloom_intensity)))
        exposure *= {"low": 0.95, "medium": 0.99, "high": 1.0, "ultra": 1.03}.get(token, 1.0)
        exposure = max(0.92, min(1.50, float(exposure)))
        if bool(getattr(self, "_video_bot_visibility_boost", False)):
            # Keep capture readable without aggressive glow halos.
            bloom_intensity = min(0.58, float(bloom_intensity))
            exposure = min(1.18, float(exposure))

        if getattr(self, "_advanced_rendering", True) and hasattr(self, "screen_quad"):
            try:
                self.screen_quad.set_shader_input("bloom_intensity", bloom_intensity)
            except Exception:
                pass
            try:
                self.screen_quad.set_shader_input("bloom_threshold", max(0.40, min(1.35, float(bloom_threshold))))
            except Exception:
                pass
            try:
                self.screen_quad.set_shader_input("exposure", exposure)
            except Exception:
                pass
        try:
            self.render.set_shader_input("exposure", exposure, priority=1000)
        except Exception:
            pass

        self._apply_lighting_from_settings(token)
        self._gfx_quality = token.title()
        try:
            tuned_count = self._apply_texture_sampler_defaults(token)
            if tuned_count > 0:
                logger.debug(f"[Visuals] Updated texture sampling defaults for {tuned_count} textures.")
        except Exception as exc:
            logger.debug(f"[Visuals] Texture sampling update skipped: {exc}")

        perf_mgr = getattr(self, "adaptive_perf_mgr", None)
        if perf_mgr and hasattr(perf_mgr, "on_quality_changed"):
            try:
                perf_mgr.on_quality_changed(self._gfx_quality, user_initiated=bool(persist))
            except Exception as exc:
                logger.debug(f"[AdaptivePerformance] Quality update hook failed: {exc}")

        if persist and cfg and isinstance(cfg.graphics_settings, dict):
            cfg.graphics_settings["quality"] = self._gfx_quality
            cfg.save_settings("graphics_settings.json", cfg.graphics_settings)

    def _setup_window(self, initial=True):
        props = WindowProperties()
        props.setTitle("King Wizard")
        if initial:
            props.setOpen(True)
        if not self._is_fullscreen:
            props.setSize(self._windowed_size[0], self._windowed_size[1])
            props.setOrigin(self._windowed_origin[0], self._windowed_origin[1])
        props.setForeground(True)
        self.win.requestProperties(props)
        self._setup_cursor()
        logger.info("Window properties requested and forced foreground.")

    def _build_cursor_texture(self, cursor_path):
        img = PNMImage()
        if not img.read(cursor_path):
            return self.loader.loadTexture(cursor_path)

        if img.hasAlpha():
            tex = Texture("ui_cursor_alpha_src")
            tex.load(img)
            return tex
        else:
            img.addAlpha()

        # Color-key style alpha synthesis for cursor files without alpha channel.
        # Input file has checkerboard baked in; key out neutral checker tones.
        for py in range(img.getYSize()):
            for px in range(img.getXSize()):
                r = img.getRed(px, py)
                g = img.getGreen(px, py)
                b = img.getBlue(px, py)
                mx = max(r, g, b)
                mn = min(r, g, b)
                sat = 0.0 if mx <= 1e-6 else (mx - mn) / mx
                lum = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
                neutral = abs(r - g) < 0.07 and abs(g - b) < 0.07
                if neutral and lum < 0.78:
                    alpha = 0.0
                else:
                    alpha = max(0.0, min(1.0, ((sat - 0.08) / 0.30) + ((lum - 0.20) / 0.55)))
                    if b > g + 0.03 and g > r + 0.02:
                        alpha = max(alpha, min(1.0, (b - 0.22) / 0.45))

                img.setAlpha(px, py, alpha)

        tex = Texture("ui_cursor_alpha")
        tex.load(img)
        return tex

    def _setup_cursor(self):
        preferred = [
            "assets/textures/menu_cursor.png",
            "assets/textures/game_cursor.png",
        ]
        cursor_path = next((p for p in preferred if os.path.exists(p)), None)
        if not cursor_path:
            return
        if not hasattr(self, "_cursor_image"):
            from direct.gui.DirectGui import OnscreenImage
            cursor_tex = self._build_cursor_texture(cursor_path)
            self._cursor_scale_px = 24.0
            self._cursor_hotspot_px = (19.0, -19.0)
            self._cursor_image = OnscreenImage(
                image=cursor_tex if cursor_tex else cursor_path,
                pos=(0, 0, 0),
                scale=self._cursor_scale_px,
                parent=self.pixel2d,
            )
            self._cursor_image.setTransparency(TransparencyAttrib.MAlpha)
            self._cursor_image.setBin("fixed", 100)
            self._cursor_image.setDepthTest(False)
            self._cursor_image.setDepthWrite(False)
            self._cursor_image.setShaderOff(1001)
        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)

    def _cursor_task(self, task):
        if not hasattr(self, "_cursor_image") or not self.win:
            return Task.cont
        input_locked = bool(self._video_bot_input_locked())
        force_virtual = bool(input_locked and getattr(self, "_video_bot_enabled", False))
        use_virtual = bool(getattr(self, "_video_bot_cursor_visible", False) or force_virtual)
        state = getattr(getattr(self, "state_mgr", None), "current_state", None)
        ui_states = {
            getattr(self.GameState, "MAIN_MENU", None),
            getattr(self.GameState, "PAUSED", None),
            getattr(self.GameState, "INVENTORY", None),
            getattr(self.GameState, "DIALOG", None),
        }
        show_cursor = bool(state in ui_states)
        if bool(getattr(self, "_video_bot_enabled", False)) and not show_cursor:
            self._cursor_image.hide()
            return Task.cont
        self._cursor_image.show()
        if use_virtual:
            x, y = getattr(self, "_video_bot_cursor_pos", (0.0, 0.0))
        else:
            if not self.mouseWatcherNode.hasMouse():
                self._cursor_image.hide()
                return Task.cont
            x = self.mouseWatcherNode.getMouseX()
            y = self.mouseWatcherNode.getMouseY()
        sx = self.win.getXSize()
        sy = self.win.getYSize()
        px = (x + 1.0) * 0.5 * sx
        py = (1.0 - y) * 0.5 * sy
        hx, hy = getattr(self, "_cursor_hotspot_px", (0.0, 0.0))
        self._cursor_image.setPos(px + hx, 0, -(py - hy))
        base_scale = float(getattr(self, "_cursor_scale_px", 24.0) or 24.0)
        if float(getattr(self, "_video_bot_elapsed", 0.0) or 0.0) <= float(
            getattr(self, "_video_bot_cursor_click_until", -1.0) or -1.0
        ):
            self._cursor_image.setScale(base_scale * 1.24)
        else:
            self._cursor_image.setScale(base_scale)
        return Task.cont

    def _on_window_event(self, window):
        if window != self.win or not self.win:
            return
        try:
            wp = WindowProperties()
            wp.setCursorHidden(True)
            self.win.requestProperties(wp)
        except Exception:
            pass
        props = self.win.getProperties()
        self._is_fullscreen = bool(props.getFullscreen())
        if not self._is_fullscreen:
            if props.getXSize() > 0 and props.getYSize() > 0:
                self._windowed_size = (props.getXSize(), props.getYSize())
            if props.getOpen():
                self._windowed_origin = (props.getXOrigin(), props.getYOrigin())
        if hasattr(self, "main_menu") and self.main_menu:
            try:
                self.main_menu.on_window_resized(self.getAspectRatio())
            except Exception:
                pass
        if hasattr(self, "pause_menu") and self.pause_menu:
            try:
                self.pause_menu.on_window_resized(self.getAspectRatio())
            except Exception:
                pass
        if hasattr(self, "inventory_ui") and self.inventory_ui:
            try:
                self.inventory_ui.on_window_resized(self.getAspectRatio())
            except Exception:
                pass

    def _request_fullscreen_toggle(self):
        if self._video_bot_input_locked():
            return
        now = globalClock.getFrameTime()
        if now - self._last_fs_toggle_time < 0.25:
            return
        self._last_fs_toggle_time = now
        self.toggle_fullscreen()

    def _on_escape_pressed(self, from_video_bot=False):
        if self._video_bot_input_locked() and not bool(from_video_bot):
            return
        state = self.state_mgr.current_state

        if state == self.GameState.DIALOG:
            dialog = getattr(self, "dialog_cinematic", None)
            if dialog and hasattr(dialog, "is_active") and dialog.is_active():
                try:
                    dialog.finish()
                except Exception:
                    pass
            return

        if state == self.GameState.PLAYING:
            director = getattr(self, "camera_director", None)
            if director and hasattr(director, "is_cutscene_active"):
                try:
                    if director.is_cutscene_active():
                        return
                except Exception:
                    pass
            self.state_mgr.set_state(self.GameState.PAUSED)
            self.aspect2d.show() # Make UI layer visible
            self.pause_menu.set_loading(False)
            self.pause_menu.show()
            return

        if state == self.GameState.PAUSED:
            self.pause_menu.hide()
            self.aspect2d.hide() # Hide UI layer again
            self.state_mgr.set_state(self.GameState.PLAYING)
            return

        if state == self.GameState.INVENTORY:
            self.inventory_ui.hide()
            self.state_mgr.set_state(self.GameState.PLAYING)

    def toggle_fullscreen(self):
        if not self.win:
            return
        props = self.win.getProperties()
        entering_fullscreen = not self._is_fullscreen

        wp = WindowProperties()
        wp.setFullscreen(entering_fullscreen)
        wp.setUndecorated(entering_fullscreen)

        if entering_fullscreen:
            if props.getXSize() > 0 and props.getYSize() > 0:
                self._windowed_size = (props.getXSize(), props.getYSize())
            self._windowed_origin = (props.getXOrigin(), props.getYOrigin())
            disp_w = self.pipe.getDisplayWidth()
            disp_h = self.pipe.getDisplayHeight()
            if disp_w <= 0 or disp_h <= 0:
                disp_w = max(props.getXSize(), 1280)
                disp_h = max(props.getYSize(), 720)
            wp.setSize(disp_w, disp_h)
            wp.setOrigin(0, 0)
        else:
            wp.setSize(self._windowed_size[0], self._windowed_size[1])
            wp.setOrigin(self._windowed_origin[0], self._windowed_origin[1])
        self.win.requestProperties(wp)
        logger.info(f"Fullscreen toggled: {'ON' if entering_fullscreen else 'OFF'}")

    def _on_intro_done(self):
        self.setBackgroundColor(0.45, 0.62, 0.85)

        # Runtime test launchers can request deterministic auto-start after intro.
        has_test_bootstrap = bool(self._test_profile or self._test_location_raw or self._test_scenario_raw)
        if bool(getattr(self, "_auto_start_requested", False)) and has_test_bootstrap:
            logger.info(
                "[TestLauncher] Auto-starting runtime test "
                f"profile='{self._test_profile or '-'}' "
                f"location='{self._test_location_raw or '-'}' "
                f"scenario='{self._test_scenario_raw or '-'}'."
            )
            self.hud.set_autosave(False)
            self.render.clearColorScale()
            self.aspect2d.clearColorScale()
            self.state_mgr.set_state(self.GameState.MAIN_MENU)
            self.aspect2d.hide()
            self.main_menu.hide()
            self.start_play(load_save=False)
            return

        # Transition straight to Main Menu without loading the heavy 3D world yet.
        self.hud.set_autosave(False)
        self.render.clearColorScale()
        self.aspect2d.clearColorScale()
        self.state_mgr.set_state(self.GameState.MAIN_MENU)
        self.aspect2d.show()
        self.main_menu.show()

    def _collect_startup_preload_assets(self):
        candidates = [
            "assets/models/hero/sherward/sherward.glb",
            "assets/models/xbot/Xbot.glb",
            "assets/models/xbot/idle.glb",
            "assets/models/xbot/walk.glb",
            "assets/models/xbot/run.glb",
            "assets/models/enemies/golem_boss.glb",
            "assets/models/bosses/dragon_evolved.glb",
        ]

        player_cfg = {}
        payload = getattr(self.data_mgr, "player_config", None)
        if isinstance(payload, dict):
            row = payload.get("player")
            if isinstance(row, dict):
                player_cfg = row

        for key in ("model", "fallback_model"):
            value = player_cfg.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        model_candidates = player_cfg.get("model_candidates", [])
        if isinstance(model_candidates, list):
            for value in model_candidates:
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
        base_anims = player_cfg.get("base_anims", {})
        if isinstance(base_anims, dict):
            for value in base_anims.values():
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())

        out = []
        seen = set()
        for raw in candidates:
            token = str(raw or "").strip().replace("\\", "/")
            if not token or token in seen:
                continue
            seen.add(token)
            abs_path = os.path.join(self.project_root, token)
            if os.path.exists(abs_path):
                out.append(token)
        return out

    def _merge_asset_targets(self, *groups):
        out = []
        seen = set()
        for group in groups:
            for raw in list(group or []):
                token = str(raw or "").strip().replace("\\", "/")
                if not token or token in seen:
                    continue
                seen.add(token)
                out.append(token)
        return out

    def start_game_loading(self):
        logger.info("Starting Game - Queueing heavy assets for preloading...")
        self.loading_screen.show(context="startup")
        self.hud.set_autosave(True)
        preload_targets = self._collect_startup_preload_assets()
        if getattr(self, "asset_bundle_mgr", None):
            try:
                bundle_targets = self.asset_bundle_mgr.activate_profile("startup")
                loc_targets = self.asset_bundle_mgr.activate_for_location("sharuan")
                preload_targets = self._merge_asset_targets(preload_targets, bundle_targets, loc_targets)
            except Exception as exc:
                logger.debug(f"[AssetBundle] Startup activation skipped: {exc}")
        if hasattr(self.preload_mgr, "merge_with_cached"):
            try:
                preload_targets = self.preload_mgr.merge_with_cached(preload_targets, limit=56)
            except Exception as exc:
                logger.debug(f"[PreloadManager] cache merge failed: {exc}")
        self.preload_mgr.preload_assets(preload_targets)

        if hasattr(self.audio, "warmup_cache"):
            try:
                warmed = int(self.audio.warmup_cache(include_sfx=True, sfx_limit=12))
                logger.info(f"[Audio] Warmed audio cache entries: {warmed}")
            except Exception as exc:
                logger.debug(f"[Audio] Warmup skipped: {exc}")

        # -- World Generation --
        self.world = SharuanWorld(self)
        self.taskMgr.add(self._world_gen_task, "world_gen_task")

    def _bootstrap_quests(self):
        if not isinstance(self.data_mgr.quests, dict):
            return
        if self.quest_mgr.active_quests:
            return

        supported = {"reach_location", "interact"}
        for quest in self.data_mgr.quests.values():
            if not isinstance(quest, dict):
                continue
            quest_id = quest.get("id")
            objectives = quest.get("objectives")
            if not quest_id or not isinstance(objectives, list) or not objectives:
                continue
            first_obj = objectives[0]
            if not isinstance(first_obj, dict):
                continue
            obj_type = first_obj.get("type")
            if obj_type not in supported:
                continue
            if obj_type == "reach_location":
                target = first_obj.get("target")
                if not (isinstance(target, list) and len(target) == 3):
                    continue
                if "radius" not in first_obj:
                    continue
            if self.quest_mgr.start_quest(quest_id):
                logger.info(f"[Quest] Bootstrapped quest: {quest_id}")
                return

    def _resolve_test_location(self, token):
        raw = str(token or "").strip().lower()
        if not raw:
            return None

        world = getattr(self, "world", None)

        def _zone_center(zone_id):
            layout = getattr(world, "layout", None) if world else None
            zones = layout.get("zones", []) if isinstance(layout, dict) else []
            target = str(zone_id or "").strip().lower()
            if not target or not isinstance(zones, list):
                return None
            for row in zones:
                if not isinstance(row, dict):
                    continue
                row_id = str(row.get("id", "") or "").strip().lower()
                center = row.get("center")
                if row_id != target or not (isinstance(center, list) and len(center) >= 2):
                    continue
                try:
                    x = float(center[0])
                    y = float(center[1])
                    z = float(center[2]) if len(center) >= 3 else 0.0
                    return Vec3(x, y, z)
                except Exception:
                    continue
            return None

        presets = {
            "town": Vec3(0.0, 0.0, 0.0),
            "castle": Vec3(0.0, 78.0, 0.0),
            "castle_interior": Vec3(0.0, 79.0, 0.0),
            "prince_chamber": Vec3(6.0, 74.0, 0.0),
            "world_map_gallery": Vec3(-4.0, 72.0, 0.0),
            "royal_laundry": Vec3(-9.0, 70.0, 0.0),
            "throne_hall": Vec3(0.0, 88.0, 0.0),
            "docks": Vec3(18.0, -62.0, 0.0),
            "port": Vec3(18.0, -62.0, 0.0),
            "dragon_arena": Vec3(34.0, -6.0, 0.0),
            "boats": Vec3(23.0, -74.0, 0.0),
            "training": Vec3(18.0, 24.0, 0.0),
            "training_grounds": Vec3(18.0, 24.0, 0.0),
            "parkour": Vec3(42.0, 33.0, 0.0),
            "stealth_climb": Vec3(72.0, 24.0, 0.0),
            "stealth": Vec3(72.0, 24.0, 0.0),
            "flight": Vec3(-5.0, 23.0, 0.0),
            "kremor_forest": Vec3(76.0, 12.0, 0.0),
            "dwarven_caves": Vec3(96.0, -14.0, 0.0),
            "dwarven_caves_gate": Vec3(92.0, -6.0, 0.0),
            "dwarven_caves_halls": Vec3(96.0, -14.0, 0.0),
            "dwarven_caves_throne": Vec3(102.0, -24.0, 0.0),
            "ultimate_sandbox": Vec3(0.0, 0.0, 5.0),
        }
        zone_overrides = {
            "castle": "inner_castle",
            "castle_interior": "castle_interior",
            "prince_chamber": "prince_chamber",
            "world_map_gallery": "world_map_gallery",
            "royal_laundry": "royal_laundry",
            "throne_hall": "throne_hall",
            "docks": "port_town",
            "port": "port_town",
            "training": "training_grounds",
            "training_grounds": "training_grounds",
            "parkour": "parkour_grounds",
            "stealth_climb": "stealth_climb_grounds",
            "stealth": "stealth_climb_grounds",
            "flight": "flight_grounds",
            "kremor_forest": "kremor_forest_crash",
            "dwarven_caves": "dwarven_caves_halls",
            "dwarven_caves_gate": "dwarven_caves_gate",
            "dwarven_caves_halls": "dwarven_caves_halls",
            "dwarven_caves_throne": "dwarven_caves_throne",
        }
        for key, zone_id in zone_overrides.items():
            center = _zone_center(zone_id)
            if center is not None:
                presets[key] = Vec3(center)

        from_preset = False
        if raw in presets:
            pos = Vec3(presets[raw])
            from_preset = True
        else:
            # Try direct zone resolution from layout
            center = _zone_center(raw)
            if center is not None:
                pos = Vec3(center)
                from_preset = True
            else:
                parts = [p.strip() for p in raw.split(",")]
            if len(parts) not in {2, 3}:
                return None
            try:
                x = float(parts[0])
                y = float(parts[1])
                z = float(parts[2]) if len(parts) == 3 else 0.0
                pos = Vec3(x, y, z)
            except Exception:
                return None

        if self.world and hasattr(self.world, "_th"):
            try:
                pos.z = float(self.world._th(pos.x, pos.y)) + 2.2
            except Exception:
                pass
        if from_preset and world and hasattr(world, "sample_water_height"):
            try:
                # Keep authored preset teleports safely above water level to avoid
                # camera-underwater captures in automated footage.
                water_floor = float(world.sample_water_height(pos.x, pos.y)) + 0.75
                if pos.z < water_floor:
                    pos.z = water_floor
            except Exception:
                pass
        return pos

    def _resolve_test_world_location_name(self, token):
        raw = str(token or "").strip().lower()
        if not raw:
            return ""

        world = getattr(self, "world", None)
        layout = getattr(world, "layout", None) if world else None
        zones = layout.get("zones", []) if isinstance(layout, dict) else []

        zone_alias = {
            "castle": "inner_castle",
            "castle_interior": "castle_interior",
            "prince_chamber": "prince_chamber",
            "world_map_gallery": "world_map_gallery",
            "royal_laundry": "royal_laundry",
            "throne_hall": "throne_hall",
            "town": "town_center",
            "docks": "port_town",
            "port": "port_town",
            "dragon_arena": "dragon_arena",
            "boats": "boats_route",
            "training": "training_grounds",
            "training_grounds": "training_grounds",
            "parkour": "parkour_grounds",
            "stealth_climb": "stealth_climb_grounds",
            "stealth": "stealth_climb_grounds",
            "flight": "flight_grounds",
            "kremor_forest": "kremor_forest_crash",
            "dwarven_caves": "dwarven_caves_halls",
            "dwarven_caves_gate": "dwarven_caves_gate",
            "dwarven_caves_halls": "dwarven_caves_halls",
            "dwarven_caves_throne": "dwarven_caves_throne",
        }
        target_zone = zone_alias.get(raw, raw)
        if isinstance(zones, list):
            for row in zones:
                if not isinstance(row, dict):
                    continue
                row_id = str(row.get("id", "") or "").strip().lower()
                if row_id != target_zone:
                    continue
                name = str(row.get("name", "") or "").strip()
                if name:
                    return name

        fallback = {
            "castle": "Castle Courtyard",
            "castle_interior": "Castle Interior",
            "prince_chamber": "Prince Chamber",
            "world_map_gallery": "World Map Gallery",
            "royal_laundry": "Royal Laundry",
            "throne_hall": "Throne Hall",
            "town": "Town Center",
            "docks": "Southern Docks",
            "port": "Southern Docks",
            "dragon_arena": "Dragon Arena",
            "training": "Training Grounds",
            "training_grounds": "Training Grounds",
            "parkour": "Forest Parkour Grounds",
            "stealth_climb": "Stealth Climb Grounds",
            "flight": "Coastal Flight Grounds",
            "kremor_forest": "Kremor Forest Crash Site",
            "dwarven_caves": "Dwarven Forge Halls",
            "dwarven_caves_gate": "Dwarven Caves Gate",
            "dwarven_caves_halls": "Dwarven Forge Halls",
            "dwarven_caves_throne": "Dwarven Grand Throne",
            "ultimate_sandbox": "Ultimate Sandbox",
        }
        return str(fallback.get(raw, "") or "")

    def _resolve_test_scenario(self, token):
        raw = str(token or "").strip().lower()
        if not raw:
            return None
        getter = getattr(getattr(self, "data_mgr", None), "get_test_scenarios", None)
        if not callable(getter):
            return None
        rows = getter() or []
        if not isinstance(rows, list) or not rows:
            return None

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(rows):
                row = rows[idx]
                return dict(row) if isinstance(row, dict) else None

        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id", "") or "").strip().lower()
            if row_id and row_id == raw:
                return dict(row)
        return None

    def _teleport_player_to(self, pos):
        if not self.player or not self.player.actor or pos is None:
            return False

        self.player.actor.setPos(pos)
        if HAS_CORE and self.char_state:
            try:
                self.char_state.position = gc.Vec3(pos.x, pos.y, pos.z)
                self.char_state.velocity = gc.Vec3(0.0, 0.0, 0.0)
            except Exception:
                pass

        self.camera.setPos(pos.x, pos.y - 18.0, pos.z + 10.0)
        self.camera.lookAt(self.player.actor)
        return True

    def _activate_journal_test_data(self):
        if not hasattr(self, "quest_mgr") or not self.quest_mgr:
            return
        started = 0
        if isinstance(self.data_mgr.quests, dict):
            for quest_id in self.data_mgr.quests.keys():
                if self.quest_mgr.start_quest(quest_id):
                    started += 1
        if started == 0:
            self._bootstrap_quests()

    def _emit_cutscene_event(self, event_name, payload=None):
        payload = payload or {}
        mgr = getattr(self, "cutscene_triggers", None)
        if not mgr or not hasattr(mgr, "emit"):
            mgr_ok = False
        else:
            mgr_ok = True
            try:
                mgr.emit(event_name, payload)
            except Exception as exc:
                logger.debug(f"[CutsceneTriggers] emit failed '{event_name}': {exc}")
        bus = getattr(self, "event_bus", None)
        if bus and hasattr(bus, "emit"):
            try:
                bus.emit(f"game.{str(event_name or '').strip().lower()}", payload, immediate=False)
                bus.emit("game.event", {"name": str(event_name), "payload": dict(payload)}, immediate=False)
            except Exception as exc:
                logger.debug(f"[EventBus] emit failed '{event_name}': {exc}")
        if not mgr_ok:
            return

    def on_quest_started(self, quest_id, quest):
        del quest
        self._emit_cutscene_event("quest_started", {"quest_id": str(quest_id)})

    def on_quest_completed(self, quest_id, quest):
        del quest
        self._emit_cutscene_event("quest_completed", {"quest_id": str(quest_id)})

    def on_quest_objective_advanced(self, quest_id, objective_index, objective_total):
        self._emit_cutscene_event(
            "quest_objective_advanced",
            {
                "quest_id": str(quest_id),
                "objective_index": int(objective_index),
                "objective_total": int(objective_total),
            },
        )

    def _ensure_tutorial_quest_started(self):
        qm = getattr(self, "quest_mgr", None)
        quest_id = str(getattr(self, "_tutorial_quest_id", "movement_tutorial"))
        if not qm or not quest_id:
            return False
        if quest_id in getattr(qm, "completed_quests", set()):
            return False
        if quest_id in getattr(qm, "active_quests", {}):
            return False
        try:
            return bool(qm.start_quest(quest_id))
        except Exception:
            return False

    def _complete_tutorial_quest(self):
        qm = getattr(self, "quest_mgr", None)
        quest_id = str(getattr(self, "_tutorial_quest_id", "movement_tutorial"))
        if not qm or not quest_id:
            return False
        if quest_id in getattr(qm, "completed_quests", set()):
            return False
        if hasattr(qm, "complete_quest"):
            try:
                return bool(qm.complete_quest(quest_id, grant_rewards=True))
            except Exception as exc:
                logger.warning(f"[TutorialQuest] complete_quest failed: {exc}")
                return False
        return False

    def _sync_tutorial_completion_flags(self):
        tutorial = getattr(self, "movement_tutorial", None)
        if not tutorial:
            self._tutorial_core_complete_sent = False
            self._tutorial_full_complete_sent = False
            return
        snap = tutorial.get_status_snapshot() if hasattr(tutorial, "get_status_snapshot") else {}
        self._tutorial_core_complete_sent = bool(snap.get("core_complete", False))
        self._tutorial_full_complete_sent = bool(snap.get("full_complete", False))

    def _start_tutorial_flow(self, *, reset, mode, source="runtime"):
        tutorial = getattr(self, "movement_tutorial", None)
        if not tutorial:
            return

        was_enabled = bool(getattr(tutorial, "enabled", False))
        prev_snap = tutorial.get_status_snapshot() if hasattr(tutorial, "get_status_snapshot") else {}
        tutorial.enable(reset=bool(reset), mode=mode)
        self._sync_tutorial_completion_flags()

        if self._norm_test_mode() != "movement" and str(mode).lower() == "main":
            self._ensure_tutorial_quest_started()

        new_snap = tutorial.get_status_snapshot() if hasattr(tutorial, "get_status_snapshot") else {}
        started_now = (not was_enabled) or bool(reset) or (not prev_snap.get("enabled", False))
        if started_now:
            self._emit_cutscene_event(
                "tutorial_started",
                {"mode": str(mode), "source": str(source or "runtime")},
            )
        logger.info(
            f"[Tutorial] Flow mode={mode} reset={bool(reset)} source={source} "
            f"progress={new_snap.get('required_done', 0)}/{new_snap.get('required_total', 0)}"
        )

    def _load_opening_memory_package(self):
        package = getattr(self, "_opening_memory_pkg", None)
        if isinstance(package, dict) and package:
            return package
        dm = getattr(self, "data_mgr", None)
        if not dm or not hasattr(dm, "_load_file"):
            return {}
        try:
            package = dm._load_file("story/opening_memory_package.json")
        except Exception:
            package = {}
        if isinstance(package, dict):
            self._opening_memory_pkg = dict(package)
            return self._opening_memory_pkg
        return {}

    def _normalize_opening_banner(self, row, index):
        if not isinstance(row, dict):
            return None
        entry_id = str(row.get("id", f"opening_{index + 1}") or f"opening_{index + 1}").strip().lower()
        if not entry_id:
            return None
        try:
            delay = max(0.0, float(row.get("delay", 0.0) or 0.0))
        except Exception:
            delay = 0.0
        try:
            duration = max(1.25, float(row.get("duration", 4.5) or 4.5))
        except Exception:
            duration = 4.5
        keys = row.get("keys", [])
        if not isinstance(keys, list):
            keys = []
        return {
            "id": entry_id,
            "delay": delay,
            "duration": duration,
            "header_key": str(row.get("header_key", "") or "").strip(),
            "header_default": str(row.get("header_default", "Field Notes") or "Field Notes"),
            "title_key": str(row.get("title_key", "") or "").strip(),
            "title_default": str(row.get("title_default", entry_id.replace("_", " ").title()) or ""),
            "text_key": str(row.get("text_key", "") or "").strip(),
            "text_default": str(row.get("text_default", "") or "").strip(),
            "keys": [str(token or "").strip().upper() for token in keys if str(token or "").strip()],
            "index": int(index),
        }

    def _seed_opening_codex(self, package):
        if not isinstance(package, dict):
            return
        seed = package.get("codex_seed", {})
        if not isinstance(seed, dict):
            return
        for section, rows in seed.items():
            section_key = str(section or "").strip().lower()
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                token = str(row.get("id", "") or "").strip()
                title = str(row.get("title", token) or token).strip()
                details = str(row.get("details", "") or "").strip()
                self._codex_mark(section_key, token or title, title, details)

    def _apply_opening_memory_environment(self, package):
        sky = getattr(self, "sky_mgr", None)
        if not sky:
            return
        env = package.get("opening_environment", {}) if isinstance(package, dict) else {}
        if not isinstance(env, dict):
            env = {}
        time_key = str(env.get("time_preset", "morning") or "morning").strip().lower()
        weather_key = str(env.get("weather_preset", "clear") or "clear").strip().lower()
        try:
            sky.set_time_preset(time_key)
        except Exception as exc:
            logger.debug(f"[OpeningMemory] Failed to apply time preset '{time_key}': {exc}")
        try:
            sky.set_weather_preset(weather_key)
        except Exception as exc:
            logger.debug(f"[OpeningMemory] Failed to apply weather preset '{weather_key}': {exc}")

    def _resolve_dialog_location(self, location_id="", location_name="", position=None, z_offset=2.2):
        parsed_pos = None
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            try:
                px = float(position[0])
                py = float(position[1])
                pz = float(position[2]) if len(position) >= 3 else 0.0
                parsed_pos = Vec3(px, py, pz)
            except Exception:
                parsed_pos = None
        elif isinstance(position, str):
            parts = [str(p or "").strip() for p in position.split(",")]
            if len(parts) in {2, 3}:
                try:
                    px = float(parts[0])
                    py = float(parts[1])
                    pz = float(parts[2]) if len(parts) == 3 else 0.0
                    parsed_pos = Vec3(px, py, pz)
                except Exception:
                    parsed_pos = None

        world = getattr(self, "world", None)
        layout = getattr(world, "layout", {}) if world else {}
        zones = layout.get("zones", []) if isinstance(layout, dict) else []
        location_rows = []
        if isinstance(zones, list):
            for row in zones:
                if not isinstance(row, dict):
                    continue
                center = row.get("center", [])
                if not (isinstance(center, list) and len(center) >= 3):
                    continue
                try:
                    cx = float(center[0]); cy = float(center[1]); cz = float(center[2])
                except Exception:
                    continue
                location_rows.append(
                    {
                        "id": str(row.get("id", "") or "").strip().lower(),
                        "name": str(row.get("name", "") or "").strip(),
                        "pos": Vec3(cx, cy, cz),
                    }
                )

        if world and isinstance(getattr(world, "locations", None), list):
            for row in world.locations:
                if not isinstance(row, dict):
                    continue
                pos = row.get("pos", [])
                if not (isinstance(pos, list) and len(pos) >= 3):
                    continue
                try:
                    cx = float(pos[0]); cy = float(pos[1]); cz = float(pos[2])
                except Exception:
                    continue
                location_rows.append(
                    {
                        "id": str(row.get("id", "") or "").strip().lower(),
                        "name": str(row.get("name", "") or "").strip(),
                        "pos": Vec3(cx, cy, cz),
                    }
                )

        resolved_name = ""
        resolved_pos = parsed_pos
        target_id = str(location_id or "").strip().lower()
        target_name = str(location_name or "").strip().lower()
        if resolved_pos is None and (target_id or target_name):
            for row in location_rows:
                row_id = str(row.get("id", "")).strip().lower()
                row_name = str(row.get("name", "")).strip().lower()
                if target_id and row_id and row_id == target_id:
                    resolved_name = str(row.get("name", "") or "")
                    resolved_pos = Vec3(row["pos"])
                    break
                if target_name and row_name and row_name == target_name:
                    resolved_name = str(row.get("name", "") or "")
                    resolved_pos = Vec3(row["pos"])
                    break
            if resolved_pos is None and target_name:
                for row in location_rows:
                    row_name = str(row.get("name", "")).strip().lower()
                    if target_name in row_name:
                        resolved_name = str(row.get("name", "") or "")
                        resolved_pos = Vec3(row["pos"])
                        break

        if resolved_pos is not None and world and hasattr(world, "_th"):
            try:
                resolved_pos.z = float(world._th(resolved_pos.x, resolved_pos.y)) + float(z_offset or 0.0)
            except Exception:
                pass
        return resolved_pos, resolved_name

    def apply_dialog_directives(self, node_directives=None, text_tags=None, node=None):
        node_directives = node_directives if isinstance(node_directives, dict) else {}
        text_tags = text_tags if isinstance(text_tags, dict) else {}
        del node

        location_id = str(node_directives.get("location_id", text_tags.get("location", "")) or "").strip()
        location_name = str(node_directives.get("location_name", text_tags.get("location_name", "")) or "").strip()
        explicit_position = node_directives.get("position")
        try:
            z_offset = float(node_directives.get("z_offset", 2.2) or 2.2)
        except Exception:
            z_offset = 2.2

        resolved_pos, resolved_name = self._resolve_dialog_location(
            location_id=location_id,
            location_name=location_name,
            position=explicit_position,
            z_offset=z_offset,
        )
        if resolved_pos is not None:
            self._teleport_player_to(resolved_pos)
            world = getattr(self, "world", None)
            if world:
                active_name = str(node_directives.get("active_location", resolved_name) or resolved_name).strip()
                if active_name:
                    world.active_location = active_name

        sky = getattr(self, "sky_mgr", None)
        time_key = str(node_directives.get("time_preset", text_tags.get("time", "")) or "").strip().lower()
        weather_key = str(node_directives.get("weather_preset", text_tags.get("weather", "")) or "").strip().lower()
        if sky and time_key:
            try:
                sky.set_time_preset(time_key)
            except Exception as exc:
                logger.debug(f"[DialogDirectives] time preset '{time_key}' failed: {exc}")
        if sky and weather_key:
            try:
                sky.set_weather_preset(weather_key)
            except Exception as exc:
                logger.debug(f"[DialogDirectives] weather preset '{weather_key}' failed: {exc}")

        emit_event = str(node_directives.get("emit_event", text_tags.get("event", "")) or "").strip()
        if emit_event:
            payload = node_directives.get("event_payload", {})
            if not isinstance(payload, dict):
                payload = {}
            self._emit_cutscene_event(emit_event, payload)

        camera_shot = node_directives.get("camera_shot")
        if isinstance(camera_shot, dict):
            try:
                duration = float(camera_shot.get("duration", 0.85) or 0.85)
            except Exception:
                duration = 0.85
            try:
                side = float(camera_shot.get("side", 1.4) or 1.4)
            except Exception:
                side = 1.4
            try:
                yaw_bias = float(camera_shot.get("yaw_bias_deg", 6.0) or 6.0)
            except Exception:
                yaw_bias = 6.0
            try:
                priority = int(camera_shot.get("priority", 64) or 64)
            except Exception:
                priority = 64
            self._play_camera_shot(
                name=str(camera_shot.get("name", "dialog_directive_shot") or "dialog_directive_shot"),
                duration=duration,
                profile=str(camera_shot.get("profile", "cinematic") or "cinematic"),
                side=side,
                yaw_bias_deg=yaw_bias,
                priority=priority,
                owner="dialogue_directive",
            )

        unlocks = node_directives.get("codex_unlocks", [])
        if isinstance(unlocks, list):
            for row in unlocks:
                if not isinstance(row, dict):
                    continue
                section = str(row.get("section", "") or "").strip().lower()
                token = str(row.get("id", "") or "").strip()
                title = str(row.get("title", token) or token).strip()
                details = str(row.get("details", "") or "").strip()
                if section and token:
                    self._codex_mark(section, token, title, details)

        audio_dir = getattr(self, "audio_director", None) or getattr(self, "audio", None)
        if audio_dir:
            emotion = str(node_directives.get("emotion", text_tags.get("emotion", "")) or "").strip()
            if emotion and hasattr(audio_dir, "set_voice_emotion"):
                try:
                    emotion_intensity = float(
                        node_directives.get("emotion_intensity", text_tags.get("emotion_intensity", 1.0)) or 1.0
                    )
                except Exception:
                    emotion_intensity = 1.0
                try:
                    audio_dir.set_voice_emotion(emotion, intensity=emotion_intensity)
                except Exception as exc:
                    logger.debug(f"[DialogDirectives] emotion '{emotion}' failed: {exc}")

            corruption_raw = node_directives.get("corruption", text_tags.get("corruption", None))
            if corruption_raw not in (None, "") and hasattr(audio_dir, "set_world_corruption"):
                try:
                    corruption_value = float(corruption_raw)
                except Exception:
                    corruption_value = None
                if corruption_value is not None:
                    immediate = bool(node_directives.get("corruption_immediate", False))
                    try:
                        audio_dir.set_world_corruption(corruption_value, immediate=immediate)
                    except Exception as exc:
                        logger.debug(f"[DialogDirectives] corruption '{corruption_value}' failed: {exc}")

    def _start_opening_memory_sequence(self):
        if self._norm_test_mode():
            return False
        if bool(getattr(self, "_opening_memory_started", False)):
            return False

        package = self._load_opening_memory_package()
        if not isinstance(package, dict) or not package:
            return False
        if getattr(self, "asset_bundle_mgr", None):
            try:
                self.asset_bundle_mgr.activate_profile("opening_memory")
            except Exception as exc:
                logger.debug(f"[AssetBundle] opening_memory activation skipped: {exc}")

        self._opening_memory_started = True
        self._opening_memory_finished = False
        self._tutorial_flow_blocked_by_opening = True
        self._apply_opening_memory_environment(package)

        phase = str(package.get("phase", "morning_argument_with_father") or "morning_argument_with_father").strip()
        lead = str(package.get("lead", "sherward") or "sherward").strip()
        self._emit_cutscene_event(
            "opening_memory_started",
            {
                "context": "new_game",
                "lead": lead,
                "phase": phase,
            },
        )
        self._seed_opening_codex(package)
        self._codex_mark(
            "events",
            "opening_memory_sherward_morning",
            "Opening memory: Sherward morning argument",
            "Initial pre-game recollection before full player control.",
        )

        dialogue_asset = str(package.get("dialogue_asset", "") or "").strip().replace("\\", "/")
        dialogue_data = {}
        dm = getattr(self, "data_mgr", None)
        if dialogue_asset and dm and hasattr(dm, "_load_file"):
            try:
                dialogue_data = dm._load_file(dialogue_asset)
            except Exception:
                dialogue_data = {}

        dialog_mgr = getattr(self, "dialog_cinematic", None)
        if dialog_mgr and isinstance(dialogue_data, dict) and isinstance(dialogue_data.get("dialogue_tree"), dict):
            try:
                if dialog_mgr.start_dialogue(
                    npc_id=str(package.get("id", "opening_memory") or "opening_memory"),
                    dialogue_data=dialogue_data,
                    npc_actor=None,
                    on_end=self._on_opening_memory_finished,
                ):
                    return True
            except Exception as exc:
                logger.warning(f"[OpeningMemory] Failed to start cinematic dialogue: {exc}")

        # Fallback path if dialogue failed to start: keep tutorial gate, run banners directly.
        self._on_opening_memory_finished()
        return bool(getattr(self, "_opening_banner_active", False))

    def _on_opening_memory_finished(self):
        if bool(getattr(self, "_opening_memory_finished", False)):
            return
        self._opening_memory_finished = True
        self._emit_cutscene_event(
            "opening_memory_finished",
            {
                "context": "new_game",
                "lead": "sherward",
            },
        )

        package = self._load_opening_memory_package()
        banners = package.get("tutorial_banners", []) if isinstance(package, dict) else []
        cleaned = []
        if isinstance(banners, list):
            for idx, row in enumerate(banners):
                normalized = self._normalize_opening_banner(row, idx)
                if normalized:
                    cleaned.append(normalized)
        self._opening_banner_queue = cleaned
        self._opening_banner_cursor = 0
        self._opening_banner_current = None
        self._opening_banner_elapsed = 0.0
        self._opening_banner_time_left = 0.0
        if cleaned:
            self._opening_banner_delay_left = float(cleaned[0].get("delay", 0.0) or 0.0)
            self._opening_banner_active = True
            self._emit_cutscene_event(
                "opening_tutorial_banners_started",
                {"count": len(cleaned)},
            )
            return
        self._opening_banner_delay_left = 0.0
        self._opening_banner_active = False
        self._finalize_opening_tutorial_gate()

    def _finalize_opening_tutorial_gate(self):
        if not bool(getattr(self, "_tutorial_flow_blocked_by_opening", False)):
            return
        self._tutorial_flow_blocked_by_opening = False
        self._setup_main_game_tutorial()

    def _compose_opening_banner_state(self):
        row = getattr(self, "_opening_banner_current", None)
        if not isinstance(row, dict):
            return None
        t = getattr(getattr(self, "data_mgr", None), "t", None)
        if not callable(t):
            return None
        header = t(row.get("header_key", ""), row.get("header_default", "Field Notes"))
        title = t(row.get("title_key", ""), row.get("title_default", "Guidance"))
        text = t(row.get("text_key", ""), row.get("text_default", ""))
        total = max(1, len(getattr(self, "_opening_banner_queue", [])))
        idx = int(row.get("index", 0)) + 1
        progress_label = f"{idx}/{total}"
        progress_ratio = max(0.0, min(1.0, float(idx - 1) / float(total)))
        return {
            "visible": True,
            "phase": "opening",
            "display_mode": "banner",
            "header": str(header or "Field Notes"),
            "title": str(title or "Guidance"),
            "text": str(text or ""),
            "progress_label": progress_label,
            "progress_ratio": progress_ratio,
            "keys": list(row.get("keys", [])),
            "flash": bool(self._opening_banner_elapsed <= 0.25),
            "step_id": str(row.get("id", "")),
        }

    def _update_opening_banner_queue(self, dt):
        if not bool(getattr(self, "_opening_banner_active", False)):
            return None

        queue = getattr(self, "_opening_banner_queue", [])
        if not isinstance(queue, list) or not queue:
            self._opening_banner_active = False
            self._finalize_opening_tutorial_gate()
            return None

        if not isinstance(getattr(self, "_opening_banner_current", None), dict):
            cursor = int(getattr(self, "_opening_banner_cursor", 0))
            if cursor >= len(queue):
                self._opening_banner_active = False
                self._emit_cutscene_event("opening_tutorial_banners_completed", {"count": len(queue)})
                self._finalize_opening_tutorial_gate()
                return None
            delay_left = max(0.0, float(getattr(self, "_opening_banner_delay_left", 0.0) or 0.0) - max(0.0, float(dt or 0.0)))
            self._opening_banner_delay_left = delay_left
            if delay_left > 0.0:
                return None
            self._opening_banner_current = dict(queue[cursor])
            self._opening_banner_cursor = cursor + 1
            self._opening_banner_elapsed = 0.0
            self._opening_banner_time_left = max(1.0, float(self._opening_banner_current.get("duration", 4.5) or 4.5))
            self._emit_cutscene_event(
                "opening_tutorial_banner_shown",
                {"id": self._opening_banner_current.get("id", ""), "index": self._opening_banner_cursor},
            )

        self._opening_banner_elapsed += max(0.0, float(dt or 0.0))
        self._opening_banner_time_left -= max(0.0, float(dt or 0.0))
        payload = self._compose_opening_banner_state()

        if self._opening_banner_time_left <= 0.0:
            self._opening_banner_current = None
            cursor = int(getattr(self, "_opening_banner_cursor", 0))
            if cursor < len(queue):
                next_row = queue[cursor]
                self._opening_banner_delay_left = max(0.0, float(next_row.get("delay", 0.0) or 0.0))
            else:
                self._opening_banner_delay_left = 0.0
                self._opening_banner_active = False
                self._emit_cutscene_event("opening_tutorial_banners_completed", {"count": len(queue)})
                self._finalize_opening_tutorial_gate()
        return payload

    def _norm_test_mode(self):
        return str(getattr(self, "_test_profile", "") or "").strip().lower()

    def _video_bot_input_locked(self):
        return bool(
            getattr(self, "_video_bot_enabled", False)
            and getattr(self, "_video_bot_capture_input", False)
        )

    def _apply_test_profile_visuals(self, profile):
        sky = getattr(self, "sky_mgr", None)
        if not sky:
            return
        presets = {
            "dragon": ("dusk", "stormy"),
            "music": ("afternoon", "partly_cloudy"),
            "journal": ("noon", "clear"),
            "mounts": ("afternoon", "clear"),
            "skills": ("dusk", "overcast"),
            # Keep runtime video-test profiles bright for review visibility.
            "movement": ("noon", "clear"),
            "parkour": ("noon", "clear"),
            "stealth_climb": ("afternoon", "overcast"),
            "flight": ("noon", "clear"),
            "swim": ("noon", "clear"),
            "world_art": ("noon", "clear"),
        }
        time_key, weather_key = presets.get(profile, ("noon", "clear"))
        try:
            instant = bool(getattr(self, "_video_bot_visibility_boost", False))
            sky.set_time_preset(time_key, instant=instant)
            sky.set_weather_preset(weather_key, instant=instant)
        except TypeError:
            try:
                sky.set_time_preset(time_key)
                sky.set_weather_preset(weather_key)
            except Exception as exc:
                logger.debug(f"[TestProfile] Sky preset failed ({profile}): {exc}")
        except Exception as exc:
            logger.debug(f"[TestProfile] Sky preset failed ({profile}): {exc}")
            return
        if instant and hasattr(sky, "_apply_now"):
            try:
                sky._apply_now(force=True)
            except Exception:
                pass

    def _apply_test_profile(self):
        profile = str(self._test_profile or "").strip().lower()
        scenario = self._resolve_test_scenario(getattr(self, "_test_scenario_raw", ""))
        if scenario and not profile:
            profile = str(scenario.get("profile", "") or "").strip().lower()

        if not profile and not self._test_location_raw and not scenario:
            return

        default_location = {
            "dragon": "dragon_arena",
            "music": "docks",
            "journal": "town",
            "mounts": "9,6,0",
            "skills": "0,0,0",
            "movement": "training",
            "parkour": "parkour",
            "stealth_climb": "stealth_climb",
            "flight": "flight",
        }.get(profile, "")
        scenario_location = ""
        if isinstance(scenario, dict):
            scenario_location = str(scenario.get("location", "") or "").strip()
            if scenario_location:
                default_location = scenario_location

        desired_token = self._test_location_raw or default_location
        if (
            scenario_location
            and bool(getattr(self, "_video_bot_enabled", False))
            and not str(getattr(self, "_test_location_raw", "") or "").strip()
        ):
            # Video scenarios should be deterministic to the scenario catalog
            # even when launchers provide a generic fallback location.
            desired_token = scenario_location

        desired = self._resolve_test_location(desired_token)
        if desired is not None:
            self._teleport_player_to(desired)

        resolved_world_location = self._resolve_test_world_location_name(desired_token)
        if self.world and resolved_world_location:
            self.world.active_location = resolved_world_location

        self._apply_test_profile_visuals(profile)

        if self.movement_tutorial:
            self.movement_tutorial.disable()
            self.movement_tutorial.set_mode("main", reset=False)

        if profile == "dragon":
            primary = None
            if self.boss_manager and hasattr(self.boss_manager, "get_primary"):
                primary = self.boss_manager.get_primary("golem")
            if primary and getattr(primary, "root", None) and self.player and self.player.actor:
                p = self.player.actor.getPos(self.render)
                primary.root.setPos(p.x + 8.0, p.y + 18.0, p.z + 2.0)
            elif self.dragon_boss and self.dragon_boss.root and self.player and self.player.actor:
                p = self.player.actor.getPos(self.render)
                self.dragon_boss.root.setPos(p.x + 8.0, p.y + 18.0, p.z + 2.0)
            if self.world:
                self.world.active_location = "Sharuan Castle"
        elif profile == "ultimate_sandbox":
            # Spawn a squad of wolves for combat testing
            if self.world:
                self.world.active_location = "ultimate_sandbox"
            
            p = self.player.actor.getPos(self.render) if self.player and self.player.actor else Vec3(150, 150, 5)
            
            # 1. Standard Enemies
            if self.npc_mgr:
                self.npc_mgr.spawn_from_data({
                    "sandbox_wolf_1": {"name": "Test Wolf 1", "role": "enemy", "pos": [165.0, 165.0, 5.0], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.2}},
                    "sandbox_wolf_2": {"name": "Test Wolf 2", "role": "enemy", "pos": [135.0, 165.0, 5.0], "appearance": {"model": "assets/models/enemies/wolf.glb", "scale": 1.2}},
                    "sandbox_sentinel": {"name": "Test Sentinel", "role": "guard", "pos": [150.0, 135.0, 5.0], "appearance": {"species": "dracolite", "armor_type": "plate", "scale": 1.1}}
                })
            
            # 2. Bosses
            # Spawn Golem at marker location
            if self.boss_manager:
                golem = self.boss_manager.get_primary("golem")
                if golem and hasattr(golem, "root"):
                    golem.root.setPos(110.0, 190.0, 5.5)
            
            # Spawn Dragon
            if hasattr(self, "dragon_boss") and self.dragon_boss and hasattr(self.dragon_boss, "root"):
                self.dragon_boss.root.setPos(190.0, 190.0, 6.0)
        elif profile == "music":
            if self.world:
                self.world.active_location = "Southern Docks"
        elif profile == "journal":
            self._activate_journal_test_data()
            self.aspect2d.show()
            self.inventory_ui.show()
            self.inventory_ui._switch_tab("journal")
            self.state_mgr.set_state(self.GameState.INVENTORY)
        elif profile == "movement":
            if self.world and not resolved_world_location:
                self.world.active_location = "Training Grounds"
            if self.movement_tutorial:
                self._start_tutorial_flow(reset=True, mode="demo", source="test_profile")
        elif profile == "parkour":
            if self.world:
                self.world.active_location = "Forest Parkour Grounds"
        elif profile == "stealth_climb":
            if self.world:
                self.world.active_location = "Stealth Climb Grounds"
        elif profile == "flight":
            if self.world:
                self.world.active_location = "Coastal Flight Grounds"
            if self.player and self.player.actor:
                pos = self.player.actor.getPos(self.render)
                flight_pos = Vec3(pos.x, pos.y, pos.z + 9.0)
                self.player.actor.setPos(flight_pos)
                if HAS_CORE and self.char_state:
                    try:
                        self.char_state.position = gc.Vec3(flight_pos.x, flight_pos.y, flight_pos.z)
                        self.char_state.velocity = gc.Vec3(0.0, 0.0, 0.0)
                    except Exception:
                        pass
                # Keep test launcher deterministic: flight profile starts already airborne.
                self.player._is_flying = True
        elif profile == "mounts":
            if self.world:
                self.world.active_location = "Port Caravan Trail"
        elif profile == "skills":
            if self.world:
                self.world.active_location = "Town Hall"
            skill_mgr = getattr(self, "skill_tree_mgr", None)
            if skill_mgr and hasattr(skill_mgr, "get_points") and hasattr(skill_mgr, "grant_points"):
                try:
                    if int(skill_mgr.get_points()) < 4:
                        skill_mgr.grant_points(4)
                except Exception:
                    pass

        if isinstance(scenario, dict) and self.world:
            world_loc = str(scenario.get("world_location", "") or "").strip()
            if world_loc:
                self.world.active_location = world_loc
        scenario_id = str(scenario.get("id", "")).strip() if isinstance(scenario, dict) else ""

        logger.info(
            f"[TestProfile] Applied profile='{profile or 'custom'}' "
            f"location='{desired_token or '-'}' "
            f"scenario='{scenario_id or '-'}'"
        )

    def _setup_video_bot(self):
        self._video_bot_plan_name = resolve_video_bot_plan_name(self._video_bot_plan_raw)
        raw_plan_token = (
            str(getattr(self, "_video_bot_plan_raw", "") or "")
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        self._video_bot_elapsed = 0.0
        self._video_bot_event_idx = 0
        self._video_bot_hold_actions = {}
        self._video_bot_forced_flags = {}
        self._video_bot_warned_actions = set()
        self._video_bot_done = False
        self._video_bot_bindings = {}
        self._video_bot_cursor_pos = (0.0, 0.0)
        self._video_bot_cursor_target = (0.0, 0.0)
        self._video_bot_cursor_visible = False
        self._video_bot_visibility_refresh_at = 0.0
        self._video_bot_cursor_visible_until = 0.0
        self._video_bot_cursor_click_until = 0.0
        self._video_bot_started = False
        self._video_bot_start_ready_at = 0.0
        self._video_bot_last_real_time = 0.0
        self._video_bot_cycle_count = 0
        player = getattr(self, "player", None)
        if player and isinstance(getattr(player, "_keys", None), dict):
            for key in list(player._keys.keys()):
                player._keys[key] = False
        if player and isinstance(getattr(player, "_consumed", None), dict):
            for key in list(player._consumed.keys()):
                player._consumed[key] = False
        if not self._video_bot_enabled:
            self._video_bot_plan = []
            return
        if self._video_bot_plan_name == "ground" and raw_plan_token not in {
            "",
            "ground",
            "movement",
            "mechanics",
            "base",
            "default",
        }:
            logger.warning(
                f"[VideoBot] Unknown plan token '{self._video_bot_plan_raw}', falling back to 'ground'."
            )
        try:
            self._video_bot_plan = build_video_bot_events(self._video_bot_plan_name)
        except Exception as exc:
            self._video_bot_plan = []
            logger.warning(f"[VideoBot] Failed to build plan '{self._video_bot_plan_name}': {exc}")
            return
        logger.info(
            f"[VideoBot] Enabled plan='{self._video_bot_plan_name}' events={len(self._video_bot_plan)}"
        )

    def _video_bot_refresh_bindings(self):
        bindings = {}
        data_mgr = getattr(self, "data_mgr", None)
        if data_mgr and isinstance(getattr(data_mgr, "controls", {}), dict):
            source = data_mgr.controls.get("bindings", {})
            if isinstance(source, dict):
                for action, token in source.items():
                    key = str(action or "").strip().lower()
                    value = str(token or "").strip().lower()
                    if key:
                        bindings[key] = value
        self._video_bot_bindings = bindings

    def _video_bot_resolve_key(self, action):
        return resolve_action_binding(action, getattr(self, "_video_bot_bindings", {}))

    def _video_bot_set_action(self, action, pressed):
        player = getattr(self, "player", None)
        if not player:
            return False
        action_key = str(action or "").strip().lower()
        key = self._video_bot_resolve_key(action_key)
        if not key:
            if action_key and action_key not in self._video_bot_warned_actions:
                logger.debug(f"[VideoBot] Missing binding for action '{action_key}', skipping.")
                self._video_bot_warned_actions.add(action_key)
            return False
        try:
            if bool(pressed):
                player._key_down(key, synthetic=True)
            else:
                player._key_up(key, synthetic=True)
            return True
        except Exception:
            return False

    def _video_bot_apply_flag(self, flag, value):
        token = str(flag or "").strip().lower()
        state = bool(value)
        if token in {"is_flying", "flying"}:
            if getattr(self, "player", None):
                self.player._is_flying = state
                if not state:
                    self._video_bot_set_action("flight_up", False)
                    self._video_bot_set_action("flight_down", False)
        elif token in {"in_water", "water"}:
            if getattr(self, "player", None):
                try:
                    self.player._py_in_water = state
                except Exception:
                    pass
            if HAS_CORE and getattr(self, "char_state", None) and hasattr(self.char_state, "in_water"):
                try:
                    self.char_state.in_water = state
                except Exception:
                    pass

    def _video_bot_teleport_training_pool(self):
        if not getattr(self, "player", None) or not getattr(self.player, "actor", None):
            return
        pool_x = 4.0
        pool_y = 36.0
        pool_z = 0.6
        world = getattr(self, "world", None)
        if world and hasattr(world, "_th"):
            try:
                pool_z = float(world._th(pool_x, pool_y)) - 0.95
            except Exception:
                pass
        self.player.actor.setPos(pool_x, pool_y, pool_z)
        try:
            self.player._py_in_water = True
        except Exception:
            pass
        if HAS_CORE and getattr(self, "char_state", None):
            try:
                self.char_state.position = gc.Vec3(pool_x, pool_y, pool_z)
                self.char_state.velocity = gc.Vec3(0.0, 0.0, 0.0)
                if hasattr(self.char_state, "in_water"):
                    self.char_state.in_water = True
            except Exception:
                pass
        self.camera.setPos(pool_x, pool_y - 18.0, pool_z + 10.0)
        self.camera.lookAt(self.player.actor)
        if world:
            world.active_location = "Training Grounds"

    def _video_bot_default_cursor_for_ui(self, token, event_row):
        if token == "inventory_tab":
            tab = str(event_row.get("tab", "") or "").strip().lower()
            return {
                "inventory": (-0.58, 0.46),
                "map": (-0.20, 0.46),
                "skills": (0.20, 0.46),
                "journal": (0.58, 0.46),
            }.get(tab, (0.0, 0.46))
        return {
            "open_inventory": (0.0, 0.25),
            "close_inventory": (0.0, -0.66),
            "open_pause": (0.0, 0.10),
            "close_pause": (0.0, 0.12),
            "resume": (0.0, 0.12),
            "pause_open_settings": (0.0, -0.30),
            "pause_toggle_quality": (0.18, 0.08),
            "pause_toggle_vsync": (0.18, -0.02),
            "pause_close_settings": (0.0, -0.56),
            "pause_open_load": (0.0, -0.16),
            "pause_close_load": (0.0, -0.56),
            "pause_nav_next": (0.0, -0.02),
            "pause_nav_prev": (0.0, -0.16),
            "pause_nav_activate": (0.0, 0.12),
        }.get(token)

    def _video_bot_set_virtual_cursor(self, cursor_row, fallback_xy=None):
        xy = None
        click = False
        if isinstance(cursor_row, dict):
            try:
                cx = float(cursor_row.get("x", 0.0) or 0.0)
                cy = float(cursor_row.get("y", 0.0) or 0.0)
                xy = (cx, cy)
            except Exception:
                xy = None
            click = bool(cursor_row.get("click", False))
        elif isinstance(fallback_xy, (list, tuple)) and len(fallback_xy) >= 2:
            try:
                xy = (float(fallback_xy[0]), float(fallback_xy[1]))
            except Exception:
                xy = None
            click = True
        if xy is None:
            return
        tx = max(-0.98, min(0.98, float(xy[0])))
        ty = max(-0.98, min(0.98, float(xy[1])))
        if not bool(getattr(self, "_video_bot_cursor_visible", False)):
            self._video_bot_cursor_pos = (tx, ty)
        self._video_bot_cursor_target = (tx, ty)
        self._video_bot_cursor_visible = True
        now = float(getattr(self, "_video_bot_elapsed", 0.0) or 0.0)
        self._video_bot_cursor_visible_until = now + (0.90 if click else 0.55)
        if click:
            self._video_bot_cursor_click_until = now + 0.26

    def _video_bot_update_virtual_cursor(self, dt):
        if not bool(getattr(self, "_video_bot_cursor_visible", False)):
            return
        state = getattr(getattr(self, "state_mgr", None), "current_state", None)
        if state == getattr(self.GameState, "PLAYING", None):
            self._video_bot_cursor_visible = False
            return
        cx, cy = getattr(self, "_video_bot_cursor_pos", (0.0, 0.0))
        tx, ty = getattr(self, "_video_bot_cursor_target", (0.0, 0.0))
        gain = max(0.0, min(1.0, float(dt or 0.0) * 10.0))
        nx = cx + (tx - cx) * gain
        ny = cy + (ty - cy) * gain
        self._video_bot_cursor_pos = (nx, ny)

    def _video_bot_enforce_visibility(self, force=False):
        if not bool(getattr(self, "_video_bot_visibility_boost", False)):
            return
        now = float(globalClock.getRealTime() or globalClock.getFrameTime() or 0.0)
        next_refresh = float(getattr(self, "_video_bot_visibility_refresh_at", 0.0) or 0.0)
        if (not bool(force)) and now < next_refresh:
            return
        self._video_bot_visibility_refresh_at = now + 0.90
        try:
            self.render.clearFog()
        except Exception:
            pass
        try:
            self.render.setColorScale(1.0, 1.0, 1.0, 1.0)
        except Exception:
            pass
        sky = getattr(self, "sky_mgr", None)
        if not sky:
            return
        try:
            sky.min_visibility = max(0.72, float(getattr(sky, "min_visibility", 0.36) or 0.36))
            sky.min_ambient_light = max(0.42, float(getattr(sky, "min_ambient_light", 0.22) or 0.22))
            sky.min_sun_light = max(0.34, float(getattr(sky, "min_sun_light", 0.14) or 0.14))
        except Exception:
            pass
        try:
            if hasattr(sky, "_apply_now"):
                sky._apply_now(force=True)
        except Exception:
            pass

    def _video_bot_apply_environment_event(self, event_row):
        if not isinstance(event_row, dict):
            return
        token = str(event_row.get("type", "") or "").strip().lower()
        if token == "set_weather":
            preset = str(event_row.get("preset", "") or "").strip().lower()
            sky = getattr(self, "sky_mgr", None)
            if sky and preset and hasattr(sky, "set_weather_preset"):
                try:
                    sky.set_weather_preset(preset, instant=True)
                except TypeError:
                    try:
                        sky.set_weather_preset(preset)
                    except Exception:
                        pass
                except Exception:
                    pass
            return
        if token == "set_time":
            preset = str(event_row.get("preset", "") or "").strip().lower()
            sky = getattr(self, "sky_mgr", None)
            if sky and preset and hasattr(sky, "set_time_preset"):
                try:
                    sky.set_time_preset(preset, instant=True)
                except TypeError:
                    try:
                        sky.set_time_preset(preset)
                    except Exception:
                        pass
                except Exception:
                    pass
            return
        if token == "camera_impact":
            director = getattr(self, "camera_director", None)
            if director and hasattr(director, "emit_impact"):
                kind = str(event_row.get("kind", "heavy") or "heavy").strip().lower()
                intensity = float(event_row.get("intensity", 1.0) or 1.0)
                direction = float(event_row.get("direction_deg", 0.0) or 0.0)
                try:
                    director.emit_impact(kind=kind, intensity=intensity, direction_deg=direction)
                except Exception:
                    pass

    def _video_bot_apply_equip_event(self, event_row):
        if not isinstance(event_row, dict):
            return False
        player = getattr(self, "player", None)
        if not player:
            return False
        item_id = str(event_row.get("item_id", "") or "").strip()
        if item_id and hasattr(player, "equip_item"):
            try:
                ok, _reason = player.equip_item(item_id)
                return bool(ok)
            except Exception:
                return False
        slot = str(event_row.get("slot", "") or "").strip()
        if slot and hasattr(player, "unequip_slot"):
            try:
                return bool(player.unequip_slot(slot))
            except Exception:
                return False
        return False

    def _video_bot_apply_quest_action(self, action, event_row):
        del event_row
        token = str(action or "").strip().lower()
        if not token:
            return False
        if token in {"bootstrap_all", "start_all", "start_quests"}:
            try:
                self._activate_journal_test_data()
                return True
            except Exception:
                return False
        if token in {"start_tutorial", "tutorial_start"}:
            try:
                return bool(self._ensure_tutorial_quest_started())
            except Exception:
                return False
        if token in {"complete_tutorial", "tutorial_complete"}:
            try:
                return bool(self._complete_tutorial_quest())
            except Exception:
                return False
        return False

    def _video_bot_apply_portal_jump(self, event_row):
        if not isinstance(event_row, dict):
            return False
        target = str(event_row.get("target", "") or "").strip().lower()
        if not target:
            return False
        kind = str(event_row.get("kind", "arcane") or "arcane").strip().lower()
        try:
            self._emit_cutscene_event("portal_jump", {"target": target, "kind": kind})
        except Exception:
            pass

        director = getattr(self, "camera_director", None)
        if director and hasattr(director, "emit_impact"):
            try:
                director.emit_impact(kind="heavy", intensity=0.88, direction_deg=0.0)
            except Exception:
                pass

        if target == "training_pool":
            self._video_bot_teleport_training_pool()
            return True
        pos = self._resolve_test_location(target)
        if pos is None:
            return False
        self._teleport_player_to(pos)
        return True

    def _video_bot_apply_damage_player(self, event_row):
        if not isinstance(event_row, dict):
            return False
        player = getattr(self, "player", None)
        cs = getattr(self, "char_state", None)
        if cs is None and player is not None:
            cs = getattr(player, "cs", None)
        if cs is None or (not hasattr(cs, "health")):
            return False
        try:
            current_hp = float(getattr(cs, "health", 100.0) or 100.0)
        except Exception:
            current_hp = 100.0
        try:
            max_hp = float(getattr(cs, "maxHealth", current_hp) or current_hp)
        except Exception:
            max_hp = max(1.0, current_hp)
        max_hp = max(1.0, max_hp)

        try:
            amount = float(event_row.get("amount", 0.0) or 0.0)
        except Exception:
            amount = 0.0
        try:
            ratio = float(event_row.get("ratio", 0.0) or 0.0)
        except Exception:
            ratio = 0.0
        if amount <= 0.0 and ratio > 0.0:
            amount = max_hp * max(0.01, min(0.95, ratio))
        if amount <= 0.0:
            amount = max_hp * 0.14

        new_hp = max(1.0, min(max_hp, current_hp - amount))
        try:
            setattr(cs, "health", float(new_hp))
        except Exception:
            return False

        if player and hasattr(player, "_last_hp_observed"):
            try:
                player._last_hp_observed = float(current_hp)
            except Exception:
                pass

        director = getattr(self, "camera_director", None)
        if director and hasattr(director, "emit_impact"):
            try:
                director.emit_impact(kind="heavy", intensity=1.08, direction_deg=-25.0)
            except Exception:
                pass
        return True

    def _video_bot_force_enemy_aggro(self, event_row=None):
        payload = event_row if isinstance(event_row, dict) else {}
        try:
            duration = float(payload.get("duration", 8.0) or 8.0)
        except Exception:
            duration = 8.0
        duration = max(1.2, min(24.0, duration))
        teleport_to_enemy = bool(payload.get("teleport_to_enemy", True))
        try:
            teleport_max_distance = float(payload.get("teleport_max_distance", 36.0) or 36.0)
        except Exception:
            teleport_max_distance = 36.0
        teleport_max_distance = max(0.0, min(260.0, teleport_max_distance))
        now = float(globalClock.getFrameTime() or 0.0)

        player = getattr(self, "player", None)
        player_np = getattr(player, "actor", None) if player else None
        player_pos = self._node_world_pos(player_np)
        nearest_enemy_pos = None
        nearest_dist = float("inf")
        aggro_count = 0

        roster = getattr(self, "boss_manager", None)
        for unit in getattr(roster, "units", []) if roster else []:
            if hasattr(unit, "is_alive") and not bool(getattr(unit, "is_alive", True)):
                continue
            if hasattr(unit, "engaged_until"):
                try:
                    unit.engaged_until = max(float(getattr(unit, "engaged_until", 0.0) or 0.0), now + duration)
                except Exception:
                    pass
            if hasattr(unit, "_is_engaged"):
                try:
                    unit._is_engaged = True
                except Exception:
                    pass
            aggro_count += 1
            pos = self._node_world_pos(getattr(unit, "root", None))
            if pos is None:
                continue
            if player_pos is None:
                nearest_enemy_pos = pos
                continue
            try:
                dist = (pos - player_pos).length()
            except Exception:
                dist = float("inf")
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_enemy_pos = pos

        dragon = getattr(self, "dragon_boss", None)
        if dragon and bool(getattr(dragon, "is_alive", True)):
            if hasattr(dragon, "_is_engaged"):
                try:
                    dragon._is_engaged = True
                except Exception:
                    pass
            aggro_count += 1
            dpos = self._node_world_pos(getattr(dragon, "root", None))
            if dpos is not None:
                if player_pos is None:
                    nearest_enemy_pos = dpos
                else:
                    try:
                        dist = (dpos - player_pos).length()
                    except Exception:
                        dist = float("inf")
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest_enemy_pos = dpos

        can_teleport = True
        if player_pos is not None and math.isfinite(nearest_dist):
            can_teleport = nearest_dist <= teleport_max_distance

        if teleport_to_enemy and can_teleport and nearest_enemy_pos is not None and player_np:
            try:
                target = Vec3(
                    float(nearest_enemy_pos.x) - 2.6,
                    float(nearest_enemy_pos.y) - 2.2,
                    max(0.2, float(nearest_enemy_pos.z)),
                )
                self._teleport_player_to(target)
            except Exception:
                pass
        elif teleport_to_enemy and nearest_enemy_pos is not None and not can_teleport:
            logger.debug(
                f"[VideoBot] Aggro teleport skipped (distance={nearest_dist:.1f} > {teleport_max_distance:.1f})."
            )
        return aggro_count > 0

    def _video_bot_apply_ui_action(self, action, event_row):
        token = str(action or "").strip().lower()
        if not token:
            return False
        default_cursor = self._video_bot_default_cursor_for_ui(token, event_row if isinstance(event_row, dict) else {})
        cursor_row = event_row.get("cursor", {}) if isinstance(event_row, dict) else {}
        self._video_bot_set_virtual_cursor(cursor_row, fallback_xy=default_cursor)

        state = getattr(getattr(self, "state_mgr", None), "current_state", None)
        if token == "open_pause":
            if state == self.GameState.PLAYING:
                self._on_escape_pressed(from_video_bot=True)
                return True
            return False
        if token in {"close_pause", "resume"}:
            if state == self.GameState.PAUSED:
                self._on_escape_pressed(from_video_bot=True)
                return True
            return False
        if token == "open_inventory":
            if state == self.GameState.PLAYING and getattr(self, "inventory_ui", None):
                self.state_mgr.set_state(self.GameState.INVENTORY)
                self.inventory_ui.show()
                return True
            return False
        if token == "close_inventory":
            if state == self.GameState.INVENTORY and getattr(self, "inventory_ui", None):
                self.inventory_ui.hide()
                self.state_mgr.set_state(self.GameState.PLAYING)
                return True
            return False
        if token == "inventory_tab":
            tab = str(event_row.get("tab", "") or "").strip().lower()
            if tab not in {"inventory", "map", "skills", "journal"}:
                return False
            if getattr(self, "inventory_ui", None):
                if state != self.GameState.INVENTORY:
                    self.state_mgr.set_state(self.GameState.INVENTORY)
                    self.inventory_ui.show()
                self.inventory_ui._switch_tab(tab)
                return True
            return False
        if token == "pause_open_settings":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_settings"):
                pause_menu._on_settings()
                return True
            return False
        if token == "pause_close_settings":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_close_settings"):
                pause_menu._on_close_settings()
                return True
            return False
        if token == "pause_open_load":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_load_game"):
                pause_menu._on_load_game()
                return True
            return False
        if token == "pause_close_load":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_close_load_panel"):
                pause_menu._on_close_load_panel()
                return True
            return False
        if token == "pause_toggle_quality":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_toggle_quality"):
                pause_menu._on_toggle_quality()
                return True
            return False
        if token == "pause_toggle_vsync":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_toggle_vsync"):
                pause_menu._on_toggle_vsync()
                return True
            return False
        if token == "pause_nav_next":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_nav_next"):
                pause_menu._on_nav_next()
                return True
            return False
        if token == "pause_nav_prev":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_nav_prev"):
                pause_menu._on_nav_prev()
                return True
            return False
        if token == "pause_nav_activate":
            pause_menu = getattr(self, "pause_menu", None)
            if state == self.GameState.PAUSED and pause_menu and hasattr(pause_menu, "_on_nav_activate"):
                pause_menu._on_nav_activate()
                return True
            return False
        return False

    def _video_bot_release_all_actions(self):
        if not isinstance(getattr(self, "_video_bot_hold_actions", None), dict):
            self._video_bot_hold_actions = {}
            return
        for action in list(self._video_bot_hold_actions.keys()):
            self._video_bot_set_action(action, False)
        self._video_bot_hold_actions.clear()

    def _video_bot_run_event(self, event_row, now_sec):
        if not isinstance(event_row, dict):
            return
        kind = str(event_row.get("type", "") or "").strip().lower()
        if kind in {"tap", "hold"}:
            action = str(event_row.get("action", "") or "").strip().lower()
            if not action:
                return
            duration = 0.18 if kind == "tap" else 0.0
            try:
                custom_duration = float(event_row.get("duration", duration) or duration)
                duration = max(0.09, custom_duration)
            except Exception:
                duration = 0.18 if kind == "tap" else 0.32
            if self._video_bot_set_action(action, True):
                self._video_bot_hold_actions[action] = max(
                    float(self._video_bot_hold_actions.get(action, 0.0) or 0.0),
                    float(now_sec) + float(duration),
                )
            return

        if kind == "set_flag":
            flag = str(event_row.get("flag", "") or "").strip().lower()
            if not flag:
                return
            value = bool(event_row.get("value", True))
            self._video_bot_apply_flag(flag, value)
            duration = float(event_row.get("duration", 0.0) or 0.0)
            if duration > 0.0:
                self._video_bot_forced_flags[flag] = {
                    "value": value,
                    "until": float(now_sec) + float(duration),
                }
            elif flag in self._video_bot_forced_flags:
                del self._video_bot_forced_flags[flag]
            return

        if kind == "teleport":
            target = str(event_row.get("target", "") or "").strip().lower()
            moved = False
            if target == "training_pool":
                self._video_bot_teleport_training_pool()
                moved = True
            elif target:
                pos = self._resolve_test_location(target)
                if pos is not None:
                    moved = bool(self._teleport_player_to(pos))
            if moved and target.startswith("dwarven_caves"):
                # Keep cave debug shots readable and reduce camera-wall clipping.
                player = getattr(self, "player", None)
                actor = getattr(player, "actor", None) if player else None
                if actor:
                    p = actor.getPos(self.render)
                    self.camera.setPos(p.x, p.y - 11.0, p.z + 6.3)
                    self.camera.lookAt(actor)
            return

        if kind == "portal_jump":
            self._video_bot_apply_portal_jump(event_row)
            return

        if kind == "equip_item":
            self._video_bot_apply_equip_event(event_row)
            return

        if kind == "quest_action":
            self._video_bot_apply_quest_action(event_row.get("action", ""), event_row)
            return

        if kind == "damage_player":
            self._video_bot_apply_damage_player(event_row)
            return

        if kind == "force_aggro":
            self._video_bot_force_enemy_aggro(event_row)
            return

        if kind == "camera_profile":
            director = getattr(self, "camera_director", None)
            if director and hasattr(director, "set_profile"):
                profile = str(event_row.get("profile", "exploration") or "exploration").strip().lower()
                try:
                    hold_seconds = float(event_row.get("hold_seconds", 2.0) or 2.0)
                except Exception:
                    hold_seconds = 2.0
                priority = event_row.get("priority", None)
                try:
                    director.set_profile(
                        profile_name=profile,
                        hold_seconds=max(0.0, hold_seconds),
                        priority=priority,
                        owner="video_bot",
                    )
                except Exception:
                    pass
            return

        if kind == "camera_shot":
            try:
                self.play_camera_shot(
                    name=str(event_row.get("name", "shot") or "shot"),
                    duration=float(event_row.get("duration", 1.15) or 1.15),
                    profile=str(event_row.get("profile", "exploration") or "exploration"),
                    side=float(event_row.get("side", 0.0) or 0.0),
                    yaw_bias_deg=float(event_row.get("yaw_bias_deg", 0.0) or 0.0),
                    priority=event_row.get("priority", None),
                    owner="video_bot",
                )
            except Exception:
                pass
            return

        if kind in {"set_weather", "set_time", "camera_impact"}:
            self._video_bot_apply_environment_event(event_row)
            return

        if kind == "transition_next":
            self._dev_transition_next()
            return

        if kind == "ui_action":
            self._video_bot_apply_ui_action(event_row.get("action", ""), event_row)

    def _video_bot_can_drive_gameplay(self):
        if not getattr(self, "player", None):
            return False
        state_mgr = getattr(self, "state_mgr", None)
        if not state_mgr:
            return False
        state = getattr(state_mgr, "current_state", None)
        if state != getattr(self.GameState, "PLAYING", None):
            return False
        loading_screen = getattr(self, "loading_screen", None)
        if loading_screen and hasattr(loading_screen, "frame"):
            try:
                if not loading_screen.frame.isHidden():
                    return False
            except Exception:
                pass
        return True

    def _video_bot_update(self, dt):
        if not bool(getattr(self, "_video_bot_enabled", False)):
            return
        if bool(getattr(self, "_video_bot_done", False)):
            return
        if not isinstance(getattr(self, "_video_bot_plan", None), list):
            return
        self._video_bot_enforce_visibility(force=False)

        real_now = float(globalClock.getRealTime() or globalClock.getFrameTime() or 0.0)
        last_real = float(getattr(self, "_video_bot_last_real_time", 0.0) or 0.0)
        if last_real <= 1e-6:
            real_dt = 0.0
        else:
            real_dt = max(0.0, real_now - last_real)
        self._video_bot_last_real_time = real_now

        if not self._video_bot_can_drive_gameplay():
            if bool(getattr(self, "_video_bot_started", False)) and real_dt > 0.0:
                # Pause timeline while gameplay control is unavailable (loading, cutscene, menus).
                self._video_bot_start_ready_at = float(
                    getattr(self, "_video_bot_start_ready_at", real_now) or real_now
                ) + real_dt
            self._video_bot_update_virtual_cursor(dt)
            return

        if not bool(getattr(self, "_video_bot_started", False)):
            self._video_bot_started = True
            self._video_bot_elapsed = 0.0
            self._video_bot_event_idx = 0
            self._video_bot_hold_actions = {}
            self._video_bot_forced_flags = {}
            self._video_bot_start_ready_at = real_now + max(
                0.0,
                float(getattr(self, "_video_bot_start_delay_sec", 1.1) or 1.1),
            )
            logger.info(
                f"[VideoBot] Gameplay ready, plan '{self._video_bot_plan_name}' starts in "
                f"{max(0.0, float(getattr(self, '_video_bot_start_delay_sec', 1.1) or 1.1)):.2f}s."
            )

        if real_now + 1e-6 < float(getattr(self, "_video_bot_start_ready_at", 0.0) or 0.0):
            self._video_bot_update_virtual_cursor(dt)
            return

        now = max(
            0.0,
            real_now - float(getattr(self, "_video_bot_start_ready_at", real_now) or real_now),
        )
        self._video_bot_elapsed = now
        self._video_bot_update_virtual_cursor(dt)

        for action, until in list(self._video_bot_hold_actions.items()):
            if now >= float(until or 0.0):
                self._video_bot_set_action(action, False)
                del self._video_bot_hold_actions[action]

        for flag, payload in list(self._video_bot_forced_flags.items()):
            if not isinstance(payload, dict):
                del self._video_bot_forced_flags[flag]
                continue
            until = float(payload.get("until", 0.0) or 0.0)
            if now <= until:
                self._video_bot_apply_flag(flag, bool(payload.get("value", True)))
            else:
                if str(flag).strip().lower() in {"in_water", "water"}:
                    self._video_bot_apply_flag(flag, False)
                del self._video_bot_forced_flags[flag]

        while self._video_bot_event_idx < len(self._video_bot_plan):
            row = self._video_bot_plan[self._video_bot_event_idx]
            try:
                at = float(row.get("at", 0.0) or 0.0)
            except Exception:
                at = 0.0
            if now + 1e-6 < at:
                break
            self._video_bot_run_event(row, now)
            self._video_bot_event_idx += 1

        if (
            self._video_bot_event_idx >= len(self._video_bot_plan)
            and not self._video_bot_hold_actions
            and not self._video_bot_forced_flags
        ):
            self._video_bot_cycle_count = int(getattr(self, "_video_bot_cycle_count", 0) or 0) + 1
            logger.info(
                f"[VideoBot] Completed plan '{self._video_bot_plan_name}' "
                f"cycle={self._video_bot_cycle_count}."
            )
            if bool(getattr(self, "_video_bot_loop_plan", False)) and self._video_bot_plan:
                self._video_bot_event_idx = 0
                self._video_bot_elapsed = 0.0
                self._video_bot_hold_actions = {}
                self._video_bot_forced_flags = {}
                self._video_bot_cursor_visible = False
                self._video_bot_cursor_visible_until = 0.0
                self._video_bot_cursor_click_until = 0.0
                self._video_bot_start_ready_at = real_now + max(
                    0.0,
                    float(getattr(self, "_video_bot_loop_gap_sec", 0.45) or 0.45),
                )
                return
            self._video_bot_done = True
            self._video_bot_cursor_visible = False

    def _setup_main_game_tutorial(self):
        tutorial = getattr(self, "movement_tutorial", None)
        if not tutorial:
            return

        if bool(getattr(self, "_video_bot_enabled", False)):
            tutorial.disable()
            self._sync_tutorial_completion_flags()
            return

        if bool(getattr(self, "_tutorial_flow_blocked_by_opening", False)):
            tutorial.disable()
            self._sync_tutorial_completion_flags()
            return

        profile = self._norm_test_mode()
        if profile == "movement":
            return
        if profile:
            tutorial.disable()
            self._sync_tutorial_completion_flags()
            return

        if tutorial.is_complete():
            tutorial.disable()
            self._sync_tutorial_completion_flags()
            return

        if tutorial.has_progress():
            self._start_tutorial_flow(reset=False, mode="main", source="resume_save")
            return

        tutorial.set_mode("main", reset=False)

        xp = 0
        try:
            xp = int(getattr(self, "profile", {}).get("xp", 0) or 0)
        except Exception:
            xp = 0
        completed = getattr(getattr(self, "quest_mgr", None), "completed_quests", set()) or set()
        if xp <= 0 and not completed:
            self._start_tutorial_flow(reset=True, mode="main", source="new_game")
        else:
            tutorial.disable()
            self._sync_tutorial_completion_flags()

    def _restart_main_tutorial_hotkey(self):
        if self._video_bot_input_locked():
            return
        if not self.state_mgr.is_playing() or not self.player or not self.movement_tutorial:
            return
        self._start_tutorial_flow(reset=True, mode="main", source="hotkey_f8")
        logger.info("[Tutorial] Restarted main training flow (F8).")

    def _restart_full_tutorial_hotkey(self):
        if self._video_bot_input_locked():
            return
        if not self.state_mgr.is_playing() or not self.player or not self.movement_tutorial:
            return
        self._start_tutorial_flow(reset=True, mode="demo", source="hotkey_shift_f8")
        logger.info("[Tutorial] Restarted full training flow (Shift+F8).")

    def play_camera_shot(
        self,
        name="shot",
        duration=1.35,
        profile="boss",
        side=0.0,
        yaw_bias_deg=0.0,
        priority=50,
        owner="runtime",
    ):
        director = getattr(self, "camera_director", None)
        if not director or not hasattr(director, "play_camera_shot"):
            return False
        try:
            return bool(
                director.play_camera_shot(
                    name=name,
                    duration=duration,
                    profile=profile,
                    side=side,
                    yaw_bias_deg=yaw_bias_deg,
                    priority=priority,
                    owner=owner,
                )
            )
        except Exception as exc:
            logger.debug(f"[CameraDirector] Failed to play shot '{name}': {exc}")
            return False

    def _dev_transition_next(self):
        if not self.world or not self.world.locations:
            return
        loc = self.world.locations[self._dev_location_idx % len(self.world.locations)]
        self._dev_location_idx += 1
        loc_name = loc.get("name") if isinstance(loc, dict) else None
        if loc_name:
            self.transition_to_location(loc_name)

    def grant_rewards(self, rewards):
        if not isinstance(rewards, dict):
            return

        xp_gain = int(rewards.get("xp", rewards.get("experience", 0)) or 0)
        gold_gain = int(rewards.get("gold", 0) or 0)

        self.profile["xp"] = int(self.profile.get("xp", 0)) + xp_gain
        self.profile["gold"] = int(self.profile.get("gold", 0)) + gold_gain

        item_bag = self.profile.setdefault("items", {})
        reward_items = rewards.get("items", [])
        if isinstance(reward_items, list):
            for item in reward_items:
                if isinstance(item, str):
                    item_id = item
                    qty = 1
                elif isinstance(item, dict):
                    item_id = item.get("id") or item.get("item_id")
                    qty = int(item.get("quantity", 1) or 1)
                else:
                    continue
                if not item_id:
                    continue
                item_bag[item_id] = int(item_bag.get(item_id, 0)) + max(1, qty)

        logger.info(
            f"[Rewards] +XP {xp_gain}, +Gold {gold_gain}, "
            f"items={rewards.get('items', [])}"
        )
        self._save_autosave()

    def start_play(self, load_save=False, slot_index=None):
        logger.info(f"Preparing to start game. Load save: {load_save}, Slot: {slot_index}")
        self._hide_all_menus()
        self._reset_opening_memory_runtime()

        # We can't actually load yet because the world doesn't exist.
        # Save the intent, then start loading the world.
        if load_save:
            self.pending_save_load = {"slot_index": slot_index}
        else:
            self.pending_save_load = None

        self.start_game_loading()
        return True

    def _reset_opening_memory_runtime(self):
        self._tutorial_flow_blocked_by_opening = False
        self._opening_memory_started = False
        self._opening_memory_finished = False
        self._opening_banner_queue = []
        self._opening_banner_cursor = 0
        self._opening_banner_delay_left = 0.0
        self._opening_banner_time_left = 0.0
        self._opening_banner_elapsed = 0.0
        self._opening_banner_current = None
        self._opening_banner_active = False

    def _save_slot_hotkey(self, slot_index):
        if self._video_bot_input_locked():
            return
        if not self.state_mgr.is_playing() or not self.player:
            return
        try:
            path = self.save_mgr.save_slot(slot_index)
            self.hud.set_autosave(True)
            self._autosave_flash_until = max(
                self._autosave_flash_until,
                globalClock.getFrameTime() + 1.2,
            )
            logger.info(f"[SaveManager] Saved slot {int(slot_index)} -> {path}")
        except Exception as exc:
            logger.warning(f"[SaveManager] Slot save failed ({slot_index}): {exc}")

    def _load_slot_hotkey(self, slot_index):
        if self._video_bot_input_locked():
            return
        if not self.world:
            return
        try:
            loaded = self.save_mgr.load_slot(slot_index)
        except Exception as exc:
            logger.warning(f"[SaveManager] Slot load failed ({slot_index}): {exc}")
            return

        if not loaded:
            logger.info(f"[SaveManager] Slot {int(slot_index)} is empty or invalid.")
            return

        self._hide_all_menus()
        self.state_mgr.set_state(self.GameState.PLAYING)
        self._last_autosave_time = globalClock.getFrameTime()
        self.hud.set_autosave(True)
        self._autosave_flash_until = max(
            self._autosave_flash_until,
            globalClock.getFrameTime() + 1.2,
        )
        self._setup_main_game_tutorial()

    def _hide_all_menus(self):
        if hasattr(self, "main_menu") and self.main_menu:
            self.main_menu.hide()
        if hasattr(self, "pause_menu") and self.pause_menu:
            self.pause_menu.hide()

    def _save_autosave(self):
        try:
            self.hud.set_autosave(True)
            self._autosave_flash_until = max(
                self._autosave_flash_until,
                globalClock.getFrameTime() + 1.2,
            )
            path = self.save_mgr.save_autosave()
            logger.info(f"[SaveManager] Autosaved -> {path}")
            return True
        except Exception as exc:
            logger.warning(f"[SaveManager] Autosave failed: {exc}")
            return False

    def _autosave_task(self, task):
        now = task.time

        is_loading = (
            hasattr(self, "loading_screen")
            and self.loading_screen
            and hasattr(self.loading_screen, "frame")
            and not self.loading_screen.frame.isHidden()
        )
        if not is_loading and now >= self._autosave_flash_until and self.state_mgr.is_playing():
            self.hud.set_autosave(False)

        if not self.state_mgr.is_playing() or not self.player:
            return Task.cont

        if now - self._last_autosave_time >= self._autosave_interval:
            self._last_autosave_time = now
            self._save_autosave()

        return Task.cont

    def _world_gen_task(self, task):
        # Continue preloading assets if not done
        if not self.preload_mgr.finished:
            p = self.preload_mgr.get_progress()
            self.loading_screen.set_progress(p * 0.3, "Preloading character assets...")
            return Task.cont

        # Step-by-step world building
        progress, status = self.world.generate_step()
        # Scale progress to start after preloading (0.3 -> 1.0)
        total_p = 0.3 + (progress * 0.7)
        self.loading_screen.set_progress(total_p, status)

        if self.world.is_built:
            logger.info("World and assets ready. Finalizing setup...")
            self._finalize_initialization()
            return Task.done

        return Task.cont

    def _finalize_initialization(self):
        logger.info("Finalizing initialization...")
        if not getattr(self, "sky_mgr", None):
            if bool(getattr(self, "_video_bot_visibility_boost", False)):
                try:
                    self.render.clearFog()
                except Exception:
                    pass
            else:
                fog = Fog("scene_fog")
                fog.setColor(0.45, 0.62, 0.85)
                fog.setExpDensity(0.008)
                self.render.setFog(fog)

        if not hasattr(self, 'player') or self.player is None:
            self.player = Player(
                self, self.render, self.loader,
                self.char_state, self.phys,
                self.combat, self.parkour,
                self.magic, self.particles,
                self.parkour_state
            )
            # Spawn slightly away from (0,0,0) so we don't start inside the pillar
            if "sharuan" in str(self.world.__class__).lower():
                self.player.actor.setPos(15.0, -20.0, 5.0)
        self._video_bot_refresh_bindings()

        self.enemy_proxies = []
        force_enemy_runtime = bool(getattr(self, "_video_bot_force_aggro_mobs", False))
        lightweight_test_runtime = (not HAS_CORE) and (
            (bool(getattr(self, "_video_bot_enabled", False)) or bool(self._norm_test_mode()))
            and (not force_enemy_runtime)
        )
        if lightweight_test_runtime:
            logger.info(
                "[Perf] Python-only runtime test: skipping NPC/enemy spawns and cinematic triggers for stability."
            )
            self.boss_manager = None
            self.dragon_boss = None
            self._cutscene_triggers_enabled = False
            tutorial = getattr(self, "movement_tutorial", None)
            if tutorial and hasattr(tutorial, "disable"):
                try:
                    tutorial.disable()
                except Exception:
                    pass
            director = getattr(self, "camera_director", None)
            if director and hasattr(director, "_cutscene"):
                try:
                    director._cutscene = None
                except Exception:
                    pass
        else:
            if (not HAS_CORE) and force_enemy_runtime:
                logger.info(
                    "[Perf] Aggro override active: keeping NPC/enemy spawns enabled in Python-only runtime test."
                )
            self._cutscene_triggers_enabled = True
            self._spawn_npcs()
            if self.boss_manager is None:
                try:
                    self.boss_manager = BossManager(self)
                except Exception as exc:
                    logger.warning(f"[EnemyRoster] Failed to initialize enemy roster: {exc}")
                    self.boss_manager = None
            if self.dragon_boss is None and self.boss_manager and hasattr(self.boss_manager, "get_primary"):
                self.dragon_boss = self.boss_manager.get_primary("golem")

        # Camera — follow player from behind at a readable distance
        self.disableMouse()
        if self.player:
            player_pos = self.player.actor.getPos()
            self.camera.setPos(player_pos.x, player_pos.y - 18, player_pos.z + 10)
            self.camera.lookAt(self.player.actor)
        else:
            self.camera.setPos(0, -18, 12)
            self.camera.lookAt(0, 0, 0)

        try:
            self._apply_texture_sampler_defaults(str(getattr(self, "_gfx_quality", "high")).strip().lower())
        except Exception as exc:
            logger.debug(f"[Visuals] Post-world texture clarity pass skipped: {exc}")

        # Ready!
        if bool(getattr(self, "_video_bot_visibility_boost", False)):
            self._video_bot_enforce_visibility(force=True)
        logger.info("Transitioning to Gameplay...")
        self._bootstrap_quests()
        self.loading_screen.hide()
        self.hud.set_autosave(False)
        self.main_menu.set_loading(False)
        self.pause_menu.hide()
        self.vehicle_mgr.spawn_default_vehicles()
        
        # --- NEW: Reset clock to kill the 30-sec load spike ---
        globalClock.setFrameCount(0)
        globalClock.reset()

        # Start game state immediately
        self.state_mgr.set_state(self.GameState.PLAYING)
        pending_save = getattr(self, "pending_save_load", None)
        should_run_opening = False

        if pending_save:
            slot_idx = self.pending_save_load.get("slot_index")
            logger.info("Deferred save load triggering now...")
            if slot_idx is None:
                self.save_mgr.load_latest()
            else:
                self.save_mgr.load_slot(slot_idx)
            self.pending_save_load = None
        else:
            # Opening memory should run only on fresh starts, never on loaded saves.
            should_run_opening = True

        self._apply_test_profile()
        if bool(getattr(self, "_video_bot_visibility_boost", False)):
            self._video_bot_enforce_visibility(force=True)
        opening_started = False
        if should_run_opening and not self._norm_test_mode():
            opening_started = bool(self._start_opening_memory_sequence())
        if not opening_started:
            self._setup_main_game_tutorial()
        try:
            audit_node_visual_health(
                self.render,
                report_path="logs/scene_visual_audit.json",
                debug_label="post_finalize",
            )
        except Exception as exc:
            logger.debug(f"[Visuals] Scene audit failed: {exc}")

        self._last_autosave_time = globalClock.getFrameTime()

        # Final focus push without forcing window geometry.
        self._setup_cursor()
        logger.info(f"Final Vis - Playing: True, Loading: {not self.loading_screen.frame.isHidden()}")

    def transition_to_location(self, loc_name):
        """Triggers a cinematic seamless transition to a new location."""
        logger.info(f"Transitioning to location: {loc_name}")
        self.hud.set_autosave(True)
        context_tag = str(loc_name or "travel").strip().lower() or "travel"
        bundle_targets = []
        if getattr(self, "asset_bundle_mgr", None):
            try:
                bundle_targets = self.asset_bundle_mgr.activate_for_location(context_tag)
            except Exception as exc:
                logger.debug(f"[AssetBundle] Location activation skipped: {exc}")

        # 1. Fade out current world & Show Loading Screen
        self.loading_screen.set_progress(0, f"Travelling to {loc_name}...")

        # Cinematic sequence: Fade to black -> Show Loading -> Load -> Fade In
        Sequence(
            LerpColorScaleInterval(self.render, 0.5, LColor(0,0,0,1), LColor(1,1,1,1)),
            Func(self.loading_screen.show, context_tag),
            Wait(0.1),
            Func(self.preload_mgr.preload_area, loc_name, lambda: self._start_world_rebuild(loc_name), bundle_targets)
        ).start()

    def _start_world_rebuild(self, loc_name):
        # 3. Clean up old location (remove children of render if needed)
        # (For now we just reset SharuanWorld steps)
        self.hud.set_autosave(True)
        if getattr(self, "story_interaction", None):
            try:
                self.story_interaction.clear()
            except Exception:
                pass
        self.world._current_step = 0
        self.world.is_built = False
        self.taskMgr.add(self._world_gen_task, "world_gen_task")

    def _spawn_npcs(self):
        if getattr(self, "npc_mgr", None):
            try:
                self.npc_mgr.spawn_from_data(self.data_mgr.npcs)
                return
            except Exception as exc:
                logger.warning(f"[NPCManager] Spawn failed, fallback to static NPCs: {exc}")

        model_path = "assets/models/xbot/Xbot.glb"
        template = getattr(self, "_npc_static_template", None)
        if not template or template.isEmpty():
            try:
                template = self.loader.loadModel(model_path)
            except Exception as exc:
                logger.warning(f"[XBotApp] Failed to load static NPC template '{model_path}': {exc}")
                return
            if not template or template.isEmpty():
                logger.warning(f"[XBotApp] Static NPC template is empty: '{model_path}'")
                return
            template.reparentTo(self.hidden)
            self._npc_static_template = template

        for npc_id, data in self.data_mgr.npcs.items():
            if not isinstance(data, dict):
                continue
            pos = data.get("pos", [0, 0, 0])
            if not (isinstance(pos, list) and len(pos) >= 3):
                pos = [0, 0, 0]
            np = template.instanceTo(self.render)
            np.setName(f"npc_static_{npc_id}")
            np.setPos(float(pos[0]), float(pos[1]), float(pos[2]))
            np.setScale(float(data.get("appearance", {}).get("scale", 1.0)))
            np.setTag("npc_id", str(npc_id))
            ensure_model_visual_defaults(
                np,
                apply_skin=False,
                debug_label=f"npc_static:{npc_id}",
            )
            if getattr(self, "char_state", None) is None:
                try:
                    np.setShaderOff(1002)
                except Exception:
                    pass
                try:
                    np.setColorScale(1.0, 1.0, 1.0, 1.0)
                except Exception:
                    pass
                try:
                    np.setTwoSided(True)
                except Exception:
                    pass
            logger.info(f"[XBotApp] Spawned static NPC fallback: {data.get('name', npc_id)} at {pos}")

    def _init_core_systems(self):
        if HAS_CORE:
            self.phys = gc.PhysicsEngine()
            self.combat = gc.CombatSystem()
            self.parkour = gc.ParkourSystem()
            self.magic = gc.MagicSystem()
            self.particles = gc.ParticleSystem()
            self.char_state = gc.CharacterState()
            self.parkour_state = gc.ParkourState()
            # Initial position
            self.char_state.position = gc.Vec3(0, 0, 5)

            # Water simulation (gridSize, worldSize)
            self.water_sim = gc.WaterSimulation(64, 200.0)
        else:
            self.phys = self.combat = self.parkour = self.magic = None
            self.particles = self.water_sim = None
            self.char_state = self.parkour_state = None

        self.enableParticles()
        self.magic_vfx = MagicVFXSystem(self)

    def _handle_tutorial_runtime_events(self):
        tutorial = getattr(self, "movement_tutorial", None)
        if not tutorial or not hasattr(tutorial, "get_status_snapshot"):
            return
        snap = tutorial.get_status_snapshot()
        core_complete = bool(snap.get("core_complete", False))
        full_complete = bool(snap.get("full_complete", False))

        if core_complete and not self._tutorial_core_complete_sent:
            self._tutorial_core_complete_sent = True
            if self._norm_test_mode() != "movement":
                self._complete_tutorial_quest()
            self._emit_cutscene_event(
                "tutorial_completed",
                {
                    "phase": "core",
                    "mode": str(snap.get("mode", "")),
                },
            )

        if full_complete and not self._tutorial_full_complete_sent:
            self._tutorial_full_complete_sent = True
            self._emit_cutscene_event(
                "tutorial_completed",
                {
                    "phase": "full",
                    "mode": str(snap.get("mode", "")),
                },
            )

    def _ensure_codex_profile(self):
        profile = getattr(self, "profile", None)
        if not isinstance(profile, dict):
            profile = {}
            self.profile = profile
        codex = profile.get("codex")
        if not isinstance(codex, dict):
            codex = {}
            profile["codex"] = codex
        for key in ("locations", "characters", "factions", "npcs", "enemies", "tutorial", "events"):
            rows = codex.get(key)
            if not isinstance(rows, list):
                codex[key] = []
        return codex

    def _codex_mark(self, section, token, title="", details=""):
        section_key = str(section or "").strip().lower()
        if section_key not in {"locations", "characters", "factions", "npcs", "enemies", "tutorial", "events"}:
            return False
        entry_id = str(token or "").strip().lower()
        if not entry_id:
            return False

        codex = self._ensure_codex_profile()
        rows = codex.get(section_key, [])
        if not isinstance(rows, list):
            rows = []
            codex[section_key] = rows
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("id", "")).strip().lower() == entry_id:
                return False

        row = {"id": entry_id}
        clean_title = str(title or "").strip()
        clean_details = str(details or "").strip()
        if clean_title:
            row["title"] = clean_title
        if clean_details:
            row["details"] = clean_details
        rows.append(row)
        if len(rows) > 72:
            codex[section_key] = rows[-72:]
        return True

    def _node_world_pos(self, node):
        if not node:
            return None
        try:
            if hasattr(node, "isEmpty") and node.isEmpty():
                return None
            return node.getPos(self.render)
        except Exception:
            return None

    def _build_target_candidate(
        self,
        kind,
        token,
        name,
        node,
        cam_pos,
        cam_fwd,
        max_dist=46.0,
        min_dot=0.955,
        meta=None,
    ):
        pos = self._node_world_pos(node)
        if pos is None:
            return None

        if kind in {"enemy", "npc"}:
            pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.4)
        elif kind == "vehicle":
            pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.0)
        elif kind == "story":
            pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 0.9)

        to_target = pos - cam_pos
        dist = float(to_target.length())
        if dist <= 0.001 or dist > float(max_dist):
            return None
        try:
            dir_norm = Vec3(to_target)
            dir_norm.normalize()
            dot = float(dir_norm.dot(cam_fwd))
        except Exception:
            return None
        if dot < float(min_dot):
            return None

        score = (dot * 1.35) - (dist / max(1.0, float(max_dist)))
        out = {
            "kind": str(kind),
            "id": str(token or ""),
            "name": str(name or token or kind),
            "node": node,
            "position": pos,
            "distance": dist,
            "dot": dot,
            "score": score,
            "locked": False,
        }
        if isinstance(meta, dict):
            out.update(meta)
        return out

    def _enemy_target_meta(self, unit):
        if not unit:
            return {}
        hp_raw = getattr(unit, "hp", 0.0)
        max_hp_raw = getattr(unit, "max_hp", 1.0)
        try:
            hp = max(0.0, float(hp_raw or 0.0))
        except Exception:
            hp = 0.0
        try:
            max_hp = max(1.0, float(max_hp_raw or 1.0))
        except Exception:
            max_hp = 1.0
        hp = min(max_hp, hp)
        hp_ratio = hp / max_hp
        return {
            "is_boss": bool(getattr(unit, "is_boss", False)),
            "hp": hp,
            "max_hp": max_hp,
            "hp_ratio": max(0.0, min(1.0, float(hp_ratio))),
        }

    def _lookup_locked_target(self, cam_pos, cam_fwd):
        kind = str(getattr(self, "_lock_target_kind", "") or "").strip().lower()
        token = str(getattr(self, "_lock_target_id", "") or "").strip()
        if not kind or not token:
            return None

        if kind == "enemy":
            manager = getattr(self, "boss_manager", None)
            for unit in getattr(manager, "units", []) if manager else []:
                unit_id = str(getattr(unit, "id", "")).strip()
                if unit_id != token:
                    continue
                if hasattr(unit, "is_alive") and not bool(getattr(unit, "is_alive", True)):
                    return None
                node = getattr(unit, "root", None)
                name = getattr(unit, "name", unit_id)
                return self._build_target_candidate(
                    "enemy",
                    unit_id,
                    name,
                    node,
                    cam_pos,
                    cam_fwd,
                    max_dist=78.0,
                    min_dot=0.50,
                    meta=self._enemy_target_meta(unit),
                )
            return None

        if kind == "npc":
            manager = getattr(self, "npc_mgr", None)
            for unit in getattr(manager, "units", []) if manager else []:
                if not isinstance(unit, dict):
                    continue
                unit_id = str(unit.get("id", "")).strip()
                if unit_id != token:
                    continue
                return self._build_target_candidate(
                    "npc",
                    unit_id,
                    str(unit.get("name", unit_id)),
                    unit.get("actor"),
                    cam_pos,
                    cam_fwd,
                    max_dist=52.0,
                    min_dot=0.40,
                )
            return None

        if kind == "vehicle":
            manager = getattr(self, "vehicle_mgr", None)
            row = manager._vehicles_by_id.get(token) if manager and hasattr(manager, "_vehicles_by_id") else None
            if not isinstance(row, dict):
                return None
            return self._build_target_candidate(
                "vehicle",
                token,
                str(row.get("kind", token)),
                row.get("node"),
                cam_pos,
                cam_fwd,
                max_dist=64.0,
                min_dot=0.35,
            )
        if kind == "story":
            manager = getattr(self, "story_interaction", None)
            row = manager.get_anchor(token) if manager and hasattr(manager, "get_anchor") else None
            if not isinstance(row, dict):
                return None
            return self._build_target_candidate(
                "story",
                token,
                str(row.get("name", token)),
                row.get("node"),
                cam_pos,
                cam_fwd,
                max_dist=42.0,
                min_dot=0.30,
                meta={
                    "codex_unlocks": list(row.get("codex_unlocks", [])) if isinstance(row.get("codex_unlocks"), list) else [],
                },
            )
        return None

    def _scan_aim_target(self):
        if not self.player or not getattr(self.player, "actor", None):
            return None
        if not self.camera:
            return None
        try:
            cam_pos = self.camera.getPos(self.render)
            cam_fwd = self.render.getRelativeVector(self.camera, Vec3(0, 1, 0))
            cam_fwd.normalize()
        except Exception:
            return None

        candidates = []

        npc_mgr = getattr(self, "npc_mgr", None)
        for unit in getattr(npc_mgr, "units", []) if npc_mgr else []:
            if not isinstance(unit, dict):
                continue
            cand = self._build_target_candidate(
                "npc",
                unit.get("id", ""),
                unit.get("name", unit.get("id", "NPC")),
                unit.get("actor"),
                cam_pos,
                cam_fwd,
                max_dist=22.0,
                min_dot=0.965,
            )
            if cand:
                cand["score"] += 0.03
                candidates.append(cand)

        roster = getattr(self, "boss_manager", None)
        for unit in getattr(roster, "units", []) if roster else []:
            node = getattr(unit, "root", None)
            if not node:
                continue
            if hasattr(unit, "is_alive") and not bool(getattr(unit, "is_alive", True)):
                continue
            cand = self._build_target_candidate(
                "enemy",
                getattr(unit, "id", ""),
                getattr(unit, "name", getattr(unit, "id", "Enemy")),
                node,
                cam_pos,
                cam_fwd,
                max_dist=58.0,
                min_dot=0.96,
                meta=self._enemy_target_meta(unit),
            )
            if cand:
                cand["score"] += 0.11
                candidates.append(cand)

        vehicle_mgr = getattr(self, "vehicle_mgr", None)
        for vehicle in getattr(vehicle_mgr, "vehicles", []) if vehicle_mgr else []:
            if not isinstance(vehicle, dict):
                continue
            cand = self._build_target_candidate(
                "vehicle",
                vehicle.get("id", ""),
                vehicle.get("kind", "Vehicle"),
                vehicle.get("node"),
                cam_pos,
                cam_fwd,
                max_dist=18.0,
                min_dot=0.97,
            )
            if cand:
                candidates.append(cand)

        story_mgr = getattr(self, "story_interaction", None)
        rows = story_mgr.iter_target_rows(max_dist=32.0) if story_mgr and hasattr(story_mgr, "iter_target_rows") else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cand = self._build_target_candidate(
                "story",
                row.get("id", ""),
                row.get("name", "Interaction"),
                row.get("node"),
                cam_pos,
                cam_fwd,
                max_dist=24.0,
                min_dot=0.968,
                meta={
                    "codex_unlocks": list(row.get("codex_unlocks", [])) if isinstance(row.get("codex_unlocks"), list) else [],
                    "location_name": str(row.get("location_name", "") or "").strip(),
                },
            )
            if cand:
                cand["score"] += 0.06
                candidates.append(cand)

        if not candidates:
            return None
        candidates.sort(key=lambda row: float(row.get("score", 0.0)), reverse=True)
        return candidates[0]

    def _clear_target_lock(self):
        self._lock_target_kind = ""
        self._lock_target_id = ""

    def _clear_aim_target_highlight(self):
        node = getattr(self, "_aim_highlight_node", None)
        prev = getattr(self, "_aim_highlight_prev_color", None)
        self._aim_highlight_node = None
        self._aim_highlight_prev_color = None
        if not node:
            return
        try:
            if hasattr(node, "isEmpty") and node.isEmpty():
                return
            if isinstance(prev, tuple) and len(prev) == 4:
                node.setColorScale(float(prev[0]), float(prev[1]), float(prev[2]), float(prev[3]))
            else:
                node.clearColorScale()
        except Exception:
            return

    def _apply_aim_target_highlight(self, target_info):
        if not isinstance(target_info, dict):
            self._clear_aim_target_highlight()
            return
        node = target_info.get("node")
        if not node:
            self._clear_aim_target_highlight()
            return
        try:
            if hasattr(node, "isEmpty") and node.isEmpty():
                self._clear_aim_target_highlight()
                return
        except Exception:
            self._clear_aim_target_highlight()
            return

        locked = bool(target_info.get("locked", False))
        kind = str(target_info.get("kind", "") or "").strip().lower()
        if locked:
            color = (1.0, 0.86, 0.42, 1.0)
        elif kind == "enemy":
            color = (1.0, 0.68, 0.62, 1.0)
        elif kind == "npc":
            color = (0.82, 0.98, 0.84, 1.0)
        elif kind == "story":
            color = (0.84, 0.86, 1.0, 1.0)
        else:
            color = (0.84, 0.90, 1.0, 1.0)

        if node is not self._aim_highlight_node:
            self._clear_aim_target_highlight()
            prev = None
            try:
                p = node.getColorScale()
                prev = (float(p[0]), float(p[1]), float(p[2]), float(p[3]))
            except Exception:
                prev = None
            self._aim_highlight_node = node
            self._aim_highlight_prev_color = prev
        try:
            node.setColorScale(float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        except Exception:
            self._clear_aim_target_highlight()

    def _update_aim_and_lock(self, dt):
        _ = dt
        candidate = self._scan_aim_target()
        if self.player and hasattr(self.player, "_once_action") and self.player._once_action("target_lock"):
            if self._lock_target_id:
                self._clear_target_lock()
                self._codex_mark("events", "target_lock_off", "Target lock released")
            elif isinstance(candidate, dict):
                self._lock_target_kind = str(candidate.get("kind", "")).strip().lower()
                self._lock_target_id = str(candidate.get("id", "")).strip()
                if self._lock_target_id:
                    candidate["locked"] = True
                    self._codex_mark(
                        "events",
                        f"target_lock:{self._lock_target_kind}:{self._lock_target_id}",
                        "Target lock engaged",
                        str(candidate.get("name", "")),
                    )

        if self._lock_target_id:
            try:
                cam_pos = self.camera.getPos(self.render)
                cam_fwd = self.render.getRelativeVector(self.camera, Vec3(0, 1, 0))
                cam_fwd.normalize()
            except Exception:
                cam_pos = None
                cam_fwd = None
            locked = self._lookup_locked_target(cam_pos, cam_fwd) if (cam_pos is not None and cam_fwd is not None) else None
            if isinstance(locked, dict):
                locked["locked"] = True
                self._aim_target_info = locked
                self._apply_aim_target_highlight(locked)
                return locked
            self._clear_target_lock()

        self._aim_target_info = candidate
        self._apply_aim_target_highlight(candidate)
        return candidate

    def _update_codex_runtime(self, player_pos, tutorial_state=None, target_info=None):
        self._ensure_codex_profile()
        world = getattr(self, "world", None)
        active_location = str(getattr(world, "active_location", "") or "").strip()
        if active_location and active_location != self._last_codex_location:
            self._last_codex_location = active_location
            
            # Sync with HUD display
            location_display_name = self._resolve_test_world_location_name(active_location)
            self.hud.set_location_name(location_display_name or active_location)
            
            self._codex_mark(
                "locations",
                active_location,
                location_display_name or active_location,
                "Visited",
            )

        if isinstance(target_info, dict):
            kind = str(target_info.get("kind", "")).strip().lower()
            token = str(target_info.get("id", "")).strip()
            name = str(target_info.get("name", token)).strip()
            if kind == "npc":
                self._codex_mark("npcs", token or name, name)
                self._codex_mark("characters", token or name, name)
            elif kind == "enemy":
                self._codex_mark("enemies", token or name, name)
            elif kind == "story":
                unlocks = target_info.get("codex_unlocks", [])
                if isinstance(unlocks, list):
                    for row in unlocks:
                        if not isinstance(row, dict):
                            continue
                        section = str(row.get("section", "") or "").strip().lower()
                        entry_id = str(row.get("id", "") or "").strip()
                        title = str(row.get("title", entry_id) or entry_id).strip()
                        details = str(row.get("details", "") or "").strip()
                        if section and entry_id:
                            self._codex_mark(section, entry_id, title, details)
                self._codex_mark("events", token or name, name or token)

        p_vec = None
        try:
            p_vec = Vec3(float(player_pos.x), float(player_pos.y), float(player_pos.z))
        except Exception:
            p_vec = None
        if p_vec is not None:
            npc_mgr = getattr(self, "npc_mgr", None)
            for unit in getattr(npc_mgr, "units", []) if npc_mgr else []:
                if not isinstance(unit, dict):
                    continue
                pos = self._node_world_pos(unit.get("actor"))
                if pos is None:
                    continue
                if (pos - p_vec).length() <= 6.5:
                    uid = str(unit.get("id", "")).strip()
                    self._codex_mark("npcs", uid or str(unit.get("name", "npc")), str(unit.get("name", uid)))
                    self._codex_mark("characters", uid or str(unit.get("name", "npc")), str(unit.get("name", uid)))

            roster = getattr(self, "boss_manager", None)
            for enemy in getattr(roster, "units", []) if roster else []:
                if hasattr(enemy, "is_alive") and not bool(getattr(enemy, "is_alive", True)):
                    continue
                pos = self._node_world_pos(getattr(enemy, "root", None))
                if pos is None:
                    continue
                if (pos - p_vec).length() <= 18.0:
                    eid = str(getattr(enemy, "id", "")).strip()
                    self._codex_mark("enemies", eid or str(getattr(enemy, "name", "enemy")), str(getattr(enemy, "name", eid)))

        if isinstance(tutorial_state, dict):
            step_id = str(tutorial_state.get("step_id", "") or "").strip().lower()
            if step_id:
                self._codex_mark(
                    "tutorial",
                    step_id,
                    step_id.replace("_", " ").title(),
                    str(tutorial_state.get("title", "") or "").strip(),
                )
            phase = str(tutorial_state.get("phase", "")).strip().lower()
            if phase == "complete":
                self._codex_mark("events", "tutorial_complete", "Tutorial completed")

    def _apply_target_lock_camera(self, center, dt, manual_look=False, shot_active=False):
        if manual_look or shot_active:
            return
        target = getattr(self, "_aim_target_info", None)
        if not isinstance(target, dict) or not bool(target.get("locked", False)):
            return
        node = target.get("node")
        if node:
            pos = self._node_world_pos(node)
            if pos is not None:
                if str(target.get("kind", "")).strip().lower() in {"npc", "enemy"}:
                    pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.4)
                elif str(target.get("kind", "")).strip().lower() == "vehicle":
                    pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.0)
                elif str(target.get("kind", "")).strip().lower() == "story":
                    pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 0.9)
                target["position"] = pos
        pos = target.get("position")
        if pos is None:
            return

        dx = float(pos.x) - float(center.x)
        dy = float(pos.y) - float(center.y)
        dz = float(pos.z) - (float(center.z) + 1.6)
        h_dist = math.sqrt((dx * dx) + (dy * dy))
        if h_dist <= 0.001:
            return

        desired_yaw = math.degrees(math.atan2(dx, dy))
        desired_pitch = -math.degrees(math.atan2(dz, max(0.001, h_dist)))
        yaw_delta = ((desired_yaw - self._cam_yaw + 180.0) % 360.0) - 180.0
        yaw_rate = 195.0
        pitch_rate = 150.0
        self._cam_yaw += max(-yaw_rate * dt, min(yaw_rate * dt, yaw_delta))
        pitch_delta = desired_pitch - self._cam_pitch
        self._cam_pitch += max(-pitch_rate * dt, min(pitch_rate * dt, pitch_delta))
        self._cam_pitch = max(-80.0, min(80.0, self._cam_pitch))

    def _update_magic_vfx_runtime(self, dt):
        magic_vfx = getattr(self, "magic_vfx", None)
        if not magic_vfx:
            return
        try:
            magic_vfx.update(float(dt))
        except Exception:
            pass

    def _sync_party_runtime(self):
        """Sync runtime CompanionUnit instances with active companion/pet slots from companion_mgr."""
        mgr = getattr(self, "companion_mgr", None)
        if not mgr or not hasattr(mgr, "get_active_companion_id") or not hasattr(mgr, "get_active_pet_id"):
            return
        if not hasattr(self, "_active_party") or self._active_party is None:
            self._active_party = {}
        comp_id = str(getattr(mgr, "get_active_companion_id", lambda: "")() or "").strip().lower()
        pet_id = str(getattr(mgr, "get_active_pet_id", lambda: "")() or "").strip().lower()
        wanted = {i for i in (comp_id, pet_id) if i}
        for token in list(self._active_party.keys()):
            if token not in wanted:
                unit = self._active_party.pop(token, None)
                if unit and hasattr(unit, "despawn"):
                    try:
                        unit.despawn()
                    except Exception:
                        pass
        player = getattr(self, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if not actor:
            return
        try:
            ppos = actor.getPos(self.render) if hasattr(self, "render") else actor.getPos()
        except Exception:
            ppos = Vec3(0, 0, 0)
        if hasattr(ppos, "x"):
            spawn_pos = Vec3(float(ppos.x), float(ppos.y), float(ppos.z))
        else:
            spawn_pos = Vec3(0, 0, 0)
        for member_id in wanted:
            if member_id in self._active_party:
                continue
            if not hasattr(mgr, "get_runtime_member_data"):
                continue
            data = mgr.get_runtime_member_data(member_id)
            if not isinstance(data, dict) or not data.get("id"):
                continue
            try:
                unit = CompanionUnit(self, member_id, data)
                unit.spawn(spawn_pos)
                self._active_party[member_id] = unit
            except Exception as exc:
                logger.debug(f"[Companion] Failed to spawn {member_id}: {exc}")

    def _update(self, task):
        dt_raw = globalClock.getDt()
        dt_real = dt_raw
        dt_real = min(dt_real, 0.05) # Cap delta time
        time_fx = getattr(self, "time_fx", None)
        dt_world = time_fx.scaled_dt("world", dt_real) if time_fx else dt_real
        dt_player = time_fx.scaled_dt("player", dt_real) if time_fx else dt_real
        is_playing = bool(self.state_mgr.is_playing())
        observed_fps = float(self.clock.getAverageFrameRate()) if self.clock else 0.0
        if observed_fps <= 0.0 and dt_raw > 0.0:
            observed_fps = 1.0 / max(1e-5, dt_raw)

        dt_enemies = dt_world
        dt_particles = dt_world
        world_state = dict(self._world_state_cache) if isinstance(self._world_state_cache, dict) else {}

        self._update_time_systems_v2(dt_real)
        self._update_world_systems_v2(dt_world)
        self._update_camera_tracking_v2()
        self._update_adaptive_performance_v2(dt_raw, is_playing, observed_fps)
        self._update_ui_state_v2(is_playing)

        if bool(getattr(self, "_video_bot_enabled", False)):
            self._video_bot_update(dt_player)

        if not is_playing or not self.player:
            if bool(getattr(self, "_video_bot_enabled", False)) and not self.player:
                self._video_bot_release_all_actions()
            self._clear_aim_target_highlight()
            return Task.cont

        if hasattr(self, "influence_mgr") and self.influence_mgr:
            dt_inf = self._runtime_take_dt("influence", dt_world)
            if dt_inf > 0.0:
                self.influence_mgr.update(dt_inf)

        # Attention-based simulation tier manager
        if hasattr(self, "sim_tier_mgr") and self.sim_tier_mgr and self.player:
            try:
                cam = self.camera
                cam_pos = cam.getPos(self.render)
                cam_fwd_np = self.render.getRelativeVector(cam, (0, 1, 0))
                # Approximate angular speed from last forward direction
                prev_fwd = getattr(self, "_prev_cam_fwd", None)
                ang_speed = 0.0
                if prev_fwd is not None:
                    dot = max(-1.0, min(1.0, (
                        cam_fwd_np.x * prev_fwd[0] +
                        cam_fwd_np.y * prev_fwd[1] +
                        cam_fwd_np.z * prev_fwd[2]
                    )))
                    ang_speed = math.acos(dot) / max(dt_real, 0.001)
                self._prev_cam_fwd = (cam_fwd_np.x, cam_fwd_np.y, cam_fwd_np.z)
                self.sim_tier_mgr.update(dt_world, cam_pos, cam_fwd_np, ang_speed)
            except Exception as _exc:
                pass

        if HAS_CORE:
            self.particles.update(dt_particles)
            self._particle_upload_accum += dt_world
            if self._particle_upload_accum >= self._particle_upload_interval:
                self._upload_particles()
                self._particle_upload_accum = 0.0
            if self.water_sim:
                self.water_sim.update(task.time)

        self._sample_gamepad_axes()
        self.player.update(dt_player, self._cam_yaw)
        player_pos = self.player.actor.getPos()
        stealth_state = {}
        if getattr(self, "stealth_mgr", None):
            try:
                stealth_state = self.stealth_mgr.update(
                    dt_world,
                    self.player,
                    world_state=world_state,
                    motion_plan=getattr(self.player, "_motion_plan", {}),
                )
            except Exception as exc:
                logger.debug(f"[StealthManager] Update failed: {exc}")
                stealth_state = {}
        self._stealth_state_cache = stealth_state if isinstance(stealth_state, dict) else {}

        if getattr(self, "npc_mgr", None):
            dt_npc_logic = self._runtime_take_dt("npc_logic", dt_world)
            if dt_npc_logic > 0.0:
                try:
                    self.npc_mgr.update(
                        dt_npc_logic,
                        world_state=world_state,
                        stealth_state=stealth_state,
                    )
                except Exception as exc:
                    logger.warning(f"[NPCManager] Update failed: {exc}")
                    self.npc_mgr = None
        if getattr(self, "npc_activity_director", None):
            dt_npc_activity = self._runtime_take_dt("npc_activity", dt_world)
            if dt_npc_activity > 0.0:
                try:
                    self.npc_activity_director.update(dt_npc_activity)
                except Exception as exc:
                    logger.debug(f"[NPCActivityDirector] Update failed: {exc}")
        if getattr(self, "npc_interaction", None):
            dt_npc_interaction = self._runtime_take_dt("npc_interaction", dt_world)
            if dt_npc_interaction > 0.0:
                try:
                    self.npc_interaction.update(dt_npc_interaction)
                except Exception as exc:
                    logger.debug(f"[NPCInteraction] Update failed: {exc}")
        if getattr(self, "story_interaction", None):
            dt_story_interaction = self._runtime_take_dt("story_interaction", dt_world)
            if dt_story_interaction > 0.0:
                try:
                    self.story_interaction.update(dt_story_interaction)
                except Exception as exc:
                    logger.debug(f"[StoryInteraction] Update failed: {exc}")
        if self.boss_manager and self.player:
            dt_enemy_logic = self._runtime_take_dt("enemy_logic", dt_enemies)
            if dt_enemy_logic > 0.0:
                try:
                    self.boss_manager.update(dt_enemy_logic, self.player.actor.getPos(self.render))
                    self._boss_update_fail_count = 0
                except Exception as exc:
                    self._boss_update_fail_count += 1
                    now = globalClock.getFrameTime()
                    if (now - self._boss_update_last_log_time) >= 2.0:
                        self._boss_update_last_log_time = now
                        logger.warning(
                            f"[EnemyRoster] Update failed ({self._boss_update_fail_count}x): {exc}"
                        )
        self.quest_mgr.update(player_pos)
        self.world.update(player_pos)
        self._update_magic_vfx_runtime(dt_world)
        # Sync environmental state with terrain/prop shaders
        weather = getattr(self, "weather_mgr", None)
        if weather and self.render:
            self.render.set_shader_input("cursed_blend", float(weather.cursed_blend))
            
        if bool(getattr(self, "_cutscene_triggers_enabled", True)) and getattr(self, "cutscene_triggers", None):
            dt_cutscene = self._runtime_take_dt("cutscene_triggers", dt_world)
            if dt_cutscene > 0.0:
                try:
                    self.cutscene_triggers.update(
                        player_pos,
                        getattr(self.world, "active_location", None),
                    )
                except Exception as exc:
                    logger.debug(f"[CutsceneTriggers] Update failed: {exc}")
        mount_hint = ""
        if hasattr(self, "vehicle_mgr") and self.vehicle_mgr:
            try:
                mount_hint = self.vehicle_mgr.get_interaction_hint(self.player)
            except Exception:
                mount_hint = ""
        if getattr(self, "story_interaction", None):
            try:
                story_hint = self.story_interaction.get_interaction_hint()
            except Exception:
                story_hint = ""
            if story_hint:
                mount_hint = str(story_hint)
        quest_data = []
        if hasattr(self, "quest_mgr") and self.quest_mgr:
            try:
                quest_data = self.quest_mgr.get_hud_data(player_pos=player_pos)
            except Exception:
                quest_data = []
        combat_event = None
        tutorial_message = ""
        tutorial_state = None
        opening_tutorial_state = None
        target_info = None
        spell_labels = []
        active_skill_idx = 0
        ultimate_skill_idx = 0
        if hasattr(self.player, "get_hud_combat_event"):
            try:
                combat_event = self.player.get_hud_combat_event()
            except Exception:
                combat_event = None
        if hasattr(self.player, "get_skill_wheel_state"):
            try:
                spell_labels, active_skill_idx, ultimate_skill_idx = self.player.get_skill_wheel_state()
            except Exception:
                spell_labels, active_skill_idx, ultimate_skill_idx = [], 0, 0
        if self.movement_tutorial:
            try:
                self.movement_tutorial.update(dt_world)
                tutorial_message = self.movement_tutorial.get_hud_message()
                if hasattr(self.movement_tutorial, "get_hud_payload"):
                    tutorial_state = self.movement_tutorial.get_hud_payload()
                self._handle_tutorial_runtime_events()
            except Exception as exc:
                logger.debug(f"[MovementTutorial] Update failed: {exc}")
                tutorial_message = ""
                tutorial_state = None
            if hasattr(self.movement_tutorial, "get_checkpoint_entry"):
                try:
                    tutorial_cp = self.movement_tutorial.get_checkpoint_entry(player_pos=player_pos)
                except Exception:
                    tutorial_cp = None
                if isinstance(tutorial_cp, dict):
                    filtered = []
                    for entry in quest_data:
                        if not isinstance(entry, dict):
                            continue
                        if str(entry.get("quest_id", "")).strip().lower() == "movement_tutorial":
                            continue
                        filtered.append(entry)
                    quest_data = [tutorial_cp] + filtered
        try:
            opening_tutorial_state = self._update_opening_banner_queue(dt_world)
        except Exception as exc:
            logger.debug(f"[OpeningMemory] Tutorial banner update failed: {exc}")
            opening_tutorial_state = None
        if isinstance(opening_tutorial_state, dict):
            tutorial_state = opening_tutorial_state
            tutorial_message = ""
        try:
            target_info = self._update_aim_and_lock(dt_real)
        except Exception as exc:
            logger.debug(f"[Targeting] Update failed: {exc}")
            target_info = None
        try:
            self._update_codex_runtime(
                player_pos=player_pos,
                tutorial_state=tutorial_state,
                target_info=target_info,
            )
        except Exception as exc:
            logger.debug(f"[Codex] Runtime update failed: {exc}")
        self.hud.update(
            dt_real,
            self.char_state,
            quest_data,
            self.profile,
            mount_hint,
            combat_event,
            spell_labels,
            active_skill_idx,
            ultimate_skill_idx,
            player_pos,
            tutorial_message=tutorial_message,
            tutorial_state=tutorial_state,
            target_info=target_info,
            stealth_state=stealth_state,
        )

        self._follow_camera(dt_real)

        return Task.cont

    def _follow_camera(self, dt):
        if self.player and self.player.actor:
            profile_cfg = None
            director = getattr(self, "camera_director", None)
            input_locked = bool(self._video_bot_input_locked())
            gp_axes = self._gp_axes if isinstance(getattr(self, "_gp_axes", None), dict) else {}
            gp_look_x = 0.0 if input_locked else float(gp_axes.get("look_x", 0.0) or 0.0)
            gp_look_y = 0.0 if input_locked else float(gp_axes.get("look_y", 0.0) or 0.0)
            manual_look = bool(
                self.state_mgr.is_playing()
                and not input_locked
                and self.mouseWatcherNode
                and self.mouseWatcherNode.isButtonDown(MouseButton.three())
            )
            manual_look = manual_look or (abs(gp_look_x) > 0.04 or abs(gp_look_y) > 0.04)
            shot_active = bool(
                director
                and hasattr(director, "is_cutscene_active")
                and director.is_cutscene_active()
            )
            if director:
                try:
                    profile_cfg = director.update(dt, manual_look=manual_look)
                except Exception as exc:
                    logger.debug(f"[CameraDirector] Update failed: {exc}")
                    profile_cfg = None

            # Fallback to actor position if char_state is missing
            if self.char_state:
                cp = self.char_state.position
                center = Vec3(float(cp.x), float(cp.y), float(cp.z))
                base_z = float(cp.z)
            else:
                # Python-only mode fallback
                ap = self.player.actor.getPos()
                center = Vec3(float(ap.x), float(ap.y), float(ap.z))
                base_z = float(ap.z)

            # --- Handle Mouse Look ---
            if self.mouseWatcherNode.hasMouse():
                mouse_x = self.mouseWatcherNode.getMouseX()
                mouse_y = self.mouseWatcherNode.getMouseY()

                # Apply rotation based on mouse delta from center
                # We don't recenter here to allow simple UI interaction, just relative drag
                if (not shot_active) and getattr(self, '_last_mouse_x', None) is not None and manual_look:
                    dx = mouse_x - self._last_mouse_x
                    dy = mouse_y - self._last_mouse_y
                    sens = max(40.0, min(320.0, float(getattr(self, "_cam_mouse_sens", 150.0) or 150.0)))
                    self._cam_yaw += dx * -sens
                    if bool(getattr(self, "_cam_invert_y", False)):
                        self._cam_pitch += dy * sens
                    else:
                        self._cam_pitch -= dy * sens

                    # Clamp pitch
                    self._cam_pitch = max(-80.0, min(80.0, self._cam_pitch))

                self._last_mouse_x = mouse_x
                self._last_mouse_y = mouse_y

            if (not shot_active) and (abs(gp_look_x) > 0.01 or abs(gp_look_y) > 0.01):
                sens = max(40.0, min(320.0, float(getattr(self, "_cam_mouse_sens", 150.0) or 150.0)))
                stick_scale = max(0.0, float(dt or 0.0)) * 1.8
                self._cam_yaw += (-gp_look_x) * sens * stick_scale
                if bool(getattr(self, "_cam_invert_y", False)):
                    self._cam_pitch += gp_look_y * sens * stick_scale
                else:
                    self._cam_pitch -= gp_look_y * sens * stick_scale
                self._cam_pitch = max(-80.0, min(80.0, self._cam_pitch))

            self._apply_target_lock_camera(
                center=center,
                dt=max(0.0, float(dt or 0.0)),
                manual_look=manual_look,
                shot_active=shot_active,
            )

            angles = (self._cam_yaw, self._cam_pitch)
            if angles != self._cam_angles_cache:
                self._cam_angles_cache = angles
                self._cam_yaw_rad = math.radians(self._cam_yaw)
                self._cam_pitch_rad = math.radians(self._cam_pitch)

            yr = self._cam_yaw_rad
            pr = self._cam_pitch_rad
            if director:
                try:
                    cam_pos, target = director.resolve_transform(
                        center=center,
                        base_z=base_z,
                        yaw_rad=yr,
                        pitch_rad=pr,
                        profile_cfg=profile_cfg,
                    )
                    # Protect against NaN transforms from CameraDirector
                    if not any(math.isnan(float(c)) or math.isinf(float(c)) for c in [cam_pos.x, cam_pos.y, cam_pos.z, target.x, target.y, target.z]):
                        self.camera.setPos(cam_pos)
                        self.camera.lookAt(target)
                        return
                    else:
                        logger.warning(f"[Camera] Corrupt transform from director: pos={cam_pos} target={target}. Falling back.")
                except Exception as exc:
                    logger.debug(f"[CameraDirector] Resolve transform failed: {exc}")

            cx = center.x + self._cam_dist * math.sin(yr) * math.cos(pr)
            cy = center.y - self._cam_dist * math.cos(yr) * math.cos(pr)
            cz = base_z + 1.8 + self._cam_dist * math.sin(-pr)

            if cz < base_z + 0.5:
                cz = base_z + 0.5 # Basic terrain anti-clipping for camera
            
            # Final safety check for manual/fallback camera
            if not any(math.isnan(float(c)) or math.isinf(float(c)) for c in [cx, cy, cz]):
                self.camera.setPos(cx, cy, cz)
                self.camera.lookAt(LPoint3(center.x, center.y, base_z + 1.8))
            else:
                logger.error(f"[Camera] FATAL: Fallback camera position is NaN! center={center} dist={self._cam_dist}")

    def _heartbeat(self, task):
        if task.frame < 10:
            logger.debug(f"Heartbeat - Frame {task.frame} processed.")
        elif task.frame == 10:
            logger.info("Main loop confirmed healthy (10 frames processed).")
        else:
            now = globalClock.getRealTime()
            if (now - self._last_diag_log_time) >= self._diag_log_interval_sec:
                self._last_diag_log_time = now
                cam = self.camera.getPos()
                plyr = self.player.actor.getPos() if self.player else "None"
                load_level = int(getattr(self, "_runtime_load_level", 0))
                perf_mgr = getattr(self, "adaptive_perf_mgr", None)
                perf_fps = perf_mgr.average_fps if perf_mgr else 0.0
                adaptive_mode = str(getattr(self, "_adaptive_mode", "balanced") or "balanced")
                if perf_mgr and hasattr(perf_mgr, "debug_snapshot"):
                    try:
                        snap = perf_mgr.debug_snapshot() or {}
                        load_level = int(snap.get("level", load_level))
                        perf_fps = float(snap.get("average_fps", 0.0) or 0.0)
                        adaptive_mode = str(snap.get("mode", adaptive_mode) or adaptive_mode)
                    except Exception:
                        perf_fps = 0.0
                logger.info(
                    f"[Diagnostics] FPS: {globalClock.getAverageFrameRate():.1f} | "
                    f"Adaptive: {adaptive_mode}/L{load_level} ({perf_fps:.1f}) | "
                    f"Cam: {cam} | Player: {plyr} | Particles: {self._last_particle_count}"
                )
        return Task.cont

    def _upload_particles(self):
        if not HAS_CORE or not self.particles:
            self._last_particle_count = 0
            return
        try:
            self._last_particle_count = int(self.particles.aliveCount())
        except Exception:
            self._last_particle_count = 0

    def _update_time_systems_v2(self, dt_real):
        bus = getattr(self, "event_bus", None)
        if bus and hasattr(bus, "flush"):
            try:
                bus.flush(max_events=32)
            except Exception as exc:
                logger.debug(f"[EventBus] flush failed: {exc}")
        time_fx = getattr(self, "time_fx", None)
        if time_fx:
            try:
                time_fx.update(dt_real)
            except Exception as exc:
                logger.debug(f"[TimeFx] Update failed: {exc}")

    def _update_world_systems_v2(self, dt_world):
        world_state = dict(self._world_state_cache) if isinstance(self._world_state_cache, dict) else {}
        if getattr(self, "sky_mgr", None):
            dt_sky = self._runtime_take_dt("sky", dt_world)
            if dt_sky > 0.0:
                try:
                    self.sky_mgr.update(dt_sky)
                    if hasattr(self.sky_mgr, "get_world_state"):
                        world_state = self.sky_mgr.get_world_state() or {}
                except Exception:
                    pass
        self._world_state_cache = world_state
        if getattr(self, "audio", None):
            self.audio.update(dt_world)

    def _update_camera_tracking_v2(self):
        if self.player and self.player.actor:
            try:
                ppos = self.player.actor.getPos()
                if all(math.isfinite(float(c)) for c in ppos):
                    self.camera.lookAt(self.player.actor)
            except Exception:
                pass
        if globalClock.getFrameCount() == 12 and not getattr(self, "_screenspace_ready", False):
            self._safe_screenspace_init()

    def _update_adaptive_performance_v2(self, dt_raw, is_playing, observed_fps):
        perf_mgr = getattr(self, "adaptive_perf_mgr", None)
        if perf_mgr:
            try:
                perf_mgr.update(dt_raw, is_playing=is_playing, observed_fps=observed_fps)
            except Exception:
                pass
        self._fps_sample_accum = float(getattr(self, "_fps_sample_accum", 0.0) or 0.0) + max(0.0, float(dt_raw or 0.0))
        if self._fps_sample_accum >= 0.35:
            self._fps_sample_accum = 0.0
            try:
                avg_fps = float(self.clock.getAverageFrameRate())
            except Exception:
                avg_fps = 0.0
            if avg_fps <= 0.0:
                avg_fps = observed_fps if observed_fps > 0.0 else (1.0 / max(1e-5, dt_raw))
            self._fps_last_avg = avg_fps
            base_budget = int(getattr(self, "_enemy_fire_particle_budget", 320) or 320)
            self._enemy_fire_particle_budget_live = scale_particle_budget_for_fps(
                base_budget,
                avg_fps,
                min_fps=float(getattr(self, "_fps_target_min", 30.0) or 30.0),
                max_fps=float(getattr(self, "_fps_target_max", 60.0) or 60.0),
            )

    def _update_ui_state_v2(self, is_playing):
        if is_playing:
            self.hud.show()
        else:
            self.hud.hide()
