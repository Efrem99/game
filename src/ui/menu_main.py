import os
from datetime import datetime
from pathlib import Path

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from direct.showbase.DirectObject import DirectObject
from direct.showbase.ShowBaseGlobal import globalClock
from direct.interval.IntervalGlobal import LerpColorScaleInterval, Sequence, Wait
from panda3d.core import TextNode, TransparencyAttrib

from managers.save_paths import save_path_aliases
from ui.design_system import (
    BUTTON_COLORS,
    THEME,
    ParchmentPanel,
    body_font,
    get_parchment_texture_path,
    place_ui_on_top,
    title_font,
)
from ui.ui_audio import play_ui_sfx


CONTROL_ACTIONS = [
    "forward",
    "backward",
    "left",
    "right",
    "jump",
    "run",
    "crouch_toggle",
    "flight_toggle",
    "flight_up",
    "flight_down",
    "interact",
    "inventory",
    "attack_light",
    "attack_heavy",
    "attack_thrust",
    "target_lock",
    "skill_wheel",
    "block",
    "roll",
    "dash",
    "spell_1",
    "spell_2",
    "spell_3",
    "spell_4",
    "spell_5",
    "spell_6",
    "spell_7",
]

ACTION_KEYBOARD_OPTIONS = {
    "forward": ["w", "arrow_up", "i", "none"],
    "backward": ["s", "arrow_down", "k", "none"],
    "left": ["a", "arrow_left", "j", "none"],
    "right": ["d", "arrow_right", "l", "none"],
    "jump": ["space", "mouse2", "q", "e", "none"],
    "run": ["shift", "lcontrol", "rcontrol", "none"],
    "crouch_toggle": ["c", "lcontrol", "rcontrol", "none"],
    "flight_toggle": ["v", "g", "none"],
    "flight_up": ["space", "e", "r", "none"],
    "flight_down": ["lcontrol", "q", "f", "none"],
    "interact": ["f", "x", "mouse3", "none"],
    "inventory": ["i", "tab", "b", "none"],
    "attack_light": ["mouse1", "q", "e", "none"],
    "attack_heavy": ["e", "mouse2", "r", "none"],
    "attack_thrust": ["mouse3", "none"],
    "target_lock": ["t", "middlemouse", "g", "none"],
    "skill_wheel": ["tab", "leftalt", "none"],
    "block": ["q", "mouse2", "f", "none"],
    "roll": ["r", "space", "z", "none"],
    "dash": ["z", "x", "c", "none"],
    "spell_1": ["1", "q", "none"],
    "spell_2": ["2", "w", "none"],
    "spell_3": ["3", "e", "none"],
    "spell_4": ["4", "r", "none"],
    "spell_5": ["5", "none"],
    "spell_6": ["6", "none"],
    "spell_7": ["7", "none"],
}

KEYBOARD_CAPTURE_TOKENS = [
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "space", "enter", "tab", "backspace", "escape",
    "shift", "lshift", "rshift",
    "control", "lcontrol", "rcontrol",
    "alt", "lalt", "ralt", "leftalt", "rightalt",
    "arrow_up", "arrow_down", "arrow_left", "arrow_right",
    "home", "end", "page_up", "page_down", "insert", "delete",
    "mouse1", "mouse2", "mouse3", "wheel_up", "wheel_down",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
]

GAMEPAD_COMMON_OPTIONS = [
    "gamepad-face_a",
    "gamepad-face_b",
    "gamepad-face_x",
    "gamepad-face_y",
    "gamepad-lshoulder",
    "gamepad-rshoulder",
    "gamepad-ltrigger",
    "gamepad-rtrigger",
    "gamepad-back",
    "gamepad-start",
    "gamepad-dpad_up",
    "gamepad-dpad_down",
    "gamepad-dpad_left",
    "gamepad-dpad_right",
    "none",
]

GAMEPAD_CAPTURE_TOKENS = [
    "gamepad-face_a",
    "gamepad-face_b",
    "gamepad-face_x",
    "gamepad-face_y",
    "gamepad-lshoulder",
    "gamepad-rshoulder",
    "gamepad-ltrigger",
    "gamepad-rtrigger",
    "gamepad-back",
    "gamepad-start",
    "gamepad-dpad_up",
    "gamepad-dpad_down",
    "gamepad-dpad_left",
    "gamepad-dpad_right",
    "gamepad-lstick",
    "gamepad-rstick",
]

ACTION_GAMEPAD_OPTIONS = {
    "forward": ["none", "gamepad-dpad_up", "gamepad-face_y"],
    "backward": ["none", "gamepad-dpad_down", "gamepad-face_a"],
    "left": ["none", "gamepad-dpad_left", "gamepad-lshoulder"],
    "right": ["none", "gamepad-dpad_right", "gamepad-rshoulder"],
    "flight_up": ["gamepad-face_a", "gamepad-rtrigger", "none"],
    "flight_down": ["gamepad-ltrigger", "gamepad-face_b", "none"],
}

DEFAULT_GAMEPAD_BINDINGS = {
    "jump": "gamepad-face_a",
    "run": "gamepad-face_b",
    "crouch_toggle": "gamepad-dpad_down",
    "flight_toggle": "gamepad-face_y",
    "flight_up": "gamepad-rtrigger",
    "flight_down": "gamepad-ltrigger",
    "interact": "gamepad-face_x",
    "inventory": "gamepad-start",
    "attack_light": "none",
    "attack_heavy": "none",
    "attack_thrust": "mouse3",
    "target_lock": "gamepad-back",
    "skill_wheel": "gamepad-rshoulder",
    "block": "none",
    "roll": "none",
    "dash": "none",
    "spell_1": "none",
    "spell_2": "none",
    "spell_3": "none",
}


class BaseMenu(DirectObject):
    def __init__(self, app):
        DirectObject.__init__(self)
        self.app = app
        self._reveal_seq = None
        self._loading = False
        self._menu_nav_bound = False
        self._menu_nav_events = []
        self._focused_button_idx = 0

        asp = self.app.getAspectRatio()
        self.frame = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-asp, asp, -1, 1),
            parent=self.app.aspect2d,
            # Keep the root menu frame mouse-active so child buttons receive input.
            suppressMouse=0,
        )
        place_ui_on_top(self.frame, 42)

        self.settings_panel = None
        self.controls_panel = None
        self.load_panel = None
        self.save_panel = None
        self.load_slot_buttons = []
        self.save_slot_buttons = []
        self._controls_actions = list(CONTROL_ACTIONS)
        self._controls_page_size = 8
        self._controls_page = 0
        self._controls_rows = []
        self._controls_capture_active = False
        self._controls_capture_action = None
        self._controls_capture_device = None
        self._controls_capture_events = []
        self._controls_capture_ignore_until = 0.0

        self._build_background(asp)
        self._build_layout()
        self._build_buttons()
        self._build_settings()
        self._build_controls_panel()
        self._build_load_panel()
        self._build_save_panel()
        self._apply_responsive_layout(asp)
        self.refresh_text()
        self.set_loading(False)
        self.hide()

    def _build_background(self, asp):
        tex_path = get_parchment_texture_path()
        if tex_path:
            self.background = DirectFrame(
                frameTexture=tex_path,
                frameColor=(0.98, 0.94, 0.86, 1),
                frameSize=(-asp, asp, -1, 1),
                parent=self.frame,
                suppressMouse=1,
            )
            place_ui_on_top(self.background, 40)
        else:
            self.background = DirectFrame(
                frameColor=THEME["bg_deep"],
                frameSize=(-asp, asp, -1, 1),
                parent=self.frame,
                suppressMouse=1,
            )
            place_ui_on_top(self.background, 40)

        overlay_alpha = 0.10 if bool(getattr(self.app, "_video_bot_visibility_boost", False)) else 0.20
        self.darken = DirectFrame(
            frameColor=(0, 0, 0, overlay_alpha),
            frameSize=(-asp, asp, -1, 1),
            parent=self.frame,
            suppressMouse=1,
        )
        place_ui_on_top(self.darken, 41)

        self.panel = ParchmentPanel(
            self.app,
            parent=self.frame,
            frameSize=(-0.55, 0.55, -0.65, 0.35),
            pos=(0, 0, -0.05),
            sort=43,
        )

    def _build_layout(self):
        t_font = title_font(self.app)
        b_font = body_font(self.app)

        self.title = OnscreenText(
            text="",
            pos=(0, 0.72),
            scale=0.15,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 0.85),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=True,
            font=t_font,
        )
        place_ui_on_top(self.title, 44)

        self.subtitle = OnscreenText(
            text="",
            pos=(0, 0.58),
            scale=0.06,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=True,
            font=b_font,
        )
        place_ui_on_top(self.subtitle, 44)

        self.status = OnscreenText(
            text="",
            # Keep status inside a conservative safe-zone for DPI-scaled windows.
            pos=(0.0, -0.88),
            scale=0.038,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.65),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=True,
            font=b_font,
        )
        place_ui_on_top(self.status, 44)

        self.nav_hint = OnscreenText(
            text="",
            pos=(0.0, -0.81),
            scale=0.031,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.65),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=True,
            font=b_font,
        )
        place_ui_on_top(self.nav_hint, 44)

    def _btn_texture_set(self):
        tex_off = "assets_raw/textures/ui/button_ready_off.png"
        tex_on = "assets_raw/textures/ui/button_ready_on.png"
        if os.path.exists(tex_off) and os.path.exists(tex_on):
            return (tex_off, tex_on, tex_on, tex_off)
        return None

    def _play_ui_sfx(self, key, volume=1.0, rate=1.0):
        return play_ui_sfx(self.app, key, volume=volume, rate=rate)

    def _wrap_button_command(self, command):
        if not callable(command):
            return command

        def _wrapped(*args, **kwargs):
            self._play_ui_sfx("ui_click", volume=0.48, rate=1.0)
            return command(*args, **kwargs)

        return _wrapped

    def _make_button(self, key, y_pos, command):
        b_font = body_font(self.app)
        textures = self._btn_texture_set()
        kwargs = {}
        if textures:
            kwargs["frameTexture"] = textures
            kwargs["frameColor"] = (1, 1, 1, 1)
        else:
            kwargs["frameColor"] = (0.14, 0.12, 0.10, 0.9)
        btn = DirectButton(
            text=self._t(key, key),
            text_fg=BUTTON_COLORS["normal"],
            text_scale=0.62,
            text_font=b_font,
            pos=(0, 0, y_pos),
            scale=0.12,
            frameSize=(-2.0, 2.0, -0.45, 0.45),
            relief=DGG.FLAT,
            pressEffect=1, # Re-enable press effect
            command=self._wrap_button_command(command),
            parent=self.frame,
            **kwargs,
        )
        if not textures:
            # Add subtle hover/press colors
            btn["frameColor"] = (
                (0.14, 0.12, 0.10, 0.9),  # normal
                (0.20, 0.18, 0.15, 0.95),  # press
                (0.25, 0.22, 0.18, 0.95),  # hover
                (0.10, 0.10, 0.10, 0.5)    # disable
            )

        place_ui_on_top(btn, 45)
        btn.setTransparency(TransparencyAttrib.MAlpha)
        btn["text_align"] = TextNode.ACenter
        btn["text_pos"] = (0, -0.08)
        btn._base_y = y_pos
        btn._hovered = False

        def _hover_on(_evt):
            btn._hovered = True
            self._play_ui_sfx("ui_hover", volume=0.28, rate=1.02)
            self._focus_button_by_ref(btn)

        def _hover_off(_evt):
            btn._hovered = False
            self._refresh_button_focus_visuals()

        btn.bind(DGG.WITHIN, _hover_on)
        btn.bind(DGG.WITHOUT, _hover_off)

        return btn

    def _build_buttons(self):
        self.btn_new = self._make_button("ui.new_game", 0.12, self._on_new_game)
        self.btn_continue = self._make_button("ui.continue", -0.02, self._on_continue_game)
        self.btn_load = self._make_button("ui.load_game", -0.16, self._on_load_game)
        self.btn_settings = self._make_button("ui.settings", -0.30, self._on_settings)
        self.btn_exit = self._make_button("ui.quit", -0.44, self._on_exit)
        self._button_order = [
            self.btn_new,
            self.btn_continue,
            self.btn_load,
            self.btn_settings,
            self.btn_exit,
        ]
        self._button_x = 0.0
        self._refresh_button_focus_visuals()

    def _build_settings(self):
        self._ensure_default_gamepad_bindings()
        self.settings_panel = ParchmentPanel(
            self.app,
            parent=self.frame,
            frameSize=(-0.76, 0.76, -1.00, 0.56),
            pos=(0, 0, 0),
            sort=50,
        )
        self.settings_panel.hide()

        t_font = title_font(self.app)
        b_font = body_font(self.app)
        gfx = self.app.data_mgr.graphics_settings if isinstance(self.app.data_mgr.graphics_settings, dict) else {}
        audio_cfg = self.app.data_mgr.audio_settings if isinstance(self.app.data_mgr.audio_settings, dict) else {}
        camera_cfg = gfx.get("camera", {}) if isinstance(gfx.get("camera"), dict) else {}

        self.settings_title = OnscreenText(
            text=self._t("ui.settings", "Settings"),
            pos=(0, 0.46),
            scale=0.09,
            fg=THEME["text_accent"],
            shadow=(0, 0, 0, 0.5),
            align=TextNode.ACenter,
            parent=self.settings_panel,
            mayChange=True,
            font=t_font,
        )

        # Language toggle
        lang_code = str(self.app.data_mgr.get_language()).upper() if hasattr(self.app, 'data_mgr') else "EN"
        self.lang_btn = DirectButton(
            text=self._t("ui.language", "Language") + f": {lang_code}",
            text_fg=THEME["gold_primary"],
            text_scale=0.060,
            text_font=b_font,
            pos=(0, 0, 0.34),
            frameColor=(0.10, 0.08, 0.05, 0.4),
            frameSize=(-0.55, 0.55, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_language,
            parent=self.settings_panel,
        )
        self.controls_btn = DirectButton(
            text=self._t("ui.controls_customization", "Controls Customization"),
            text_fg=THEME["gold_primary"],
            text_scale=0.052,
            text_font=b_font,
            pos=(0, 0, 0.28),
            frameColor=(0.10, 0.08, 0.05, 0.4),
            frameSize=(-0.55, 0.55, -0.045, 0.045),
            relief=DGG.FLAT,
            command=self._on_open_controls_panel,
            parent=self.settings_panel,
        )

        # Graphics quality
        self._graphics_levels = ["Low", "Medium", "High", "Ultra"]
        current_quality = str(getattr(self.app, "_gfx_quality", "Medium") or "Medium").title()
        if current_quality not in self._graphics_levels:
            current_quality = "Medium"
        self._graphics_idx = self._graphics_levels.index(current_quality)
        self.quality_lbl = OnscreenText(
            text=self._t("ui.quality", "Graphics Quality") + ":",
            pos=(-0.58, 0.22),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        self.quality_btn = DirectButton(
            text=self._graphics_levels[self._graphics_idx],
            text_fg=THEME["gold_primary"],
            text_scale=0.055,
            text_font=b_font,
            pos=(0.34, 0, 0.22),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.28, 0.28, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_quality,
            parent=self.settings_panel,
        )

        # Music volume
        self._music_vol = float(audio_cfg.get("music", 0.8) or 0.8)
        self.music_lbl = OnscreenText(
            text=self._t("ui.music_vol", "Music Volume") + ":",
            pos=(-0.58, 0.10),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        DirectButton(
            text="-", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.08, 0, 0.10), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("music", -0.1), parent=self.settings_panel,
        )
        self.music_val_lbl = OnscreenText(
            text=f"{int(self._music_vol * 100)}%", pos=(0.24, 0.10), scale=0.052,
            fg=THEME["gold_soft"], align=TextNode.ACenter,
            parent=self.settings_panel, mayChange=True, font=b_font,
        )
        DirectButton(
            text="+", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.42, 0, 0.10), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("music", 0.1), parent=self.settings_panel,
        )

        # SFX volume
        self._sfx_vol = float(audio_cfg.get("sfx", 1.0) or 1.0)
        self.sfx_lbl = OnscreenText(
            text=self._t("ui.sfx_vol", "SFX Volume") + ":",
            pos=(-0.58, -0.02),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        DirectButton(
            text="-", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.08, 0, -0.02), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("sfx", -0.1), parent=self.settings_panel,
        )
        self.sfx_val_lbl = OnscreenText(
            text=f"{int(self._sfx_vol * 100)}%", pos=(0.24, -0.02), scale=0.052,
            fg=THEME["gold_soft"], align=TextNode.ACenter,
            parent=self.settings_panel, mayChange=True, font=b_font,
        )
        DirectButton(
            text="+", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.42, 0, -0.02), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("sfx", 0.1), parent=self.settings_panel,
        )

        # Detailed graphics
        self._vsync_enabled = bool(gfx.get("vsync", True))
        self._msaa_options = [0, 2, 4, 8]
        pbr_cfg = gfx.get("pbr", {}) if isinstance(gfx.get("pbr"), dict) else {}
        current_msaa = int(pbr_cfg.get("msaa_samples", 4) or 4)
        self._msaa_idx = 0
        for idx, sample in enumerate(self._msaa_options):
            if current_msaa <= sample:
                self._msaa_idx = idx
                break
        else:
            self._msaa_idx = len(self._msaa_options) - 1
        pp_cfg = gfx.get("post_processing", {}) if isinstance(gfx.get("post_processing"), dict) else {}
        bloom_cfg = pp_cfg.get("bloom", {}) if isinstance(pp_cfg.get("bloom"), dict) else {}
        self._bloom_intensity = max(0.0, min(3.0, float(bloom_cfg.get("intensity", 1.2) or 1.2)))
        props = self.app.win.getProperties() if getattr(self.app, "win", None) else None
        self._fullscreen_enabled = bool(props and props.getFullscreen())

        self.fullscreen_lbl = OnscreenText(
            text=self._t("ui.fullscreen", "Fullscreen") + ":",
            pos=(-0.58, -0.18),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        self.fullscreen_btn = DirectButton(
            text="",
            text_fg=THEME["gold_primary"],
            text_scale=0.055,
            text_font=b_font,
            pos=(0.34, 0, -0.18),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.28, 0.28, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_fullscreen_setting,
            parent=self.settings_panel,
        )

        self.vsync_lbl = OnscreenText(
            text=self._t("ui.vsync", "VSync") + ":",
            pos=(-0.58, -0.30),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        self.vsync_btn = DirectButton(
            text="",
            text_fg=THEME["gold_primary"],
            text_scale=0.055,
            text_font=b_font,
            pos=(0.34, 0, -0.30),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.28, 0.28, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_vsync,
            parent=self.settings_panel,
        )

        self.msaa_lbl = OnscreenText(
            text=self._t("ui.msaa", "MSAA") + ":",
            pos=(-0.58, -0.42),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        DirectButton(
            text="-", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.08, 0, -0.42), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_msaa(-1), parent=self.settings_panel,
        )
        self.msaa_val_lbl = OnscreenText(
            text="", pos=(0.24, -0.42), scale=0.052,
            fg=THEME["gold_soft"], align=TextNode.ACenter,
            parent=self.settings_panel, mayChange=True, font=b_font,
        )
        DirectButton(
            text="+", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.42, 0, -0.42), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_msaa(1), parent=self.settings_panel,
        )

        self.bloom_lbl = OnscreenText(
            text=self._t("ui.bloom_intensity", "Bloom") + ":",
            pos=(-0.58, -0.54),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        DirectButton(
            text="-", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.08, 0, -0.54), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_bloom(-0.1), parent=self.settings_panel,
        )
        self.bloom_val_lbl = OnscreenText(
            text="", pos=(0.24, -0.54), scale=0.052,
            fg=THEME["gold_soft"], align=TextNode.ACenter,
            parent=self.settings_panel, mayChange=True, font=b_font,
        )
        DirectButton(
            text="+", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.42, 0, -0.54), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_bloom(0.1), parent=self.settings_panel,
        )

        # Controls
        self._cam_mouse_sens = max(40.0, min(320.0, float(camera_cfg.get("mouse_sensitivity", 150.0) or 150.0)))
        self._cam_invert_y = bool(camera_cfg.get("invert_y", False))
        self._move_preset = str(self.app.data_mgr.controls.get("meta", {}).get("move_preset", "classic") or "classic").lower()
        if self._move_preset not in {"classic", "arrows"}:
            self._move_preset = "classic"

        self.mouse_sens_row_lbl = OnscreenText(
            text=self._t("ui.mouse_sensitivity", "Mouse Sensitivity") + ":",
            pos=(-0.58, -0.66),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        DirectButton(
            text="-", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.08, 0, -0.66), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_mouse_sens(-10.0), parent=self.settings_panel,
        )
        self.mouse_sens_lbl = OnscreenText(
            text="", pos=(0.24, -0.66), scale=0.052,
            fg=THEME["gold_soft"], align=TextNode.ACenter,
            parent=self.settings_panel, mayChange=True, font=b_font,
        )
        DirectButton(
            text="+", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.42, 0, -0.66), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_mouse_sens(10.0), parent=self.settings_panel,
        )

        self.invert_y_lbl = OnscreenText(
            text=self._t("ui.invert_y", "Invert Y") + ":",
            pos=(-0.58, -0.78),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        self.invert_y_btn = DirectButton(
            text="",
            text_fg=THEME["gold_primary"],
            text_scale=0.055,
            text_font=b_font,
            pos=(0.34, 0, -0.78),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.28, 0.28, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_invert_y,
            parent=self.settings_panel,
        )

        self.move_preset_lbl = OnscreenText(
            text=self._t("ui.move_preset", "Move Preset") + ":",
            pos=(-0.58, -0.90),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        self.move_preset_btn = DirectButton(
            text="",
            text_fg=THEME["gold_primary"],
            text_scale=0.055,
            text_font=b_font,
            pos=(0.34, 0, -0.90),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.28, 0.28, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_move_preset,
            parent=self.settings_panel,
        )

        # --- Back ---
        self.btn_back = DirectButton(
            text=self._t("ui.back", "Back"),
            text_fg=THEME["text_accent"],
            text_scale=0.07,
            text_font=b_font,
            pos=(0, 0, -0.96),
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            command=self._on_close_settings,
            parent=self.settings_panel,
        )
        self._refresh_advanced_settings_labels()

    def _action_display_name(self, action):
        token = str(action or "").strip()
        pretty = token.replace("_", " ").title()
        return self._t(f"controls.{token}", pretty)

    def _format_binding_token(self, token):
        value = str(token or "").strip()
        if not value or value.lower() == "none":
            return self._t("ui.unbound", "Unbound")
        low = value.lower()
        if low.startswith("gamepad-"):
            return low.replace("gamepad-", "GP ").replace("_", " ").title()
        if low.startswith("mouse"):
            return low.upper()
        if low.startswith("arrow_"):
            return low.replace("arrow_", "ARROW ").upper()
        return value.upper()

    def _keyboard_options_for_action(self, action):
        action_key = str(action or "").strip().lower()
        options = ACTION_KEYBOARD_OPTIONS.get(action_key)
        if isinstance(options, list) and options:
            return list(options)
        return ["none"]

    def _keyboard_capture_tokens(self, action):
        values = []
        values.extend(self._keyboard_options_for_action(action))
        values.extend(KEYBOARD_CAPTURE_TOKENS)
        out = []
        seen = set()
        for token in values:
            key = str(token or "").strip().lower()
            if not key or key == "none" or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    def _gamepad_options_for_action(self, action):
        action_key = str(action or "").strip().lower()
        options = ACTION_GAMEPAD_OPTIONS.get(action_key)
        if isinstance(options, list) and options:
            return list(options)
        return list(GAMEPAD_COMMON_OPTIONS)

    def _gamepad_capture_tokens(self, action):
        values = []
        values.extend(self._gamepad_options_for_action(action))
        values.extend(GAMEPAD_CAPTURE_TOKENS)
        out = []
        seen = set()
        for token in values:
            key = str(token or "").strip().lower()
            if not key or key == "none" or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    def _refresh_controls_hint(self):
        if not hasattr(self, "controls_hint"):
            return
        if bool(getattr(self, "_controls_capture_active", False)):
            device = str(getattr(self, "_controls_capture_device", "kbm") or "kbm").lower()
            if device == "gamepad":
                key = "ui.controls_capture_wait_gp"
                fallback = "Press a gamepad button. Esc - cancel, Backspace - clear"
            else:
                key = "ui.controls_capture_wait_kbm"
                fallback = "Press keyboard/mouse input. Esc - cancel, Backspace - clear"
            self.controls_hint.setText(self._t(key, fallback))
            return
        self.controls_hint.setText(
            self._t(
                "ui.controls_bind_hint",
                "Click a bind button, then press key/button",
            )
        )

    def _clear_binding_capture_listeners(self):
        for event_name in list(getattr(self, "_controls_capture_events", [])):
            try:
                self.ignore(event_name)
            except Exception:
                continue
        self._controls_capture_events = []

    def _cancel_binding_capture(self, *_args, refresh=True):
        had_capture = bool(getattr(self, "_controls_capture_active", False))
        had_events = bool(getattr(self, "_controls_capture_events", []))
        self._controls_capture_active = False
        self._controls_capture_action = None
        self._controls_capture_device = None
        self._controls_capture_ignore_until = 0.0
        self._clear_binding_capture_listeners()
        if refresh and (had_capture or had_events):
            self._refresh_controls_page()
            self._refresh_controls_hint()

    def _on_binding_unbind_request(self):
        if not bool(getattr(self, "_controls_capture_active", False)):
            return
        action = str(getattr(self, "_controls_capture_action", "") or "").strip().lower()
        device = str(getattr(self, "_controls_capture_device", "kbm") or "kbm").lower()
        if not action:
            self._cancel_binding_capture()
            return
        self._set_binding_value(action, "gamepad" if device == "gamepad" else "kbm", "none")
        self._cancel_binding_capture(refresh=True)

    def _on_binding_captured(self, token):
        if not bool(getattr(self, "_controls_capture_active", False)):
            return
        if globalClock.getFrameTime() < float(getattr(self, "_controls_capture_ignore_until", 0.0) or 0.0):
            return
        action = str(getattr(self, "_controls_capture_action", "") or "").strip().lower()
        device = str(getattr(self, "_controls_capture_device", "kbm") or "kbm").lower()
        value = str(token or "").strip().lower()
        if not action or not value or value.endswith("-up"):
            return
        if device == "gamepad":
            if not value.startswith("gamepad-"):
                return
            target = "gamepad"
        else:
            if value.startswith("gamepad-"):
                return
            target = "kbm"
        self._set_binding_value(action, target, value)
        self._cancel_binding_capture(refresh=True)

    def _start_binding_capture(self, action, device):
        action_key = str(action or "").strip().lower()
        device_key = "gamepad" if str(device or "").strip().lower() == "gamepad" else "kbm"
        if not action_key:
            return
        self._cancel_binding_capture(refresh=False)
        tokens = (
            self._gamepad_capture_tokens(action_key)
            if device_key == "gamepad"
            else self._keyboard_capture_tokens(action_key)
        )
        self._controls_capture_active = True
        self._controls_capture_action = action_key
        self._controls_capture_device = device_key
        # Ignore the click event that opened capture, so mouse1 is not auto-captured.
        self._controls_capture_ignore_until = globalClock.getFrameTime() + 0.12
        self.accept("escape", self._cancel_binding_capture)
        self._controls_capture_events.append("escape")
        self.accept("backspace", self._on_binding_unbind_request)
        self._controls_capture_events.append("backspace")
        for token_name in tokens:
            if token_name in self._controls_capture_events:
                continue
            self.accept(token_name, self._on_binding_captured, [token_name])
            self._controls_capture_events.append(token_name)
        self._refresh_controls_page()
        self._refresh_controls_hint()

    def _action_for_row(self, row_idx):
        try:
            idx = (int(self._controls_page) * int(self._controls_page_size)) + int(row_idx)
        except Exception:
            return None
        if idx < 0 or idx >= len(self._controls_actions):
            return None
        return self._controls_actions[idx]

    def _on_control_bind(self, row_idx, device):
        action = self._action_for_row(row_idx)
        if not action:
            return
        self._start_binding_capture(action, device)

    def _ensure_default_gamepad_bindings(self):
        controls = self.app.data_mgr.controls if isinstance(self.app.data_mgr.controls, dict) else {}
        if not isinstance(controls, dict):
            controls = {}
            self.app.data_mgr.controls = controls
        gp = controls.setdefault("gamepad_bindings", {})
        if not isinstance(gp, dict):
            gp = {}
            controls["gamepad_bindings"] = gp
        changed = False
        for action, value in DEFAULT_GAMEPAD_BINDINGS.items():
            if action not in gp:
                gp[action] = value
                changed = True
        if changed:
            self.app.data_mgr.save_settings("controls.json", controls)

    def _binding_value(self, action, device):
        controls = self.app.data_mgr.controls if isinstance(self.app.data_mgr.controls, dict) else {}
        if device == "gamepad":
            gp = controls.get("gamepad_bindings", {}) if isinstance(controls.get("gamepad_bindings"), dict) else {}
            return str(gp.get(action, "none") or "none").lower()
        kb = controls.get("bindings", {}) if isinstance(controls.get("bindings"), dict) else {}
        return str(kb.get(action, "none") or "none").lower()

    def _set_binding_value(self, action, device, value):
        controls = self.app.data_mgr.controls if isinstance(self.app.data_mgr.controls, dict) else {}
        if not isinstance(controls, dict):
            controls = {}
            self.app.data_mgr.controls = controls
        if device == "gamepad":
            mapping = controls.setdefault("gamepad_bindings", {})
        else:
            mapping = controls.setdefault("bindings", {})
        if not isinstance(mapping, dict):
            mapping = {}
            if device == "gamepad":
                controls["gamepad_bindings"] = mapping
            else:
                controls["bindings"] = mapping

        token = str(value or "none").strip().lower()
        mapping[action] = token
        if token and token != "none":
            self._ensure_player_key_listener(token)
        self.app.data_mgr.save_settings("controls.json", controls)

    def _refresh_controls_page(self):
        if not self._controls_rows:
            return
        total = len(self._controls_actions)
        page_count = max(1, (total + self._controls_page_size - 1) // self._controls_page_size)
        self._controls_page = max(0, min(self._controls_page, page_count - 1))
        start = self._controls_page * self._controls_page_size
        active_action = str(getattr(self, "_controls_capture_action", "") or "").strip().lower()
        active_device = str(getattr(self, "_controls_capture_device", "") or "").strip().lower()
        waiting_txt = self._t("ui.controls_waiting", "PRESS...")

        for row_idx, row in enumerate(self._controls_rows):
            action_idx = start + row_idx
            if action_idx >= total:
                row["label"].setText("")
                row["kbm_btn"].hide()
                row["gp_btn"].hide()
                continue
            action = self._controls_actions[action_idx]
            row["label"].setText(self._action_display_name(action))
            row["kbm_btn"]["text"] = self._format_binding_token(self._binding_value(action, "kbm"))
            row["gp_btn"]["text"] = self._format_binding_token(self._binding_value(action, "gamepad"))
            row["kbm_btn"]["text_fg"] = THEME["gold_primary"]
            row["gp_btn"]["text_fg"] = THEME["gold_primary"]
            row["kbm_btn"]["frameColor"] = (0.10, 0.08, 0.05, 0.55)
            row["gp_btn"]["frameColor"] = (0.10, 0.08, 0.05, 0.55)
            if bool(getattr(self, "_controls_capture_active", False)) and str(action).lower() == active_action:
                if active_device == "gamepad":
                    row["gp_btn"]["text"] = waiting_txt
                    row["gp_btn"]["text_fg"] = THEME["text_accent"]
                    row["gp_btn"]["frameColor"] = (0.28, 0.16, 0.08, 0.80)
                else:
                    row["kbm_btn"]["text"] = waiting_txt
                    row["kbm_btn"]["text_fg"] = THEME["text_accent"]
                    row["kbm_btn"]["frameColor"] = (0.28, 0.16, 0.08, 0.80)
            row["kbm_btn"].show()
            row["gp_btn"].show()

        if hasattr(self, "controls_page_text"):
            self.controls_page_text.setText(f"{self._controls_page + 1}/{page_count}")

    def _on_controls_prev_page(self):
        self._cancel_binding_capture(refresh=False)
        self._controls_page = max(0, int(self._controls_page) - 1)
        self._refresh_controls_page()
        self._refresh_controls_hint()

    def _on_controls_next_page(self):
        self._cancel_binding_capture(refresh=False)
        total = len(self._controls_actions)
        page_count = max(1, (total + self._controls_page_size - 1) // self._controls_page_size)
        self._controls_page = min(page_count - 1, int(self._controls_page) + 1)
        self._refresh_controls_page()
        self._refresh_controls_hint()

    def _on_open_controls_panel(self):
        self._hide_overlays()
        self._hide_main_content()
        self._ensure_default_gamepad_bindings()
        self._cancel_binding_capture(refresh=False)
        self._controls_page = 0
        self._refresh_controls_page()
        self._refresh_controls_hint()
        if self.controls_panel:
            self.controls_panel.show()
        self._refresh_button_focus_visuals()

    def _on_close_controls_panel(self):
        self._cancel_binding_capture(refresh=False)
        self._hide_overlays()
        self._show_main_content()
        self._refresh_controls_hint()
        self._refresh_button_focus_visuals()

    def _build_controls_panel(self):
        self.controls_panel = ParchmentPanel(
            self.app,
            parent=self.frame,
            frameSize=(-0.92, 0.92, -0.84, 0.70),
            pos=(0, 0, 0),
            sort=50,
        )
        self.controls_panel.hide()

        t_font = title_font(self.app)
        b_font = body_font(self.app)

        self.controls_title = OnscreenText(
            text=self._t("ui.controls_customization", "Controls Customization"),
            pos=(0, 0.59),
            scale=0.078,
            fg=THEME["text_accent"],
            shadow=(0, 0, 0, 0.55),
            align=TextNode.ACenter,
            parent=self.controls_panel,
            mayChange=True,
            font=t_font,
        )
        self.controls_hint = OnscreenText(
            text=self._t("ui.controls_bind_hint", "Click a bind button, then press key/button"),
            pos=(0, 0.50),
            scale=0.040,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.45),
            align=TextNode.ACenter,
            parent=self.controls_panel,
            mayChange=True,
            font=b_font,
        )
        self.controls_col_action = OnscreenText(
            text=self._t("ui.controls_action_col", "Action"),
            pos=(-0.78, 0.43),
            scale=0.038,
            fg=THEME["gold_soft"],
            align=TextNode.ALeft,
            parent=self.controls_panel,
            mayChange=True,
            font=b_font,
        )
        self.controls_col_kbm = OnscreenText(
            text=self._t("ui.controls_kbm_col", "Keyboard/Mouse"),
            pos=(0.02, 0.43),
            scale=0.038,
            fg=THEME["gold_soft"],
            align=TextNode.ALeft,
            parent=self.controls_panel,
            mayChange=True,
            font=b_font,
        )
        self.controls_col_gp = OnscreenText(
            text=self._t("ui.controls_gp_col", "Gamepad"),
            pos=(0.48, 0.43),
            scale=0.038,
            fg=THEME["gold_soft"],
            align=TextNode.ALeft,
            parent=self.controls_panel,
            mayChange=True,
            font=b_font,
        )
        for node in (
            self.controls_title,
            self.controls_hint,
            self.controls_col_action,
            self.controls_col_kbm,
            self.controls_col_gp,
        ):
            place_ui_on_top(node, 52)

        self._controls_rows = []
        for row_idx in range(self._controls_page_size):
            y = 0.34 - (row_idx * 0.10)
            label = OnscreenText(
                text="",
                pos=(-0.78, y),
                scale=0.034,
                fg=THEME["text_main"],
                align=TextNode.ALeft,
                parent=self.controls_panel,
                mayChange=True,
                font=b_font,
            )
            kbm_btn = DirectButton(
                text="",
                text_fg=THEME["gold_primary"],
                text_scale=0.048,
                text_font=b_font,
                pos=(0.20, 0, y),
                frameColor=(0.10, 0.08, 0.05, 0.55),
                frameSize=(-0.20, 0.20, -0.042, 0.042),
                relief=DGG.FLAT,
                command=lambda idx=row_idx: self._on_control_bind(idx, "kbm"),
                parent=self.controls_panel,
            )
            gp_btn = DirectButton(
                text="",
                text_fg=THEME["gold_primary"],
                text_scale=0.048,
                text_font=b_font,
                pos=(0.66, 0, y),
                frameColor=(0.10, 0.08, 0.05, 0.55),
                frameSize=(-0.20, 0.20, -0.042, 0.042),
                relief=DGG.FLAT,
                command=lambda idx=row_idx: self._on_control_bind(idx, "gamepad"),
                parent=self.controls_panel,
            )
            place_ui_on_top(label, 52)
            place_ui_on_top(kbm_btn, 52)
            place_ui_on_top(gp_btn, 52)
            self._controls_rows.append({"label": label, "kbm_btn": kbm_btn, "gp_btn": gp_btn})

        self.controls_prev_btn = DirectButton(
            text=self._t("ui.prev", "Prev"),
            text_fg=THEME["text_main"],
            text_scale=0.055,
            text_font=b_font,
            pos=(-0.24, 0, -0.66),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.13, 0.13, -0.045, 0.045),
            relief=DGG.FLAT,
            command=self._on_controls_prev_page,
            parent=self.controls_panel,
        )
        self.controls_page_text = OnscreenText(
            text="1/1",
            pos=(0.0, -0.67),
            scale=0.040,
            fg=THEME["gold_soft"],
            align=TextNode.ACenter,
            parent=self.controls_panel,
            mayChange=True,
            font=b_font,
        )
        self.controls_next_btn = DirectButton(
            text=self._t("ui.next", "Next"),
            text_fg=THEME["text_main"],
            text_scale=0.055,
            text_font=b_font,
            pos=(0.24, 0, -0.66),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.13, 0.13, -0.045, 0.045),
            relief=DGG.FLAT,
            command=self._on_controls_next_page,
            parent=self.controls_panel,
        )
        self.controls_back_btn = DirectButton(
            text=self._t("ui.back", "Back"),
            text_fg=THEME["text_accent"],
            text_scale=0.065,
            text_font=b_font,
            pos=(0, 0, -0.76),
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            command=self._on_close_controls_panel,
            parent=self.controls_panel,
        )
        for node in (
            self.controls_prev_btn,
            self.controls_page_text,
            self.controls_next_btn,
            self.controls_back_btn,
        ):
            place_ui_on_top(node, 52)
        self._refresh_controls_page()
        self._refresh_controls_hint()

    def _build_load_panel(self):
        self.load_panel = ParchmentPanel(
            self.app,
            parent=self.frame,
            frameSize=(-0.72, 0.72, -0.60, 0.50),
            pos=(0, 0, 0),
            sort=50,
        )
        self.load_panel.hide()

        t_font = title_font(self.app)
        b_font = body_font(self.app)

        self.load_title = OnscreenText(
            text=self._t("ui.load_game", "Load Game"),
            pos=(0, 0.38),
            scale=0.08,
            fg=THEME["text_accent"],
            shadow=(0, 0, 0, 0.5),
            align=TextNode.ACenter,
            parent=self.load_panel,
            mayChange=True,
            font=t_font,
        )

        self.load_hint = OnscreenText(
            text=self._t("ui.choose_slot", "Select a save slot"),
            pos=(0, 0.28),
            scale=0.045,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.55),
            align=TextNode.ACenter,
            parent=self.load_panel,
            mayChange=True,
            font=b_font,
        )

        slot_positions = [0.12, -0.06, -0.24]
        self.load_slot_buttons = []
        for slot_index, y_pos in enumerate(slot_positions, start=1):
            button = DirectButton(
                text=f"Slot {slot_index}",
                text_fg=THEME["text_main"],
                text_scale=0.50,
                text_font=b_font,
                pos=(0, 0, y_pos),
                scale=0.10,
                frameSize=(-3.0, 3.0, -0.56, 0.56),
                frameColor=(0.14, 0.12, 0.10, 0.92),
                relief=DGG.FLAT,
                pressEffect=False,
                command=self._on_load_slot,
                extraArgs=[slot_index],
                parent=self.load_panel,
            )
            button["text_align"] = TextNode.ACenter
            button["text_pos"] = (0, -0.11)
            place_ui_on_top(button, 52)
            self.load_slot_buttons.append(button)

        self.load_back_btn = DirectButton(
            text=self._t("ui.back", "Back"),
            text_fg=THEME["text_accent"],
            text_scale=0.065,
            text_font=b_font,
            pos=(0, 0, -0.46),
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            command=self._on_close_load_panel,
            parent=self.load_panel,
        )
        place_ui_on_top(self.load_back_btn, 52)

    def _build_save_panel(self):
        self.save_panel = ParchmentPanel(
            self.app,
            parent=self.frame,
            frameSize=(-0.72, 0.72, -0.60, 0.50),
            pos=(0, 0, 0),
            sort=50,
        )
        self.save_panel.hide()

        t_font = title_font(self.app)
        b_font = body_font(self.app)

        self.save_title = OnscreenText(
            text=self._t("ui.save_game", "Save Game"),
            pos=(0, 0.38),
            scale=0.08,
            fg=THEME["text_accent"],
            shadow=(0, 0, 0, 0.5),
            align=TextNode.ACenter,
            parent=self.save_panel,
            mayChange=True,
            font=t_font,
        )

        self.save_hint = OnscreenText(
            text=self._t("ui.choose_slot_save", "Select slot to overwrite"),
            pos=(0, 0.28),
            scale=0.045,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.55),
            align=TextNode.ACenter,
            parent=self.save_panel,
            mayChange=True,
            font=b_font,
        )

        slot_positions = [0.12, -0.06, -0.24]
        self.save_slot_buttons = []
        for slot_index, y_pos in enumerate(slot_positions, start=1):
            button = DirectButton(
                text=f"Slot {slot_index}",
                text_fg=THEME["text_main"],
                text_scale=0.50,
                text_font=b_font,
                pos=(0, 0, y_pos),
                scale=0.10,
                frameSize=(-3.0, 3.0, -0.56, 0.56),
                frameColor=(0.14, 0.12, 0.10, 0.92),
                relief=DGG.FLAT,
                pressEffect=False,
                command=self._on_save_slot,
                extraArgs=[slot_index],
                parent=self.save_panel,
            )
            button["text_align"] = TextNode.ACenter
            button["text_pos"] = (0, -0.11)
            place_ui_on_top(button, 52)
            self.save_slot_buttons.append(button)

        self.save_back_btn = DirectButton(
            text=self._t("ui.back", "Back"),
            text_fg=THEME["text_accent"],
            text_scale=0.065,
            text_font=b_font,
            pos=(0, 0, -0.46),
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            command=self._on_close_save_panel,
            parent=self.save_panel,
        )
        place_ui_on_top(self.save_back_btn, 52)

    def _t(self, key, default):
        return self.app.data_mgr.t(key, default)

    def _has_save_data(self):
        if hasattr(self.app, "save_mgr") and hasattr(self.app.save_mgr, "has_save"):
            try:
                return bool(self.app.save_mgr.has_save())
            except Exception:
                pass
        base_dir = Path("saves")
        candidate_paths = []
        if hasattr(self.app, "save_mgr") and hasattr(self.app.save_mgr, "candidate_paths"):
            try:
                candidate_paths = list(self.app.save_mgr.candidate_paths())
            except Exception:
                candidate_paths = []
        if hasattr(self.app, "save_mgr") and hasattr(self.app.save_mgr, "save_dir"):
            try:
                base_dir = Path(self.app.save_mgr.save_dir)
            except Exception:
                base_dir = Path("saves")
        if not candidate_paths:
            seeds = [
                base_dir / "slot1.json",
                base_dir / "slot2.json",
                base_dir / "slot3.json",
                base_dir / "latest.json",
                base_dir / "autosave.json",
                Path("savegame.json"),
            ]
            for seed in seeds:
                candidate_paths.extend(save_path_aliases(seed))
        candidates = []
        for candidate in candidate_paths:
            path = Path(candidate)
            if path not in candidates:
                candidates.append(path)
        return any(path.exists() for path in candidates)

    def _can_save_game(self):
        if not hasattr(self.app, "save_mgr"):
            return False
        if not getattr(self.app, "player", None):
            return False
        allowed_states = {
            self.app.GameState.PLAYING,
            self.app.GameState.PAUSED,
            self.app.GameState.INVENTORY,
        }
        return self.app.state_mgr.current_state in allowed_states

    def _slot_metas(self):
        if hasattr(self.app, "save_mgr") and hasattr(self.app.save_mgr, "list_slots"):
            try:
                metas = self.app.save_mgr.list_slots()
                if isinstance(metas, list):
                    return metas
            except Exception:
                pass

        out = []
        base_dir = Path("saves")
        if hasattr(self.app, "save_mgr") and hasattr(self.app.save_mgr, "save_dir"):
            try:
                base_dir = Path(self.app.save_mgr.save_dir)
            except Exception:
                base_dir = Path("saves")
        for idx in range(1, 4):
            path = base_dir / f"slot{idx}.json"
            out.append(
                {
                    "slot": idx,
                    "path": str(path),
                    "exists": path.exists(),
                    "saved_at_utc": None,
                    "xp": 0,
                    "gold": 0,
                    "location": None,
                }
            )
        return out

    def _fmt_saved_at(self, value):
        if not value:
            return self._t("ui.unknown", "Unknown")
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(value)

    def _slot_button_label(self, slot_meta):
        slot_id = int(slot_meta.get("slot", 0) or 0)
        exists = bool(slot_meta.get("exists"))
        if not exists:
            return f"SLOT {slot_id}\n{self._t('ui.empty_slot', 'Empty')}"

        stamp = self._fmt_saved_at(slot_meta.get("saved_at_utc"))
        xp = int(slot_meta.get("xp", 0) or 0)
        gold = int(slot_meta.get("gold", 0) or 0)
        location = str(slot_meta.get("location") or self._t("ui.unknown", "Unknown"))
        return f"SLOT {slot_id}  {stamp}\nXP {xp} | Gold {gold} | {location}"

    def _refresh_load_slots(self):
        self._refresh_slot_buttons(
            self.load_slot_buttons,
            require_existing=True,
            disable_all=self._loading,
        )

    def _refresh_save_slots(self):
        self._refresh_slot_buttons(
            self.save_slot_buttons,
            require_existing=False,
            disable_all=(self._loading or (not self._can_save_game())),
        )

    def _refresh_slot_buttons(self, buttons, require_existing, disable_all):
        metas = self._slot_metas()
        by_slot = {}
        for meta in metas:
            try:
                by_slot[int(meta.get("slot", 0) or 0)] = meta
            except Exception:
                continue

        for slot_id, button in enumerate(buttons, start=1):
            meta = by_slot.get(
                slot_id,
                {
                    "slot": slot_id,
                    "exists": False,
                    "saved_at_utc": None,
                    "xp": 0,
                    "gold": 0,
                    "location": None,
                },
            )
            button["text"] = self._slot_button_label(meta)
            if disable_all:
                self._set_button_enabled(button, False)
            elif require_existing:
                self._set_button_enabled(button, bool(meta.get("exists")))
            else:
                self._set_button_enabled(button, True)

    def _set_button_enabled(self, button, enabled):
        button["state"] = DGG.NORMAL if enabled else DGG.DISABLED
        self._refresh_button_focus_visuals()

    def _menu_overlay_visible(self):
        overlays = (self.settings_panel, self.controls_panel, self.load_panel, self.save_panel)
        for panel in overlays:
            try:
                if panel and not panel.isHidden():
                    return True
            except Exception:
                continue
        return False

    def _focusable_main_buttons(self):
        focusable = []
        for button in getattr(self, "_button_order", []):
            try:
                if button.isHidden():
                    continue
                if button["state"] == DGG.DISABLED:
                    continue
            except Exception:
                continue
            focusable.append(button)
        return focusable

    def _refresh_button_focus_visuals(self):
        focusable = self._focusable_main_buttons()
        if focusable:
            self._focused_button_idx = max(0, min(self._focused_button_idx, len(focusable) - 1))
            focused_btn = focusable[self._focused_button_idx]
        else:
            focused_btn = None

        for button in getattr(self, "_button_order", []):
            try:
                hovered = bool(getattr(button, "_hovered", False))
                disabled = button["state"] == DGG.DISABLED
                if disabled:
                    button["text_fg"] = BUTTON_COLORS["disabled"]
                elif hovered or button is focused_btn:
                    button["text_fg"] = THEME["gold_primary"]
                else:
                    button["text_fg"] = BUTTON_COLORS["normal"]
            except Exception:
                continue

    def _focus_button_by_ref(self, button):
        focusable = self._focusable_main_buttons()
        if not focusable:
            self._focused_button_idx = 0
            self._refresh_button_focus_visuals()
            return
        for idx, ref in enumerate(focusable):
            if ref is button:
                self._focused_button_idx = idx
                break
        self._refresh_button_focus_visuals()

    def _focus_shift(self, direction):
        focusable = self._focusable_main_buttons()
        if not focusable:
            return
        self._focused_button_idx = (self._focused_button_idx + int(direction)) % len(focusable)
        self._refresh_button_focus_visuals()

    def _activate_focused_button(self):
        focusable = self._focusable_main_buttons()
        if not focusable:
            return
        button = focusable[self._focused_button_idx]
        try:
            if button["state"] == DGG.DISABLED:
                return
        except Exception:
            return
        try:
            command = button["command"]
        except Exception:
            command = None
        try:
            extra_args = button["extraArgs"]
        except Exception:
            extra_args = []
        if callable(command):
            command(*list(extra_args or []))

    def _on_nav_prev(self):
        if self.frame.isHidden() or self._loading or self._menu_overlay_visible():
            return
        self._focus_shift(-1)

    def _on_nav_next(self):
        if self.frame.isHidden() or self._loading or self._menu_overlay_visible():
            return
        self._focus_shift(1)

    def _on_nav_activate(self):
        if self.frame.isHidden() or self._loading or self._menu_overlay_visible():
            return
        self._activate_focused_button()

    def _bind_menu_navigation(self):
        if self._menu_nav_bound:
            return
        bindings = [
            ("arrow_up", self._on_nav_prev),
            ("w", self._on_nav_prev),
            ("arrow_down", self._on_nav_next),
            ("s", self._on_nav_next),
            ("enter", self._on_nav_activate),
            ("space", self._on_nav_activate),
            ("gamepad-dpad_up", self._on_nav_prev),
            ("gamepad-dpad_down", self._on_nav_next),
            ("gamepad-face_a", self._on_nav_activate),
        ]
        for event_name, handler in bindings:
            self.accept(event_name, handler)
        self._menu_nav_events = [event_name for event_name, _ in bindings]
        self._menu_nav_bound = True

    def _unbind_menu_navigation(self):
        if not self._menu_nav_bound:
            return
        for event_name in self._menu_nav_events:
            self.ignore(event_name)
        self._menu_nav_events = []
        self._menu_nav_bound = False

    def _show_main_content(self):
        self.panel.show()
        self.title.show()
        self.subtitle.show()
        self.nav_hint.show()
        for button in self._button_order:
            button.show()
        self._refresh_button_focus_visuals()

    def _hide_main_content(self):
        self.panel.hide()
        self.title.hide()
        self.subtitle.hide()
        self.nav_hint.hide()
        for button in self._button_order:
            button.hide()

    def _hide_overlays(self):
        self._cancel_binding_capture(refresh=False)
        if self.settings_panel:
            self.settings_panel.hide()
        if self.controls_panel:
            self.controls_panel.hide()
        if self.load_panel:
            self.load_panel.hide()
        if self.save_panel:
            self.save_panel.hide()

    def set_loading(self, is_loading, status_text=None):
        self._loading = bool(is_loading)
        has_save = self._has_save_data()
        self._set_button_enabled(self.btn_new, not self._loading)
        self._set_button_enabled(self.btn_continue, (not self._loading) and has_save)
        self._set_button_enabled(self.btn_load, (not self._loading) and has_save)
        self._set_button_enabled(self.btn_settings, not self._loading)
        self._set_button_enabled(self.btn_exit, True)
        self._refresh_load_slots()
        self._refresh_save_slots()
        if status_text:
            self.status.setText(status_text)
        else:
            self.status.setText(self._t("ui.loading", "Loading...") if self._loading else "")

    def refresh_text(self):
        self.title.setText(self._t("ui.game_title_alt", "KING WIZARD RPG"))
        self.subtitle.setText(self._t("ui.subtitle", "A Medieval Fantasy Adventure"))
        self.btn_new["text"] = self._t("ui.new_game", "New Game")
        self.btn_continue["text"] = self._t("ui.continue", "Continue")
        self.btn_load["text"] = self._t("ui.load_game", "Load Game")
        self.btn_settings["text"] = self._t("ui.settings", "Settings")
        self.btn_exit["text"] = self._t("ui.quit", "Quit")
        self.nav_hint.setText(
            self._t(
                "ui.menu_nav_hint",
                "Arrows/WASD - navigate   Enter/Space - select",
            )
        )

        self.settings_title.setText(self._t("ui.settings", "Settings"))
        lang_code = str(self.app.data_mgr.get_language()).upper()
        self.lang_btn["text"] = f"{self._t('ui.language', 'Language')}: {lang_code}"
        if hasattr(self, "controls_btn"):
            self.controls_btn["text"] = self._t("ui.controls_customization", "Controls Customization")
        if hasattr(self, "quality_lbl"):
            self.quality_lbl.setText(self._t("ui.quality", "Graphics Quality") + ":")
        if hasattr(self, "music_lbl"):
            self.music_lbl.setText(self._t("ui.music_vol", "Music Volume") + ":")
        if hasattr(self, "sfx_lbl"):
            self.sfx_lbl.setText(self._t("ui.sfx_vol", "SFX Volume") + ":")
        if hasattr(self, "fullscreen_lbl"):
            self.fullscreen_lbl.setText(self._t("ui.fullscreen", "Fullscreen") + ":")
        if hasattr(self, "vsync_lbl"):
            self.vsync_lbl.setText(self._t("ui.vsync", "VSync") + ":")
        if hasattr(self, "msaa_lbl"):
            self.msaa_lbl.setText(self._t("ui.msaa", "MSAA") + ":")
        if hasattr(self, "bloom_lbl"):
            self.bloom_lbl.setText(self._t("ui.bloom_intensity", "Bloom") + ":")
        if hasattr(self, "mouse_sens_row_lbl"):
            self.mouse_sens_row_lbl.setText(self._t("ui.mouse_sensitivity", "Mouse Sensitivity") + ":")
        if hasattr(self, "invert_y_lbl"):
            self.invert_y_lbl.setText(self._t("ui.invert_y", "Invert Y") + ":")
        if hasattr(self, "move_preset_lbl"):
            self.move_preset_lbl.setText(self._t("ui.move_preset", "Move Preset") + ":")
        self.btn_back["text"] = self._t("ui.back", "Back")
        self._refresh_advanced_settings_labels()
        if hasattr(self, "controls_title"):
            self.controls_title.setText(self._t("ui.controls_customization", "Controls Customization"))
        self._refresh_controls_hint()
        if hasattr(self, "controls_col_action"):
            self.controls_col_action.setText(self._t("ui.controls_action_col", "Action"))
        if hasattr(self, "controls_col_kbm"):
            self.controls_col_kbm.setText(self._t("ui.controls_kbm_col", "Keyboard/Mouse"))
        if hasattr(self, "controls_col_gp"):
            self.controls_col_gp.setText(self._t("ui.controls_gp_col", "Gamepad"))
        if hasattr(self, "controls_prev_btn"):
            self.controls_prev_btn["text"] = self._t("ui.prev", "Prev")
        if hasattr(self, "controls_next_btn"):
            self.controls_next_btn["text"] = self._t("ui.next", "Next")
        if hasattr(self, "controls_back_btn"):
            self.controls_back_btn["text"] = self._t("ui.back", "Back")
        self._refresh_controls_page()

        self.load_title.setText(self._t("ui.load_game", "Load Game"))
        self.load_hint.setText(self._t("ui.choose_slot", "Select a save slot"))
        self.load_back_btn["text"] = self._t("ui.back", "Back")

        self.save_title.setText(self._t("ui.save_game", "Save Game"))
        self.save_hint.setText(self._t("ui.choose_slot_save", "Select slot to overwrite"))
        self.save_back_btn["text"] = self._t("ui.back", "Back")

        self._refresh_load_slots()
        self._refresh_save_slots()
        self.set_loading(self._loading)

    def _animate_reveal(self):
        if self._reveal_seq:
            self._reveal_seq.pause()
            self._reveal_seq = None

        nodes = [self.title, self.subtitle, self.panel] + self._button_order
        for node in nodes:
            node.setColorScale(1, 1, 1, 0)

        seq = Sequence()
        for idx, node in enumerate(nodes):
            seq.append(Wait(0.06 if idx > 0 else 0.01))
            seq.append(
                LerpColorScaleInterval(
                    node,
                    0.20 if idx < 3 else 0.16,
                    (1, 1, 1, 1),
                    startColorScale=(1, 1, 1, 0),
                )
            )
        self._reveal_seq = seq
        self._reveal_seq.start()

    def _start_game(self, load_save=False, slot_index=None):
        # Ignore stale key/mouse events while intro is still active or menu is hidden.
        intro = getattr(self.app, "intro", None)
        if intro and not bool(getattr(intro, "_done", False)):
            return False
        if self.frame.isHidden():
            return False
        if getattr(self.app.state_mgr, "current_state", None) != self.app.GameState.MAIN_MENU:
            return False

        if hasattr(self.app, "start_play"):
            loaded = self.app.start_play(load_save=load_save, slot_index=slot_index)
            if load_save and not loaded:
                self.status.setText(self._t("ui.loading", "No save found"))
                return False
            return True

        self.hide()
        self.app.state_mgr.set_state(self.app.GameState.PLAYING)
        return True

    def _on_new_game(self):
        self._start_game(load_save=False)

    def _on_continue_game(self):
        if not self._has_save_data():
            self.status.setText(self._t("ui.loading", "No save found"))
            return
        self._start_game(load_save=True)

    def _on_load_game(self):
        if not self._has_save_data():
            self.status.setText(self._t("ui.loading", "No save found"))
            return
        self._refresh_load_slots()
        self._hide_overlays()
        self._hide_main_content()
        self.load_panel.show()
        self._refresh_button_focus_visuals()

    def _on_save_game(self):
        if not self._can_save_game():
            self.status.setText(self._t("ui.cannot_save_now", "Cannot save right now"))
            return
        self._refresh_save_slots()
        self._hide_overlays()
        self._hide_main_content()
        self.save_panel.show()
        self._refresh_button_focus_visuals()

    def _on_load_slot(self, slot_index):
        if self._loading:
            return
        loaded = self._start_game(load_save=True, slot_index=slot_index)
        if not loaded:
            self._refresh_load_slots()

    def _on_save_slot(self, slot_index):
        if self._loading or not self._can_save_game():
            return
        try:
            self.app.save_mgr.save_slot(slot_index)
        except Exception:
            self.status.setText(self._t("ui.save_failed", "Save failed"))
            return

        slot_num = int(slot_index)
        self.status.setText(f"{self._t('ui.saved_to_slot', 'Saved to slot')} {slot_num}")
        self._refresh_load_slots()
        self._refresh_save_slots()

        if hasattr(self.app, "hud") and self.app.hud:
            self.app.hud.set_autosave(True)
        if hasattr(self.app, "_autosave_flash_until"):
            try:
                self.app._autosave_flash_until = max(
                    self.app._autosave_flash_until,
                    globalClock.getFrameTime() + 1.2,
                )
            except Exception:
                pass

    def _on_settings(self):
        self._hide_overlays()
        self._hide_main_content()
        if self.settings_panel:
            self.settings_panel.show()
        self._refresh_button_focus_visuals()

    def _on_toggle_language(self):
        langs = self.app.data_mgr.get_available_languages()
        if len(langs) >= 2:
            current = self.app.data_mgr.get_language()
            idx = langs.index(current) if current in langs else 0
            new_lang = langs[(idx + 1) % len(langs)]
            self.app.data_mgr.set_language(new_lang)
            lang_code = str(new_lang).upper()
            self.lang_btn["text"] = self._t("ui.language", "Language") + f": {lang_code}"
            self.refresh_text()
            if hasattr(self.app, "hud") and self.app.hud:
                self.app.hud.refresh_locale()
            self.app.data_mgr.graphics_settings["language"] = new_lang
            self.app.data_mgr.save_settings("graphics_settings.json", self.app.data_mgr.graphics_settings)

    def _on_toggle_quality(self):
        if not hasattr(self, "_graphics_idx"):
            self._graphics_levels = ["Low", "Medium", "High", "Ultra"]
            self._graphics_idx = 1
        self._graphics_idx = (self._graphics_idx + 1) % len(self._graphics_levels)
        level = self._graphics_levels[self._graphics_idx]
        if hasattr(self, "quality_btn"):
            self.quality_btn["text"] = level
        if hasattr(self.app, "apply_graphics_quality"):
            self.app.apply_graphics_quality(level, persist=True)
        else:
            self.app.data_mgr.graphics_settings["quality"] = level
            self.app.data_mgr.save_settings("graphics_settings.json", self.app.data_mgr.graphics_settings)
        self._refresh_advanced_settings_labels()

    def _adjust_vol(self, channel, delta):
        self._play_ui_sfx("ui_click", volume=0.55, rate=1.0)
        if channel == "music":
            self._music_vol = max(0.0, min(1.0, getattr(self, "_music_vol", 0.8) + delta))
            if hasattr(self, "music_val_lbl"):
                self.music_val_lbl.setText(f"{int(self._music_vol * 100)}%")
            try:
                self.app.musicManager.setVolume(self._music_vol)
            except Exception:
                pass
            self.app.data_mgr.audio_settings["music"] = self._music_vol
            self.app.data_mgr.save_settings("audio_settings.json", self.app.data_mgr.audio_settings)
        elif channel == "sfx":
            self._sfx_vol = max(0.0, min(1.0, getattr(self, "_sfx_vol", 1.0) + delta))
            if hasattr(self, "sfx_val_lbl"):
                self.sfx_val_lbl.setText(f"{int(self._sfx_vol * 100)}%")
            try:
                self.app.sfxManagerList[0].setVolume(self._sfx_vol)
            except Exception:
                pass
            self.app.data_mgr.audio_settings["sfx"] = self._sfx_vol
            self.app.data_mgr.save_settings("audio_settings.json", self.app.data_mgr.audio_settings)

    def _persist_graphics_setting(self):
        gfx = self.app.data_mgr.graphics_settings
        if not isinstance(gfx, dict):
            gfx = {}
            self.app.data_mgr.graphics_settings = gfx
        self.app.data_mgr.save_settings("graphics_settings.json", gfx)

    def _ensure_player_key_listener(self, key_name):
        player = getattr(self.app, "player", None)
        token = str(key_name or "").strip().lower()
        if not player or not token or token == "none":
            return
        keys = getattr(player, "_keys", None)
        consumed = getattr(player, "_consumed", None)
        if not isinstance(keys, dict) or not isinstance(consumed, dict):
            return

        def _bind_key_once(token):
            if not token or token in keys:
                return
            keys[token] = False
            consumed[token] = False
            self.app.accept(token, player._key_down, [token])
            self.app.accept(f"{token}-up", player._key_up, [token])

        _bind_key_once(token)
        ru_map = getattr(player, "_ru_map", {})
        if isinstance(ru_map, dict):
            _bind_key_once(ru_map.get(token))

    def _apply_move_preset(self, preset):
        token = str(preset or "classic").strip().lower()
        if token not in {"classic", "arrows"}:
            token = "classic"
        if token == "arrows":
            mapping = {
                "forward": "arrow_up",
                "backward": "arrow_down",
                "left": "arrow_left",
                "right": "arrow_right",
            }
        else:
            mapping = {
                "forward": "w",
                "backward": "s",
                "left": "a",
                "right": "d",
            }

        controls = self.app.data_mgr.controls
        if not isinstance(controls, dict):
            controls = {}
            self.app.data_mgr.controls = controls
        bindings = controls.setdefault("bindings", {})
        meta = controls.setdefault("meta", {})
        if not isinstance(bindings, dict):
            bindings = {}
            controls["bindings"] = bindings
        if not isinstance(meta, dict):
            meta = {}
            controls["meta"] = meta
        for action, key_name in mapping.items():
            bindings[action] = key_name
            self._ensure_player_key_listener(key_name)
        meta["move_preset"] = token
        self._move_preset = token
        self.app.data_mgr.save_settings("controls.json", controls)

    def _refresh_advanced_settings_labels(self):
        on_txt = self._t("ui.on", "ON")
        off_txt = self._t("ui.off", "OFF")
        if hasattr(self, "fullscreen_btn"):
            self.fullscreen_btn["text"] = on_txt if bool(getattr(self, "_fullscreen_enabled", False)) else off_txt
        if hasattr(self, "vsync_btn"):
            self.vsync_btn["text"] = on_txt if bool(getattr(self, "_vsync_enabled", False)) else off_txt
        if hasattr(self, "invert_y_btn"):
            self.invert_y_btn["text"] = on_txt if bool(getattr(self, "_cam_invert_y", False)) else off_txt
        if hasattr(self, "msaa_val_lbl"):
            msaa = self._msaa_options[self._msaa_idx] if hasattr(self, "_msaa_options") else 0
            self.msaa_val_lbl.setText("OFF" if msaa <= 0 else f"{msaa}x")
        if hasattr(self, "bloom_val_lbl"):
            self.bloom_val_lbl.setText(f"{float(getattr(self, '_bloom_intensity', 1.2) or 1.2):.1f}")
        if hasattr(self, "mouse_sens_lbl"):
            self.mouse_sens_lbl.setText(f"{int(round(float(getattr(self, '_cam_mouse_sens', 150.0) or 150.0)))}")
        if hasattr(self, "move_preset_btn"):
            preset = str(getattr(self, "_move_preset", "classic") or "classic").lower()
            if preset == "arrows":
                self.move_preset_btn["text"] = self._t("ui.move_preset_arrows", "Arrows")
            else:
                self.move_preset_btn["text"] = self._t("ui.move_preset_classic", "Classic WASD")

    def _on_toggle_fullscreen_setting(self):
        try:
            self.app.toggle_fullscreen()
        except Exception:
            pass
        try:
            props = self.app.win.getProperties() if self.app.win else None
            self._fullscreen_enabled = bool(props and props.getFullscreen())
        except Exception:
            self._fullscreen_enabled = not bool(getattr(self, "_fullscreen_enabled", False))
        self._refresh_advanced_settings_labels()

    def _on_toggle_vsync(self):
        self._vsync_enabled = not bool(getattr(self, "_vsync_enabled", True))
        try:
            from panda3d.core import WindowProperties
            wp = WindowProperties()
            wp.setSyncVideo(bool(self._vsync_enabled))
            self.app.win.requestProperties(wp)
        except Exception:
            pass
        gfx = self.app.data_mgr.graphics_settings if isinstance(self.app.data_mgr.graphics_settings, dict) else {}
        gfx["vsync"] = bool(self._vsync_enabled)
        self.app.data_mgr.graphics_settings = gfx
        self._persist_graphics_setting()
        self._refresh_advanced_settings_labels()

    def _adjust_msaa(self, delta):
        if not hasattr(self, "_msaa_options") or not self._msaa_options:
            self._msaa_options = [0, 2, 4, 8]
            self._msaa_idx = 2
        self._msaa_idx = max(0, min(len(self._msaa_options) - 1, int(self._msaa_idx) + int(delta)))
        samples = int(self._msaa_options[self._msaa_idx])
        try:
            from panda3d.core import AntialiasAttrib
            if samples <= 0:
                self.app.render.setAntialias(0)
            else:
                self.app.render.setAntialias(AntialiasAttrib.MMultisample, samples)
        except Exception:
            pass
        gfx = self.app.data_mgr.graphics_settings if isinstance(self.app.data_mgr.graphics_settings, dict) else {}
        pbr = gfx.setdefault("pbr", {})
        if isinstance(pbr, dict):
            pbr["msaa_samples"] = samples
        self.app.data_mgr.graphics_settings = gfx
        self._persist_graphics_setting()
        self._refresh_advanced_settings_labels()

    def _adjust_bloom(self, delta):
        self._bloom_intensity = max(0.0, min(3.0, float(getattr(self, "_bloom_intensity", 1.2) or 1.2) + float(delta)))
        if hasattr(self.app, "screen_quad") and self.app.screen_quad:
            try:
                self.app.screen_quad.set_shader_input("bloom_intensity", self._bloom_intensity)
            except Exception:
                pass
        gfx = self.app.data_mgr.graphics_settings if isinstance(self.app.data_mgr.graphics_settings, dict) else {}
        pp = gfx.setdefault("post_processing", {})
        if isinstance(pp, dict):
            bloom = pp.setdefault("bloom", {})
            if isinstance(bloom, dict):
                bloom["intensity"] = self._bloom_intensity
        self.app.data_mgr.graphics_settings = gfx
        self._persist_graphics_setting()
        self._refresh_advanced_settings_labels()

    def _adjust_mouse_sens(self, delta):
        self._cam_mouse_sens = max(40.0, min(320.0, float(getattr(self, "_cam_mouse_sens", 150.0) or 150.0) + float(delta)))
        setattr(self.app, "_cam_mouse_sens", float(self._cam_mouse_sens))
        gfx = self.app.data_mgr.graphics_settings if isinstance(self.app.data_mgr.graphics_settings, dict) else {}
        camera = gfx.setdefault("camera", {})
        if isinstance(camera, dict):
            camera["mouse_sensitivity"] = float(self._cam_mouse_sens)
            camera["invert_y"] = bool(getattr(self, "_cam_invert_y", False))
        self.app.data_mgr.graphics_settings = gfx
        self._persist_graphics_setting()
        self._refresh_advanced_settings_labels()

    def _on_toggle_invert_y(self):
        self._cam_invert_y = not bool(getattr(self, "_cam_invert_y", False))
        setattr(self.app, "_cam_invert_y", bool(self._cam_invert_y))
        gfx = self.app.data_mgr.graphics_settings if isinstance(self.app.data_mgr.graphics_settings, dict) else {}
        camera = gfx.setdefault("camera", {})
        if isinstance(camera, dict):
            camera["mouse_sensitivity"] = float(getattr(self, "_cam_mouse_sens", 150.0))
            camera["invert_y"] = bool(self._cam_invert_y)
        self.app.data_mgr.graphics_settings = gfx
        self._persist_graphics_setting()
        self._refresh_advanced_settings_labels()

    def _on_toggle_move_preset(self):
        next_token = "arrows" if str(getattr(self, "_move_preset", "classic")) == "classic" else "classic"
        self._apply_move_preset(next_token)
        self._refresh_advanced_settings_labels()
        self._refresh_controls_page()

    def _on_close_settings(self):
        self._hide_overlays()
        self._show_main_content()
        self._refresh_button_focus_visuals()

    def _on_close_load_panel(self):
        self._hide_overlays()
        self._show_main_content()
        self._refresh_button_focus_visuals()

    def _on_close_save_panel(self):
        self._hide_overlays()
        self._show_main_content()
        self._refresh_button_focus_visuals()

    def _on_exit(self):
        self.app.userExit()

    def show(self):
        self._hide_overlays()
        self._show_main_content()
        self._apply_responsive_layout(self.app.getAspectRatio())
        self.refresh_text()
        self.frame.show()
        self._bind_menu_navigation()
        self._focused_button_idx = 0
        self._refresh_button_focus_visuals()
        self._animate_reveal()

    def hide(self):
        if self._reveal_seq:
            self._reveal_seq.pause()
            self._reveal_seq = None
        self._cancel_binding_capture(refresh=False)
        self._unbind_menu_navigation()
        self.frame.hide()

    def on_window_resized(self, aspect):
        self._apply_responsive_layout(aspect)

    def _apply_responsive_layout(self, aspect):
        aspect = max(1.25, min(3.2, float(aspect)))
        self.frame["frameSize"] = (-aspect, aspect, -1, 1)

        if self.background is not None:
            self.background["frameSize"] = (-aspect, aspect, -1, 1)

        self.panel.setPos(0, 0, -0.05)

        if self.darken is not None:
            self.darken["frameSize"] = (-aspect, aspect, -1, 1)

        ui_scale = max(0.9, min(1.1, aspect / 1.777777))
        self.title.setPos(0, 0.72)
        self.subtitle.setPos(0, 0.58)
        self.status.setPos(0, -0.88)
        self.nav_hint.setPos(0, -0.81)
        self.title.setScale(0.15 * ui_scale)
        self.subtitle.setScale(0.06 * ui_scale)
        self.nav_hint.setScale(0.031 * ui_scale)

        self._button_x = 0.0
        for i, button in enumerate(self._button_order):
            y = 0.08 - i * 0.14
            button.setPos(self._button_x, 0, y)
            button.setScale(0.11 * ui_scale)
            button["text_scale"] = 0.65
        self._refresh_button_focus_visuals()


class MainMenu(BaseMenu):
    """Main menu implementation built on top of BaseMenu."""

    pass
