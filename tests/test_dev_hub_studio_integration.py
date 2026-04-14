from pathlib import Path


DEV_HUB_PATH = Path(r"C:\Users\efrem\.codex\worktrees\9259\Король Волшебник\dev_hub.pyw")
STUDIO_WINDOW_PATH = Path(r"C:\Users\efrem\.codex\worktrees\9259\Король Волшебник\dev\studio_window.py")


def test_dev_hub_embeds_visual_and_logic_studios():
    source = DEV_HUB_PATH.read_text(encoding="utf-8")

    assert "StudioShell" in source
    assert 'text="Visual Studio"' in source
    assert 'text="Logic Studio"' in source
    assert 'self._build_studio_tab("visual_studio")' in source
    assert 'self._build_studio_tab("logic_studio")' in source


def test_studio_shell_mentions_graph_and_story_inspectors():
    source = STUDIO_WINDOW_PATH.read_text(encoding="utf-8")

    assert "Flow Graph" in source
    assert "Authoring Tree" in source
    assert "Asset Catalog" in source
    assert "Properties" in source
    assert "create_script_node_from_preview" in source
    assert "insert_scene_asset_from_preview" in source
    assert "Drop onto the Flow Graph" in source
    assert "Choice Links" in source
    assert "Apply Node Changes" in source
    assert "Quest Inspector" in source
    assert "Scene Inspector" in source
    assert "Scene Placement" in source
    assert "Insert Into Scene" in source
    assert "Script Node Setup" in source
    assert "Create Script Node" in source
