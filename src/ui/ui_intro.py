"""Polished cinematic intro sequence.

Improvements over the previous version:
- Cinematic letterbox bars (top + bottom) with smooth slide-in/out
- Breathing pulse on logo scale (organic feel)
- Longer, softer fade durations with cubic easing feel
- Post-idle wait before any crossfade (logo 'lands' first)
- Tagline appears with a gentle upward drift
- Graceful fallback for missing assets (text logo)
"""

import os

from direct.gui.DirectGui import DirectFrame, OnscreenImage, OnscreenText
from direct.interval.IntervalGlobal import (
    Func,
    LerpColorScaleInterval,
    LerpHprInterval,
    LerpPosInterval,
    LerpScaleInterval,
    Parallel,
    Sequence,
    Wait,
)
from panda3d.core import TransparencyAttrib, TextNode

from ui.design_system import THEME, title_font, body_font, place_ui_on_top
from utils.logger import logger

# ─────────────────────────────────────────────────────────────────────
# Easing helpers via Panda3D blend type strings
# ─────────────────────────────────────────────────────────────────────
_EASE_IN_OUT = "easeInOut"   # Panda3D blendType (valid)
_EASE_OUT    = "easeOut"     # Panda3D blendType (valid)
_EASE_IN     = "easeIn"      # Panda3D blendType (valid)


def _fade_in(node, duration, start_alpha=0.0, end_alpha=1.0, blend=_EASE_IN_OUT):
    return LerpColorScaleInterval(
        node, duration,
        (1, 1, 1, end_alpha),
        startColorScale=(1, 1, 1, start_alpha),
        blendType=blend,
    )


def _fade_out(node, duration, start_alpha=1.0, end_alpha=0.0, blend=_EASE_IN_OUT):
    return LerpColorScaleInterval(
        node, duration,
        (1, 1, 1, end_alpha),
        startColorScale=(1, 1, 1, start_alpha),
        blendType=blend,
    )


def _scale_in(node, duration, start_scale_factor=0.92, blend=_EASE_OUT):
    base = node.getScale()
    return LerpScaleInterval(
        node, duration,
        base,
        startScale=base * start_scale_factor,
        blendType=blend,
    )


def _scale_out(node, duration, end_scale_factor=1.05, blend=_EASE_IN):
    base = node.getScale()
    return LerpScaleInterval(
        node, duration,
        base * end_scale_factor,
        blendType=blend,
    )


class IntroUI:
    def __init__(self, app, on_complete):
        self.app = app
        self.on_complete = on_complete
        self.main_seq = None
        self._ui_nodes = []
        self._done = False

        # ── Full-screen black background ───────────────────────────
        self.bg = DirectFrame(
            frameColor=THEME["bg_deep"],
            frameSize=(-2, 2, -2, 2),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self.bg, 30)
        self._ui_nodes.append(self.bg)

        # ── Cinematic letterbox bars ───────────────────────────────
        bar_h = 0.14
        self.bar_top = DirectFrame(
            frameColor=(0, 0, 0, 1),
            frameSize=(-2, 2, 0, bar_h),
            pos=(0, 0, 1.0 + bar_h),   # starts hidden above screen
            parent=self.bg,
        )
        place_ui_on_top(self.bar_top, 38)
        self._ui_nodes.append(self.bar_top)

        self.bar_bot = DirectFrame(
            frameColor=(0, 0, 0, 1),
            frameSize=(-2, 2, -bar_h, 0),
            pos=(0, 0, -(1.0 + bar_h)), # starts hidden below screen
            parent=self.bg,
        )
        place_ui_on_top(self.bar_bot, 38)
        self._ui_nodes.append(self.bar_bot)

        self._bar_h = bar_h

        # ── Vignette overlay ──────────────────────────────────────
        self.vignette = DirectFrame(
            frameColor=(0, 0, 0, 0.42),
            frameSize=(-1.78, 1.78, -1, 1),
            parent=self.bg,
        )
        place_ui_on_top(self.vignette, 31)
        self._ui_nodes.append(self.vignette)

        # ── Logo nodes ────────────────────────────────────────────
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

        # ── Skip hint ─────────────────────────────────────────────
        self.skip_hint = OnscreenText(
            text=self.app.data_mgr.t("ui.press_space_skip", "Press Space to skip"),
            # Lower safe-zone to avoid clipping on DPI-scaled window clients.
            pos=(0.0, -0.82),
            scale=0.038,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.7),
            align=TextNode.ACenter,
            parent=self.bg,
            mayChange=True,
            font=body_font(self.app),
        )
        self.skip_hint.setColorScale(1, 1, 1, 0)
        place_ui_on_top(self.skip_hint, 34)
        self._ui_nodes.append(self.skip_hint)

        # ── Tagline ───────────────────────────────────────────────
        self.tagline = OnscreenText(
            text=self.app.data_mgr.t("ui.intro_tagline", "The Kingdom is Waiting"),
            pos=(0.0, -0.70),
            scale=0.065,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.85),
            align=TextNode.ACenter,
            parent=self.bg,
            mayChange=True,
            font=title_font(self.app),
        )
        self.tagline.setColorScale(1, 1, 1, 0)
        place_ui_on_top(self.tagline, 34)
        self._ui_nodes.append(self.tagline)

    # ──────────────────────────────────────────────────────────────
    # Node factories
    # ──────────────────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────────────────
    # Logo appearance (fade-in + scale-up, then breathing pulse)
    # ──────────────────────────────────────────────────────────────

    def _logo_appear(self, node, duration=0.75):
        return Parallel(
            _fade_in(node, duration, blend=_EASE_OUT),
            _scale_in(node, duration, start_scale_factor=0.90, blend=_EASE_OUT),
        )

    def _logo_breathe(self, node, count=2, half=0.8):
        """Very subtle breathing scale animation while logo is displayed."""
        base = node.getScale()
        up   = LerpScaleInterval(node, half, base * 1.018, blendType=_EASE_IN_OUT)
        down = LerpScaleInterval(node, half, base,         blendType=_EASE_IN_OUT)
        return Sequence(*([up, down] * count))

    def _logo_exit(self, node, duration=0.55):
        return Parallel(
            _fade_out(node, duration, blend=_EASE_IN),
            _scale_out(node, duration, end_scale_factor=1.04, blend=_EASE_IN),
        )

    # ──────────────────────────────────────────────────────────────
    # Letterbox helpers
    # ──────────────────────────────────────────────────────────────

    def _bars_in(self, duration=0.55):
        bar_h = self._bar_h
        return Parallel(
            LerpPosInterval(self.bar_top, duration, (0, 0, 1.0 - bar_h),
                            blendType=_EASE_OUT),
            LerpPosInterval(self.bar_bot, duration, (0, 0, -(1.0 - bar_h)),
                            blendType=_EASE_OUT),
        )

    def _bars_out(self, duration=0.55):
        bar_h = self._bar_h
        return Parallel(
            LerpPosInterval(self.bar_top, duration, (0, 0, 1.0 + bar_h),
                            blendType=_EASE_IN),
            LerpPosInterval(self.bar_bot, duration, (0, 0, -(1.0 + bar_h)),
                            blendType=_EASE_IN),
        )

    # ──────────────────────────────────────────────────────────────
    # Sequence builder
    # ──────────────────────────────────────────────────────────────

    def _build_sequence(self):
        seq = Sequence()

        # 0. Letterbox slides in + skip hint fades in
        seq.append(Func(logger.info, "Intro: letterbox in"))
        seq.append(Parallel(
            self._bars_in(0.55),
            _fade_in(self.skip_hint, 0.8, blend=_EASE_IN_OUT),
        ))

        # 1. ANTIGRAVITY STUDIOS logo
        seq.append(Func(logger.info, "Intro: AG logo"))
        seq.append(Func(self.ag_logo.show))
        seq.append(self._logo_appear(self.ag_logo, 0.75))
        seq.append(self._logo_breathe(self.ag_logo, count=1, half=0.9))
        seq.append(Wait(0.6))  # intentional hold

        # 2. Crossfade to KW logo
        seq.append(Func(logger.info, "Intro: crossfade → KW logo"))
        seq.append(Func(self.kw_logo.show))
        seq.append(Parallel(
            self._logo_exit(self.ag_logo, 0.55),
            Sequence(
                Wait(0.15),   # slight offset so KW doesn't pop on immediately
                self._logo_appear(self.kw_logo, 0.65),
            ),
        ))
        seq.append(Func(self.ag_logo.hide))
        seq.append(self._logo_breathe(self.kw_logo, count=1, half=0.95))
        seq.append(Wait(0.7))  # intentional hold

        # 3. KW logo exits
        seq.append(self._logo_exit(self.kw_logo, 0.65))
        seq.append(Func(self.kw_logo.hide))

        # 4. Optional title slide
        if self.slide is not None:
            seq.append(Func(logger.info, "Intro: title slide"))
            seq.append(Func(self.slide.show))
            seq.append(Parallel(
                _fade_in(self.slide, 1.4, blend=_EASE_IN_OUT),
                Sequence(
                    Wait(0.4),
                    _fade_in(self.tagline, 1.0, blend=_EASE_OUT),
                ),
            ))
            seq.append(Wait(2.8))
            seq.append(Parallel(
                _fade_out(self.slide, 1.4, blend=_EASE_IN_OUT),
                _fade_out(self.tagline, 1.1, blend=_EASE_IN),
            ))
            seq.append(Func(self.slide.hide))

        # 5. Letterbox slides out + skip hint fades out
        seq.append(Parallel(
            self._bars_out(0.55),
            _fade_out(self.skip_hint, 0.45),
        ))

        # 6. Whole background fades to game
        seq.append(Wait(0.25))
        seq.append(_fade_out(self.bg, 0.8, blend=_EASE_IN_OUT))
        seq.append(Func(logger.info, "Intro: finished"))
        seq.append(Func(self.finish))
        return seq

    # ──────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────

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
