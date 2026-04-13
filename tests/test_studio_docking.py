from launchers.studio_docking import (
    find_panel_zone,
    move_panel,
    normalize_studio_dock_layout,
)


def test_normalize_studio_dock_layout_provides_default_panels():
    layout = normalize_studio_dock_layout({})

    assert layout["left"] == ["navigator"]
    assert layout["top"] == ["catalog", "graph", "overview"]
    assert layout["bottom"] == ["properties", "source"]


def test_move_panel_moves_between_zones_and_preserves_uniqueness():
    layout = normalize_studio_dock_layout({})

    updated = move_panel(layout, "source", "top", 0)

    assert updated["left"] == ["navigator"]
    assert updated["top"] == ["source", "catalog", "graph", "overview"]
    assert updated["bottom"] == ["properties"]
    assert find_panel_zone(updated, "source") == "top"
