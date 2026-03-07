import math
import random
import os

from direct.gui.DirectGui import DirectFrame, DirectWaitBar, OnscreenImage, OnscreenText
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TextNode, TransparencyAttrib

from ui.design_system import THEME, body_font, title_font, place_ui_on_top
from utils.logger import logger


class LoadingScreen:
    def __init__(self, app):
        self.app = app
        self._context = "startup"
        self._spin_task_name = "loading_spinner_task"
        self._spinner_frames = [" .  ", " .. ", " ...", "....", " ...", " .. "]
        self._spinner_step = 0.14
        self._art_image = None
        self._tips_by_context = {}
        self._arts_by_context = {}
        self._load_config()

        self.frame = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self.frame, 60)

        self.bg = DirectFrame(
            frameColor=(0.01, 0.01, 0.02, 0.92),
            frameSize=(-2, 2, -1, 1),
            parent=self.frame,
        )
        place_ui_on_top(self.bg, 60)

        self.title = OnscreenText(
            text="",
            pos=(0.0, 0.62),
            scale=0.085,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=True,
            font=title_font(self.app),
        )
        place_ui_on_top(self.title, 61)

        self.art_back = DirectFrame(
            frameColor=(0.02, 0.02, 0.03, 0.80),
            frameSize=(-0.58, 0.58, -0.34, 0.34),
            pos=(0.0, 0.0, -0.06),
            parent=self.frame,
        )
        place_ui_on_top(self.art_back, 61)

        self.spinner = OnscreenText(
            text=self._spinner_frames[0],
            pos=(0.0, 0.18),
            scale=0.11,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.spinner, 61)

        self.hints = self._tips_for_context("default")

        self.hint_text = OnscreenText(
            text="",
            pos=(0.0, -0.45),
            scale=0.045,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.7),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.hint_text, 61)

        self.bar_bg = DirectFrame(
            frameColor=(0.06, 0.06, 0.08, 0.95),
            frameSize=(-0.82, 0.82, -0.03, 0.03),
            pos=(0.0, 0.0, -0.72),
            parent=self.frame,
        )
        place_ui_on_top(self.bar_bg, 61)

        self.bar = DirectWaitBar(
            text="",
            value=0.0,
            range=100.0,
            pos=(0.0, 0.0, -0.72),
            frameSize=(-0.8, 0.8, -0.02, 0.02),
            frameColor=(0, 0, 0, 0),
            barColor=(0.38, 0.56, 0.95, 0.95),
            relief=DGG.FLAT,
            barRelief=DGG.FLAT,
            parent=self.frame,
        )
        place_ui_on_top(self.bar, 62)

        self.frame.hide()

    def _load_config(self):
        cfg = {}
        dm_cfg = getattr(getattr(self.app, "data_mgr", None), "loading_screen_config", None)
        if isinstance(dm_cfg, dict) and dm_cfg:
            cfg = dm_cfg
        self._context = str(cfg.get("default_context", "startup") or "startup").strip().lower()
        tips = cfg.get("tips", {}) if isinstance(cfg.get("tips"), dict) else {}
        arts = cfg.get("art_images", {}) if isinstance(cfg.get("art_images"), dict) else {}
        self._tips_by_context = tips if isinstance(tips, dict) else {}
        self._arts_by_context = arts if isinstance(arts, dict) else {}

    def _context_values(self, payload, context):
        row = payload.get(context, []) if isinstance(payload, dict) else []
        if not isinstance(row, list):
            row = []
        if row:
            return [str(v).strip() for v in row if str(v or "").strip()]
        default = payload.get("default", []) if isinstance(payload, dict) else []
        if isinstance(default, list):
            return [str(v).strip() for v in default if str(v or "").strip()]
        return []

    def _tips_for_context(self, context):
        token = str(context or self._context or "default").strip().lower()
        rows = self._context_values(self._tips_by_context, token)
        if rows:
            return rows
        return [
            "Tip: Explore side paths to find hidden rewards.",
            "Tip: Use parkour to bypass direct fights.",
            "Tip: Save often before entering dangerous zones.",
            "Tip: Block and dodge to keep combo momentum.",
        ]

    def _arts_for_context(self, context):
        token = str(context or self._context or "default").strip().lower()
        rows = self._context_values(self._arts_by_context, token)
        out = []
        for rel in rows:
            candidate = str(rel or "").replace("\\", "/").strip()
            if not candidate:
                continue
            abs_path = os.path.join(getattr(self.app, "project_root", "."), candidate)
            if os.path.exists(abs_path):
                out.append(candidate)
        return out

    def _set_art_image(self, rel_path):
        if self._art_image:
            try:
                self._art_image.destroy()
            except Exception:
                pass
            self._art_image = None
        token = str(rel_path or "").strip()
        if not token:
            return
        self._art_image = OnscreenImage(
            image=token,
            pos=(0.0, 0.0, -0.06),
            scale=(0.56, 1.0, 0.31),
            parent=self.frame,
        )
        self._art_image.setTransparency(TransparencyAttrib.MAlpha)
        self._art_image.setColorScale(1.0, 1.0, 1.0, 0.78)
        place_ui_on_top(self._art_image, 62)

    def set_progress(self, value, status=""):
        clamped = max(0.0, min(1.0, float(value)))
        self.bar["value"] = clamped * 100.0
        if status:
            self.title.setText(status.upper())
        else:
            self.title.setText(self.app.data_mgr.t("ui.loading", "Loading").upper())

    def set_context(self, context):
        token = str(context or "").strip().lower()
        if token:
            self._context = token

    def update_hint(self, context=None):
        rows = self._tips_for_context(context or self._context)
        if rows:
            self.hint_text.setText(random.choice(rows))
        else:
            self.hint_text.setText("")

    def _update_art(self, context=None):
        rows = self._arts_for_context(context or self._context)
        if not rows:
            self._set_art_image("")
            return
        self._set_art_image(random.choice(rows))

    def _spin_logic(self, task):
        frame_idx = int(task.time / self._spinner_step) % len(self._spinner_frames)
        self.spinner.setText(self._spinner_frames[frame_idx])
        pulse = 0.90 + (0.08 * (0.5 + (0.5 * math.sin(task.time * 4.8))))
        self.spinner.setScale(0.105 * pulse)
        return task.cont

    def show(self, context=None):
        logger.debug("[LoadingScreen] Showing...")
        if context:
            self.set_context(context)
        self.frame.show()
        self.set_progress(self.bar["value"] / 100.0)
        self.update_hint(self._context)
        self._update_art(self._context)
        if not self.app.taskMgr.hasTaskNamed(self._spin_task_name):
            self.app.taskMgr.add(self._spin_logic, self._spin_task_name)

    def hide(self):
        logger.debug("[LoadingScreen] Hiding...")
        if self.app.taskMgr.hasTaskNamed(self._spin_task_name):
            self.app.taskMgr.remove(self._spin_task_name)
        self.frame.hide()
