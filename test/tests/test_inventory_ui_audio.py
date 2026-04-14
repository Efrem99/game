import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import types

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_direct_gui = types.ModuleType("direct.gui.DirectGui")


class _StubWidget:
    def __init__(self, *args, **kwargs):
        del args, kwargs

    def show(self):
        return None

    def hide(self):
        return None

    def setPos(self, *args, **kwargs):
        return None


_direct_gui.DirectFrame = _StubWidget
_direct_gui.DirectScrolledFrame = _StubWidget
_direct_gui.OnscreenText = _StubWidget
_direct_gui.DirectButton = _StubWidget
_direct_gui.DGG = types.SimpleNamespace(DISABLED="disabled")
_gui_pkg = types.ModuleType("direct.gui")
_gui_pkg.DirectGui = _direct_gui
_showbase_global = types.ModuleType("direct.showbase.ShowBaseGlobal")
_showbase_global.globalClock = types.SimpleNamespace(getFrameTime=lambda: 1.0)
_showbase_pkg = types.ModuleType("direct.showbase")
_showbase_pkg.ShowBaseGlobal = _showbase_global
_direct_pkg = types.ModuleType("direct")
_direct_pkg.gui = _gui_pkg
_direct_pkg.showbase = _showbase_pkg
_core_pkg = types.ModuleType("panda3d.core")
_core_pkg.TextNode = types.SimpleNamespace(ALeft="left", ACenter="center")
_core_pkg.TransparencyAttrib = types.SimpleNamespace(MAlpha=1)
sys.modules.setdefault("direct", _direct_pkg)
sys.modules.setdefault("direct.gui", _gui_pkg)
sys.modules.setdefault("direct.gui.DirectGui", _direct_gui)
sys.modules.setdefault("direct.showbase", _showbase_pkg)
sys.modules.setdefault("direct.showbase.ShowBaseGlobal", _showbase_global)
sys.modules.setdefault("panda3d.core", _core_pkg)
sys.modules.setdefault(
    "render.model_visuals",
    types.SimpleNamespace(ensure_model_visual_defaults=lambda *args, **kwargs: None),
)
sys.modules.setdefault(
    "ui.design_system",
    types.SimpleNamespace(
        BUTTON_COLORS={"normal": (1, 1, 1, 1)},
        THEME={"bg_panel": (0, 0, 0, 1), "text_muted": (1, 1, 1, 1), "text_main": (1, 1, 1, 1), "danger": (1, 0, 0, 1)},
        ParchmentPanel=_StubWidget,
        body_font=lambda _app=None: None,
        title_font=lambda _app=None: None,
        place_ui_on_top=lambda *args, **kwargs: None,
    ),
)
sys.modules.setdefault(
    "utils.asset_pathing",
    types.SimpleNamespace(prefer_bam_path=lambda value, **kwargs: value),
)

from ui.menu_inventory import InventoryUI


class _VisibleNode:
    def __init__(self):
        self.visible = False
        self.props = {}

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def __setitem__(self, key, value):
        self.props[str(key)] = value


class _InventoryAudioDummy:
    _switch_tab = InventoryUI._switch_tab
    show = InventoryUI.show
    _request_close = InventoryUI._request_close

    def __init__(self):
        self._current_tab = "inventory"
        self._played = []
        self.frame = _VisibleNode()
        self.btn_inv = _VisibleNode()
        self.btn_party = _VisibleNode()
        self.btn_map = _VisibleNode()
        self.btn_skills = _VisibleNode()
        self.btn_journal = _VisibleNode()
        self.inventory_showcase = _VisibleNode()
        self.inventory_showcase_title = _VisibleNode()
        self.item_list = _VisibleNode()
        self.map_panel = _VisibleNode()
        self.map_title = _VisibleNode()
        self.map_pin_text = _VisibleNode()
        self.map_text = _VisibleNode()
        self.journal_text = _VisibleNode()
        self.journal_panel = _VisibleNode()
        self.inventory_status_text = _VisibleNode()
        self.app = SimpleNamespace(
            getAspectRatio=lambda: 16.0 / 9.0,
            aspect2d=_VisibleNode(),
            state_mgr=SimpleNamespace(current_state="PLAYING"),
            GameState=SimpleNamespace(INVENTORY="INVENTORY", PLAYING="PLAYING"),
        )

    def _play_ui_sfx(self, key, volume=1.0, rate=1.0):
        self._played.append((str(key), float(volume), float(rate)))
        return True

    def _apply_item_list_layout(self, mode):
        self.item_list.props["layout_mode"] = mode

    def _clear_map_labels(self):
        return None

    def _refresh_inventory(self):
        return None

    def _refresh_party(self):
        return None

    def _refresh_map(self):
        return None

    def _refresh_skills(self):
        return None

    def _refresh_journal(self):
        return None

    def on_window_resized(self, aspect=None):
        return aspect

    def hide(self):
        self.frame.hide()


class InventoryUIAudioTests(unittest.TestCase):
    def test_switch_tab_plays_ui_tab_sound(self):
        dummy = _InventoryAudioDummy()

        dummy._switch_tab("map")

        self.assertEqual("ui_tab", dummy._played[-1][0])

    def test_show_plays_ui_open_sound(self):
        dummy = _InventoryAudioDummy()

        dummy.show()

        self.assertEqual("ui_open", dummy._played[-1][0])

    def test_request_close_plays_ui_close_sound(self):
        dummy = _InventoryAudioDummy()

        dummy._request_close()

        self.assertEqual("ui_close", dummy._played[-1][0])


if __name__ == "__main__":
    unittest.main()
