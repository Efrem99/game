import json
from pathlib import Path

from launchers.studio_preview import load_preview, save_preview_text


def test_load_preview_lists_directory_children(tmp_path: Path):
    (tmp_path / "quests").mkdir()
    (tmp_path / "quests" / "tutorial.json").write_text("{}", encoding="utf-8")
    (tmp_path / "quests" / "notes.txt").write_text("hello", encoding="utf-8")

    preview = load_preview(tmp_path, "quests")

    assert preview["kind"] == "directory"
    assert [child["relative_path"] for child in preview["children"]] == [
        "quests/notes.txt",
        "quests/tutorial.json",
    ]


def test_load_preview_builds_json_cards(tmp_path: Path):
    payload = {
        "id": "tutorial_quest",
        "title": "Tutorial Quest",
        "steps": [{"id": "move"}],
    }
    (tmp_path / "tutorial_quest.json").write_text(json.dumps(payload), encoding="utf-8")

    preview = load_preview(tmp_path, "tutorial_quest.json")

    assert preview["kind"] == "json"
    assert preview["editable"] is True
    assert any(card["title"] == "id" for card in preview["cards"])


def test_save_preview_text_writes_back(tmp_path: Path):
    path = tmp_path / "logic.json"
    path.write_text("{}", encoding="utf-8")

    saved = save_preview_text(tmp_path, "logic.json", '{\n  "ok": true\n}\n')

    assert saved.exists()
    assert '"ok": true' in path.read_text(encoding="utf-8")
