"""Internal gameplay video capture for minimized-window-safe test runs."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from panda3d.core import Camera, Texture

from utils.logger import logger


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "1" if default else "0") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class InternalVideoCapture:
    """Pipe render frames from Panda3D directly into ffmpeg.

    This path is intended for automated gameplay capture where a desktop/window
    grabber would fail once the game window is minimized or occluded.
    """

    def __init__(self, app):
        self.app = app
        self.enabled = _env_flag("XBOT_INTERNAL_VIDEO_CAPTURE", False)
        self.ffmpeg_path = str(os.environ.get("XBOT_INTERNAL_VIDEO_CAPTURE_FFMPEG", "") or "").strip()
        self.output_path = str(os.environ.get("XBOT_INTERNAL_VIDEO_CAPTURE_OUTPUT", "") or "").strip()
        self.start_file = str(os.environ.get("XBOT_INTERNAL_VIDEO_CAPTURE_START_FILE", "") or "").strip()
        self.stop_file = str(os.environ.get("XBOT_INTERNAL_VIDEO_CAPTURE_STOP_FILE", "") or "").strip()
        self.status_path = str(os.environ.get("XBOT_INTERNAL_VIDEO_CAPTURE_STATUS_PATH", "") or "").strip()
        self.video_filter = str(os.environ.get("XBOT_INTERNAL_VIDEO_CAPTURE_FILTER", "") or "").strip()
        self._thread_budget = self._parse_thread_budget(os.environ.get("XBOT_FFMPEG_THREADS", "2"))
        self._capture_started = False
        self._capture_stopped = False
        self._frames_written = 0
        self._start_perf = 0.0
        self._next_frame_at = 0.0
        self._capture_width = 0
        self._capture_height = 0
        self._frame_bytes = 0
        self._proc = None
        self._stderr_handle = None
        self._texture = None
        self._buffer = None
        self._capture_cam = None
        self._capture_cam2d = None
        self._last_frame_bytes = None
        self._warned_extract = False
        self._warned_length = False
        self._warned_window_fallback = False
        self._status = {
            "enabled": bool(self.enabled),
            "started": False,
            "stopped": False,
            "frames_written": 0,
            "ffmpeg_exit_code": None,
            "output_path": self.output_path,
            "error": None,
            "reason": "idle",
            "fps": self._resolve_fps(),
            "width": None,
            "height": None,
        }
        if not self.enabled:
            return
        if not self.ffmpeg_path or not self.output_path:
            self.enabled = False
            self._status["enabled"] = False
            self._status["error"] = "missing ffmpeg path or output path"
            self._status["reason"] = "invalid-config"
            self._write_status()
            logger.warning("[InternalCapture] Disabled: missing ffmpeg path or output path.")
            return
        self._safe_unlink(self.start_file)
        self._safe_unlink(self.stop_file)
        self._safe_unlink(self.output_path)
        self._write_status()

    def _parse_thread_budget(self, raw) -> int:
        try:
            value = int(str(raw).strip())
        except Exception:
            return 2
        return max(1, value)

    def _resolve_fps(self) -> int:
        try:
            return max(1, int(str(os.environ.get("XBOT_INTERNAL_VIDEO_CAPTURE_FPS", "30")).strip()))
        except Exception:
            return 30

    @property
    def fps(self) -> int:
        return int(self._status.get("fps", 30) or 30)

    def update(self) -> None:
        if not self.enabled or self._capture_stopped:
            return
        if not self._capture_started:
            if self.stop_file and os.path.exists(self.stop_file):
                self._capture_stopped = True
                self._status["stopped"] = True
                self._status["reason"] = "stop-before-start"
                self._write_status()
                return
            if self.start_file and not os.path.exists(self.start_file):
                return
            self._start_capture()
            return
        if self._proc and self._proc.poll() is not None:
            code = self._proc.returncode
            self._capture_stopped = True
            self._status["stopped"] = True
            self._status["ffmpeg_exit_code"] = code
            self._status["error"] = f"ffmpeg exited early with code {code}"
            self._status["reason"] = "ffmpeg-exited-early"
            self._write_status()
            logger.error(f"[InternalCapture] ffmpeg exited early with code {code}.")
            return
        if self.stop_file and os.path.exists(self.stop_file):
            self.stop("stop-file")
            return
        self._capture_due_frames()

    def stop(self, reason: str = "manual") -> None:
        if not self.enabled or self._capture_stopped:
            return
        self._capture_stopped = True
        self._status["stopped"] = True
        self._status["reason"] = str(reason or "manual")
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=12)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._status["ffmpeg_exit_code"] = self._proc.returncode
            if self._proc.returncode not in (0, None) and not self._status.get("error"):
                self._status["error"] = f"ffmpeg exited with code {self._proc.returncode}"
        if self._stderr_handle is not None:
            try:
                self._stderr_handle.close()
            except Exception:
                pass
            self._stderr_handle = None
        if self._buffer is not None:
            try:
                self.app.graphicsEngine.removeWindow(self._buffer)
            except Exception:
                pass
            self._buffer = None
        self._capture_cam = None
        self._capture_cam2d = None
        self._write_status()
        logger.info(
            f"[InternalCapture] Stopped reason={self._status['reason']} frames={self._frames_written} "
            f"exit={self._status.get('ffmpeg_exit_code')}"
        )

    def _start_capture(self) -> None:
        win = getattr(self.app, "win", None)
        gsg = win.getGsg() if win is not None else None
        if win is None or gsg is None:
            logger.debug("[InternalCapture] Waiting for graphics window before starting capture.")
            return
        self._capture_width = int(win.getXSize() or 0)
        self._capture_height = int(win.getYSize() or 0)
        if self._capture_width < 16 or self._capture_height < 16:
            logger.debug(
                f"[InternalCapture] Waiting for valid window size before starting capture: "
                f"{self._capture_width}x{self._capture_height}"
            )
            return
        self._frame_bytes = self._capture_width * self._capture_height * 4
        self._texture = Texture("internal_video_capture")
        self._texture.setKeepRamImage(True)
        self._buffer = win.makeTextureBuffer(
            "internal_video_capture_buffer",
            self._capture_width,
            self._capture_height,
            self._texture,
            True,
        )
        if self._buffer is None:
            self.enabled = False
            self._capture_stopped = True
            self._status["enabled"] = False
            self._status["stopped"] = True
            self._status["error"] = "makeTextureBuffer returned null"
            self._status["reason"] = "buffer-create-failed"
            self._write_status()
            logger.error("[InternalCapture] Failed to create offscreen texture buffer.")
            return
        self._buffer.setSort(91)
        self._capture_cam = self._create_follow_capture_camera()
        if self._capture_cam is None:
            self.enabled = False
            self._capture_stopped = True
            self._status["enabled"] = False
            self._status["stopped"] = True
            self._status["error"] = "capture camera setup failed"
            self._status["reason"] = "camera-bind-failed"
            self._write_status()
            logger.error("[InternalCapture] Failed to bind capture camera to gameplay camera rig.")
            return
        self._capture_cam2d = self._create_overlay_capture_camera()
        output_path = Path(self.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        log_path = output_path.with_suffix(".internal-ffmpeg.log")
        self._stderr_handle = open(log_path, "w", encoding="utf-8", errors="replace")
        ffmpeg_args = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgra",
            "-video_size",
            f"{self._capture_width}x{self._capture_height}",
            "-framerate",
            str(self.fps),
            "-i",
            "-",
            "-vf",
            self._effective_video_filter(),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-threads",
            str(self._thread_budget),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            self.output_path,
        ]
        self._proc = subprocess.Popen(
            ffmpeg_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=self._stderr_handle,
            bufsize=0,
        )
        self._capture_started = True
        self._start_perf = time.perf_counter()
        self._next_frame_at = self._start_perf
        self._status["started"] = True
        self._status["reason"] = "capturing"
        self._status["width"] = self._capture_width
        self._status["height"] = self._capture_height
        self._write_status()
        logger.info(
            f"[InternalCapture] Started {self._capture_width}x{self._capture_height} at {self.fps}fps -> {self.output_path}"
        )

    def _create_follow_capture_camera(self):
        if self._buffer is None:
            return None
        gameplay_camera = getattr(self.app, "camera", None)
        if gameplay_camera is None:
            return None
        try:
            capture_camera = Camera("internal_capture_cam")
            source_cam_node = getattr(self.app, "camNode", None)
            source_lens = source_cam_node.getLens() if source_cam_node is not None else None
            if source_lens is not None and hasattr(source_lens, "makeCopy"):
                capture_camera.setLens(source_lens.makeCopy())
            capture_cam_np = gameplay_camera.attachNewNode(capture_camera)
            capture_cam_np.setPos(0, 0, 0)
            capture_cam_np.setHpr(0, 0, 0)
            display_region = self._buffer.makeDisplayRegion()
            display_region.setCamera(capture_cam_np)
            logger.info("[InternalCapture] Capture camera attached to gameplay camera rig.")
            return capture_cam_np
        except Exception as exc:
            logger.warning(f"[InternalCapture] Capture camera bind failed: {exc}")
            return None

    def _create_overlay_capture_camera(self):
        render2d = getattr(self.app, "render2d", None)
        make_camera_2d = getattr(self.app, "makeCamera2d", None)
        if render2d is None or not callable(make_camera_2d):
            return None
        try:
            overlay_cam = make_camera_2d(
                self._buffer,
                sort=20,
                displayRegion=(0, 1, 0, 1),
                cameraName="internal_capture_overlay",
            )
            logger.info("[InternalCapture] 2D overlay capture enabled for HUD/aspect2d.")
            return overlay_cam
        except Exception as exc:
            logger.warning(f"[InternalCapture] 2D overlay bind failed: {exc}")
            return None

    def _effective_video_filter(self) -> str:
        user_filter = self.video_filter.strip()
        if user_filter:
            return f"vflip,{user_filter}"
        return "vflip"

    def _capture_due_frames(self) -> None:
        if self._proc is None or self._texture is None:
            return
        now = time.perf_counter()
        if now + 1e-6 < self._next_frame_at:
            return
        raw = self._read_current_frame()
        if raw is not None:
            self._last_frame_bytes = raw
        if self._last_frame_bytes is None:
            return
        frame_interval = 1.0 / max(1, self.fps)
        due_count = max(1, int((now - self._next_frame_at) / frame_interval) + 1)
        due_count = min(12, due_count)
        for _ in range(due_count):
            if not self._write_frame(self._last_frame_bytes):
                return
            self._next_frame_at += frame_interval

    def _read_current_frame(self):
        win = getattr(self.app, "win", None)
        gsg = win.getGsg() if win is not None else None
        if win is None or gsg is None or self._proc is None or self._proc.stdin is None:
            return None
        raw = None
        if self._buffer is not None:
            self._refresh_offscreen_texture(gsg)
            raw = self._extract_texture_bytes(
                self._texture,
                source_label="offscreen buffer",
                warn_missing=True,
            )
        if raw is not None:
            return raw
        composite_texture = self._capture_window_screenshot_texture(win)
        raw = self._extract_texture_bytes(
            composite_texture,
            source_label="window screenshot",
            warn_missing=False,
        )
        if raw is not None and not self._warned_window_fallback:
            logger.warning(
                "[InternalCapture] Offscreen buffer недоступен, временно используем screenshot окна."
            )
            self._warned_window_fallback = True
        return raw

    def _refresh_offscreen_texture(self, gsg) -> None:
        if self._texture is None or gsg is None:
            return
        engine = getattr(self.app, "graphicsEngine", None)
        extractor = getattr(engine, "extractTextureData", None)
        if not callable(extractor):
            return
        try:
            extractor(self._texture, gsg)
        except Exception as exc:
            if not self._warned_extract:
                logger.warning(f"[InternalCapture] Offscreen extract failed: {exc}")
                self._warned_extract = True

    def _capture_window_screenshot_texture(self, win):
        getter = getattr(win, "getScreenshot", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception as exc:
            if not self._warned_extract:
                logger.warning(f"[InternalCapture] Window screenshot failed: {exc}")
                self._warned_extract = True
            return None

    def _extract_texture_bytes(self, texture, source_label="texture", warn_missing=True):
        if texture is None:
            return None
        try:
            has_image = bool(texture.hasRamImage())
        except Exception:
            has_image = False
        if not has_image:
            if warn_missing and not self._warned_extract:
                logger.warning(f"[InternalCapture] {source_label} has no RAM image yet.")
                self._warned_extract = True
            return None
        try:
            raw = bytes(texture.getRamImage())
        except Exception as exc:
            if not self._warned_extract:
                logger.warning(f"[InternalCapture] {source_label} getRamImage failed: {exc}")
                self._warned_extract = True
            return None
        if len(raw) == self._frame_bytes:
            return raw
        reorder = getattr(texture, "getRamImageAs", None)
        if callable(reorder):
            try:
                reordered = bytes(reorder("BGRA"))
            except Exception:
                reordered = b""
            if len(reordered) == self._frame_bytes:
                return reordered
        if not self._warned_length:
            logger.warning(
                f"[InternalCapture] Unexpected {source_label} byte size: "
                f"got={len(raw)} expected={self._frame_bytes}"
            )
            self._warned_length = True
        return None

    def _write_frame(self, raw: bytes) -> bool:
        try:
            self._proc.stdin.write(raw)
        except BrokenPipeError:
            logger.error("[InternalCapture] ffmpeg pipe closed during capture.")
            self._status["error"] = "ffmpeg pipe closed during capture"
            self.stop("broken-pipe")
            return False
        except Exception as exc:
            logger.error(f"[InternalCapture] Failed to write frame to ffmpeg: {exc}")
            self._status["error"] = f"write failed: {exc}"
            self.stop("write-failed")
            return False
        self._frames_written += 1
        self._status["frames_written"] = self._frames_written
        return True

    def _write_status(self) -> None:
        if not self.status_path:
            return
        try:
            status_path = Path(self.status_path)
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(
                json.dumps(self._status, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug(f"[InternalCapture] Failed to write status file: {exc}")

    def _safe_unlink(self, target: str) -> None:
        if not target:
            return
        try:
            Path(target).unlink(missing_ok=True)
        except Exception:
            pass
