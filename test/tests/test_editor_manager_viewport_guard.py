import sys
from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.editor_manager import EditorManager


def test_live_viewport_disabled_during_internal_capture(monkeypatch):
    monkeypatch.setenv("XBOT_INTERNAL_VIDEO_CAPTURE", "1")
    monkeypatch.delenv("XBOT_VIDEO_BOT", raising=False)

    manager = EditorManager.__new__(EditorManager)

    assert manager._should_enable_live_viewport() is False


def test_live_viewport_disabled_during_video_bot(monkeypatch):
    monkeypatch.delenv("XBOT_INTERNAL_VIDEO_CAPTURE", raising=False)
    monkeypatch.setenv("XBOT_VIDEO_BOT", "1")

    manager = EditorManager.__new__(EditorManager)

    assert manager._should_enable_live_viewport() is False


def test_live_viewport_enabled_for_normal_session(monkeypatch):
    monkeypatch.delenv("XBOT_INTERNAL_VIDEO_CAPTURE", raising=False)
    monkeypatch.delenv("XBOT_VIDEO_BOT", raising=False)

    manager = EditorManager.__new__(EditorManager)

    assert manager._should_enable_live_viewport() is True
