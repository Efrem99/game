from launchers.studio_session import build_studio_session_payload


def test_build_studio_session_payload_normalizes_layout_and_paths():
    payload = build_studio_session_payload(
        studio_key="logic_studio",
        active_path="data/dialogues/quest_giver_dialogue.json",
        dock_layout={"left": ["source"], "top": ["graph"], "bottom": ["navigator"]},
    )

    assert payload["studio_key"] == "logic_studio"
    assert payload["active_path"] == "data/dialogues/quest_giver_dialogue.json"
    assert payload["dock_layout"]["left"] == ["source"]
    assert payload["dock_layout"]["top"] == ["graph", "catalog", "overview"]
    assert payload["dock_layout"]["bottom"] == ["navigator", "properties"]


def test_build_studio_session_payload_handles_empty_inputs():
    payload = build_studio_session_payload(studio_key="", active_path="", dock_layout={})

    assert payload["studio_key"] == ""
    assert payload["active_path"] == ""
    assert payload["dock_layout"]["left"] == ["navigator"]


def test_build_studio_session_payload_persists_favorites_and_recent_paths():
    payload = build_studio_session_payload(
        studio_key="visual_studio",
        active_path="data/scenes/village_square.json",
        dock_layout={"left": ["navigator"], "top": ["graph"], "bottom": ["source"]},
        favorite_paths=["src/ui/menu_main.py", "data/scenes/village_square.json", "src/ui/menu_main.py"],
        recent_paths=["data/dialogues/merchant.json", "data/scenes/village_square.json", ""],
    )

    assert payload["favorite_paths"] == [
        "src/ui/menu_main.py",
        "data/scenes/village_square.json",
    ]
    assert payload["recent_paths"] == [
        "data/dialogues/merchant.json",
        "data/scenes/village_square.json",
    ]
