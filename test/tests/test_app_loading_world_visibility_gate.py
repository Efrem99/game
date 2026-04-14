from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]


def _app_source_block(signature, next_signature):
    content = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    start = content.index(signature)
    end = content.index(next_signature, start)
    return content[start:end]


def test_main_menu_keeps_3d_world_hidden_until_gameplay_ready():
    intro_source = _app_source_block(
        "    def _on_intro_done(self):",
        "    def _collect_startup_preload_assets(self):",
    )
    start_loading_source = _app_source_block(
        "    def start_game_loading(self):",
        "    def _bootstrap_quests(self):",
    )
    finalize_source = _app_source_block(
        "    def _finalize_initialization(self):",
        "    def transition_to_location(self, loc_name):",
    )

    assert '_set_loading_world_visibility(False, reason="main-menu idle")' in intro_source

    hide_world_idx = start_loading_source.index(
        'self._set_loading_world_visibility(False, reason="startup loading")'
    )
    show_loading_idx = start_loading_source.index('self.loading_screen.show(context="startup")')
    assert hide_world_idx < show_loading_idx

    reveal_world_idx = finalize_source.index(
        'self._set_loading_world_visibility(True, reason="gameplay ready")'
    )
    hide_loading_idx = finalize_source.index("self.loading_screen.hide()")
    assert reveal_world_idx < hide_loading_idx


def test_location_transition_hides_3d_world_before_showing_loading_screen():
    transition_source = _app_source_block(
        "    def transition_to_location(self, loc_name):",
        "    def _start_world_rebuild(self, loc_name):",
    )

    hide_world_idx = transition_source.index(
        'Func(self._set_loading_world_visibility, False, "location transition")'
    )
    show_loading_idx = transition_source.index("Func(self.loading_screen.show, context_tag)")
    assert hide_world_idx < show_loading_idx


def test_loading_screen_background_is_fully_opaque():
    source = (ROOT / "src" / "ui" / "loading_screen.py").read_text(encoding="utf-8")
    assert "frameColor=(0.01, 0.01, 0.02, 1.0)" in source
