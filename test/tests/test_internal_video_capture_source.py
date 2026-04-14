from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]


def test_app_source_wires_internal_video_capture_manager():
    app_source = (ROOT / "src" / "app.py").read_text(encoding="utf-8")

    assert "from utils.internal_video_capture import InternalVideoCapture" in app_source
    assert "self._internal_video_capture = InternalVideoCapture(self)" in app_source
    assert '"internal_video_capture_task"' in app_source


def test_app_source_emits_ready_marker_expected_by_video_scenarios():
    app_source = (ROOT / "src" / "app.py").read_text(encoding="utf-8")

    assert "Final Vis - Playing: True, Loading:" in app_source


def test_internal_capture_module_uses_expected_env_contract():
    capture_source = (ROOT / "src" / "utils" / "internal_video_capture.py").read_text(encoding="utf-8")

    assert 'XBOT_INTERNAL_VIDEO_CAPTURE' in capture_source
    assert 'XBOT_INTERNAL_VIDEO_CAPTURE_FFMPEG' in capture_source
    assert 'XBOT_INTERNAL_VIDEO_CAPTURE_OUTPUT' in capture_source
    assert 'XBOT_INTERNAL_VIDEO_CAPTURE_START_FILE' in capture_source
    assert 'XBOT_INTERNAL_VIDEO_CAPTURE_STOP_FILE' in capture_source
    assert 'XBOT_INTERNAL_VIDEO_CAPTURE_STATUS_PATH' in capture_source


def test_internal_capture_source_binds_to_gameplay_camera_rig():
    capture_source = (ROOT / "src" / "utils" / "internal_video_capture.py").read_text(encoding="utf-8")

    assert "attachNewNode(capture_camera)" in capture_source
    assert "useCamera=self.app.cam" not in capture_source


def test_internal_capture_source_includes_render2d_overlay_camera():
    capture_source = (ROOT / "src" / "utils" / "internal_video_capture.py").read_text(encoding="utf-8")

    assert "_create_overlay_capture_camera" in capture_source
    assert "make_camera_2d = getattr(self.app, \"makeCamera2d\", None)" in capture_source
    assert "2D overlay capture enabled for HUD/aspect2d." in capture_source
