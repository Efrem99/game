import os
from datetime import datetime
from pathlib import Path

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from direct.showbase.ShowBaseGlobal import globalClock
from direct.interval.IntervalGlobal import LerpColorScaleInterval, Sequence, Wait
from panda3d.core import TextNode, TransparencyAttrib

from ui.design_system import (
    BUTTON_COLORS,
    THEME,
    ParchmentPanel,
    body_font,
    get_parchment_texture_path,
    place_ui_on_top,
    title_font,
)


class BaseMenu:
    def __init__(self, app):
        self.app = app
        self._reveal_seq = None
        self._loading = False

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
        self.load_panel = None
        self.save_panel = None
        self.load_slot_buttons = []
        self.save_slot_buttons = []

        self._build_background(asp)
        self._build_layout()
        self._build_buttons()
        self._build_settings()
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

        self.darken = DirectFrame(
            frameColor=(0, 0, 0, 0.20),
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

    def _btn_texture_set(self):
        tex_off = "assets_raw/textures/ui/button_ready_off.png"
        tex_on = "assets_raw/textures/ui/button_ready_on.png"
        if os.path.exists(tex_off) and os.path.exists(tex_on):
            return (tex_off, tex_on, tex_on, tex_off)
        return None

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
            command=command,
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

        def _hover_on(evt):
            btn["text_fg"] = THEME["gold_primary"]
        def _hover_off(evt):
            btn["text_fg"] = BUTTON_COLORS["normal"]
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

    def _build_settings(self):
        self.settings_panel = ParchmentPanel(
            self.app,
            parent=self.frame,
            frameSize=(-0.68, 0.68, -0.70, 0.52),
            pos=(0, 0, 0),
            sort=50,
        )
        self.settings_panel.hide()

        t_font = title_font(self.app)
        b_font = body_font(self.app)

        self.settings_title = OnscreenText(
            text=self._t("ui.settings", "Settings"),
            pos=(0, 0.38),
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
            pos=(0, 0, 0.22),
            frameColor=(0.10, 0.08, 0.05, 0.4),
            frameSize=(-0.55, 0.55, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_language,
            parent=self.settings_panel,
        )

        # Graphics quality
        self._graphics_levels = ["Low", "Medium", "High", "Ultra"]
        current_quality = str(getattr(self.app, "_gfx_quality", "Medium") or "Medium").title()
        if current_quality not in self._graphics_levels:
            current_quality = "Medium"
        self._graphics_idx = self._graphics_levels.index(current_quality)
        OnscreenText(
            text=self._t("ui.quality", "Graphics Quality") + ":",
            pos=(-0.52, 0.07),
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
            pos=(0.30, 0, 0.07),
            frameColor=(0.10, 0.08, 0.05, 0.5),
            frameSize=(-0.28, 0.28, -0.055, 0.055),
            relief=DGG.FLAT,
            command=self._on_toggle_quality,
            parent=self.settings_panel,
        )

        # Music volume
        self._music_vol = self.app.data_mgr.audio_settings.get("music", 0.8)
        OnscreenText(
            text=self._t("ui.music_vol", "Music Volume") + ":",
            pos=(-0.52, -0.07),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        DirectButton(
            text="-", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.04, 0, -0.07), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("music", -0.1), parent=self.settings_panel,
        )
        self.music_val_lbl = OnscreenText(
            text=f"{int(self._music_vol * 100)}%", pos=(0.22, -0.07), scale=0.052,
            fg=THEME["gold_soft"], align=TextNode.ACenter,
            parent=self.settings_panel, mayChange=True, font=b_font,
        )
        DirectButton(
            text="+", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.40, 0, -0.07), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("music", 0.1), parent=self.settings_panel,
        )

        # SFX volume
        self._sfx_vol = self.app.data_mgr.audio_settings.get("sfx", 1.0)
        OnscreenText(
            text=self._t("ui.sfx_vol", "SFX Volume") + ":",
            pos=(-0.52, -0.22),
            scale=0.047,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.settings_panel,
            font=b_font,
        )
        DirectButton(
            text="-", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.04, 0, -0.22), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("sfx", -0.1), parent=self.settings_panel,
        )
        self.sfx_val_lbl = OnscreenText(
            text="100%", pos=(0.22, -0.22), scale=0.052,
            fg=THEME["gold_soft"], align=TextNode.ACenter,
            parent=self.settings_panel, mayChange=True, font=b_font,
        )
        DirectButton(
            text="+", text_fg=THEME["text_main"], text_scale=0.08, text_font=b_font,
            pos=(0.40, 0, -0.22), frameColor=(0.10,0.08,0.05,0.5),
            frameSize=(-0.06,0.06,-0.05,0.05), relief=DGG.FLAT,
            command=lambda: self._adjust_vol("sfx", 0.1), parent=self.settings_panel,
        )

        # --- Back ---
        self.btn_back = DirectButton(
            text=self._t("ui.back", "Back"),
            text_fg=THEME["text_accent"],
            text_scale=0.07,
            text_font=b_font,
            pos=(0, 0, -0.55),
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            command=self._on_close_settings,
            parent=self.settings_panel,
        )

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
        candidates = [
            Path("saves/slot1.json"),
            Path("saves/slot2.json"),
            Path("saves/slot3.json"),
            Path("saves/latest.json"),
            Path("saves/autosave.json"),
            Path("savegame.json"),
        ]
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
        for idx in range(1, 4):
            path = Path(f"saves/slot{idx}.json")
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

    def _show_main_content(self):
        self.panel.show()
        self.title.show()
        self.subtitle.show()
        for button in self._button_order:
            button.show()

    def _hide_main_content(self):
        self.panel.hide()
        self.title.hide()
        self.subtitle.hide()
        for button in self._button_order:
            button.hide()

    def _hide_overlays(self):
        if self.settings_panel:
            self.settings_panel.hide()
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

        self.settings_title.setText(self._t("ui.settings", "Settings"))
        lang_code = str(self.app.data_mgr.get_language()).upper()
        self.lang_btn["text"] = f"{self._t('ui.language', 'Language')}: {lang_code}"
        self.btn_back["text"] = self._t("ui.back", "Back")

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

    def _on_save_game(self):
        if not self._can_save_game():
            self.status.setText(self._t("ui.cannot_save_now", "Cannot save right now"))
            return
        self._refresh_save_slots()
        self._hide_overlays()
        self._hide_main_content()
        self.save_panel.show()

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

    def _adjust_vol(self, channel, delta):
        audio = getattr(self.app, "audio", None)
        if audio:
            try:
                audio.play_sfx("ui_click", volume=0.55)
            except Exception:
                pass
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

    def _on_close_settings(self):
        self._hide_overlays()
        self._show_main_content()

    def _on_close_load_panel(self):
        self._hide_overlays()
        self._show_main_content()

    def _on_close_save_panel(self):
        self._hide_overlays()
        self._show_main_content()

    def _on_exit(self):
        self.app.userExit()

    def show(self):
        self._hide_overlays()
        self._show_main_content()
        self._apply_responsive_layout(self.app.getAspectRatio())
        self.refresh_text()
        self.frame.show()
        self._animate_reveal()

    def hide(self):
        if self._reveal_seq:
            self._reveal_seq.pause()
            self._reveal_seq = None
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
        self.title.setScale(0.15 * ui_scale)
        self.subtitle.setScale(0.06 * ui_scale)

        self._button_x = 0.0
        for i, button in enumerate(self._button_order):
            y = 0.08 - i * 0.14
            button.setPos(self._button_x, 0, y)
            button.setScale(0.11 * ui_scale)
            button["text_scale"] = 0.65


class MainMenu(BaseMenu):
    """Main menu implementation built on top of BaseMenu."""

    pass
