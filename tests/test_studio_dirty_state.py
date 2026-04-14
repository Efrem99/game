from launchers.studio_dirty_state import (
    compose_preview_status,
    decorate_preview_title,
    is_source_dirty,
    normalize_source_text,
)


def test_normalize_source_text_flattens_windows_newlines():
    assert normalize_source_text("a\r\nb\r\n") == "a\nb\n"


def test_is_source_dirty_ignores_newline_style_only_changes():
    assert is_source_dirty(
        persisted_text="{\r\n  \"ok\": true\r\n}\r\n",
        buffer_text="{\n  \"ok\": true\n}\n",
        editable=True,
    ) is False


def test_is_source_dirty_respects_editable_flag():
    assert is_source_dirty(persisted_text="{}", buffer_text='{"changed": true}', editable=False) is False


def test_decorate_preview_title_marks_unsaved_selection():
    assert decorate_preview_title("Quest Dialogue", dirty=True) == "Quest Dialogue *"
    assert decorate_preview_title("Quest Dialogue", dirty=False) == "Quest Dialogue"


def test_compose_preview_status_appends_unsaved_hint_when_needed():
    assert compose_preview_status("Saved to canonical source file.", dirty=False) == "Saved to canonical source file."
    assert compose_preview_status("Selected graph node: intro", dirty=True) == "Selected graph node: intro Unsaved changes pending."
    assert compose_preview_status("Created script node intro. Save to persist.", dirty=True) == "Created script node intro. Save to persist."
