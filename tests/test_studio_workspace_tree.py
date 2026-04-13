from pathlib import Path

from launchers.studio_workspace_tree import build_workspace_tree


def test_build_workspace_tree_merges_workspace_paths_under_shared_roots(tmp_path: Path):
    (tmp_path / "data" / "dialogues").mkdir(parents=True)
    (tmp_path / "data" / "quests").mkdir(parents=True)
    (tmp_path / "src" / "ui").mkdir(parents=True)
    (tmp_path / "data" / "dialogues" / "merchant.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "quests" / "tutorial_quest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src" / "ui" / "menu_main.py").write_text("print('ok')", encoding="utf-8")

    tree = build_workspace_tree(
        tmp_path,
        [
            "data/dialogues",
            "data/quests",
            "src/ui",
        ],
    )

    assert [node["label"] for node in tree] == ["data", "src"]
    data_node = tree[0]
    assert [child["label"] for child in data_node["children"]] == ["dialogues", "quests"]
    assert data_node["children"][0]["children"][0]["relative_path"] == "data/dialogues/merchant.json"
    assert data_node["children"][1]["children"][0]["relative_path"] == "data/quests/tutorial_quest.json"
    assert tree[1]["children"][0]["children"][0]["relative_path"] == "src/ui/menu_main.py"


def test_build_workspace_tree_skips_missing_paths_and_keeps_direct_files(tmp_path: Path):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "README.md").write_text("# Studio", encoding="utf-8")
    (tmp_path / "docs" / "notes.md").write_text("hello", encoding="utf-8")

    tree = build_workspace_tree(
        tmp_path,
        [
            "README.md",
            "docs",
            "missing/path",
        ],
    )

    assert [node["label"] for node in tree] == ["README.md", "docs"]
    assert tree[0]["kind"] == "file"
    assert tree[0]["relative_path"] == "README.md"
    assert tree[1]["kind"] == "directory"
    assert tree[1]["children"][0]["relative_path"] == "docs/notes.md"
