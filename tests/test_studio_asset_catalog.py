from pathlib import Path

from launchers.studio_asset_catalog import (
    build_asset_catalog,
    build_asset_properties,
)


def test_build_asset_catalog_indexes_visual_and_script_assets(tmp_path: Path):
    (tmp_path / "assets" / "models").mkdir(parents=True)
    (tmp_path / "assets" / "textures").mkdir(parents=True)
    (tmp_path / "src" / "logic").mkdir(parents=True)
    (tmp_path / "assets" / "models" / "dragon.glb").write_text("stub", encoding="utf-8")
    (tmp_path / "assets" / "textures" / "icon.png").write_text("stub", encoding="utf-8")
    (tmp_path / "src" / "logic" / "quest_rule.py").write_text("def run():\n    return True\n", encoding="utf-8")

    catalog = build_asset_catalog(tmp_path, ["assets/models", "assets/textures", "src"])

    assert [entry["relative_path"] for entry in catalog] == [
        "assets/models/dragon.glb",
        "assets/textures/icon.png",
        "src/logic/quest_rule.py",
    ]
    assert catalog[0]["kind"] == "model"
    assert catalog[1]["kind"] == "image"
    assert catalog[2]["kind"] == "script"


def test_build_asset_catalog_respects_query_filter(tmp_path: Path):
    (tmp_path / "assets" / "textures").mkdir(parents=True)
    (tmp_path / "assets" / "textures" / "fire.png").write_text("stub", encoding="utf-8")
    (tmp_path / "assets" / "textures" / "ice.png").write_text("stub", encoding="utf-8")

    catalog = build_asset_catalog(tmp_path, ["assets/textures"], query="fire")

    assert [entry["relative_path"] for entry in catalog] == ["assets/textures/fire.png"]


def test_build_asset_properties_returns_previewable_metadata_for_image(tmp_path: Path):
    (tmp_path / "assets" / "textures").mkdir(parents=True)
    asset_path = tmp_path / "assets" / "textures" / "icon.png"
    asset_path.write_text("stub", encoding="utf-8")

    properties = build_asset_properties(
        tmp_path,
        {
            "relative_path": "assets/textures/icon.png",
            "kind": "image",
            "label": "icon.png",
            "source_root": "assets/textures",
        },
    )

    assert properties["kind"] == "asset"
    assert properties["fields"]["path"] == "assets/textures/icon.png"
    assert properties["fields"]["type"] == "image"
    assert properties["fields"]["preview_hint"] == "image"
