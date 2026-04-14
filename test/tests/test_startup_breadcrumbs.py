import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.startup_breadcrumbs import write_startup_breadcrumb


def test_write_startup_breadcrumb_appends_stage_entries():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_startup_breadcrumb(root, "before_showbase_init")
        write_startup_breadcrumb(root, "after_showbase_init", {"has_window": True})

        log_path = root / "logs" / "startup_breadcrumbs.jsonl"
        lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert [row["stage"] for row in lines] == ["before_showbase_init", "after_showbase_init"]
    assert lines[1]["context"]["has_window"] is True


def test_app_source_includes_showbase_startup_breadcrumbs():
    content = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    assert "before_showbase_init" in content
    assert "after_showbase_init" in content
    assert "graphics_window_ready" in content


def test_bootstrap_source_includes_constructor_breadcrumbs():
    content = (ROOT / "launchers" / "bootstrap.py").read_text(encoding="utf-8")
    assert "before_xbotapp_ctor" in content
    assert "after_xbotapp_ctor" in content
