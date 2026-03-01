import os

from direct.gui.DirectGui import DirectFrame, OnscreenImage, OnscreenText
from direct.interval.IntervalGlobal import (
    Sequence,
    Wait,
    Func,
    LerpColorScaleInterval,
    LerpScaleInterval,
    Parallel,
)
from panda3d.core import TransparencyAttrib, TextNode

from ui.design_system import THEME, title_font, body_font, place_ui_on_top
from utils.logger import logger


class IntroUI:
    def __init__(self, app, on_complete):
        self.app = app
        self.on_complete = on_complete
        self.main_seq = None
        self._ui_nodes = []
        self._done = False

        self.bg = DirectFrame(
            frameColor=THEME["bg_deep"],
            frameSize=(-2, 2, -2, 2),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self.bg, 30)
        self._ui_nodes.append(self.bg)

        self.vignette = DirectFrame(
            frameColor=(0, 0, 0, 0.46),
            frameSize=(-1.7, 1.7, -1, 1),
            parent=self.bg,
        )
        place_ui_on_top(self.vignette, 31)
        self._ui_nodes.append(self.vignette)

        self.ag_logo = self._create_logo(
            "assets/textures/antigravity_logo.png",
            "ANTIGRAVITY STUDIOS",
            scale=0.34,
        )
        self.kw_logo = self._create_logo(
            "assets/textures/kw_logo.png",
            "KING WIZARD",
            scale=0.30,
        )
        self.slide = self._create_slide("assets_raw/textures/ui/big_background.png")

        self.skip_hint = OnscreenText(
            text=self.app.data_mgr.t("ui.press_space_skip", "Press Space to skip"),
            pos=(0.0, -0.90),
            scale=0.04,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.7),
            align=TextNode.ACenter,
            parent=self.bg,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.skip_hint, 34)
        self._ui_nodes.append(self.skip_hint)

        self.tagline = OnscreenText(
            text=self.app.data_mgr.t("ui.intro_tagline", "The Kingdom is Waiting"),
            pos=(0.0, -0.72),
            scale=0.06,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ACenter,
            parent=self.bg,
            mayChange=True,
            font=title_font(self.app),
        )
        self.tagline.setColorScale(1, 1, 1, 0)
        place_ui_on_top(self.tagline, 34)
        self._ui_nodes.append(self.tagline)

    def _create_logo(self, path, fallback, scale):
        if os.path.exists(path):
            node = OnscreenImage(image=path, parent=self.bg, scale=scale)
            node.setTransparency(TransparencyAttrib.MAlpha)
        else:
            node = OnscreenText(
                text=fallback,
                parent=self.bg,
                scale=0.11,
                fg=THEME["gold_primary"],
                align=TextNode.ACenter,
                font=title_font(self.app),
            )
        node.setColorScale(1, 1, 1, 0)
        node.hide()
        place_ui_on_top(node, 33)
        self._ui_nodes.append(node)
        return node

    def _create_slide(self, path):
        if not os.path.exists(path):
            return None
        slide = OnscreenImage(image=path, parent=self.bg, scale=(1.78, 1, 1))
        slide.setTransparency(TransparencyAttrib.MAlpha)
        slide.setColorScale(1, 1, 1, 0)
        slide.hide()
        place_ui_on_top(slide, 32)
        self._ui_nodes.append(slide)
        return slide

    def _logo_appearance(self, node):
        return Parallel(
            LerpColorScaleInterval(
                node,
                0.6,
                (1, 1, 1, 1),
                startColorScale=(1, 1, 1, 0),
            ),
            LerpScaleInterval(
                node,
                0.6,
                node.getScale(),
                startScale=node.getScale() * 0.95,
            ),
        )

    def _build_sequence(self):
        seq = Sequence(
            Func(logger.info, "Intro stage 1: antigravity logo"),
            Func(self.ag_logo.show),
            self._logo_appearance(self.ag_logo),
            Wait(1.6),
            Func(logger.info, "Intro crossfade to KW logo"),
            Func(self.kw_logo.show),
            Parallel(
                LerpColorScaleInterval(
                    self.ag_logo,
                    0.5,
                    (1, 1, 1, 0),
                    startColorScale=(1, 1, 1, 1),
                ),
                LerpColorScaleInterval(
                    self.kw_logo,
                    0.5,
                    (1, 1, 1, 1),
                    startColorScale=(1, 1, 1, 0),
                ),
                LerpScaleInterval(
                    self.kw_logo,
                    0.5,
                    self.kw_logo.getScale(),
                    startScale=self.kw_logo.getScale() * 0.95,
                ),
            ),
            Func(self.ag_logo.hide),
            Wait(1.6),
            Parallel(
                LerpColorScaleInterval(
                    self.kw_logo,
                    0.6,
                    (1, 1, 1, 0),
                    startColorScale=(1, 1, 1, 1),
                ),
                LerpScaleInterval(
                    self.kw_logo,
                    0.6,
                    self.kw_logo.getScale() * 1.04,
                    startScale=self.kw_logo.getScale(),
                ),
            ),
            Func(self.kw_logo.hide),
        )
        if self.slide is not None:
            seq.append(Func(logger.info, "Intro optional slide"))
            seq.append(Func(self.slide.show))
            seq.append(
                Parallel(
                    LerpColorScaleInterval(
                        self.slide,
                        1.2,
                        (1, 1, 1, 1),
                        startColorScale=(1, 1, 1, 0),
                    ),
                    LerpColorScaleInterval(
                        self.tagline,
                        1.2,
                        (1, 1, 1, 1),
                        startColorScale=(1, 1, 1, 0),
                    ),
                )
            )
            seq.append(Wait(2.5))
            seq.append(
                Parallel(
                    LerpColorScaleInterval(
                        self.slide,
                        1.2,
                        (1, 1, 1, 0),
                        startColorScale=(1, 1, 1, 1),
                    ),
                    LerpColorScaleInterval(
                        self.tagline,
                        1.2,
                        (1, 1, 1, 0),
                        startColorScale=(1, 1, 1, 1),
                    ),
                )
            )
            seq.append(Func(self.slide.hide))

        seq.append(Wait(0.5))
        seq.append(
            LerpColorScaleInterval(
                self.bg,
                0.5,
                (1, 1, 1, 0),
                startColorScale=(1, 1, 1, 1),
            )
        )
        seq.append(Func(logger.info, "Intro finished"))
        seq.append(Func(self.finish))
        return seq

    def start(self):
        self._done = False
        self.app.accept("space", self.finish)
        self.main_seq = self._build_sequence()
        self.main_seq.start()

    def _cleanup(self):
        self.app.ignore("space")
        if self.main_seq:
            self.main_seq.pause()
            self.main_seq = None
        for node in self._ui_nodes:
            try:
                node.destroy()
            except Exception:
                pass
        self._ui_nodes = []

    def finish(self):
        if self._done:
            return
        self._done = True
        self._cleanup()
        if self.on_complete:
            self.on_complete()
