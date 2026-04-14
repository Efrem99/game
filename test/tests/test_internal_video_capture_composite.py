import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).absolute().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.core_runtime import HAS_CORE  # noqa: F401
from utils.internal_video_capture import InternalVideoCapture


class _FakeTexture:
    def __init__(self, raw=b"", bgra_raw=None):
        self._raw = raw
        self._bgra_raw = bgra_raw

    def hasRamImage(self):
        return bool(self._raw or self._bgra_raw)

    def getRamImage(self):
        return self._raw

    def getRamImageAs(self, fmt):
        if str(fmt).upper() != "BGRA" or self._bgra_raw is None:
            return b""
        return self._bgra_raw


class _FakeWindow:
    def __init__(self, screenshot_texture=None):
        self._screenshot_texture = screenshot_texture
        self.screenshot_calls = 0

    def getGsg(self):
        return object()

    def getScreenshot(self):
        self.screenshot_calls += 1
        return self._screenshot_texture


class _FakeGraphicsEngine:
    def __init__(self):
        self.extract_calls = []

    def extractTextureData(self, texture, gsg):
        self.extract_calls.append((texture, gsg))


class InternalVideoCaptureCompositeTests(unittest.TestCase):
    def _capture(self, screenshot_texture=None, offscreen_texture=None, frame_bytes=16):
        graphics = _FakeGraphicsEngine()
        capture = InternalVideoCapture.__new__(InternalVideoCapture)
        capture.app = SimpleNamespace(
            win=_FakeWindow(screenshot_texture=screenshot_texture),
            graphicsEngine=graphics,
        )
        capture._proc = SimpleNamespace(stdin=object())
        capture._buffer = object() if offscreen_texture is not None else None
        capture._texture = offscreen_texture
        capture._frame_bytes = int(frame_bytes)
        capture._warned_extract = False
        capture._warned_length = False
        return capture

    def test_read_current_frame_prefers_offscreen_buffer_when_available(self):
        composite = _FakeTexture(raw=b"A" * 16)
        offscreen = _FakeTexture(raw=b"B" * 16)
        capture = self._capture(
            screenshot_texture=composite,
            offscreen_texture=offscreen,
            frame_bytes=16,
        )
        capture._warned_window_fallback = False

        raw = InternalVideoCapture._read_current_frame(capture)

        self.assertEqual(b"B" * 16, raw)
        self.assertEqual(0, capture.app.win.screenshot_calls)
        self.assertEqual(1, len(capture.app.graphicsEngine.extract_calls))

    def test_read_current_frame_falls_back_to_window_screenshot_when_offscreen_missing(self):
        composite = _FakeTexture(raw=b"A" * 16)
        capture = self._capture(
            screenshot_texture=composite,
            offscreen_texture=None,
            frame_bytes=16,
        )
        capture._warned_window_fallback = False

        raw = InternalVideoCapture._read_current_frame(capture)

        self.assertEqual(b"A" * 16, raw)
        self.assertEqual(1, capture.app.win.screenshot_calls)
        self.assertEqual(0, len(capture.app.graphicsEngine.extract_calls))

    def test_read_current_frame_reorders_offscreen_texture_to_bgra_when_needed(self):
        offscreen = _FakeTexture(raw=b"C" * 12, bgra_raw=b"D" * 16)
        capture = self._capture(screenshot_texture=None, offscreen_texture=offscreen, frame_bytes=16)
        capture._warned_window_fallback = False

        raw = InternalVideoCapture._read_current_frame(capture)

        self.assertEqual(b"D" * 16, raw)

    def test_read_current_frame_reorders_window_texture_when_fallback_used(self):
        composite = _FakeTexture(raw=b"C" * 12, bgra_raw=b"D" * 16)
        capture = self._capture(screenshot_texture=composite, offscreen_texture=None, frame_bytes=16)
        capture._warned_window_fallback = False

        raw = InternalVideoCapture._read_current_frame(capture)

        self.assertEqual(b"D" * 16, raw)


if __name__ == "__main__":
    unittest.main()
