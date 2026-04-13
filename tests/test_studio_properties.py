from launchers.studio_properties import build_properties_payload


def test_build_properties_payload_prefers_asset_selection():
    payload = build_properties_payload(
        preview={"relative_path": "data/scenes/forest.json", "kind": "json", "editable": True},
        asset_properties={
            "kind": "asset",
            "title": "dragon.glb",
            "fields": {"path": "assets/models/dragon.glb", "type": "model"},
            "cards": [{"title": "Asset", "body": "dragon"}],
        },
    )

    assert payload["kind"] == "asset"
    assert payload["fields"]["path"] == "assets/models/dragon.glb"


def test_build_properties_payload_builds_preview_metadata_when_no_selection():
    payload = build_properties_payload(
        preview={
            "title": "forest.json",
            "relative_path": "data/scenes/forest.json",
            "kind": "json",
            "editable": True,
            "raw_text": "{\n  \"name\": \"Forest\"\n}\n",
        },
    )

    assert payload["kind"] == "preview"
    assert payload["fields"]["path"] == "data/scenes/forest.json"
    assert payload["fields"]["editable"] == "yes"
