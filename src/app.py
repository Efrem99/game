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
from entities.boss_manager import BossManager
from entities.player import Player
from managers.data_manager import DataManager
from managers.audio_director import AudioDirector
from managers.state_manager import StateManager, GameState
from managers.quest_manager import QuestManager
from managers.save_manager import SaveManager
from managers.vehicle_manager import VehicleManager
from managers.npc_manager import NPCManager
from managers.movement_tutorial_manager import MovementTutorialManager
from render.model_visuals import ensure_model_visual_defaults
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
        self.apply_graphics_quality(
            self.data_mgr.graphics_settings.get("quality", "High"),
            persist=False,
        )

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

        self.profile = {"xp": 0, "gold": 0, "items": {}}
        self.state_mgr = StateManager(self)
        self.quest_mgr = QuestManager(self, self.data_mgr.quests)
        self.preload_mgr = PreloadManager(self)
        self.save_mgr = SaveManager(self)
        self.vehicle_mgr = VehicleManager(self)
        self.npc_mgr = NPCManager(self)
        self.movement_tutorial = MovementTutorialManager(self)
        self._autosave_interval = 45.0
        self._last_autosave_time = 0.0
        self._autosave_flash_until = 0.0

        # -- UI --
        self.main_menu = MainMenu(self)
        self.pause_menu = PauseMenu(self)
        self.inventory_ui = InventoryUI(self)
        self.accept("i", self.inventory_ui.toggle)
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

        if state == self.GameState.PLAYING:
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
        self.aspect2d.show()
        self.main_menu.show()

    def start_game_loading(self):
        logger.info("Starting Game - Queueing heavy assets for preloading...")
        self.loading_screen.show()
        self.hud.set_autosave(True)
        self.preload_mgr.preload_assets([
            "assets/models/xbot/Xbot.glb",
            "assets/models/xbot/idle.glb",
            "assets/models/xbot/walk.glb",
            "assets/models/xbot/run.glb",
        ])

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
        }.get(profile, "")

        desired = self._resolve_test_location(self._test_location_raw or default_location)
        if desired is not None:
            self._teleport_player_to(desired)

        if self.movement_tutorial:
            self.movement_tutorial.disable()

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
                self.movement_tutorial.enable(reset=True)

        logger.info(
            f"[TestProfile] Applied profile='{profile or 'custom'}' "
            f"location='{self._test_location_raw or default_location or '-'}'"
        )

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

        # We can't actually load yet because the world doesn't exist.
        # Save the intent, then start loading the world.
        if load_save:
            self.pending_save_load = {"slot_index": slot_index}
        else:
            self.pending_save_load = None

        self.start_game_loading()
        return True

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
        # Fog
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

        if getattr(self, 'pending_save_load', None):
            slot_idx = self.pending_save_load.get("slot_index")
            logger.info("Deferred save load triggering now...")
            if slot_idx is None:
                self.save_mgr.load_latest()
            else:
                self.save_mgr.load_slot(slot_idx)
            self.pending_save_load = None

        self._apply_test_profile()

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

    def _update(self, task):
        dt = globalClock.getDt()
        dt = min(dt, 0.05) # Cap delta time
        if getattr(self, "audio", None):
            self.audio.update(dt)
        if self.state_mgr.is_playing():
            self.hud.show()
        else:
            self.hud.hide()

        if not self.state_mgr.is_playing() or not self.player:
            return Task.cont

        if HAS_CORE:
            self.particles.update(dt)
            self._particle_upload_accum += dt
            if self._particle_upload_accum >= self._particle_upload_interval:
                self._upload_particles()
                self._particle_upload_accum = 0.0
            if self.water_sim:
                self.water_sim.update(task.time)

        self.player.update(dt, self._cam_yaw)
        player_pos = self.player.actor.getPos()
        if getattr(self, "npc_mgr", None):
            try:
                self.npc_mgr.update(dt)
            except Exception as exc:
                logger.warning(f"[NPCManager] Update failed: {exc}")
                self.npc_mgr = None
        if self.boss_manager and self.player:
            try:
                self.boss_manager.update(dt, self.player.actor.getPos(self.render))
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
        mount_hint = ""
        if hasattr(self, "vehicle_mgr") and self.vehicle_mgr:
            try:
                mount_hint = self.vehicle_mgr.get_interaction_hint(self.player)
            except Exception:
                mount_hint = ""
        combat_event = None
        tutorial_message = ""
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
                self.movement_tutorial.update(dt)
                tutorial_message = self.movement_tutorial.get_hud_message()
            except Exception as exc:
                logger.debug(f"[MovementTutorial] Update failed: {exc}")
                tutorial_message = ""
        self.hud.update(
            dt,
            self.char_state,
            self.quest_mgr.get_hud_data(player_pos=player_pos),
            self.profile,
            mount_hint,
            combat_event,
            spell_labels,
            active_skill_idx,
            ultimate_skill_idx,
            player_pos,
            tutorial_message,
        )

        self._follow_camera(dt)

        return Task.cont

    def _follow_camera(self, dt):
        if self.player and self.player.actor:
            # Fallback to actor position if char_state is missing
            if self.char_state:
                cp = self.char_state.position
                target = LPoint3(cp.x, cp.y, cp.z + 1.8)
                base_z = cp.z
            else:
                # Python-only mode fallback
                ap = self.player.actor.getPos()
                target = LPoint3(ap.x, ap.y, ap.z + 1.8)
                cp = ap # Use actor pos as center
                base_z = ap.z

            # --- Handle Mouse Look ---
            if self.mouseWatcherNode.hasMouse():
                mouse_x = self.mouseWatcherNode.getMouseX()
                mouse_y = self.mouseWatcherNode.getMouseY()

                # Apply rotation based on mouse delta from center
                # We don't recenter here to allow simple UI interaction, just relative drag
                if getattr(self, '_last_mouse_x', None) is not None and self.state_mgr.is_playing() and \
                   self.mouseWatcherNode.isButtonDown(MouseButton.three()):
                    dx = mouse_x - self._last_mouse_x
                    dy = mouse_y - self._last_mouse_y
                    self._cam_yaw += dx * -150.0  # Sensitivity
                    self._cam_pitch -= dy * 150.0

                    # Clamp pitch
                    self._cam_pitch = max(-80.0, min(80.0, self._cam_pitch))

                self._last_mouse_x = mouse_x
                self._last_mouse_y = mouse_y

            angles = (self._cam_yaw, self._cam_pitch)
            if angles != self._cam_angles_cache:
                self._cam_angles_cache = angles
                self._cam_yaw_rad = math.radians(self._cam_yaw)
                self._cam_pitch_rad = math.radians(self._cam_pitch)

            yr = self._cam_yaw_rad
            pr = self._cam_pitch_rad
            cx = cp.x + self._cam_dist * math.sin(yr) * math.cos(pr)
            cy = cp.y - self._cam_dist * math.cos(yr) * math.cos(pr)
            cz = base_z + 1.8 + self._cam_dist * math.sin(-pr)

            if cz < base_z + 0.5:
                cz = base_z + 0.5 # Basic terrain anti-clipping for camera

            self.camera.setPos(cx, cy, cz)
            self.camera.lookAt(target)

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
