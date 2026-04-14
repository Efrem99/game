from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]


def test_app_source_supports_env_window_title_override():
    content = (ROOT / "src" / "app.py").read_text(encoding="utf-8")

    assert 'os.environ.get("XBOT_WINDOW_TITLE"' in content
    assert 'loadPrcFileData("", f"window-title {_WINDOW_TITLE}")' in content
    assert "props.setTitle(_WINDOW_TITLE)" in content
