"""
King Wizard — Level Editor Window
==================================
A standalone CTkToplevel that combines:
  • Live 30fps viewport  (mmap ← Panda3D offscreen buffer)
  • Entity Inspector     (transform sliders, sync via SQLite)
  • Placement Palette    (props + hazard zones)
  • Magic VFX Tester     (spell dropdown + world position)
  • Terrain Sculpting    (brush controls)
  • Bake button          (runs bake_level.py)

Open it from the Hub with:
    from dev.level_editor_window import LevelEditorWindow
    win = LevelEditorWindow(hub_root, db_path, log_fn)
    win.open()
"""

import os
import sys
import time
import json
import math
import sqlite3
import msgpack
import threading
import io as _io
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ── path setup ────────────────────────────────────────────────────────────
_HERE   = Path(__file__).parent
_ROOT   = _HERE.parent
sys.path.insert(0, str(_HERE))

try:
    from editor_viewport_server import EditorViewportClient
    _CLIENT_OK = True
except Exception:
    _CLIENT_OK = False

# ── constants ─────────────────────────────────────────────────────────────
VP_W, VP_H        = 860, 484      # viewport canvas pixel size
POLL_MS           = 33            # ~30 fps
BRIDGE_POLL_MS    = 100
PANEL_W           = 380

HAZARDS = [
    ("🔥 Lava Pool",   "lava_pool",     "#c0392b"),
    ("🌿 Swamp Pool",  "swamp_pool",    "#27ae60"),
    ("💧 Water Pool",  "water_pool",    "#2980b9"),
    ("☠️  Poison Zone", "poison_cloud",  "#8e44ad"),
    ("❄️  Blizzard",    "blizzard_zone", "#5dade2"),
    ("🌋 Fire Area",   "fire_area",     "#e67e22"),
]
PROPS = [
    ("Rock",       "rock",       "#7f8c8d"),
    ("Barrel",     "barrel",     "#e67e22"),
    ("Tree Trunk", "tree_trunk", "#27ae60"),
    ("Chest",      "chest",      "#f1c40f"),
]
DEFAULT_SPELLS = ["fireball", "meteor", "lightning", "freeze", "poison_cloud", "heal_wave"]


# ─────────────────────────────────────────────────────────────────────────
class LevelEditorWindow:
    """Full-featured level editor in a separate window."""

    def __init__(self, root_dir: Path, db_path: Path, log_fn: Callable):
        self._root    = root_dir
        self._db      = db_path
        self._log     = log_fn
        self._win: Optional[ctk.CTkToplevel] = None

        # State
        self._vp_client      = EditorViewportClient() if _CLIENT_OK else None
        self._last_frame_id  = None
        self._no_signal_img  = None
        self._inspector      = {}
        self._last_eid       = None
        self._transform_w    = {}          # {f"{group}_{i}": (slider, entry)}
        self._brush_mode     = ctk.BooleanVar(value=False)
        self._brush_type     = ctk.StringVar(value="raise")
        self._brush_radius   = 5.0
        self._brush_strength = 1.0
        self._vfx_spell      = ctk.StringVar(value="fireball")
        self._vfx_x = self._vfx_y = self._vfx_z = None

        # Canvas reference (set in _build_viewport_panel)
        self._canvas: Optional[ctk.CTkCanvas] = None
        self._canvas_img_id = None

    # ── public ────────────────────────────────────────────────────────────
    def open(self):
        if self._win and self._win.winfo_exists():
            self._win.lift()
            return
        self._win = ctk.CTkToplevel()
        self._win.title("⚔ King Wizard — Level Editor")
        self._win.geometry(f"{VP_W + PANEL_W + 30}x{VP_H + 80}")
        self._win.resizable(True, True)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_toolbar()
        self._build_main()
        self._build_status_bar()

        self._start_vp_loop()
        self._start_bridge_loop()
        self._log("[LevelEditor] Window opened.")

    def _on_close(self):
        if self._win:
            self._win.destroy()
            self._win = None
        if self._vp_client:
            try:
                self._vp_client.close()
            except Exception:
                pass

    # ── layout ────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        tb = ctk.CTkFrame(self._win, height=44, fg_color="#111827", corner_radius=0)
        tb.pack(fill="x", side="top")

        ctk.CTkLabel(tb, text="⚔  LEVEL EDITOR",
                     font=("", 14, "bold"), text_color="#e67e22").pack(side="left", padx=16)

        ctk.CTkButton(tb, text="💾 BAKE WORLD", width=130, height=30,
                      fg_color="#27ae60", hover_color="#2ecc71",
                      command=self._bake_world).pack(side="right", padx=8, pady=7)

        ctk.CTkButton(tb, text="📸 Capture Frame", width=120, height=30,
                      fg_color="#2980b9", hover_color="#3498db",
                      command=self._request_screenshot).pack(side="right", padx=4, pady=7)

        # FPS label
        self._fps_lbl = ctk.CTkLabel(tb, text="● connecting…",
                                      font=("", 11), text_color="#e74c3c")
        self._fps_lbl.pack(side="right", padx=12)

    def _build_main(self):
        paned = ctk.CTkFrame(self._win, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=6, pady=4)

        # Left: viewport
        self._build_viewport_panel(paned)

        # Right: editor controls
        self._rp = ctk.CTkScrollableFrame(paned, width=PANEL_W,
                                           fg_color="#0f172a", corner_radius=8)
        self._rp.pack(side="right", fill="both", padx=(4, 0))
        self._build_inspector_panel()
        self._build_palette_panel()
        self._build_hazard_panel()
        self._build_vfx_panel()
        self._build_terrain_panel()

    def _build_status_bar(self):
        sb = ctk.CTkFrame(self._win, height=26, fg_color="#0f172a", corner_radius=0)
        sb.pack(fill="x", side="bottom")
        self._status_lbl = ctk.CTkLabel(sb, text="Ready.", font=("Consolas", 10),
                                         text_color="#64748b")
        self._status_lbl.pack(side="left", padx=10)
        self._loc_lbl = ctk.CTkLabel(sb, text="", font=("", 10), text_color="#94a3b8")
        self._loc_lbl.pack(side="right", padx=10)

    def _set_status(self, msg: str):
        if self._win and self._win.winfo_exists():
            self._status_lbl.configure(text=msg)

    # ── viewport panel ────────────────────────────────────────────────────
    def _build_viewport_panel(self, parent):
        vf = ctk.CTkFrame(parent, fg_color="#0a0a14", corner_radius=8,
                          width=VP_W, height=VP_H)
        vf.pack(side="left", fill="both", expand=True)
        vf.pack_propagate(False)

        # Header bar inside viewport
        vhdr = ctk.CTkFrame(vf, height=28, fg_color="#111827", corner_radius=0)
        vhdr.pack(fill="x")
        ctk.CTkLabel(vhdr, text="VIEWPORT — live render (30fps)",
                     font=("", 11, "bold"), text_color="#64748b").pack(side="left", padx=8)
        ctk.CTkLabel(vhdr, text="Click objects in game to select them",
                     font=("", 10), text_color="#374151").pack(side="right", padx=8)

        # The actual canvas
        self._canvas = ctk.CTkCanvas(vf, bg="#070714", bd=0, highlightthickness=0,
                                      width=VP_W, height=VP_H - 28)
        self._canvas.pack(fill="both", expand=True)

        self._no_signal_img = self._make_no_signal()

    def _make_no_signal(self) -> ImageTk.PhotoImage:
        """Dark 'no signal' placeholder image."""
        img = Image.new("RGB", (VP_W, VP_H - 28), color=(7, 7, 20))
        draw = ImageDraw.Draw(img)
        draw.rectangle([VP_W//2 - 120, (VP_H-28)//2 - 40,
                         VP_W//2 + 120, (VP_H-28)//2 + 40],
                        outline="#1e293b", width=2)
        draw.text((VP_W//2 - 110, (VP_H-28)//2 - 14),
                   "▶  Start the game to see the live viewport",
                   fill="#334155")
        return ImageTk.PhotoImage(img)

    # ── inspector panel ───────────────────────────────────────────────────
    def _build_inspector_panel(self):
        hdr = self._section(self._rp, "🔍 ENTITY INSPECTOR", "#e67e22")
        self._inspector_body = ctk.CTkFrame(self._rp, fg_color="#1e293b", corner_radius=6)
        self._inspector_body.pack(fill="x", padx=8, pady=(0, 4))
        self._inspector_placeholder()

    def _inspector_placeholder(self):
        for w in self._inspector_body.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._inspector_body,
                     text="Click an object in game…",
                     font=("", 11, "italic"), text_color="#4a5568").pack(pady=16)

    def _refresh_inspector(self, data: dict):
        for w in self._inspector_body.winfo_children():
            w.destroy()
        self._transform_w.clear()

        # ID / type row
        info = ctk.CTkFrame(self._inspector_body, fg_color="transparent")
        info.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(info, text=data.get("entity_id", "?"),
                     font=("Consolas", 11, "bold"), text_color="#e2e8f0").pack(side="left")
        ctk.CTkLabel(info, text=data.get("type", ""),
                     font=("", 10), text_color="#64748b").pack(side="right")

        for group, axes in [("pos", "XYZ"), ("hpr", "HPR"), ("scale", "XYZ")]:
            row = ctk.CTkFrame(self._inspector_body, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=2)
            ctk.CTkLabel(row, text=group.upper(), width=44,
                         font=("", 10, "bold"), text_color="#94a3b8").pack(side="left")
            vals = data.get(group, [0, 0, 0])
            rmin, rmax = ((-500, 500) if group == "pos"
                          else ((-360, 360) if group == "hpr" else (0.05, 20.0)))
            for i, ax in enumerate(axes):
                f = ctk.CTkFrame(row, fg_color="transparent")
                f.pack(side="left", fill="x", expand=True, padx=1)
                ctk.CTkLabel(f, text=ax, width=14, font=("", 9),
                              text_color="#64748b").pack(side="left")
                sl = ctk.CTkSlider(f, from_=rmin, to=rmax, height=14,
                                    command=lambda v, g=group, idx=i: self._on_transform(g, idx, v))
                sl.set(vals[i] if i < len(vals) else 0)
                sl.pack(side="left", fill="x", expand=True)
                en = ctk.CTkEntry(f, width=46, height=20, font=("Consolas", 9))
                en.insert(0, f"{vals[i]:.2f}" if i < len(vals) else "0")
                en.pack(side="right", padx=1)
                self._transform_w[f"{group}_{i}"] = (sl, en)

    def _on_transform(self, group, index, value):
        if not self._inspector:
            return
        if group not in self._inspector:
            self._inspector[group] = [0, 0, 0]
        self._inspector[group][index] = value
        key = f"{group}_{index}"
        if key in self._transform_w:
            _, en = self._transform_w[key]
            en.delete(0, "end")
            en.insert(0, f"{value:.2f}")
        self._send_level_update()

    # ── palette panel ─────────────────────────────────────────────────────
    def _build_palette_panel(self):
        self._section(self._rp, "🪵 PLACEMENT PALETTE", "#7f8c8d")
        g = ctk.CTkFrame(self._rp, fg_color="transparent")
        g.pack(padx=8, pady=(0, 4))
        for i, (name, obj_type, color) in enumerate(PROPS):
            ctk.CTkButton(g, text=name, width=168, fg_color=color, hover_color=color,
                           font=("", 11),
                           command=lambda t=obj_type, n=name: self._spawn(t, n)
                           ).grid(row=i // 2, column=i % 2, padx=3, pady=3)

    # ── hazard panel ──────────────────────────────────────────────────────
    def _build_hazard_panel(self):
        self._section(self._rp, "⚠️  HAZARD ZONES", "#e74c3c")
        g = ctk.CTkFrame(self._rp, fg_color="transparent")
        g.pack(padx=8, pady=(0, 4))
        for i, (name, hz_type, color) in enumerate(HAZARDS):
            ctk.CTkButton(g, text=name, width=108, fg_color=color, hover_color=color,
                           font=("", 10),
                           command=lambda t=hz_type, n=name: self._spawn(t, n)
                           ).grid(row=i // 3, column=i % 3, padx=2, pady=2)

    # ── VFX panel ─────────────────────────────────────────────────────────
    def _build_vfx_panel(self):
        self._section(self._rp, "✨ MAGIC VFX TESTER", "#9b59b6")
        inner = ctk.CTkFrame(self._rp, fg_color="#1e293b", corner_radius=6)
        inner.pack(fill="x", padx=8, pady=(0, 4))

        spell_row = ctk.CTkFrame(inner, fg_color="transparent")
        spell_row.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(spell_row, text="Spell:", width=42, font=("", 11)).pack(side="left")
        spells = self._load_spell_ids()
        self._vfx_spell.set(spells[0] if spells else "fireball")
        ctk.CTkOptionMenu(spell_row, variable=self._vfx_spell,
                           values=spells, width=220).pack(side="left", padx=4)

        pos_row = ctk.CTkFrame(inner, fg_color="transparent")
        pos_row.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(pos_row, text="Pos:", width=42, font=("", 11)).pack(side="left")
        self._vfx_x = ctk.CTkEntry(pos_row, width=58, placeholder_text="X")
        self._vfx_x.insert(0, "0")
        self._vfx_x.pack(side="left", padx=2)
        self._vfx_y = ctk.CTkEntry(pos_row, width=58, placeholder_text="Y")
        self._vfx_y.insert(0, "0")
        self._vfx_y.pack(side="left", padx=2)
        self._vfx_z = ctk.CTkEntry(pos_row, width=58, placeholder_text="Z")
        self._vfx_z.insert(0, "0")
        self._vfx_z.pack(side="left", padx=2)
        # Auto-fill from inspector
        ctk.CTkButton(pos_row, text="◉", width=28, height=24,
                       fg_color="#374151", command=self._fill_vfx_pos
                       ).pack(side="left", padx=2)

        ctk.CTkButton(inner, text="🎇  CAST SPELL (VFX TEST)", height=34,
                       fg_color="#8e44ad", hover_color="#9b59b6",
                       command=self._cast_spell).pack(padx=10, pady=(0, 8), fill="x")

    def _fill_vfx_pos(self):
        pos = self._inspector.get("pos", [0, 0, 0])
        for entry, val in zip([self._vfx_x, self._vfx_y, self._vfx_z], pos):
            entry.delete(0, "end")
            entry.insert(0, f"{val:.1f}")

    # ── terrain panel ─────────────────────────────────────────────────────
    def _build_terrain_panel(self):
        self._section(self._rp, "🏔 TERRAIN SCULPTING", "#3498db")
        inner = ctk.CTkFrame(self._rp, fg_color="#1e293b", corner_radius=6)
        inner.pack(fill="x", padx=8, pady=(0, 8))

        cb = ctk.CTkCheckBox(inner, text="Enable Terrain Brush",
                              variable=self._brush_mode,
                              command=self._send_brush_settings)
        cb.pack(padx=12, pady=8)

        seg = ctk.CTkSegmentedButton(inner, values=["raise", "lower", "flatten"],
                                      variable=self._brush_type,
                                      command=lambda _: self._send_brush_settings())
        seg.pack(padx=12, pady=(0, 6))

        for label, attr, lo, hi, default in [
            ("Radius",   "_brush_radius",   1.0, 30.0, 5.0),
            ("Strength", "_brush_strength", 0.1, 10.0, 1.0),
        ]:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=label, width=66, font=("", 10)).pack(side="left")
            val_lbl = ctk.CTkLabel(row, text=f"{default:.1f}", width=36, font=("Consolas", 10))
            val_lbl.pack(side="right")
            sl = ctk.CTkSlider(row, from_=lo, to=hi, height=14,
                                command=lambda v, a=attr, l=val_lbl: [
                                    setattr(self, a, float(v)),
                                    l.configure(text=f"{v:.1f}"),
                                    self._send_brush_settings()
                                ])
            sl.set(default)
            sl.pack(side="left", fill="x", expand=True, padx=4)

        inner.pack_configure(pady=(0, 12))

    # ── helpers ───────────────────────────────────────────────────────────
    def _section(self, parent, title: str, color: str) -> ctk.CTkFrame:
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(10, 2))
        ctk.CTkLabel(hdr, text=title, font=("", 12, "bold"),
                      text_color=color).pack(side="left")
        return hdr

    def _bridge_write(self, key: str, data: dict):
        if not self._db.parent.exists():
            return
        try:
            packed = msgpack.packb(data, use_bin_type=True)
            conn = sqlite3.connect(self._db, timeout=1.0)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)",
                          (key, sqlite3.Binary(packed)))
            conn.commit()
            conn.close()
        except Exception as e:
            self._log(f"[LevelEditor] Bridge write failed ({key}): {e}")

    def _spawn(self, obj_type: str, name: str):
        pos = self._inspector.get("pos", [0.0, 10.0, 0.0])
        self._bridge_write("spawn_request",
                            {"type": obj_type, "pos": pos, "pending": True})
        self._log(f"[Spawn] {name} → {[round(p, 1) for p in pos]}")
        self._set_status(f"Spawned: {name}")

    def _cast_spell(self):
        try:
            pos = [float(self._vfx_x.get() or 0),
                   float(self._vfx_y.get() or 0),
                   float(self._vfx_z.get() or 0)]
        except ValueError:
            pos = [0, 0, 0]
        spell = self._vfx_spell.get()
        self._bridge_write("spell_cast_request",
                            {"spell_id": spell, "pos": pos, "pending": True})
        self._log(f"[VFX] Cast '{spell}' at {pos}")
        self._set_status(f"Cast: {spell}")

    def _send_level_update(self):
        if not self._inspector:
            return
        self._bridge_write("level_update", {
            "entity_id": self._inspector.get("entity_id", ""),
            "pos":   self._inspector.get("pos",   [0, 0, 0]),
            "hpr":   self._inspector.get("hpr",   [0, 0, 0]),
            "scale": self._inspector.get("scale", [1, 1, 1]),
        })

    def _send_brush_settings(self):
        self._bridge_write("editor_settings", {
            "brush_mode": bool(self._brush_mode.get()),
            "brush": {
                "type":     self._brush_type.get(),
                "radius":   float(self._brush_radius),
                "strength": float(self._brush_strength),
            }
        })

    def _request_screenshot(self):
        self._bridge_write("screenshot_request", {"trigger": True})
        self._log("[LevelEditor] Screenshot requested.")

    def _bake_world(self):
        import subprocess
        bake = _ROOT / "dev" / "bake_level.py"
        if bake.exists():
            threading.Thread(
                target=lambda: subprocess.run([sys.executable, str(bake)], cwd=str(_ROOT)),
                daemon=True
            ).start()
            self._log("[Bake] bake_level.py started.")
        else:
            self._log("[Bake] bake_level.py not found.")
        self._set_status("Baking world…")

    def _load_spell_ids(self) -> list:
        for p in [_ROOT / "data" / "spells.json",
                  _ROOT / "data" / "abilities" / "spells.json"]:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        return [str(s.get("id", s.get("key", s))) for s in data if isinstance(s, dict)]
                    if isinstance(data, dict):
                        return list(data.keys())
                except Exception:
                    pass
        return DEFAULT_SPELLS

    # ── viewport polling loop ─────────────────────────────────────────────
    def _start_vp_loop(self):
        self._vp_frame_count = 0
        self._vp_fps_time    = time.time()
        self._update_viewport()

    def _update_viewport(self):
        if not self._win or not self._win.winfo_exists():
            return

        client = self._vp_client
        frame_data = client.read_frame() if client else None

        if frame_data:
            rgb, w, h = frame_data
            try:
                img = Image.frombytes("RGB", (w, h), rgb)
                img = img.resize((VP_W, VP_H - 28), Image.BILINEAR)
                tk_img = ImageTk.PhotoImage(img)
                c = self._canvas
                if self._canvas_img_id is None:
                    self._canvas_img_id = c.create_image(0, 0, anchor="nw", image=tk_img)
                else:
                    c.itemconfigure(self._canvas_img_id, image=tk_img)
                c._live_img_ref = tk_img   # prevent GC

                self._vp_frame_count += 1
                now = time.time()
                if now - self._vp_fps_time >= 1.0:
                    fps = self._vp_frame_count / (now - self._vp_fps_time)
                    self._fps_lbl.configure(
                        text=f"● {fps:.0f} fps", text_color="#2ecc71")
                    self._vp_frame_count = 0
                    self._vp_fps_time    = now
            except Exception as e:
                pass
        else:
            # Show placeholder
            if self._canvas_img_id is None and self._no_signal_img:
                self._canvas_img_id = self._canvas.create_image(
                    0, 0, anchor="nw", image=self._no_signal_img)
            # Try reconnect
            if client and not client._mm:
                client.connect()

        self._win.after(POLL_MS, self._update_viewport)

    # ── bridge polling loop (inspector feedback) ──────────────────────────
    def _start_bridge_loop(self):
        threading.Thread(target=self._bridge_poll_loop, daemon=True).start()

    def _bridge_poll_loop(self):
        while True:
            if not (self._win and self._win.winfo_exists()):
                break
            if self._db.exists():
                try:
                    conn = sqlite3.connect(self._db, timeout=1.0)
                    row = conn.execute(
                        "SELECT payload FROM bridge WHERE key = 'inspector_feedback'"
                    ).fetchone()
                    conn.close()
                    if row:
                        data = msgpack.unpackb(bytes(row[0]), raw=False)
                        if data.get("selected") and data.get("entity_id") != self._last_eid:
                            self._inspector = data
                            self._last_eid  = data.get("entity_id")
                            if self._win and self._win.winfo_exists():
                                self._win.after(0, lambda d=data: self._refresh_inspector(d))
                                loc = data.get("type", "")
                                self._win.after(0, lambda l=loc: self._loc_lbl.configure(text=l))
                except Exception:
                    pass
            time.sleep(BRIDGE_POLL_MS / 1000.0)
