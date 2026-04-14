"""
EditorViewportServer
====================
Streams rendered frames from the Panda3D engine to any reader (Hub viewport)
via a named mmap shared-memory segment.

Layout of the shared buffer (header = 16 bytes):
  [0:4]   uint32  write_count  — increments every new frame
  [4:8]   uint32  width
  [8:12]  uint32  height
  [12:16] uint32  frame_size   — bytes of RGB payload that follows
  [16:]   bytes   RGB24 pixel data  (width * height * 3 bytes)

Readers spin on write_count; when it changes, they decode the new frame.
"""

import mmap
import struct
import time

MMAP_NAME   = "KingWizardEditorViewport"
HEADER_FMT  = "<IIII"   # write_count, width, height, frame_size
HEADER_SIZE = struct.calcsize(HEADER_FMT)
MAX_FRAME   = 1280 * 720 * 3          # worst-case buffer
TOTAL_SIZE  = HEADER_SIZE + MAX_FRAME


class EditorViewportServer:
    """
    Runs inside the Panda3D process.
    Call setup() once, then add_frame(rgb_bytes, w, h) every frame.
    """

    def __init__(self):
        self._mm = None
        self._write_count = 0
        self._ok = False

    def setup(self):
        try:
            import sys
            if sys.platform == "win32":
                self._mm = mmap.mmap(-1, TOTAL_SIZE, tagname=MMAP_NAME,
                                     access=mmap.ACCESS_WRITE)
            else:
                import tempfile, os
                fd = os.open(f"/tmp/{MMAP_NAME}", os.O_CREAT | os.O_RDWR)
                os.ftruncate(fd, TOTAL_SIZE)
                self._mm = mmap.mmap(fd, TOTAL_SIZE, access=mmap.ACCESS_WRITE)
                os.close(fd)
            # Zero header
            self._mm.seek(0)
            self._mm.write(b"\x00" * HEADER_SIZE)
            self._ok = True
        except Exception as e:
            import logging
            logging.getLogger("XBotRPG").warning(f"[EditorViewportServer] mmap setup failed: {e}")

    def add_frame(self, rgb_bytes: bytes, width: int, height: int):
        if not self._ok or not self._mm:
            return
        try:
            frame_size = len(rgb_bytes)
            if frame_size > MAX_FRAME:
                return
            self._write_count = (self._write_count + 1) & 0xFFFFFFFF
            self._mm.seek(0)
            self._mm.write(struct.pack(HEADER_FMT,
                                       self._write_count, width, height, frame_size))
            self._mm.write(rgb_bytes)
        except Exception:
            pass

    def close(self):
        if self._mm:
            try:
                self._mm.close()
            except Exception:
                pass
            self._mm = None
        self._ok = False


# ── Reader side (used from the Hub process) ───────────────────────────────

class EditorViewportClient:
    """
    Runs inside the Hub process.
    Call read_frame() → (rgb_bytes, width, height) or None.
    """

    def __init__(self):
        self._mm = None
        self._last_count = None

    def connect(self) -> bool:
        try:
            import sys
            if sys.platform == "win32":
                self._mm = mmap.mmap(-1, TOTAL_SIZE, tagname=MMAP_NAME,
                                     access=mmap.ACCESS_READ)
            else:
                import os
                fd = os.open(f"/tmp/{MMAP_NAME}", os.O_RDONLY)
                self._mm = mmap.mmap(fd, TOTAL_SIZE, access=mmap.ACCESS_READ)
                os.close(fd)
            return True
        except Exception:
            return False

    def read_frame(self):
        """Returns (rgb_bytes, width, height) if a new frame is available, else None."""
        if not self._mm:
            if not self.connect():
                return None
        try:
            self._mm.seek(0)
            header = self._mm.read(HEADER_SIZE)
            write_count, width, height, frame_size = struct.unpack(HEADER_FMT, header)
            if write_count == 0 or write_count == self._last_count:
                return None
            if frame_size == 0 or frame_size > MAX_FRAME:
                return None
            rgb = self._mm.read(frame_size)
            self._last_count = write_count
            return rgb, width, height
        except Exception:
            self._mm = None
            return None

    def close(self):
        if self._mm:
            try:
                self._mm.close()
            except Exception:
                pass
            self._mm = None
