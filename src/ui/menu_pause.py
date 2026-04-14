from ui.menu_main import BaseMenu


class PauseMenu(BaseMenu):
    """In-game pause menu kept separate from the main menu."""

    def _build_buttons(self):
        self.btn_resume = self._make_button("ui.resume", 0.12, self._on_resume_game)
        self.btn_save = self._make_button("ui.save_game", -0.02, self._on_save_game)
        self.btn_load = self._make_button("ui.load_game", -0.16, self._on_load_game)
        self.btn_settings = self._make_button("ui.settings", -0.30, self._on_settings)
        self.btn_exit = self._make_button("ui.quit", -0.44, self._on_exit)
        self._button_order = [
            self.btn_resume,
            self.btn_save,
            self.btn_load,
            self.btn_settings,
            self.btn_exit,
        ]
        self._button_x = 0.0

    def set_loading(self, is_loading, status_text=None):
        self._loading = bool(is_loading)
        has_save = self._has_save_data()
        self._set_button_enabled(self.btn_resume, not self._loading)
        self._set_button_enabled(self.btn_save, (not self._loading) and self._can_save_game())
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
        self.title.setText(self._t("ui.paused", "PAUSED"))
        self.subtitle.setText(self._t("ui.pause_hint", "Game paused"))
        self.btn_resume["text"] = self._t("ui.resume", "Resume")
        self.btn_save["text"] = self._t("ui.save_game", "Save Game")
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

    def show(self):
        super().show()
        if hasattr(self.app, 'aspect2d'):
            self.app.aspect2d.show()

    def hide(self):
        super().hide()
        if hasattr(self.app, 'aspect2d') and self.app.state_mgr.current_state == self.app.GameState.PLAYING:
            self.app.aspect2d.hide()

    def _on_resume_game(self):
        if hasattr(self.app, "_hide_pause_menu"):
            self.app._hide_pause_menu()
        else:
            self.hide()
            self.app.state_mgr.set_state(self.app.GameState.PLAYING)
