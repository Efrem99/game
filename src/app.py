from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.interval.IntervalGlobal import Sequence, Wait, Func, LerpColorScaleInterval
from panda3d.core import (
    WindowProperties, AmbientLight, DirectionalLight,
    Vec3, Vec4, LPoint3, LColor, Fog, AntialiasAttrib,
    Texture, TransparencyAttrib, PNMImage, MouseButton,
    loadPrcFileData
)
import complexpbr
import math
import os
from utils.logger import logger

# Global Panda3D Configuration
loadPrcFileData("", "window-type normal")
loadPrcFileData("", "window-title XBot RPG Ultimate - Enhanced Edition")
loadPrcFileData("", "win-size 1280 720")
loadPrcFileData("", "win-origin 100 100")
loadPrcFileData("", "background-color 0.2 0.3 0.5")
loadPrcFileData("", "show-frame-rate-meter #t")
loadPrcFileData("", "sync-video #t")
loadPrcFileData("", "framebuffer-multisample #t")
loadPrcFileData("", "multisamples 4")
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
from managers.skill_tree_manager import SkillTreeManager
from render.model_visuals import ensure_model_visual_defaults, audit_node_visual_health
from ui.menu_main import MainMenu
from ui.menu_pause import PauseMenu
from ui.menu_inventory import InventoryUI
from ui.loading_screen import LoadingScreen
from ui.ui_intro import IntroUI
from ui.hud_overlay import HUDOverlay
from managers.preload_manager import PreloadManager

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

        # Force a window to open
        logger.info("Calling ShowBase.__init__...")
        super().__init__()

        if not self.win:
            logger.error("Failed to create graphics window!")
            return

        logger.info(f"Graphics pipe successfully opened. Window handle: {self.win}")

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
        self._cam_angles_cache = (self._cam_yaw, self._cam_pitch)
        self._cam_yaw_rad = math.radians(self._cam_yaw)
        self._cam_pitch_rad = math.radians(self._cam_pitch)
        self._gfx_quality = "Medium"

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

        complexpbr.apply_shader(
            self.render,
            intensity=1.0,
            default_lighting=False,
            custom_dir="shaders/"
        )

        # Avoid "Could not find appropriate DisplayRegion to filter" error
        try:
            if self.win and self.win.getActiveDisplayRegions():
                complexpbr.screenspace_init()
        except Exception as e:
            logger.warning(f"Could not init screenspace effects immediately: {e}")

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
        if hasattr(self, 'screen_quad'):
            logger.debug("Configuring complexpbr post-processing inputs.")
            self.screen_quad.set_shader_input("bloom_intensity", 1.2)
            for name, val in fallbacks.items():
                self.screen_quad.set_shader_input(name, val, priority=1000)

        # -- Managers --
        self.data_mgr = DataManager()
        self.event_bus = EventBus()
        self.apply_graphics_quality(
            self.data_mgr.graphics_settings.get("quality", "High"),
            persist=False,
        )
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
        self.save_mgr = SaveManager(self)
        self.vehicle_mgr = VehicleManager(self)
        self.npc_mgr = NPCManager(self)
        self.npc_activity_director = NPCActivityDirector(self)
        self.skill_tree_mgr = SkillTreeManager(self)
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
        self._last_codex_location = ""

        # -- UI --
        self.main_menu = MainMenu(self)
        self.pause_menu = PauseMenu(self)
        self.inventory_ui = InventoryUI(self)
        self.loading_screen = LoadingScreen(self)
        self.hud = HUDOverlay(self)
        self.hud.hide()

        # -- Start Preloading (Deferred till user starts the game) --
        # We save memory during the intro/menu by delaying asset loading.

        # -- Core Engine Systems (C++) --
        self._init_core_systems()
        self._last_particle_count = 0
        self._particle_upload_interval = 1.0 / 30.0
        self._particle_upload_accum = 0.0
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
        self.dialog_cinematic = DialogCinematicManager(self)
        self.npc_interaction = NPCInteractionManager(self)

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
        self.accept("f11-up", self._request_fullscreen_toggle)
        self.accept("alt-enter", self._request_fullscreen_toggle)
        self.accept("f10", self._request_fullscreen_toggle)
        self._dev_location_idx = 0
        self.accept("f9", self._dev_transition_next)
        self.accept("window-event", self._on_window_event)
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

    def _zoom_camera(self, delta):
        if self.state_mgr.is_playing():
            self._cam_dist = max(5.0, min(50.0, self._cam_dist + delta))

    def _remove_screenspace_nodes(self):
        try:
            for child in self.render.getChildren():
                if "screendisplay" in child.getName().lower():
                    child.removeNode()
        except Exception:
            pass

    def _apply_lighting_from_settings(self, quality_token):
        cfg = {}
        if hasattr(self, "data_mgr") and isinstance(getattr(self.data_mgr, "graphics_settings", {}), dict):
            cfg = self.data_mgr.graphics_settings
        lighting = cfg.get("lighting", {}) if isinstance(cfg, dict) else {}
        if not isinstance(lighting, dict):
            lighting = {}

        sun = lighting.get("sun", {}) if isinstance(lighting.get("sun"), dict) else {}
        ambient = lighting.get("ambient", {}) if isinstance(lighting.get("ambient"), dict) else {}

        q_mult = {"low": 0.82, "medium": 0.92, "high": 1.0, "ultra": 1.08}
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
        if token in {"high", "ultra"}:
            try:
                if self.camNode.getNumDisplayRegions() > 0:
                    complexpbr.screenspace_init()
            except Exception:
                pass
        else:
            self._remove_screenspace_nodes()

        bloom_intensity = 1.2
        cfg = getattr(self, "data_mgr", None)
        if cfg and isinstance(getattr(cfg, "graphics_settings", {}), dict):
            pp = cfg.graphics_settings.get("post_processing", {})
            if isinstance(pp, dict):
                bloom = pp.get("bloom", {})
                if isinstance(bloom, dict):
                    try:
                        bloom_intensity = float(bloom.get("intensity", bloom_intensity) or bloom_intensity)
                    except Exception:
                        bloom_intensity = 1.2
        bloom_scale = {"low": 0.72, "medium": 0.9, "high": 1.0, "ultra": 1.08}.get(token, 1.0)
        bloom_intensity *= bloom_scale

        if hasattr(self, "screen_quad"):
            try:
                self.screen_quad.set_shader_input("bloom_intensity", bloom_intensity)
            except Exception:
                pass

        self._apply_lighting_from_settings(token)
        self._gfx_quality = token.title()

        if persist and cfg and isinstance(cfg.graphics_settings, dict):
            cfg.graphics_settings["quality"] = self._gfx_quality
            cfg.save_settings("graphics_settings.json", cfg.graphics_settings)

    def _setup_window(self, initial=False):
        props = WindowProperties()
        props.setTitle("XBot RPG Ultimate - Enhanced Edition")
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
        if not self.mouseWatcherNode.hasMouse():
            return Task.cont
        x = self.mouseWatcherNode.getMouseX()
        y = self.mouseWatcherNode.getMouseY()
        sx = self.win.getXSize()
        sy = self.win.getYSize()
        px = (x + 1.0) * 0.5 * sx
        py = (1.0 - y) * 0.5 * sy
        hx, hy = getattr(self, "_cursor_hotspot_px", (0.0, 0.0))
        self._cursor_image.setPos(px + hx, 0, -(py - hy))
        return Task.cont

    def _on_window_event(self, window):
        if window != self.win or not self.win:
            return
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

    def _request_fullscreen_toggle(self):
        now = globalClock.getFrameTime()
        if now - self._last_fs_toggle_time < 0.25:
            return
        self._last_fs_toggle_time = now
        self.toggle_fullscreen()

    def _on_escape_pressed(self):
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

        # Transition straight to Main Menu without loading the heavy 3D world yet
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

    def start_game_loading(self):
        logger.info("Starting Game - Queueing heavy assets for preloading...")
        self.loading_screen.show()
        self.hud.set_autosave(True)
        preload_targets = self._collect_startup_preload_assets()
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

        presets = {
            "town": Vec3(0.0, 0.0, 0.0),
            "castle": Vec3(0.0, 65.0, 0.0),
            "docks": Vec3(0.0, -60.0, 0.0),
            "dragon_arena": Vec3(34.0, -6.0, 0.0),
            "boats": Vec3(0.0, -77.0, 0.0),
            "training": Vec3(18.0, 24.0, 0.0),
            "training_grounds": Vec3(18.0, 24.0, 0.0),
            "parkour": Vec3(30.0, 28.0, 0.0),
            "flight": Vec3(18.0, 24.0, 0.0),
        }
        if raw in presets:
            pos = Vec3(presets[raw])
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
        return pos

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

    def _start_opening_memory_sequence(self):
        if self._norm_test_mode():
            return False
        if bool(getattr(self, "_opening_memory_started", False)):
            return False

        package = self._load_opening_memory_package()
        if not isinstance(package, dict) or not package:
            return False

        self._opening_memory_started = True
        self._opening_memory_finished = False
        self._tutorial_flow_blocked_by_opening = True

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
            "movement": ("morning", "clear"),
            "parkour": ("afternoon", "partly_cloudy"),
            "flight": ("dawn", "clear"),
        }
        time_key, weather_key = presets.get(profile, ("noon", "clear"))
        try:
            sky.set_time_preset(time_key)
            sky.set_weather_preset(weather_key)
        except Exception as exc:
            logger.debug(f"[TestProfile] Sky preset failed ({profile}): {exc}")

    def _apply_test_profile(self):
        profile = str(self._test_profile or "").strip().lower()
        if not profile and not self._test_location_raw:
            return

        default_location = {
            "dragon": "dragon_arena",
            "music": "docks",
            "journal": "town",
            "mounts": "9,6,0",
            "skills": "0,0,0",
            "movement": "training",
            "parkour": "parkour",
            "flight": "flight",
        }.get(profile, "")

        desired = self._resolve_test_location(self._test_location_raw or default_location)
        if desired is not None:
            self._teleport_player_to(desired)

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
            if self.world:
                self.world.active_location = "Training Grounds"
            if self.movement_tutorial:
                self._start_tutorial_flow(reset=True, mode="demo", source="test_profile")
        elif profile == "parkour":
            if self.world:
                self.world.active_location = "Forest Parkour Grounds"
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

        logger.info(
            f"[TestProfile] Applied profile='{profile or 'custom'}' "
            f"location='{self._test_location_raw or default_location or '-'}'"
        )

    def _setup_main_game_tutorial(self):
        tutorial = getattr(self, "movement_tutorial", None)
        if not tutorial:
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
        if not self.state_mgr.is_playing() or not self.player or not self.movement_tutorial:
            return
        self._start_tutorial_flow(reset=True, mode="main", source="hotkey_f8")
        logger.info("[Tutorial] Restarted main training flow (F8).")

    def _restart_full_tutorial_hotkey(self):
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

        self.enemy_proxies = []
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

        # Ready!
        logger.info("Transitioning to Gameplay...")
        self._bootstrap_quests()
        self.loading_screen.hide()
        self.hud.set_autosave(False)
        self.main_menu.set_loading(False)
        self.pause_menu.hide()
        self.vehicle_mgr.spawn_default_vehicles()

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
        opening_started = False
        if should_run_opening:
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

        # 1. Fade out current world & Show Loading Screen
        self.loading_screen.set_progress(0, f"Travelling to {loc_name}...")

        # Cinematic sequence: Fade to black -> Show Loading -> Load -> Fade In
        Sequence(
            LerpColorScaleInterval(self.render, 0.5, LColor(0,0,0,1), LColor(1,1,1,1)),
            Func(self.loading_screen.show),
            Wait(0.1),
            Func(self.preload_mgr.preload_area, loc_name, lambda: self._start_world_rebuild(loc_name))
        ).start()

    def _start_world_rebuild(self, loc_name):
        # 3. Clean up old location (remove children of render if needed)
        # (For now we just reset SharuanWorld steps)
        self.hud.set_autosave(True)
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

    def _build_target_candidate(self, kind, token, name, node, cam_pos, cam_fwd, max_dist=46.0, min_dot=0.955):
        pos = self._node_world_pos(node)
        if pos is None:
            return None

        if kind in {"enemy", "npc"}:
            pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.4)
        elif kind == "vehicle":
            pos = Vec3(float(pos.x), float(pos.y), float(pos.z) + 1.0)

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
        return {
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

        if not candidates:
            return None
        candidates.sort(key=lambda row: float(row.get("score", 0.0)), reverse=True)
        return candidates[0]

    def _clear_target_lock(self):
        self._lock_target_kind = ""
        self._lock_target_id = ""

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
                return locked
            self._clear_target_lock()

        self._aim_target_info = candidate
        return candidate

    def _update_codex_runtime(self, player_pos, tutorial_state=None, target_info=None):
        self._ensure_codex_profile()
        world = getattr(self, "world", None)
        active_location = str(getattr(world, "active_location", "") or "").strip()
        if active_location and active_location != self._last_codex_location:
            self._last_codex_location = active_location
            self._codex_mark(
                "locations",
                active_location,
                active_location,
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

    def _update(self, task):
        dt_real = globalClock.getDt()
        dt_real = min(dt_real, 0.05) # Cap delta time
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
        dt_world = time_fx.scaled_dt("world", dt_real) if time_fx else dt_real
        dt_player = time_fx.scaled_dt("player", dt_real) if time_fx else dt_real
        dt_enemies = time_fx.scaled_dt("enemies", dt_real) if time_fx else dt_real
        dt_particles = time_fx.scaled_dt("particles", dt_real) if time_fx else dt_real
        world_state = {}
        if getattr(self, "sky_mgr", None):
            try:
                self.sky_mgr.update(dt_world)
                if hasattr(self.sky_mgr, "get_world_state"):
                    world_state = self.sky_mgr.get_world_state() or {}
            except Exception as exc:
                logger.debug(f"[SkyManager] Update failed: {exc}")
        self._world_state_cache = world_state
        if getattr(self, "audio", None):
            self.audio.update(dt_world)
        if self.state_mgr.is_playing():
            self.hud.show()
        else:
            self.hud.hide()

        if not self.state_mgr.is_playing() or not self.player:
            return Task.cont

        if hasattr(self, "influence_mgr") and self.influence_mgr:
            self.influence_mgr.update(dt_world)

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

        self.player.update(dt_player, self._cam_yaw)
        player_pos = self.player.actor.getPos()
        if getattr(self, "npc_mgr", None):
            try:
                self.npc_mgr.update(dt_world, world_state=world_state)
            except Exception as exc:
                logger.warning(f"[NPCManager] Update failed: {exc}")
                self.npc_mgr = None
        if getattr(self, "npc_activity_director", None):
            try:
                self.npc_activity_director.update(dt_world)
            except Exception as exc:
                logger.debug(f"[NPCActivityDirector] Update failed: {exc}")
        if getattr(self, "npc_interaction", None):
            try:
                self.npc_interaction.update(dt_world)
            except Exception as exc:
                logger.debug(f"[NPCInteraction] Update failed: {exc}")
        if self.boss_manager and self.player:
            try:
                self.boss_manager.update(dt_enemies, self.player.actor.getPos(self.render))
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
        if getattr(self, "cutscene_triggers", None):
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
        )

        self._follow_camera(dt_real)

        return Task.cont

    def _follow_camera(self, dt):
        if self.player and self.player.actor:
            profile_cfg = None
            director = getattr(self, "camera_director", None)
            manual_look = bool(
                self.state_mgr.is_playing()
                and self.mouseWatcherNode
                and self.mouseWatcherNode.isButtonDown(MouseButton.three())
            )
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
                    self._cam_yaw += dx * -150.0  # Sensitivity
                    self._cam_pitch -= dy * 150.0

                    # Clamp pitch
                    self._cam_pitch = max(-80.0, min(80.0, self._cam_pitch))

                self._last_mouse_x = mouse_x
                self._last_mouse_y = mouse_y

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
                    self.camera.setPos(cam_pos)
                    self.camera.lookAt(target)
                    return
                except Exception as exc:
                    logger.debug(f"[CameraDirector] Resolve transform failed: {exc}")

            cx = center.x + self._cam_dist * math.sin(yr) * math.cos(pr)
            cy = center.y - self._cam_dist * math.cos(yr) * math.cos(pr)
            cz = base_z + 1.8 + self._cam_dist * math.sin(-pr)

            if cz < base_z + 0.5:
                cz = base_z + 0.5 # Basic terrain anti-clipping for camera

            self.camera.setPos(cx, cy, cz)
            self.camera.lookAt(LPoint3(center.x, center.y, base_z + 1.8))

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
                logger.info(
                    f"[Diagnostics] FPS: {globalClock.getAverageFrameRate():.1f} | "
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
