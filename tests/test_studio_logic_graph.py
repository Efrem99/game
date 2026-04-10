import json

from launchers.studio_logic_graph import (
    apply_logic_focus_patch,
    build_logic_focus_from_preview,
    build_logic_graph_from_preview,
    create_logic_node_from_preview,
    delete_logic_node_from_preview,
)


def test_build_logic_graph_from_dialogue_preview_creates_nodes_and_edges():
    payload = {
        "npc_id": "quest_giver_main",
        "dialogue_tree": {
            "start": {
                "speaker": "Elder Sophia",
                "text": "Welcome, traveler.",
                "choices": [
                    {
                        "text": "Tell me more.",
                        "next_node": "details",
                        "condition": "quest_active:tutorial_quest:false",
                    },
                    {
                        "text": "Goodbye.",
                        "next_node": "farewell",
                        "action": "end_dialogue",
                    },
                ],
            },
            "details": {
                "speaker": "Elder Sophia",
                "text": "The ruins need cleansing.",
                "next_node": "farewell",
            },
            "farewell": {
                "speaker": "Elder Sophia",
                "text": "May the light guide you.",
                "choices": [],
            },
        },
    }
    preview = {
        "kind": "json",
        "relative_path": "data/dialogues/quest_giver_dialogue.json",
        "raw_text": json.dumps(payload, indent=2),
    }

    graph = build_logic_graph_from_preview(preview)

    assert graph is not None
    assert graph["kind"] == "dialogue"
    assert graph["root_id"] == "start"
    assert [node["id"] for node in graph["nodes"]] == ["start", "details", "farewell"]


def test_build_logic_focus_from_preview_returns_selected_dialogue_node_details():
    preview = {
        "kind": "json",
        "relative_path": "data/dialogues/quest_giver_dialogue.json",
        "raw_text": json.dumps(
            {
                "npc_name": "Elder Sophia",
                "dialogue_tree": {
                    "start": {
                        "speaker": "Elder Sophia",
                        "text": "Welcome, traveler.",
                        "choices": [
                            {
                                "text": "Tell me more.",
                                "next_node": "details",
                                "condition": "quest_active:tutorial_quest:false",
                            },
                            {
                                "text": "Goodbye.",
                                "next_node": "farewell",
                                "action": "end_dialogue",
                            },
                        ],
                    },
                    "details": {
                        "speaker": "Elder Sophia",
                        "text": "The ruins need cleansing.",
                        "next_node": "farewell",
                    },
                    "farewell": {"speaker": "Elder Sophia", "text": "May the light guide you."},
                },
            },
            indent=2,
        ),
    }

    focus = build_logic_focus_from_preview(preview, "start")

    assert focus["node_id"] == "start"
    assert focus["choice_lines"] == (
        "Tell me more. -> details | if quest_active:tutorial_quest:false\n"
        "Goodbye. -> farewell | do end_dialogue"
    )


def test_apply_logic_focus_patch_updates_choice_lines_and_next_node():
    preview = {
        "kind": "json",
        "relative_path": "data/dialogues/quest_giver_dialogue.json",
        "raw_text": json.dumps(
            {
                "dialogue_tree": {
                    "start": {
                        "speaker": "Narrator",
                        "text": "Choose your path.",
                        "next_node": "old_exit",
                        "choices": [{"text": "Old line", "next_node": "old_target"}],
                    }
                }
            },
            indent=2,
        ),
    }

    updated = apply_logic_focus_patch(
        preview,
        "start",
        {
            "speaker": "Guide",
            "text": "Choose wisely.",
            "next_node": "",
            "choices_text": (
                "Accept the task. -> accept | if quest_ready | do give_quest:tutorial_quest\n"
                "Refuse for now. -> refuse | do end_dialogue"
            ),
        },
    )

    payload = json.loads(updated)
    assert payload["dialogue_tree"]["start"]["speaker"] == "Guide"
    assert payload["dialogue_tree"]["start"]["text"] == "Choose wisely."
    assert "next_node" not in payload["dialogue_tree"]["start"]
    assert payload["dialogue_tree"]["start"]["choices"][0]["condition"] == "quest_ready"


def test_create_logic_node_from_preview_adds_child_and_link():
    preview = {
        "kind": "json",
        "relative_path": "data/dialogues/quest_giver_dialogue.json",
        "raw_text": json.dumps(
            {
                "npc_name": "Elder Sophia",
                "dialogue_tree": {
                    "start": {
                        "speaker": "Elder Sophia",
                        "text": "Welcome.",
                        "choices": [],
                    }
                }
            },
            indent=2,
        ),
    }

    updated = create_logic_node_from_preview(preview, "start", "new_branch", link_text="Ask about the ruins")

    payload = json.loads(updated)
    assert "new_branch" in payload["dialogue_tree"]
    assert payload["dialogue_tree"]["start"]["choices"][0]["next_node"] == "new_branch"


def test_delete_logic_node_from_preview_removes_inbound_links():
    preview = {
        "kind": "json",
        "relative_path": "data/dialogues/quest_giver_dialogue.json",
        "raw_text": json.dumps(
            {
                "dialogue_tree": {
                    "start": {
                        "speaker": "Narrator",
                        "text": "Welcome.",
                        "choices": [{"text": "Continue", "next_node": "details"}],
                    },
                    "details": {
                        "speaker": "Narrator",
                        "text": "Details.",
                        "next_node": "farewell",
                    },
                    "farewell": {"speaker": "Narrator", "text": "Bye."},
                }
            },
            indent=2,
        ),
    }

    updated = delete_logic_node_from_preview(preview, "details")

    payload = json.loads(updated)
    assert "details" not in payload["dialogue_tree"]
    assert payload["dialogue_tree"]["start"]["choices"] == []
