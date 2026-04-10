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
