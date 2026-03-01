import random

from direct.gui.DirectGui import DirectFrame, DirectWaitBar, OnscreenText
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TextNode

from ui.design_system import THEME, body_font, title_font, place_ui_on_top
from utils.logger import logger


class LoadingScreen:
    def __init__(self, app):
        self.app = app
        self._spin_task_name = "loading_spinner_task"

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

        self.spinner = OnscreenText(
            text="+",
            pos=(0.0, 0.18),
            scale=0.26,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ACenter,
            parent=self.frame,
            mayChange=False,
            font=body_font(self.app),
        )
        place_ui_on_top(self.spinner, 61)

        self.hints = [
            "Tip: Explore side paths to find hidden rewards.",
            "Tip: Use parkour to bypass direct fights.",
            "Tip: Save often before entering dangerous zones.",
            "Tip: Block and dodge to keep combo momentum.",
        ]

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

    def set_progress(self, value, status=""):
        clamped = max(0.0, min(1.0, float(value)))
        self.bar["value"] = clamped * 100.0
        if status:
            self.title.setText(status.upper())
        else:
            self.title.setText(self.app.data_mgr.t("ui.loading", "Loading").upper())

    def update_hint(self):
        self.hint_text.setText(random.choice(self.hints))

    def _spin_logic(self, task):
        self.spinner.setR((task.time * 85.0) % 360.0)
        return task.cont

    def show(self):
        logger.debug("[LoadingScreen] Showing...")
        self.frame.show()
        self.set_progress(self.bar["value"] / 100.0)
        self.update_hint()
        if not self.app.taskMgr.hasTaskNamed(self._spin_task_name):
            self.app.taskMgr.add(self._spin_logic, self._spin_task_name)

    def hide(self):
        logger.debug("[LoadingScreen] Hiding...")
        if self.app.taskMgr.hasTaskNamed(self._spin_task_name):
            self.app.taskMgr.remove(self._spin_task_name)
        self.frame.hide()
