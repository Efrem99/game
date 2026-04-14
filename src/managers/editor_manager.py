import sqlite3
import msgpack
import os
import sys
import math
import struct
import time
from panda3d.core import (
    CollisionTraverser, CollisionNode, CollisionHandlerQueue,
    CollisionRay, NodePath, Vec4, Vec3,
    GraphicsOutput, FrameBufferProperties, WindowProperties,
    GraphicsPipe, Texture, PTA_uchar
)
from utils.logger import logger

# Viewport streaming server (mmap)
try:
    _dev_dir = os.path.join(os.path.dirname(__file__), "..", "..", "dev")
    sys.path.insert(0, os.path.abspath(_dev_dir))
    from editor_viewport_server import EditorViewportServer
    _viewport_server_available = True
except Exception:
    _viewport_server_available = False


def _env_flag(name, default=False):
    raw = str(os.environ.get(name, "1" if default else "0") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class EditorManager:
    # Live viewport resolution (lower = faster)
    VIEWPORT_W = 640
    VIEWPORT_H = 360

    def __init__(self, app):
        self.app = app
        self.enabled = True

        # Picking setup
        self.picker = CollisionTraverser("editor_picker")
        self.picker_handler = CollisionHandlerQueue()
        self.picker_node = CollisionNode("mouse_ray")
        self.picker_np = self.app.camera.attachNewNode(self.picker_node)
        self.picker_ray = CollisionRay()
        self.picker_node.addSolid(self.picker_ray)
        self.picker_node.setFromCollideMask(0x1)
        self.picker.addCollider(self.picker_np, self.picker_handler)

        self.selected_np = None
        self.last_sync_time = 0.0
        self.sync_interval = 0.05

        self.db_path = os.path.join(getattr(self.app, "project_root", "."), "dev/dev_editor.sqlite3")
        self._init_db()

        self.brush_mode = False
        self.brush_settings = {"radius": 5.0, "strength": 1.0, "type": "raise"}

        # Live viewport streaming
        self._viewport_server = None
        self._offscreen_buf = None
        self._offscreen_tex = None
        self._viewport_cam_np = None
        self._last_frame_time = 0.0
        self._frame_interval = 1.0 / 30.0   # 30 fps stream
        self._viewport_enabled = False
        self._pending_viewport_setup = self._should_enable_live_viewport()  # defer to first update tick

        self.app.taskMgr.add(self._editor_update, "editor_update_task")
        logger.info("[EditorManager] Initialized: SQLite + MessagePack Bridge ready.")

    def _should_enable_live_viewport(self):
        if _env_flag("XBOT_INTERNAL_VIDEO_CAPTURE", False):
            logger.info("[EditorManager] Live viewport disabled during internal video capture.")
            return False
        if _env_flag("XBOT_VIDEO_BOT", False):
            logger.info("[EditorManager] Live viewport disabled during automated video bot run.")
            return False
        return True

    # ── DB ────────────────────────────────────────────────────────────────
    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.execute("CREATE TABLE IF NOT EXISTS bridge (key TEXT PRIMARY KEY, payload BLOB)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[EditorManager] DB Init failed: {e}")

    # ── Main task ─────────────────────────────────────────────────────────
    def _editor_update(self, task):
        if not self.enabled:
            return task.cont

        # Deferred viewport setup (needs world to be loaded)
        if self._pending_viewport_setup and getattr(self.app, "world", None):
            self._setup_live_viewport()
            self._pending_viewport_setup = False

        if self.app.mouseWatcherNode.hasMouse():
            if self.app.mouseWatcherNode.isButtonDown("mouse1"):
                if self.brush_mode:
                    self._perform_terrain_paint()
                else:
                    self._perform_pick()

        now = task.time
        if now - self.last_sync_time > self.sync_interval:
            self._sync_with_hub()
            self.last_sync_time = now

        # Stream live frame
        if self._viewport_enabled and now - self._last_frame_time > self._frame_interval:
            self._stream_frame()
            self._last_frame_time = now

        return task.cont

    # ── Live viewport ─────────────────────────────────────────────────────
    def _setup_live_viewport(self):
        """Create an offscreen buffer and a secondary camera for live streaming."""
        if not _viewport_server_available:
            logger.warning("[EditorManager] Viewport server not available (mmap module missing?)")
            return
        try:
            pipe = self.app.pipe
            fbp = FrameBufferProperties()
            fbp.setRgbColor(True)
            fbp.setDepthBits(16)

            wp = WindowProperties.size(self.VIEWPORT_W, self.VIEWPORT_H)

            self._offscreen_buf = self.app.graphicsEngine.makeOutput(
                pipe, "editor_offscreen", -100, fbp, wp,
                GraphicsPipe.BFRefuseWindow, self.app.win.getGsg(), self.app.win
            )
            if not self._offscreen_buf:
                logger.warning("[EditorManager] Could not create offscreen buffer.")
                return

            self._offscreen_tex = Texture("editor_viewport_tex")
            self._offscreen_buf.addRenderTexture(
                self._offscreen_tex,
                GraphicsOutput.RTMCopyRam,
                GraphicsOutput.RTPColor
            )

            # Dedicated camera (follows app.camera)
            self._viewport_cam_np = self.app.render.attachNewNode("editor_viewport_cam_node")
            from panda3d.core import Camera, PerspectiveLens
            vp_cam = Camera("editor_viewport_cam")
            lens = PerspectiveLens()
            lens.setFov(60)
            lens.setAspectRatio(self.VIEWPORT_W / self.VIEWPORT_H)
            vp_cam.setLens(lens)

            vp_cam_np = self._viewport_cam_np.attachNewNode(vp_cam)
            dr = self._offscreen_buf.makeDisplayRegion()
            dr.setCamera(vp_cam_np)

            # Reparent to follow game camera
            self._viewport_cam_np.reparentTo(self.app.camera)
            self._viewport_cam_np.setPos(0, 0, 0)
            self._viewport_cam_np.setHpr(0, 0, 0)

            # Start mmap server
            self._viewport_server = EditorViewportServer()
            self._viewport_server.setup()

            self._viewport_enabled = True
            logger.info("[EditorManager] Live viewport stream started (640×360 @ 30fps).")
        except Exception as e:
            logger.error(f"[EditorManager] Viewport setup failed: {e}")

    def _stream_frame(self):
        """Read the offscreen texture and push to mmap."""
        try:
            tex = self._offscreen_tex
            if not tex or tex.getXSize() == 0:
                return
            self.app.graphicsEngine.extractTextureData(tex, self.app.win.getGsg())
            ram = tex.getRamImage()
            if not ram:
                return
            raw = bytes(ram)
            w, h = tex.getXSize(), tex.getYSize()
            # Panda3D gives BGRA or BGR depending on format — convert to RGB
            comp = tex.getNumComponents()
            if comp == 4:
                # BGRA → RGB
                rgb = bytearray(w * h * 3)
                for i in range(w * h):
                    b, g, r = raw[i*4], raw[i*4+1], raw[i*4+2]
                    rgb[i*3], rgb[i*3+1], rgb[i*3+2] = r, g, b
                raw = bytes(rgb)
            elif comp == 3:
                # BGR → RGB
                rgb = bytearray(w * h * 3)
                for i in range(w * h):
                    b, g, r = raw[i*3], raw[i*3+1], raw[i*3+2]
                    rgb[i*3], rgb[i*3+1], rgb[i*3+2] = r, g, b
                raw = bytes(rgb)
            # Panda3D image is flipped vertically — flip it
            row_size = w * 3
            rows = [raw[i*row_size:(i+1)*row_size] for i in range(h)]
            raw = b"".join(reversed(rows))
            self._viewport_server.add_frame(raw, w, h)
        except Exception as e:
            logger.debug(f"[EditorManager] Frame stream error: {e}")

    # ── Picking ───────────────────────────────────────────────────────────
    def _perform_pick(self):
        mpos = self.app.mouseWatcherNode.getMouse()
        self.picker_ray.setFromLens(self.app.camNode, mpos.getX(), mpos.getY())
        world_root = getattr(self.app.world, "render", self.app.render)
        self.picker.traverse(world_root)

        if self.picker_handler.getNumEntries() > 0:
            self.picker_handler.sortEntries()
            entry = self.picker_handler.getEntry(0)
            picked_np = entry.getIntoNodePath()
            candidate = picked_np
            while candidate and not candidate.isEmpty() and not candidate.hasTag("entity_id") and not candidate.hasTag("mesh_id"):
                candidate = candidate.getParent()
            if candidate and not candidate.isEmpty():
                if self.selected_np != candidate:
                    self._select_node(candidate)
            else:
                self._select_node(None)
        else:
            self._select_node(None)

    def _select_node(self, np):
        if self.selected_np:
            self.selected_np.clearColorScale()
        self.selected_np = np
        if self.selected_np:
            self.selected_np.setColorScale(0.3, 1.3, 1.3, 1.0)
        self._write_feedback()

    def _write_feedback(self):
        data = {"selected": False}
        if self.selected_np:
            eid = self.selected_np.getTag("entity_id") or self.selected_np.getTag("mesh_id")
            pos = self.selected_np.getPos()
            hpr = self.selected_np.getHpr()
            scale = self.selected_np.getScale()
            data = {
                "selected": True,
                "entity_id": str(eid),
                "type": str(self.selected_np.getTag("type") or "prop"),
                "pos": [round(pos.x, 3), round(pos.y, 3), round(pos.z, 3)],
                "hpr": [round(hpr.x, 2), round(hpr.y, 2), round(hpr.z, 2)],
                "scale": [round(scale.x, 3), round(scale.y, 3), round(scale.z, 3)],
            }
        try:
            packed = msgpack.packb(data, use_bin_type=True)
            conn = sqlite3.connect(self.db_path)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)", ("inspector_feedback", sqlite3.Binary(packed)))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[EditorManager] Feedback write failed: {e}")

    # ── Hub sync ──────────────────────────────────────────────────────────
    def _sync_with_hub(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 1. Level Update (transform)
            if self.selected_np:
                row = cursor.execute("SELECT payload FROM bridge WHERE key = ?", ("level_update",)).fetchone()
                if row:
                    data = msgpack.unpackb(row[0], raw=False)
                    eid = data.get("entity_id")
                    current_eid = self.selected_np.getTag("entity_id") or self.selected_np.getTag("mesh_id")
                    if eid == current_eid:
                        if "pos" in data: self.selected_np.setPos(*data["pos"])
                        if "hpr" in data: self.selected_np.setHpr(*data["hpr"])
                        if "scale" in data: self.selected_np.setScale(*data["scale"])

            # 2. Spawn Request
            spawn_row = cursor.execute("SELECT payload FROM bridge WHERE key = ?", ("spawn_request",)).fetchone()
            if spawn_row:
                data = msgpack.unpackb(spawn_row[0], raw=False)
                world = getattr(self.app, "world", None)
                if world and hasattr(world, "spawn_entity"):
                    world.spawn_entity(data)
                cursor.execute("DELETE FROM bridge WHERE key = ?", ("spawn_request",))
                conn.commit()

            # 3. Spell Cast Request
            spell_row = cursor.execute("SELECT payload FROM bridge WHERE key = ?", ("spell_cast_request",)).fetchone()
            if spell_row:
                data = msgpack.unpackb(spell_row[0], raw=False)
                world = getattr(self.app, "world", None)
                if world and hasattr(world, "trigger_vfx"):
                    world.trigger_vfx(data.get("spell_id"), data.get("pos"))
                cursor.execute("DELETE FROM bridge WHERE key = ?", ("spell_cast_request",))
                conn.commit()

            # 4. Editor Settings (brush)
            row_env = cursor.execute("SELECT payload FROM bridge WHERE key = ?", ("editor_settings",)).fetchone()
            if row_env:
                env_data = msgpack.unpackb(row_env[0], raw=False)
                self.brush_mode = env_data.get("brush_mode", False)
                self.brush_settings.update(env_data.get("brush", {}))

            # 5. Viewport enable/disable toggle from Hub
            vp_row = cursor.execute("SELECT payload FROM bridge WHERE key = ?", ("viewport_toggle",)).fetchone()
            if vp_row:
                vdata = msgpack.unpackb(vp_row[0], raw=False)
                want = bool(vdata.get("enabled", True))
                if want and not self._viewport_enabled and not self._pending_viewport_setup:
                    self._setup_live_viewport()
                elif not want:
                    self._viewport_enabled = False
                cursor.execute("DELETE FROM bridge WHERE key = ?", ("viewport_toggle",))
                conn.commit()

            conn.close()
        except Exception as e:
            logger.debug(f"[EditorManager] Sync failed: {e}")

    # ── Terrain painting ──────────────────────────────────────────────────
    def _perform_terrain_paint(self):
        mpos = self.app.mouseWatcherNode.getMouse()
        self.picker_ray.setFromLens(self.app.camNode, mpos.getX(), mpos.getY())
        world = getattr(self.app, "world", None)
        if not world or not hasattr(world, "terrain_data"): return
        terrain_np = getattr(world, "_terrain_node", None)
        if not terrain_np: return
        self.picker.traverse(terrain_np)
        if self.picker_handler.getNumEntries() > 0:
            self.picker_handler.sortEntries()
            hit_pos = self.picker_handler.getEntry(0).getSurfacePoint(world.render)
            self._sculpt_terrain(world, hit_pos)

    def _sculpt_terrain(self, world, hit_pos):
        from world.procedural_builder import update_terrain_mesh
        dh = world.terrain_data
        radius, strength = self.brush_settings.get("radius", 5.0), self.brush_settings.get("strength", 1.0)
        res, sz, hs = dh.res, dh.size, dh.size / 2
        step = sz / res
        min_ix = max(0, int((hit_pos.x - radius + hs) / step))
        max_ix = min(res, int((hit_pos.x + radius + hs) / step))
        min_iy = max(0, int((hit_pos.y - radius + hs) / step))
        max_iy = min(res, int((hit_pos.y + radius + hs) / step))
        for iy in range(min_iy, max_iy + 1):
            for ix in range(min_ix, max_ix + 1):
                px, py = -hs + ix * step, -hs + iy * step
                dist = math.sqrt((px - hit_pos.x)**2 + (py - hit_pos.y)**2)
                if dist < radius:
                    falloff = 1.0 - (dist / radius)
                    dh.grid[iy][ix] += strength * falloff * 0.1
        update_terrain_mesh(world._terrain_node, sz, res, dh)
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)",
                         ("terrain_update", sqlite3.Binary(msgpack.packb(dh.grid))))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[EditorManager] Terrain sync failed: {e}")
