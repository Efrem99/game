from launchers.studio_node_catalog import build_logic_node_catalog, build_script_node_descriptor


def test_build_script_node_descriptor_for_python_asset():
    descriptor = build_script_node_descriptor(
        {
            "label": "quest_manager.py",
            "relative_path": "src/managers/quest_manager.py",
            "kind": "script",
            "source_root": "src",
            "extension": ".py",
        }
    )

    assert descriptor["kind"] == "script_node"
    assert descriptor["script_ref"] == "src/managers/quest_manager.py"
    assert descriptor["default_node_id"] == "quest_manager_node"
    assert descriptor["default_link_text"] == "Run Quest Manager"
    assert descriptor["category"] == "Managers"


def test_build_logic_node_catalog_filters_for_script_descriptors():
    entries = [
        {
            "label": "quest_manager.py",
            "relative_path": "src/managers/quest_manager.py",
            "kind": "script",
            "source_root": "src",
            "extension": ".py",
        },
        {
            "label": "forest.json",
            "relative_path": "data/scenes/forest.json",
            "kind": "data",
            "source_root": "data/scenes",
            "extension": ".json",
        },
        {
            "label": "dialog_runtime.lua",
            "relative_path": "src/dialog_runtime.lua",
            "kind": "script",
            "source_root": "src",
            "extension": ".lua",
        },
    ]

    catalog = build_logic_node_catalog(entries, query="dialog")

    assert [item["script_ref"] for item in catalog] == ["src/dialog_runtime.lua"]
