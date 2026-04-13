import json

from launchers.studio_story_inspector import (
    apply_story_focus_patch,
    build_story_graph_from_preview,
    build_story_focus_from_preview,
    insert_scene_asset_from_preview,
)


def test_build_story_focus_from_quest_preview_returns_editable_fields():
    preview = {
        "kind": "json",
        "relative_path": "data/quests/tutorial_quest.json",
        "raw_text": json.dumps(
            {
                "id": "tutorial_quest",
                "title": "First Steps",
                "description": "Learn the basics.",
                "objectives": [{"type": "kill"}],
                "rewards": {"gold": 50},
            }
        ),
    }

    focus = build_story_focus_from_preview(preview)

    assert focus["kind"] == "quest"
    assert focus["fields"]["title"] == "First Steps"
    assert focus["fields"]["description"] == "Learn the basics."
    assert any(card["title"] == "Objectives" for card in focus["cards"])


def test_build_story_focus_from_scene_preview_returns_environment_fields():
    preview = {
        "kind": "json",
        "relative_path": "data/scenes/forest.json",
        "raw_text": json.dumps(
            {
                "id": "forest",
                "name": "Dark Forest",
                "description": "A mysterious forest",
                "environment": {"time_of_day": "dusk", "weather": "cloudy"},
                "props": [{"type": "chest"}],
                "enemies": [{"type": "wolf"}],
            }
        ),
    }

    focus = build_story_focus_from_preview(preview)

    assert focus["kind"] == "scene"
    assert focus["fields"]["name"] == "Dark Forest"
    assert focus["fields"]["time_of_day"] == "dusk"
    assert focus["fields"]["weather"] == "cloudy"


def test_apply_story_focus_patch_updates_quest_fields():
    preview = {
        "kind": "json",
        "relative_path": "data/quests/tutorial_quest.json",
        "raw_text": json.dumps(
            {
                "id": "tutorial_quest",
                "title": "First Steps",
                "description": "Learn the basics.",
            },
            indent=2,
        ),
    }

    updated = apply_story_focus_patch(
        preview,
        {
            "title": "Advanced Steps",
            "description": "Master the basics.",
        },
    )

    payload = json.loads(updated)
    assert payload["title"] == "Advanced Steps"
    assert payload["description"] == "Master the basics."


def test_build_story_graph_from_quest_preview_returns_objectives_and_rewards():
    preview = {
        "kind": "json",
        "relative_path": "data/quests/tutorial_quest.json",
        "raw_text": json.dumps(
            {
                "id": "tutorial_quest",
                "title": "First Steps",
                "description": "Learn the basics.",
                "objectives": [
                    {"type": "kill", "target": "enemy", "count": 3, "description": "Defeat 3 enemies"},
                    {"type": "explore", "target": "area", "count": 1, "description": "Explore the training ground"},
                ],
                "rewards": {"gold": 50, "experience": 100, "items": ["herb_bundle"]},
                "prerequisites": ["intro_complete"],
            }
        ),
    }

    graph = build_story_graph_from_preview(preview)

    assert graph is not None
    assert graph["kind"] == "quest"
    assert graph["root_id"] == "quest"
    assert [node["id"] for node in graph["nodes"]] == [
        "quest",
        "objective:0",
        "objective:1",
        "rewards",
        "prerequisites",
    ]


def test_build_story_focus_from_quest_objective_node_returns_objective_fields():
    preview = {
        "kind": "json",
        "relative_path": "data/quests/tutorial_quest.json",
        "raw_text": json.dumps(
            {
                "id": "tutorial_quest",
                "title": "First Steps",
                "description": "Learn the basics.",
                "objectives": [
                    {"type": "kill", "target": "enemy", "count": 3, "description": "Defeat 3 enemies"},
                ],
                "rewards": {"gold": 50},
            }
        ),
    }

    focus = build_story_focus_from_preview(preview, "objective:0")

    assert focus["kind"] == "quest_objective"
    assert focus["fields"]["type"] == "kill"
    assert focus["fields"]["target"] == "enemy"
    assert focus["fields"]["count"] == "3"
    assert focus["fields"]["description"] == "Defeat 3 enemies"


def test_apply_story_focus_patch_updates_scene_environment_and_spawn_nodes():
    preview = {
        "kind": "json",
        "relative_path": "data/scenes/forest.json",
        "raw_text": json.dumps(
            {
                "id": "forest",
                "name": "Dark Forest",
                "description": "A mysterious forest",
                "spawn_point": [0, 0, 0],
                "environment": {"time_of_day": "dusk", "weather": "cloudy"},
            },
            indent=2,
        ),
    }

    updated_environment = apply_story_focus_patch(
        preview,
        {
            "time_of_day": "night",
            "weather": "storm",
        },
        node_id="environment",
    )
    updated_spawn = apply_story_focus_patch(
        {
            "kind": "json",
            "relative_path": "data/scenes/forest.json",
            "raw_text": updated_environment,
        },
        {
            "x": "12",
            "y": "-5",
            "z": "3",
        },
        node_id="spawn_point",
    )

    payload = json.loads(updated_spawn)
    assert payload["environment"]["time_of_day"] == "night"
    assert payload["environment"]["weather"] == "storm"
    assert payload["spawn_point"] == [12.0, -5.0, 3.0]


def test_insert_scene_asset_from_preview_appends_canonical_prop_entry():
    preview = {
        "kind": "json",
        "relative_path": "data/scenes/forest.json",
        "raw_text": json.dumps(
            {
                "id": "forest",
                "name": "Dark Forest",
                "props": [{"type": "chest", "position": [12, 8, 0]}],
                "environment": {"time_of_day": "dusk", "weather": "cloudy"},
            },
            indent=2,
        ),
    }
    asset_entry = {
        "label": "oak_tree.glb",
        "relative_path": "assets/models/forest/oak_tree.glb",
        "kind": "model",
        "source_root": "assets/models",
        "extension": ".glb",
    }

    updated = insert_scene_asset_from_preview(preview, asset_entry)

    payload = json.loads(updated)
    inserted = payload["props"][-1]
    assert inserted["type"] == "oak_tree"
    assert inserted["asset"] == "assets/models/forest/oak_tree.glb"
    assert inserted["asset_kind"] == "model"
    assert inserted["position"] == [0.0, 0.0, 0.0]
    assert inserted["rotation"] == [0.0, 0.0, 0.0]
    assert inserted["scale"] == [1.0, 1.0, 1.0]
