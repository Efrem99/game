"""Shared UI theme tokens and helpers."""

import os
import shutil
import sys

from direct.gui.DirectGui import DGG, DirectFrame

_WIN_FONTS_DIR = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
_PROJECT_FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'fonts')

_PARCHMENT_TEXTURE_CANDIDATES = [
    "assets/textures/ui/parchment_main.png",
    "assets/textures/ui/parchment.jpg",
    "assets_raw/textures/ui/parchment_main.png",
    "assets_raw/textures/ui/big_background.png",
    "assets/textures/sand_seamless_texture_1771.jpg",
    "assets_raw/textures/sand_seamless_texture_1771.jpg",
]

def _ensure_system_font(name):
    """Copy a Windows system font into assets/fonts/ if missing, return the relative path."""
    dest = os.path.join(_PROJECT_FONTS, name)
    if os.path.exists(dest):
        return f"assets/fonts/{name}"
    src = os.path.join(_WIN_FONTS_DIR, name)
    if os.path.exists(src):
        os.makedirs(_PROJECT_FONTS, exist_ok=True)
        try:
            shutil.copy2(src, dest)
        except Exception:
            return None
        return f"assets/fonts/{name}"
    return None

# Pre-resolved system font paths (Unix-style relative paths Panda3D can load)
_SYS_TAHOMA_BOLD = _ensure_system_font("tahomabd.ttf")
_SYS_TAHOMA      = _ensure_system_font("tahoma.ttf")
_SYS_ARIAL_BOLD  = _ensure_system_font("arialbd.ttf")
_SYS_ARIAL       = _ensure_system_font("arial.ttf")


THEME = {
    "bg_deep": (0.02, 0.02, 0.03, 1.0),
    "bg_panel": (0.08, 0.08, 0.10, 0.78),
    "gold_primary": (0.92, 0.78, 0.32, 1.0),
    "gold_soft": (0.85, 0.75, 0.55, 1.0),
    "text_main": (0.98, 0.96, 0.92, 1.0),
    "text_muted": (0.80, 0.78, 0.75, 1.0),
    "text_accent": (0.65, 0.15, 0.12, 1.0), # Deep red accent
    "danger": (0.85, 0.25, 0.20, 1.0),
    "parchment": (0.94, 0.88, 0.78, 1.0),
}


BUTTON_COLORS = {
    "normal": (1.0, 1.0, 1.0, 0.95),
    "hover": (1.0, 1.0, 1.0, 1.0),
    "pressed": (0.95, 0.90, 0.85, 1.0),
    "disabled": (0.55, 0.55, 0.55, 0.8),
}


_FONT_CACHE = {}


def _load_font_with_fallback(loader, candidates):
    for font_name in candidates:
        # Skip missing filesystem fonts to avoid noisy pnmtext errors.
        if (
            ("/" in font_name or "\\" in font_name or font_name.lower().endswith((".ttf", ".otf")))
            and not os.path.exists(font_name)
        ):
            continue
        try:
            font = loader.loadFont(font_name)
            if font and not font.isValid():
                continue
            if font:
                if hasattr(font, 'setPixelsPerUnit'):
                    font.setPixelsPerUnit(60)
                if hasattr(font, 'setPageSize'):
                    font.setPageSize(512, 512)
                return font
        except Exception:
            continue
    return None


def _get_cached_font(app, role, candidates):
    cache_key = (role, tuple(candidates))
    if cache_key not in _FONT_CACHE:
        _FONT_CACHE[cache_key] = _load_font_with_fallback(app.loader, candidates)
    return _FONT_CACHE[cache_key]


def title_font(app):
    return _get_cached_font(
        app,
        "title",
        [f for f in [
            "assets/fonts/cinzel-bold.ttf",
            "assets/fonts/trajanpro-regular.ttf",
            _SYS_TAHOMA_BOLD,
            _SYS_TAHOMA,
            _SYS_ARIAL_BOLD,
            _SYS_ARIAL,
            "cmss12",
        ] if f],
    )


def body_font(app):
    return _get_cached_font(
        app,
        "body",
        [f for f in [
            "assets/fonts/cinzel-regular.ttf",
            "assets/fonts/merriweather-regular.ttf",
            _SYS_TAHOMA,
            _SYS_ARIAL,
            "cmss12",
        ] if f],
    )


def place_ui_on_top(node, sort=40):
    node.set_shader_off(1001)
    node.setBin("fixed", sort)
    node.setDepthTest(False)
    node.setDepthWrite(False)


def get_parchment_texture_path():
    for candidate in _PARCHMENT_TEXTURE_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def get_parchment_texture(app):
    tex_path = get_parchment_texture_path()
    if tex_path:
        return app.loader.loadTexture(tex_path)
    return None


class ParchmentPanel(DirectFrame):
    """Themed panel using sand/parchment texture with a gold-bordered relief."""
    def __init__(self, app, **kwargs):
        tex = get_parchment_texture(app)

        style = {
            "frameColor": (1, 1, 1, 1) if tex else THEME["parchment"],
            "frameTexture": tex,
            "relief": DGG.RIDGE,
            "borderWidth": (0.012, 0.012),
        }
        style.update(kwargs)
        super().__init__(**style)
        self.setTransparency(1)
        self.setColorScale(0.85, 0.82, 0.78, 1.0) # Slightly darken parchment
        place_ui_on_top(self, style.get("sort", 40))
