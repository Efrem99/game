from launchers.studio_manifest import (
    get_studio_definition,
    list_studio_keys,
    normalize_studio_manifest,
    resolve_studio_key,
)


def test_normalize_studio_manifest_preserves_known_studios():
    manifest = normalize_studio_manifest(
        {
            "studios": {
                "logic_studio": {
                    "title": "Logic Studio",
                    "workspaces": [{"title": "Dialogues", "paths": ["data/dialogues"]}],
                }
            }
        }
    )

    assert "logic_studio" in manifest["studios"]
    assert "visual_studio" in manifest["studios"]


def test_list_and_resolve_studio_keys_are_stable():
    manifest = normalize_studio_manifest({})

    assert list_studio_keys(manifest) == ["logic_studio", "visual_studio"]
    assert resolve_studio_key(manifest, "visual_studio") == "visual_studio"
    assert resolve_studio_key(manifest, "missing") == "logic_studio"


def test_get_studio_definition_returns_default_shape():
    studio = get_studio_definition(normalize_studio_manifest({}), "logic_studio")

    assert studio["title"] == "Logic Studio"
    assert isinstance(studio["workspaces"], list)


def test_default_manifest_exposes_asset_roots_for_both_studios():
    manifest = normalize_studio_manifest({})

    visual = get_studio_definition(manifest, "visual_studio")
    logic = get_studio_definition(manifest, "logic_studio")

    assert "asset_roots" in visual
    assert "assets/models" in visual["asset_roots"]
    assert "assets/textures" in visual["asset_roots"]
    assert "asset_roots" in logic
    assert "src" in logic["asset_roots"]
