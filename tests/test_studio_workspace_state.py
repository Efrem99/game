from launchers.studio_workspace_state import (
    filter_workspace_tree,
    record_recent_path,
    toggle_favorite_path,
)


def test_record_recent_path_moves_latest_to_front_and_deduplicates():
    paths = ["data/dialogues/merchant.json", "data/scenes/village_square.json"]

    updated = record_recent_path(paths, "data/scenes/village_square.json", limit=3)

    assert updated == [
        "data/scenes/village_square.json",
        "data/dialogues/merchant.json",
    ]


def test_toggle_favorite_path_adds_and_removes_entries():
    favorites = ["src/ui/menu_main.py"]

    added = toggle_favorite_path(favorites, "data/scenes/village_square.json")
    removed = toggle_favorite_path(added, "src/ui/menu_main.py")

    assert added == [
        "src/ui/menu_main.py",
        "data/scenes/village_square.json",
    ]
    assert removed == ["data/scenes/village_square.json"]


def test_filter_workspace_tree_keeps_matching_branches_only():
    tree = [
        {
            "label": "data",
            "relative_path": "data",
            "kind": "directory",
            "children": [
                {
                    "label": "dialogues",
                    "relative_path": "data/dialogues",
                    "kind": "directory",
                    "children": [
                        {
                            "label": "merchant.json",
                            "relative_path": "data/dialogues/merchant.json",
                            "kind": "file",
                            "children": [],
                        }
                    ],
                },
                {
                    "label": "scenes",
                    "relative_path": "data/scenes",
                    "kind": "directory",
                    "children": [
                        {
                            "label": "village_square.json",
                            "relative_path": "data/scenes/village_square.json",
                            "kind": "file",
                            "children": [],
                        }
                    ],
                },
            ],
        }
    ]

    filtered = filter_workspace_tree(tree, "merchant")

    assert [node["label"] for node in filtered] == ["data"]
    data_node = filtered[0]
    assert [child["label"] for child in data_node["children"]] == ["dialogues"]
    assert data_node["children"][0]["children"][0]["relative_path"] == "data/dialogues/merchant.json"
