import logging
import math
from pathlib import Path

from direct.gui.DirectGui import DirectFrame, DirectScrolledFrame, OnscreenText, DirectButton, DGG
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import TextNode, TransparencyAttrib

from render.model_visuals import ensure_model_visual_defaults
from ui.design_system import (
    BUTTON_COLORS,
    THEME,
    ParchmentPanel,
    body_font,
    title_font,
    place_ui_on_top
)
from ui.inventory_support import (
    build_skill_tree_layout,
    derive_inventory_character_visual_profile,
)
from ui.ui_audio import play_ui_sfx
from utils.asset_pathing import prefer_bam_path


logger = logging.getLogger("XBotRPG")

class InventoryUI:
    def _play_ui_sfx(self, key, volume=1.0, rate=1.0):
        return play_ui_sfx(self.app, key, volume=volume, rate=rate)

    def __init__(self, app):
        self.app = app
        self._rows = []
        self._current_tab = "inventory"  # "inventory", "party", "map", "skills", "journal"
        self._map_range = 180.0
        self._map_pin_markers = []
        self._map_pin_labels = []
        self._inventory_status = ""
        self._skill_status = ""
        self._equip_slot_frames = {}
        self._equip_slot_titles = {}
        self._equip_slot_values = {}
        self._item_list_layout_mode = ""
        self._item_list_row_layout = {}
        self._char_follow_x = 0.0
        self._char_follow_z = 0.0
        
        self._rtt_buffer = None
        self._rtt_cam = None
        self._rtt_scene = None
        self._preview_actor = None
        self._preview_light = None

        asp = self.app.getAspectRatio()
        overlay_alpha = 0.10 if bool(getattr(self.app, "_video_bot_visibility_boost", False)) else 0.18
        self.frame = DirectFrame(
            frameColor=(0, 0, 0, overlay_alpha),
            frameSize=(-asp, asp, -1, 1),
            parent=self.app.aspect2d,
            suppressMouse=1,
        )
        place_ui_on_top(self.frame, 30)

        # Main parchment panel
        self.panel = ParchmentPanel(
            self.app,
            parent=self.frame,
            frameSize=(-0.9, 0.9, -0.7, 0.7),
            pos=(0, 0, 0)
        )

        self.title = OnscreenText(
            text=self.app.data_mgr.get_ui_str("inventory", "title") or "Character Data",
            pos=(0, 0.55),
            scale=0.08,
            font=title_font(self.app),
            fg=THEME["text_main"],
            parent=self.panel
        )

        self._build_tabs()

        self.content_frame = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.8, 0.8, -0.6, 0.45),
            parent=self.panel,
        )

        self.item_list = DirectScrolledFrame(
            canvasSize=(-0.68, 0.68, -2, 0),
            frameSize=(-0.7, 0.7, -0.5, 0.4),
            frameColor=(0, 0, 0, 0),
            verticalScroll_frameColor=THEME["bg_panel"],
            verticalScroll_thumb_frameColor=THEME["text_muted"],
            verticalScroll_incButton_frameColor=THEME["bg_panel"],
            verticalScroll_decButton_frameColor=THEME["bg_panel"],
            parent=self.content_frame
        )
        self._build_inventory_showcase()
        self._apply_item_list_layout("full")

        self.map_text = OnscreenText(
            text="",
            pos=(-0.66, -0.36),
            scale=0.03,
            font=body_font(self.app),
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            mayChange=True,
            parent=self.content_frame
        )
        self._build_map_panel()

        self._build_journal_book()
        self.inventory_status_text = OnscreenText(
            text="",
            pos=(-0.66, -0.54),
            scale=0.03,
            font=body_font(self.app),
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            mayChange=True,
            parent=self.content_frame,
        )

        # Close button
        self.close_btn = DirectButton(
            parent=self.panel,
            text="Close [Esc]",
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.2, 0.2, -0.06, 0.08),
            pos=(0, 0, -0.6),
            frameColor=THEME["danger"],
            text_fg=THEME["text_main"],
            command=self._request_close,
            relief=1
        )

        self._setup_3d_preview()
        self.hide()
        if hasattr(self.app, "taskMgr") and self.app.taskMgr:
            self.app.taskMgr.add(self._inventory_character_follow_task, "inventory_character_follow_task")
        self.on_window_resized(self.app.getAspectRatio())

    @staticmethod
    def _layout_profile_for_aspect(aspect):
        try:
            asp = float(aspect)
        except Exception:
            asp = 16.0 / 9.0
        asp = max(1.20, min(3.40, asp))
        baseline = 16.0 / 9.0
        deviation = abs(asp - baseline)
        panel_scale = max(0.86, min(1.0, 1.0 - (deviation * 0.16)))
        tab_offset = max(0.56, min(0.66, 0.66 - (deviation * 0.11)))
        tab_text_scale = max(0.039, min(0.045, 0.045 - (deviation * 0.004)))
        close_text_scale = max(0.040, min(0.045, 0.045 - (deviation * 0.003)))
        return {
            "aspect": asp,
            "panel_scale": panel_scale,
            "tab_offset": tab_offset,
            "tab_text_scale": tab_text_scale,
            "close_text_scale": close_text_scale,
        }

    def on_window_resized(self, aspect=None):
        profile = self._layout_profile_for_aspect(
            self.app.getAspectRatio() if aspect is None else aspect
        )
        asp = float(profile["aspect"])
        self.frame["frameSize"] = (-asp, asp, -1, 1)
        self.panel.setScale(float(profile["panel_scale"]))

        off = float(profile["tab_offset"])
        tab_positions = (-off, -off * 0.5, 0.0, off * 0.5, off)
        tab_text_scale = float(profile["tab_text_scale"])
        for btn, x in zip(self._tab_buttons, tab_positions):
            btn.setPos(x, 0, 0)
            btn["text_scale"] = tab_text_scale
        self.close_btn["text_scale"] = float(profile["close_text_scale"])

    def _build_map_panel(self):
        self.map_panel = DirectFrame(
            frameColor=(0.10, 0.09, 0.08, 0.68),
            frameSize=(-0.66, 0.66, -0.32, 0.32),
            pos=(0.0, 0, 0.02),
            parent=self.content_frame,
        )
        self.map_grid_h = DirectFrame(
            frameColor=(0.68, 0.62, 0.50, 0.22),
            frameSize=(-0.62, 0.62, -0.0015, 0.0015),
            parent=self.map_panel,
        )
        self.map_grid_v = DirectFrame(
            frameColor=(0.68, 0.62, 0.50, 0.22),
            frameSize=(-0.0015, 0.0015, -0.28, 0.28),
            parent=self.map_panel,
        )
        self.map_player_marker = DirectFrame(
            frameColor=(0.26, 0.76, 0.95, 0.98),
            frameSize=(-0.012, 0.012, -0.012, 0.012),
            parent=self.map_panel,
        )
        for _ in range(3):
            marker = DirectFrame(
                frameColor=(0.95, 0.78, 0.28, 0.95),
                frameSize=(-0.010, 0.010, -0.010, 0.010),
                parent=self.map_panel,
            )
            marker.hide()
            self._map_pin_markers.append(marker)

        self.map_title = OnscreenText(
            text=self.app.data_mgr.t("ui.map", "Map"),
            pos=(0, 0.36),
            scale=0.05,
            font=title_font(self.app),
            fg=THEME["gold_soft"],
            align=TextNode.ACenter,
            mayChange=True,
            parent=self.content_frame,
        )
        self.map_pin_text = OnscreenText(
            text="",
            pos=(-0.66, 0.38),
            scale=0.028,
            font=body_font(self.app),
            fg=THEME["text_main"],
            align=TextNode.ALeft,
            mayChange=True,
            parent=self.content_frame,
        )

    def _build_journal_book(self):
        self.journal_panel = DirectFrame(
            frameColor=(0.14, 0.12, 0.10, 0.58),
            frameSize=(-0.70, 0.70, -0.43, 0.43),
            pos=(0.0, 0.0, -0.02),
            parent=self.content_frame,
        )
        self.journal_left_page = DirectFrame(
            frameColor=(0.94, 0.88, 0.74, 0.92),
            frameSize=(-0.67, -0.01, -0.40, 0.40),
            parent=self.journal_panel,
        )
        self.journal_right_page = DirectFrame(
            frameColor=(0.93, 0.87, 0.73, 0.92),
            frameSize=(0.01, 0.67, -0.40, 0.40),
            parent=self.journal_panel,
        )
        self.journal_spine = DirectFrame(
            frameColor=(0.28, 0.22, 0.17, 0.72),
            frameSize=(-0.012, 0.012, -0.40, 0.40),
            parent=self.journal_panel,
        )
        self.journal_left_title = OnscreenText(
            text="Chronicle",
            pos=(-0.34, 0.35),
            scale=0.036,
            font=title_font(self.app),
            fg=(0.28, 0.20, 0.12, 1.0),
            align=TextNode.ACenter,
            mayChange=True,
            parent=self.journal_panel,
        )
        self.journal_right_title = OnscreenText(
            text="Codex",
            pos=(0.34, 0.35),
            scale=0.036,
            font=title_font(self.app),
            fg=(0.28, 0.20, 0.12, 1.0),
            align=TextNode.ACenter,
            mayChange=True,
            parent=self.journal_panel,
        )
        self.journal_left_text = OnscreenText(
            text="",
            pos=(-0.65, 0.30),
            scale=0.025,
            font=body_font(self.app),
            fg=(0.22, 0.18, 0.12, 1.0),
            align=TextNode.ALeft,
            wordwrap=26,
            mayChange=True,
            parent=self.journal_panel,
        )
        self.journal_right_text = OnscreenText(
            text="",
            pos=(0.03, 0.30),
            scale=0.025,
            font=body_font(self.app),
            fg=(0.22, 0.18, 0.12, 1.0),
            align=TextNode.ALeft,
            wordwrap=26,
            mayChange=True,
            parent=self.journal_panel,
        )
        self.journal_footer_text = OnscreenText(
            text="",
            pos=(0.0, -0.37),
            scale=0.022,
            font=body_font(self.app),
            fg=(0.36, 0.28, 0.18, 1.0),
            align=TextNode.ACenter,
            mayChange=True,
            parent=self.journal_panel,
        )

        # Legacy fallback node kept for compatibility with old code paths.
        self.journal_text = OnscreenText(
            text="",
            pos=(-0.66, 0.35),
            scale=0.042,
            font=body_font(self.app),
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            wordwrap=34,
            parent=self.content_frame,
        )
        self.journal_text.hide()

    def _build_tabs(self):
        self.tabs_frame = DirectFrame(
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.45),
            parent=self.panel
        )

        self.btn_inv = DirectButton(
            parent=self.tabs_frame,
            text="Inventory",
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.17, 0.17, -0.05, 0.06),
            pos=(-0.66, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["inventory"],
            relief=1
        )

        self.btn_party = DirectButton(
            parent=self.tabs_frame,
            text=self.app.data_mgr.t("ui.party", "Party"),
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.17, 0.17, -0.05, 0.06),
            pos=(-0.33, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["party"],
            relief=1
        )

        self.btn_map = DirectButton(
            parent=self.tabs_frame,
            text="Map",
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.17, 0.17, -0.05, 0.06),
            pos=(0.0, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["map"],
            relief=1
        )

        self.btn_skills = DirectButton(
            parent=self.tabs_frame,
            text="Skills",
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.17, 0.17, -0.05, 0.06),
            pos=(0.33, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["skills"],
            relief=1
        )

        self.btn_journal = DirectButton(
            parent=self.tabs_frame,
            text="Journal",
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.17, 0.17, -0.05, 0.06),
            pos=(0.66, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["journal"],
            relief=1
        )
        self._tab_buttons = (
            self.btn_inv,
            self.btn_party,
            self.btn_map,
            self.btn_skills,
            self.btn_journal,
        )

    def _build_inventory_showcase(self):
        self.inventory_showcase = DirectFrame(
            frameColor=(0.18, 0.14, 0.11, 0.62),
            frameSize=(-0.68, 0.18, -0.53, 0.43),
            pos=(-0.08, 0.0, -0.01),
            parent=self.content_frame,
        )

        self.inventory_showcase_title = OnscreenText(
            text=self.app.data_mgr.t("ui.equipment", "Equipment"),
            pos=(-0.27, 0.38),
            scale=0.036,
            font=title_font(self.app),
            fg=THEME["gold_soft"],
            align=TextNode.ACenter,
            mayChange=False,
            parent=self.content_frame,
        )

        # The plate itself has the texture mapped to it natively.
        self.character_plate = DirectFrame(
            frameColor=(0.96, 0.91, 0.82, 0.08),
            frameSize=(-0.20, 0.20, -0.36, 0.36),
            pos=(-0.28, 0.0, -0.05),
            parent=self.inventory_showcase,
        )
        self.character_plate_border = DirectFrame(
            frameColor=(0.74, 0.66, 0.50, 0.62),
            frameSize=(-0.206, 0.206, -0.366, 0.366),
            pos=(-0.28, 0.0, -0.05),
            parent=self.inventory_showcase,
        )
        self.character_plate_border.setTransparency(TransparencyAttrib.MAlpha)

        self._add_equipment_slot_widget("weapon_main", "Main Hand", (-0.56, 0.13))
        self._add_equipment_slot_widget("offhand", "Off Hand", (0.03, 0.13))
        self._add_equipment_slot_widget("chest", "Armor", (-0.56, -0.12))
        self._add_equipment_slot_widget("trinket", "Trinket", (0.03, -0.12))

    def _add_equipment_slot_widget(self, slot_id, title, pos_xy):
        x, z = pos_xy
        frame = DirectFrame(
            frameColor=(0.26, 0.21, 0.16, 0.88),
            frameSize=(-0.17, 0.17, -0.09, 0.09),
            pos=(x, 0.0, z),
            parent=self.inventory_showcase,
        )
        title_text = OnscreenText(
            text=title,
            pos=(x, z + 0.06),
            scale=0.024,
            font=title_font(self.app),
            fg=THEME["text_muted"],
            align=TextNode.ACenter,
            mayChange=False,
            parent=self.inventory_showcase,
        )
        value_text = OnscreenText(
            text="Empty",
            pos=(x, z - 0.015),
            scale=0.024,
            font=body_font(self.app),
            fg=THEME["text_main"],
            align=TextNode.ACenter,
            mayChange=True,
            parent=self.inventory_showcase,
        )
        self._equip_slot_frames[slot_id] = frame
        self._equip_slot_titles[slot_id] = title_text
        self._equip_slot_values[slot_id] = value_text

    def _apply_item_list_layout(self, mode):
        normalized = str(mode or "full").strip().lower()
        if normalized == self._item_list_layout_mode:
            return
        self._item_list_layout_mode = normalized

        if normalized == "inventory":
            self.item_list["frameSize"] = (-0.43, 0.43, -0.5, 0.4)
            self.item_list["frameColor"] = (0.18, 0.14, 0.11, 0.40)
            self.item_list.setPos(0.35, 0.0, 0.0)
            self._item_list_row_layout = {
                "canvas_left": -0.42,
                "canvas_right": 0.42,
                "row_left": -0.40,
                "row_right": 0.40,
                "icon_x": -0.34,
                "text_x": -0.29,
                "desc_x": -0.29,
                "btn_x": 0.29,
            }
        else:
            self.item_list["frameSize"] = (-0.7, 0.7, -0.5, 0.4)
            self.item_list["frameColor"] = (0.16, 0.13, 0.10, 0.28)
            self.item_list.setPos(0.0, 0.0, 0.0)
            self._item_list_row_layout = {
                "canvas_left": -0.68,
                "canvas_right": 0.68,
                "row_left": -0.66,
                "row_right": 0.66,
                "icon_x": -0.61,
                "text_x": -0.55,
                "desc_x": -0.55,
                "btn_x": 0.48,
            }

    def _refresh_equipment_showcase(self, equipped):
        payload = equipped if isinstance(equipped, dict) else {}
        for slot in ("weapon_main", "offhand", "chest", "trinket"):
            frame = self._equip_slot_frames.get(slot)
            value_label = self._equip_slot_values.get(slot)
            token = str(payload.get(slot, "") or "").strip()
            item = self.app.data_mgr.get_item(token) if token else None
            if isinstance(item, dict):
                name = str(item.get("name", token) or token).strip() or token
                value_label["text"] = name
                active = self._slot_color(slot)
                frame["frameColor"] = (active[0], active[1], active[2], 0.95)
            else:
                value_label["text"] = "Empty"
                frame["frameColor"] = (0.18, 0.16, 0.14, 0.82)
        self._apply_character_visual_profile(derive_inventory_character_visual_profile(payload))

    def _preview_model_candidates(self):
        cfg = {}
        dm = getattr(self.app, "data_mgr", None)
        if dm and hasattr(dm, "get_player_config"):
            try:
                cfg = dm.get_player_config() or {}
            except Exception:
                cfg = {}
        candidates = []

        def _add(path_token):
            token = str(path_token or "").strip().replace("\\", "/")
            if not token:
                return
            resolved = prefer_bam_path(token)
            if resolved not in candidates:
                candidates.append(resolved)

        raw_candidates = cfg.get("model_candidates", [])
        if isinstance(raw_candidates, list):
            for entry in raw_candidates:
                _add(entry)
        _add(cfg.get("model"))
        _add(cfg.get("fallback_model"))
        _add("assets/models/xbot/Xbot.glb")
        return [path for path in candidates if Path(path).exists()]

    def _load_preview_actor(self):
        from direct.actor.Actor import Actor

        for model_path in self._preview_model_candidates():
            try:
                actor = Actor(model_path)
                mins, maxs = actor.getTightBounds()
                if mins is None or maxs is None:
                    continue
                height = abs(float((maxs - mins).z))
                depth = abs(float((maxs - mins).y))
                if height < 0.6 or depth < 0.05:
                    continue
                return actor
            except Exception:
                continue
        return None

    def _fit_preview_actor(self):
        actor = getattr(self, "_preview_actor", None)
        if not actor:
            return
        try:
            mins, maxs = actor.getTightBounds()
        except Exception:
            return
        if mins is None or maxs is None:
            return
        height = max(0.1, abs(float((maxs - mins).z)))
        target_height = 2.55
        scale_mul = max(0.6, min(2.8, target_height / height))
        actor.setScale(scale_mul)
        try:
            mins, maxs = actor.getTightBounds()
        except Exception:
            return
        if mins is None or maxs is None:
            return
        actor.setPos(0.0, 0.0, -float(mins.z) - 1.15)

    def _preview_piece(self, parent, name, model, scale, pos, color, hpr=(0.0, 0.0, 0.0)):
        node = self.app.loader.loadModel(model)
        node.reparentTo(parent)
        node.setName(str(name))
        node.setScale(*scale)
        node.setPos(*pos)
        node.setHpr(*hpr)
        node.setColorScale(*color)
        ensure_model_visual_defaults(
            node,
            apply_skin=False,
            force_two_sided=True,
            debug_label=f"inventory_preview:{name}",
        )
        return node

    def _preview_child_name(self, node):
        if node is None:
            return ""
        getter = getattr(node, "getName", None)
        if callable(getter):
            try:
                return str(getter() or "").strip()
            except Exception:
                return ""
        return str(getattr(node, "name", "") or "").strip()

    def _set_preview_named_visibility(self, root, visible_names):
        if not root or not hasattr(root, "getChildren"):
            return
        visible = {str(name or "").strip() for name in list(visible_names or []) if str(name or "").strip()}
        try:
            children = list(root.getChildren())
        except Exception:
            return
        for child in children:
            name = InventoryUI._preview_child_name(self, child)
            if not name:
                continue
            should_show = name in visible
            method_name = "show" if should_show else "hide"
            method = getattr(child, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    continue

    def _build_preview_equipment_nodes(self):
        if not getattr(self, "_preview_actor", None):
            return

        self._preview_armor_root = self._preview_actor.attachNewNode("preview_armor_root")
        self._preview_armor_root.setPos(0.0, 0.05, 0.0)
        self._preview_piece(
            self._preview_armor_root,
            "armor_plate",
            "models/misc/rgbCube",
            (0.64, 0.18, 0.84),
            (0.0, 0.0, 1.02),
            (0.74, 0.76, 0.82, 1.0),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_collar",
            "models/misc/rgbCube",
            (0.36, 0.12, 0.16),
            (0.0, 0.06, 1.50),
            (0.86, 0.82, 0.72, 0.98),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_jerkin",
            "models/misc/rgbCube",
            (0.60, 0.16, 0.78),
            (0.0, 0.04, 1.00),
            (0.42, 0.32, 0.22, 0.98),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_strap_l",
            "models/misc/rgbCube",
            (0.08, 0.05, 0.62),
            (-0.18, 0.12, 1.04),
            (0.24, 0.18, 0.12, 1.0),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_strap_r",
            "models/misc/rgbCube",
            (0.08, 0.05, 0.62),
            (0.18, 0.12, 1.04),
            (0.24, 0.18, 0.12, 1.0),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_pauldron_l",
            "models/misc/rgbCube",
            (0.22, 0.16, 0.16),
            (-0.36, 0.06, 1.38),
            (0.78, 0.78, 0.84, 0.98),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_pauldron_r",
            "models/misc/rgbCube",
            (0.22, 0.16, 0.16),
            (0.36, 0.06, 1.38),
            (0.78, 0.78, 0.84, 0.98),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_tasset_l",
            "models/misc/rgbCube",
            (0.14, 0.08, 0.26),
            (-0.16, 0.06, 0.52),
            (0.62, 0.62, 0.68, 0.96),
        )
        self._preview_piece(
            self._preview_armor_root,
            "armor_tasset_r",
            "models/misc/rgbCube",
            (0.14, 0.08, 0.26),
            (0.16, 0.06, 0.52),
            (0.62, 0.62, 0.68, 0.96),
        )

        self._preview_weapon_root = self._preview_actor.attachNewNode("preview_weapon_root")
        self._preview_weapon_root.setPos(-0.42, 0.06, 0.82)
        self._preview_weapon_root.setHpr(-20.0, 0.0, 18.0)
        self._preview_piece(
            self._preview_weapon_root,
            "weapon_blade",
            "models/misc/rgbCube",
            (0.05, 0.02, 0.78),
            (0.0, 0.0, 0.46),
            (0.88, 0.88, 0.94, 1.0),
        )
        self._preview_piece(
            self._preview_weapon_root,
            "weapon_guard",
            "models/misc/rgbCube",
            (0.18, 0.04, 0.04),
            (0.0, 0.0, 0.12),
            (0.76, 0.70, 0.58, 1.0),
        )
        self._preview_piece(
            self._preview_weapon_root,
            "bow_limb_top",
            "models/misc/rgbCube",
            (0.04, 0.02, 0.62),
            (0.0, -0.02, 0.36),
            (0.52, 0.34, 0.18, 1.0),
            hpr=(24.0, 0.0, 0.0),
        )
        self._preview_piece(
            self._preview_weapon_root,
            "bow_limb_bottom",
            "models/misc/rgbCube",
            (0.04, 0.02, 0.62),
            (0.0, -0.02, -0.18),
            (0.52, 0.34, 0.18, 1.0),
            hpr=(-24.0, 0.0, 0.0),
        )
        self._preview_piece(
            self._preview_weapon_root,
            "bow_string",
            "models/misc/rgbCube",
            (0.01, 0.01, 1.08),
            (0.0, -0.08, 0.10),
            (0.90, 0.90, 0.82, 0.86),
        )
        self._preview_piece(
            self._preview_weapon_root,
            "magic_focus",
            "models/misc/sphere",
            (0.11, 0.11, 0.11),
            (0.0, 0.02, 0.36),
            (0.52, 0.70, 0.96, 0.96),
        )
        self._preview_piece(
            self._preview_weapon_root,
            "magic_shaft",
            "models/misc/rgbCube",
            (0.04, 0.04, 0.86),
            (0.0, 0.0, -0.08),
            (0.44, 0.34, 0.24, 1.0),
        )

        self._preview_shield_root = self._preview_actor.attachNewNode("preview_shield_root")
        self._preview_shield_root.setPos(0.42, 0.02, 1.02)
        self._preview_piece(
            self._preview_shield_root,
            "shield_body",
            "models/misc/rgbCube",
            (0.24, 0.08, 0.34),
            (0.0, 0.0, 0.0),
            (0.74, 0.78, 0.84, 1.0),
        )
        self._preview_piece(
            self._preview_shield_root,
            "shield_rim",
            "models/misc/rgbCube",
            (0.28, 0.10, 0.06),
            (0.0, 0.02, 0.18),
            (0.78, 0.74, 0.66, 1.0),
        )
        self._preview_piece(
            self._preview_shield_root,
            "shield_tower_extension",
            "models/misc/rgbCube",
            (0.20, 0.08, 0.28),
            (0.0, 0.0, -0.30),
            (0.64, 0.68, 0.74, 1.0),
        )

        self._preview_trinket_root = self._preview_actor.attachNewNode("preview_trinket_root")
        self._preview_trinket_root.setPos(0.0, 0.12, 1.18)
        self._preview_piece(
            self._preview_trinket_root,
            "trinket_core",
            "models/misc/sphere",
            (0.06, 0.04, 0.08),
            (0.0, 0.0, 0.0),
            (0.90, 0.92, 0.98, 1.0),
        )
        self._preview_piece(
            self._preview_trinket_root,
            "trinket_loop",
            "models/misc/rgbCube",
            (0.07, 0.03, 0.04),
            (0.0, 0.0, 0.12),
            (0.86, 0.82, 0.54, 0.98),
        )
        self._preview_piece(
            self._preview_trinket_root,
            "trinket_plate",
            "models/misc/rgbCube",
            (0.14, 0.03, 0.10),
            (0.0, 0.0, -0.02),
            (0.72, 0.74, 0.86, 0.96),
        )
        self._preview_piece(
            self._preview_trinket_root,
            "trinket_tassel",
            "models/misc/rgbCube",
            (0.03, 0.03, 0.18),
            (0.0, 0.0, -0.18),
            (0.66, 0.54, 0.34, 0.94),
        )

    def _apply_character_visual_profile(self, profile):
        payload = profile if isinstance(profile, dict) else {}

        weapon_visible = bool(payload.get("weapon_visible"))
        shield_visible = bool(payload.get("shield_visible"))
        trinket_visible = bool(payload.get("trinket_visible"))
        weapon_style = str(payload.get("weapon_style", "blade") or "blade").strip().lower()
        armor_style = str(payload.get("armor_style", "medium") or "medium").strip().lower()
        offhand_style = str(payload.get("offhand_style", "ward") or "ward").strip().lower()
        trinket_style = str(payload.get("trinket_style", "charm") or "charm").strip().lower()
        armor_tint = tuple(payload.get("armor_tint", (0.76, 0.78, 0.84, 1.0)))
        armor_gloss = float(payload.get("armor_gloss", 0.24) or 0.24)
        weapon_color = tuple(payload.get("weapon_badge_color", (0.84, 0.68, 0.36, 1.0)))
        shield_color = tuple(payload.get("shield_badge_color", (0.72, 0.74, 0.80, 1.0)))
        trim_alpha = float(payload.get("trim_alpha", 0.72) or 0.72)
        armor_score = float(payload.get("armor_score", 0.28) or 0.28)

        actor = getattr(self, "_preview_actor", None)
        if actor and hasattr(actor, "set_shader_input"):
            try:
                actor.set_shader_input("roughness", max(0.28, min(0.88, 0.82 - (armor_gloss * 0.46))))
                actor.set_shader_input("specular_factor", max(0.12, min(0.42, 0.12 + (armor_gloss * 0.22))))
            except Exception:
                pass

        armor_root = getattr(self, "_preview_armor_root", None)
        if armor_root:
            armor_root.show()
            armor_root.setColorScale(*armor_tint)
            InventoryUI._set_preview_named_visibility(
                self,
                armor_root,
                {
                    "medium": {"armor_plate", "armor_collar"},
                    "light": {"armor_jerkin", "armor_strap_l", "armor_strap_r", "armor_collar"},
                    "heavy": {
                        "armor_plate",
                        "armor_collar",
                        "armor_pauldron_l",
                        "armor_pauldron_r",
                        "armor_tasset_l",
                        "armor_tasset_r",
                    },
                }.get(armor_style, {"armor_plate", "armor_collar"}),
            )
            if armor_style == "heavy":
                armor_root.setScale(1.00 + (armor_score * 0.14))
                if hasattr(armor_root, "setPos"):
                    armor_root.setPos(0.0, 0.05, 0.02)
            elif armor_style == "light":
                armor_root.setScale(0.92 + (armor_score * 0.08))
                if hasattr(armor_root, "setPos"):
                    armor_root.setPos(0.0, 0.06, -0.02)
            else:
                armor_root.setScale(0.96 + (armor_score * 0.10))
                if hasattr(armor_root, "setPos"):
                    armor_root.setPos(0.0, 0.05, 0.0)

        weapon_root = getattr(self, "_preview_weapon_root", None)
        if weapon_root:
            weapon_root.setColorScale(*weapon_color)
            InventoryUI._set_preview_named_visibility(
                self,
                weapon_root,
                {
                    "blade": {"weapon_blade", "weapon_guard"},
                    "bow": {"bow_limb_top", "bow_limb_bottom", "bow_string"},
                    "magic": {"magic_focus", "magic_shaft"},
                }.get(weapon_style, {"weapon_blade", "weapon_guard"}),
            )
            if weapon_style == "bow":
                weapon_root.setScale(0.90 + (armor_score * 0.05))
                if hasattr(weapon_root, "setHpr"):
                    weapon_root.setHpr(-14.0, -6.0, 28.0)
            elif weapon_style == "magic":
                weapon_root.setScale(0.98 + (armor_score * 0.04))
                if hasattr(weapon_root, "setHpr"):
                    weapon_root.setHpr(-6.0, 10.0, 12.0)
            else:
                weapon_root.setScale(0.96 + (armor_score * 0.06))
                if hasattr(weapon_root, "setHpr"):
                    weapon_root.setHpr(-20.0, 0.0, 18.0)
            if weapon_visible:
                weapon_root.show()
            else:
                weapon_root.hide()

        shield_root = getattr(self, "_preview_shield_root", None)
        if shield_root:
            shield_root.setColorScale(*shield_color)
            visible_parts = {"shield_body", "shield_rim"}
            if offhand_style == "tower":
                visible_parts.add("shield_tower_extension")
                shield_root.setScale(1.06)
                if hasattr(shield_root, "setPos"):
                    shield_root.setPos(0.42, 0.02, 1.00)
            elif offhand_style == "buckler":
                shield_root.setScale(0.88)
                if hasattr(shield_root, "setPos"):
                    shield_root.setPos(0.42, 0.02, 1.08)
            else:
                shield_root.setScale(1.0)
                if hasattr(shield_root, "setPos"):
                    shield_root.setPos(0.42, 0.02, 1.02)
            InventoryUI._set_preview_named_visibility(self, shield_root, visible_parts)
            if shield_visible:
                shield_root.show()
            else:
                shield_root.hide()

        trinket_root = getattr(self, "_preview_trinket_root", None)
        if trinket_root:
            trinket_root.setColorScale(armor_tint[0], armor_tint[1], armor_tint[2], max(0.55, trim_alpha))
            visible_parts = {"trinket_core"}
            if trinket_style == "orb":
                trinket_root.setScale(1.00 + (trim_alpha * 0.16))
            elif trinket_style == "relic":
                visible_parts.add("trinket_plate")
                visible_parts.add("trinket_loop")
                trinket_root.setScale(0.96 + (trim_alpha * 0.14))
            else:
                visible_parts.update({"trinket_loop", "trinket_tassel"})
                trinket_root.setScale(0.92 + (trim_alpha * 0.18))
            InventoryUI._set_preview_named_visibility(self, trinket_root, visible_parts)
            if trinket_visible:
                trinket_root.show()
            else:
                trinket_root.hide()

    def _setup_3d_preview(self):
        from panda3d.core import GraphicsOutput, FrameBufferProperties, WindowProperties, NodePath, Camera, OrthographicLens, DirectionalLight, AmbientLight, Vec4

        win = self.app.win
        fb_props = FrameBufferProperties()
        fb_props.setRgbaBits(8, 8, 8, 8)
        fb_props.setDepthBits(16)
        
        self._rtt_buffer = win.makeTextureBuffer("character_preview", 512, 1024, None, False, fb_props)
        self._rtt_buffer.setSort(-100)
        self._rtt_buffer.setClearColor(Vec4(0.16, 0.12, 0.09, 1.0))
        
        self._rtt_scene = NodePath("preview_scene")
        
        cam = Camera("preview_camera")
        lens = OrthographicLens()
        lens.setFilmSize(2.5, 4.9)
        cam.setLens(lens)
        self._rtt_cam = self._rtt_scene.attachNewNode(cam)
        self._rtt_cam.setPos(0, -10, 1.0)
        
        region = self._rtt_buffer.makeDisplayRegion()
        region.setCamera(self._rtt_cam)
        
        tex = self._rtt_buffer.getTexture()
        self.character_plate["image"] = tex
        
        alight = AmbientLight("alight")
        alight.setColor(Vec4(0.58, 0.54, 0.50, 1))
        self._rtt_scene.setLight(self._rtt_scene.attachNewNode(alight))

        dlight = DirectionalLight("dlight")
        dlight.setColor(Vec4(0.92, 0.86, 0.72, 1))
        dnp = self._rtt_scene.attachNewNode(dlight)
        dnp.setHpr(38, -32, 0)
        self._rtt_scene.setLight(dnp)

        rim = DirectionalLight("preview_rim")
        rim.setColor(Vec4(0.32, 0.38, 0.46, 1))
        rim_np = self._rtt_scene.attachNewNode(rim)
        rim_np.setHpr(-138, -18, 0)
        self._rtt_scene.setLight(rim_np)

        self._preview_actor = self._load_preview_actor()
        if not self._preview_actor:
            return
        self._preview_actor.reparentTo(self._rtt_scene)
        self._preview_actor.setH(180)
        ensure_model_visual_defaults(
            self._preview_actor,
            apply_skin=True,
            debug_label="inventory_preview_actor",
        )
        self._fit_preview_actor()
        self._build_preview_equipment_nodes()

        if self._preview_actor.getAnimNames():
            for anim in self._preview_actor.getAnimNames():
                if "idle" in anim.lower():
                    self._preview_actor.loop(anim)
                    break
            else:
                self._preview_actor.loop(self._preview_actor.getAnimNames()[0])

    def _inventory_character_follow_task(self, task):
        if self.frame.isHidden() or self._current_tab != "inventory":
            return task.cont

        mx = 0.0
        watcher = getattr(self.app, "mouseWatcherNode", None)
        if watcher and watcher.hasMouse():
            mx = float(watcher.getMouse().getX())
            
        if self._preview_actor:
            look_h = 180 + max(-30.0, min(30.0, mx * 45.0))
            self._preview_actor.setH(look_h)
            
        return task.cont

    def _switch_tab(self, tab_id):
        self._current_tab = tab_id
        self._play_ui_sfx("ui_tab", volume=0.44, rate=1.02)
        # Reset colors
        self.btn_inv["frameColor"] = THEME["bg_panel"]
        self.btn_party["frameColor"] = THEME["bg_panel"]
        self.btn_map["frameColor"] = THEME["bg_panel"]
        self.btn_skills["frameColor"] = THEME["bg_panel"]
        self.btn_journal["frameColor"] = THEME["bg_panel"]

        # Highlight active
        active_color = THEME["text_muted"]
        if tab_id == "inventory":
            self.btn_inv["frameColor"] = active_color
            self.inventory_showcase.show()
            self.inventory_showcase_title.show()
            self._apply_item_list_layout("inventory")
            self.item_list.show()
            self._clear_map_labels()
            self.map_panel.hide()
            self.map_title.hide()
            self.map_pin_text.hide()
            self.map_text.hide()
            self.journal_text.hide()
            self.journal_panel.hide()
            self.inventory_status_text.show()
            self._refresh_inventory()
        elif tab_id == "party":
            self.btn_party["frameColor"] = active_color
            self.inventory_showcase.hide()
            self.inventory_showcase_title.hide()
            self._apply_item_list_layout("full")
            self.item_list.show()
            self._clear_map_labels()
            self.map_panel.hide()
            self.map_title.hide()
            self.map_pin_text.hide()
            self.map_text.hide()
            self.journal_text.hide()
            self.journal_panel.hide()
            self.inventory_status_text.show()
            self._refresh_party()
        elif tab_id == "map":
            self.btn_map["frameColor"] = active_color
            self.inventory_showcase.hide()
            self.inventory_showcase_title.hide()
            self._apply_item_list_layout("full")
            self.item_list.hide()
            self.map_panel.show()
            self.map_title.show()
            self.map_pin_text.show()
            self.map_text.show()
            self.journal_text.hide()
            self.journal_panel.hide()
            self.inventory_status_text.hide()
            self._refresh_map()
        elif tab_id == "skills":
            self.btn_skills["frameColor"] = active_color
            self.inventory_showcase.hide()
            self.inventory_showcase_title.hide()
            self._apply_item_list_layout("full")
            self.item_list.show()
            self._clear_map_labels()
            self.map_panel.hide()
            self.map_title.hide()
            self.map_pin_text.hide()
            self.map_text.hide()
            self.journal_text.hide()
            self.journal_panel.hide()
            self.inventory_status_text.show()
            self._refresh_skills()
        elif tab_id == "journal":
            self.btn_journal["frameColor"] = active_color
            self.inventory_showcase.hide()
            self.inventory_showcase_title.hide()
            self._apply_item_list_layout("full")
            self.item_list.hide()
            self._clear_map_labels()
            self.map_panel.hide()
            self.map_title.hide()
            self.map_pin_text.hide()
            self.map_text.hide()
            self.journal_text.hide()
            self.journal_panel.show()
            self.inventory_status_text.hide()
            self._refresh_journal()
        logger.info(
            f"[UI] Inventory tab switched to '{self._current_tab}'. "
            "Only the active tab panel should remain visible."
        )

    def show(self):
        self.frame.show()
        # Ensure aspect2d is visible
        if hasattr(self.app, 'aspect2d'):
            self.app.aspect2d.show()
        self.on_window_resized(self.app.getAspectRatio())
        self._switch_tab(self._current_tab)
        self._play_ui_sfx("ui_open", volume=0.48, rate=1.0)

    def hide(self):
        self.frame.hide()
        if hasattr(self.app, 'state_mgr') and self.app.state_mgr.current_state == self.app.GameState.INVENTORY:
            self.app.state_mgr.set_state(self.app.GameState.PLAYING)
            # Only hide aspect2d if we are actually resuming playing
            if hasattr(self.app, 'aspect2d'):
                self.app.aspect2d.hide()

    def toggle(self):
        if self.frame.isHidden():
            if self.app.state_mgr.current_state == self.app.GameState.PLAYING:
                if hasattr(self.app, "_show_inventory_ui"):
                    self.app._show_inventory_ui(tab=self._current_tab)
                else:
                    self.app.state_mgr.set_state(self.app.GameState.INVENTORY)
                    self.show()
        else:
            self._request_close()

    def _request_close(self):
        self._play_ui_sfx("ui_close", volume=0.44, rate=0.98)
        if hasattr(self.app, "_hide_inventory_ui"):
            self.app._hide_inventory_ui()
        else:
            self.hide()

    def export_map_state(self):
        return {
            "tab": str(self._current_tab),
            "range": float(self._map_range),
        }

    def import_map_state(self, payload):
        if not isinstance(payload, dict):
            return
        tab = str(payload.get("tab", self._current_tab) or self._current_tab).strip().lower()
        if tab in {"inventory", "party", "map", "skills", "journal"}:
            self._current_tab = tab
        try:
            self._map_range = max(60.0, min(460.0, float(payload.get("range", self._map_range))))
        except Exception:
            pass

    def _party_summary_lines(self):
        cm = getattr(self.app, "companion_mgr", None)
        if not cm or not hasattr(cm, "get_party_snapshot"):
            return []
        try:
            snapshot = cm.get_party_snapshot() or {}
        except Exception:
            snapshot = {}
        lines = [self.app.data_mgr.t("ui.party", "Party") + ":"]
        active_companion = snapshot.get("active_companion")
        active_pet = snapshot.get("active_pet")
        if isinstance(active_companion, dict):
            behavior = str(active_companion.get("behavior", "follow") or "follow").replace("_", " ").title()
            lines.append(
                f"- {self.app.data_mgr.t('ui.party_companion', 'Companion')}: "
                f"{active_companion.get('name', active_companion.get('id', 'Companion'))} [{behavior}]"
            )
        else:
            lines.append(f"- {self.app.data_mgr.t('ui.party_companion', 'Companion')}: None")
        if isinstance(active_pet, dict):
            behavior = str(active_pet.get("behavior", "follow") or "follow").replace("_", " ").title()
            lines.append(
                f"- {self.app.data_mgr.t('ui.party_pet', 'Pet')}: "
                f"{active_pet.get('name', active_pet.get('id', 'Pet'))} [{behavior}]"
            )
        else:
            lines.append(f"- {self.app.data_mgr.t('ui.party_pet', 'Pet')}: None")
        return lines

    def _refresh_journal(self):
        quest_mgr = getattr(self.app, "quest_mgr", None)
        tutorial_mgr = getattr(self.app, "movement_tutorial", None)
        active = getattr(quest_mgr, "active_quests", {}) if quest_mgr else {}
        completed = sorted(
            list(getattr(quest_mgr, "completed_quests", set()) or set())
        ) if quest_mgr else []
        codex = self._profile_codex()
        left_lines = []
        right_lines = []

        left_lines.append(self.app.data_mgr.t("ui.active_quests_header", "Active Quests:"))
        if not active:
            left_lines.append("- " + self.app.data_mgr.t("ui.no_active_quests", "No active quests."))
        else:
            for q_id, objective_idx in list(active.items())[:5]:
                quest = None
                if quest_mgr and hasattr(quest_mgr, "_find_quest"):
                    try:
                        quest = quest_mgr._find_quest(q_id)
                    except Exception:
                        quest = None
                if not isinstance(quest, dict):
                    quest = self.app.data_mgr.quests.get(q_id, {}) if isinstance(self.app.data_mgr.quests, dict) else {}

                title = (
                    (quest.get("title") if isinstance(quest, dict) else None)
                    or (quest.get("name") if isinstance(quest, dict) else None)
                    or str(q_id)
                )
                objectives = quest.get("objectives", []) if isinstance(quest, dict) else []
                try:
                    idx = int(objective_idx)
                except Exception:
                    idx = -1
                progress = ""
                if isinstance(objectives, list) and objectives:
                    progress = f" [{max(1, idx + 1)}/{len(objectives)}]"
                left_lines.append(f"- {title}{progress}")

        if tutorial_mgr and hasattr(tutorial_mgr, "get_journal_lines"):
            try:
                tutorial_lines = tutorial_mgr.get_journal_lines() or []
            except Exception:
                tutorial_lines = []
            if tutorial_lines:
                left_lines.append("")
                left_lines.append(self.app.data_mgr.t("ui.tutorial_journal_header", "Training Program:"))
                for row in tutorial_lines[:5]:
                    row_text = str(row or "").strip()
                    if row_text:
                        left_lines.append(row_text if row_text.startswith("-") else f"- {row_text}")

        left_lines.append("")
        left_lines.append(self.app.data_mgr.t("ui.completed_quests_header", "Completed Quests:"))
        if completed:
            for q_id in completed[-6:]:
                quest = None
                if quest_mgr and hasattr(quest_mgr, "_find_quest"):
                    try:
                        quest = quest_mgr._find_quest(q_id)
                    except Exception:
                        quest = None
                title = (
                    (quest.get("title") if isinstance(quest, dict) else None)
                    or (self.app.data_mgr.quests.get(q_id, {}).get("title") if isinstance(self.app.data_mgr.quests, dict) else None)
                    or str(q_id)
                )
                left_lines.append(f"- {title}")
        else:
            left_lines.append("- " + self.app.data_mgr.t("ui.no_completed_quests", "No completed quests yet."))

        static_sections = self._load_static_codex_sections()
        if static_sections:
            for title, entries in static_sections[:2]:
                right_lines.append(f"{title}:")
                for row in entries[:2]:
                    txt = str(row or "").strip()
                    if txt:
                        right_lines.append(f"- {txt}")
                right_lines.append("")

        party_lines = self._party_summary_lines()
        if party_lines:
            right_lines.extend(party_lines)
            right_lines.append("")

        right_lines.append(self.app.data_mgr.t("ui.journal_characters", "Characters:"))
        right_lines.extend(self._format_codex_rows(codex.get("characters", []), limit=4))
        right_lines.append("")
        right_lines.append(self.app.data_mgr.t("ui.journal_factions", "Factions:"))
        right_lines.extend(self._format_codex_rows(codex.get("factions", []), limit=3))
        right_lines.append("")
        right_lines.append(self.app.data_mgr.t("ui.journal_locations", "Locations:"))
        right_lines.extend(self._format_codex_rows(codex.get("locations", []), limit=4))
        right_lines.append("")
        right_lines.append(self.app.data_mgr.t("ui.journal_events", "Events:"))
        right_lines.extend(self._format_codex_rows(codex.get("events", []), limit=4))
        right_lines.append("")
        right_lines.append(self.app.data_mgr.t("ui.journal_npc_archive", "NPC Archive:"))
        right_lines.extend(self._format_codex_rows(codex.get("npcs", []), limit=3))
        right_lines.append("")
        right_lines.append(self.app.data_mgr.t("ui.journal_enemy_archive", "Enemy Archive:"))
        right_lines.extend(self._format_codex_rows(codex.get("enemies", []), limit=3))
        right_lines.append("")
        right_lines.append(self.app.data_mgr.t("ui.journal_tutorial_archive", "Training Archive:"))
        right_lines.extend(self._format_codex_rows(codex.get("tutorial", []), limit=3))

        left_page = self._fit_codex_page(left_lines, max_lines=20, max_chars=720)
        right_page = self._fit_codex_page(right_lines, max_lines=20, max_chars=720)
        self.journal_left_title["text"] = self.app.data_mgr.t("ui.journal_chronicle", "Chronicle")
        self.journal_right_title["text"] = self.app.data_mgr.t("ui.journal_codex", "Codex")
        self.journal_left_text["text"] = "\n".join(left_page)
        self.journal_right_text["text"] = "\n".join(right_page)
        self.journal_footer_text["text"] = self.app.data_mgr.t(
            "ui.journal_footer_hint",
            "World records update automatically as you explore.",
        )

        # Fallback text for any legacy code path expecting plain journal text.
        merged = left_page + [""] + right_page
        self.journal_text["text"] = "\n".join(merged)

    def _profile_codex(self):
        profile = getattr(self.app, "profile", None)
        if not isinstance(profile, dict):
            profile = {}
            self.app.profile = profile
        codex = profile.get("codex")
        if not isinstance(codex, dict):
            codex = {}
            profile["codex"] = codex
        for key in ("locations", "characters", "factions", "npcs", "enemies", "tutorial", "events"):
            if not isinstance(codex.get(key), list):
                codex[key] = []
        return codex

    def _format_codex_rows(self, rows, limit=6):
        if not isinstance(rows, list):
            return ["- --"]
        formatted = []
        subset = rows[-max(1, int(limit)) :]
        for row in reversed(subset):
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", "") or row.get("id", "")).strip()
            details = str(row.get("details", "") or "").strip()
            if not title:
                continue
            if details:
                formatted.append(f"- {title}: {details}")
            else:
                formatted.append(f"- {title}")
        if not formatted:
            return ["- --"]
        return formatted

    def _fit_codex_page(self, lines, max_lines=20, max_chars=720):
        out = []
        total = 0
        for row in lines:
            text = str(row or "").rstrip()
            if not text and (not out or not out[-1]):
                continue
            if len(out) >= max_lines:
                break
            if total + len(text) > max_chars:
                break
            out.append(text)
            total += len(text)
        return out

    def _load_static_codex_sections(self):
        payload = {}
        dm = getattr(self.app, "data_mgr", None)
        if dm and hasattr(dm, "_load_file"):
            try:
                payload = dm._load_file("journal_entries.json")
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            return []
        sections = payload.get("sections", [])
        if not isinstance(sections, list) or not sections:
            return []

        out = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            title = str(section.get("title") or "").strip()
            entries = section.get("entries", [])
            if not title or not isinstance(entries, list):
                continue
            rows = []
            for item in entries:
                text = str(item or "").strip()
                if text:
                    rows.append(text)
            if rows:
                out.append((title, rows))
        return out

    def _coerce_vec3(self, value):
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            try:
                return (float(value[0]), float(value[1]), float(value[2]))
            except Exception:
                return None
        try:
            return (float(value.x), float(value.y), float(value.z))
        except Exception:
            return None

    def _player_world_pos(self):
        player = getattr(self.app, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if not actor:
            return None
        try:
            return self._coerce_vec3(actor.getPos(self.app.render))
        except Exception:
            return self._coerce_vec3(actor.getPos())

    def _refresh_map(self):
        for marker in self._map_pin_markers:
            marker.hide()
        self._clear_map_labels()

        self.map_title["text"] = self.app.data_mgr.t("ui.map", "Map")
        self.map_text["text"] = self.app.data_mgr.t(
            "ui.map_hint",
            "Blue dot is player, gold markers are tracked objectives.",
        )
        player_pos = self._player_world_pos()
        quest_mgr = getattr(self.app, "quest_mgr", None)
        quest_data = []
        if quest_mgr and player_pos and hasattr(quest_mgr, "get_hud_data"):
            try:
                quest_data = quest_mgr.get_hud_data(player_pos=player_pos) or []
            except Exception:
                quest_data = []

        if not player_pos:
            self.map_pin_text["text"] = self.app.data_mgr.t("ui.map_no_target", "No active target.")
            return

        px, py, _ = player_pos
        self.map_pin_text["text"] = ""
        map_half_x = 0.60
        map_half_z = 0.26
        map_range = max(1.0, float(self._map_range))
        summary_lines = []

        for idx, entry in enumerate(quest_data[: len(self._map_pin_markers)]):
            target = self._coerce_vec3(entry.get("target")) if isinstance(entry, dict) else None
            if not target:
                continue
            tx, ty, _ = target
            dx = tx - px
            dy = ty - py
            nx = max(-1.0, min(1.0, dx / map_range))
            ny = max(-1.0, min(1.0, dy / map_range))

            marker = self._map_pin_markers[idx]
            if idx == 0:
                marker["frameColor"] = (0.95, 0.84, 0.34, 0.98)
            else:
                marker["frameColor"] = (0.82, 0.70, 0.40, 0.84)
            marker.setPos(nx * map_half_x, 0, ny * map_half_z)
            marker.show()

            title = str(entry.get("title", "")).strip()
            objective = str(entry.get("objective", "")).strip()
            dist = entry.get("distance")
            dist_txt = "--"
            try:
                if dist is not None:
                    dist_val = max(0.0, float(dist))
                    dist_txt = f"{int(round(dist_val))} m"
            except Exception:
                dist_txt = "--"
            if title:
                summary_lines.append(f"{idx + 1}. {title} ({dist_txt})")
                if objective:
                    label = OnscreenText(
                        text=objective[:46],
                        pos=(-0.62, 0.31 - (idx * 0.06)),
                        scale=0.022,
                        font=body_font(self.app),
                        fg=THEME["text_muted"],
                        align=TextNode.ALeft,
                        mayChange=False,
                        parent=self.content_frame,
                    )
                    self._map_pin_labels.append(label)

        if summary_lines:
            self.map_pin_text["text"] = "\n".join(summary_lines)
        else:
            self.map_pin_text["text"] = self.app.data_mgr.t("ui.map_no_target", "No active target.")

    def _clear_map_labels(self):
        for label in self._map_pin_labels:
            try:
                label.destroy()
            except Exception:
                pass
        self._map_pin_labels = []

    def _clear_rows(self):
        canvas = self.item_list.getCanvas()
        for row in self._rows:
            try:
                row.destroy()
            except Exception:
                pass
        self._rows = []
        return canvas

    def _refresh_skills(self):
        canvas = self._clear_rows()
        skill_mgr = getattr(self.app, "skill_tree_mgr", None)
        if not skill_mgr or not hasattr(skill_mgr, "get_all_nodes"):
            text = OnscreenText(
                text="Skill tree manager unavailable.",
                pos=(0, -0.08),
                scale=0.05,
                font=body_font(self.app),
                align=TextNode.ACenter,
                fg=THEME.get("text_body", THEME["text_muted"]),
                parent=canvas,
                mayChange=False,
            )
            self._rows.append(text)
            self.item_list["canvasSize"] = (-0.68, 0.68, -0.45, 0)
            self._set_inventory_status("")
            return

        points = int(skill_mgr.get_points()) if hasattr(skill_mgr, "get_points") else 0
        status = f"Skill points: {points}"
        if self._skill_status:
            status = f"{status} | {self._skill_status}"
        self._set_inventory_status(status)
        rows = skill_mgr.get_all_nodes()
        if not rows:
            text = OnscreenText(
                text="No skills configured.",
                pos=(0, -0.08),
                scale=0.05,
                font=body_font(self.app),
                align=TextNode.ACenter,
                fg=THEME.get("text_body", THEME["text_muted"]),
                parent=canvas,
                mayChange=False,
            )
            self._rows.append(text)
            self.item_list["canvasSize"] = (-0.68, 0.68, -0.45, 0)
            return

        tree_layout = build_skill_tree_layout(rows)
        branch_top = -0.02
        branch_gap = 0.26
        node_x0 = -0.48
        node_dx = 0.32
        node_dy = 0.23
        node_half_w = 0.12
        node_half_h = 0.09
        min_y = -0.45

        for branch in tree_layout.get("branches", []):
            branch_name = str(branch.get("branch_name", "") or "Skills")
            nodes = list(branch.get("nodes", []))
            edges = list(branch.get("edges", []))
            if not nodes:
                continue

            branch_title = OnscreenText(
                text=branch_name.upper(),
                pos=(-0.63, branch_top + 0.02),
                scale=0.034,
                font=title_font(self.app),
                align=TextNode.ALeft,
                fg=THEME["gold_soft"],
                parent=canvas,
                mayChange=False,
            )
            self._rows.append(branch_title)

            node_origin_y = branch_top - 0.12
            node_positions = {}
            for node in nodes:
                x = node_x0 + (float(node.get("level", 0)) * node_dx)
                y = node_origin_y - (float(node.get("lane", 0)) * node_dy)
                node_positions[str(node.get("id", ""))] = (x, y)
                min_y = min(min_y, y - 0.16)

            for parent_id, child_id in edges:
                if parent_id not in node_positions or child_id not in node_positions:
                    continue
                px, py = node_positions[parent_id]
                cx, cy = node_positions[child_id]
                elbow_x = (px + cx) * 0.5

                seg_a = DirectFrame(
                    parent=canvas,
                    frameColor=(0.72, 0.60, 0.36, 0.38),
                    frameSize=(px + node_half_w, elbow_x, -0.003, 0.003),
                    pos=(0.0, 0.0, py),
                )
                seg_b = DirectFrame(
                    parent=canvas,
                    frameColor=(0.72, 0.60, 0.36, 0.38),
                    frameSize=(-0.003, 0.003, min(py, cy), max(py, cy)),
                    pos=(elbow_x, 0.0, 0.0),
                )
                seg_c = DirectFrame(
                    parent=canvas,
                    frameColor=(0.72, 0.60, 0.36, 0.38),
                    frameSize=(elbow_x, cx - node_half_w, -0.003, 0.003),
                    pos=(0.0, 0.0, cy),
                )
                self._rows.extend([seg_a, seg_b, seg_c])

            for node in nodes:
                node_id = str(node.get("id", "") or "")
                unlocked = bool(node.get("unlocked", False))
                can_unlock = bool(node.get("can_unlock", False))
                cost = int(node.get("cost", 1) or 1)
                title = str(node.get("name", node_id) or node_id)
                desc = str(node.get("description", "") or "")
                missing = node.get("missing", [])
                if not isinstance(missing, list):
                    missing = []

                x, y = node_positions.get(node_id, (0.0, 0.0))
                holder = DirectFrame(
                    parent=canvas,
                    frameColor=(
                        (0.28, 0.22, 0.16, 0.92)
                        if unlocked
                        else ((0.24, 0.19, 0.14, 0.88) if can_unlock else (0.15, 0.12, 0.10, 0.78))
                    ),
                    frameSize=(-node_half_w, node_half_w, -node_half_h, node_half_h),
                    pos=(x, 0.0, y),
                )
                self._rows.append(holder)

                glow = DirectFrame(
                    parent=holder,
                    frameColor=(
                        (0.84, 0.70, 0.32, 0.24)
                        if unlocked
                        else ((0.76, 0.58, 0.28, 0.16) if can_unlock else (0.24, 0.22, 0.20, 0.12))
                    ),
                    frameSize=(-0.106, 0.106, -0.076, 0.076),
                    pos=(0.0, 0.0, 0.0),
                )
                self._rows.append(glow)

                title_text = OnscreenText(
                    text=title,
                    pos=(x, y + 0.032),
                    scale=0.023,
                    font=title_font(self.app),
                    align=TextNode.ACenter,
                    fg=THEME["gold_soft"] if unlocked else THEME["text_main"],
                    parent=canvas,
                    mayChange=False,
                    wordwrap=8,
                )
                self._rows.append(title_text)

                status_text = "Unlocked" if unlocked else (f"Cost {cost}" if can_unlock else "Locked")
                status_fg = THEME["gold_soft"] if unlocked else ((0.92, 0.74, 0.36, 1.0) if can_unlock else THEME["text_muted"])
                status = OnscreenText(
                    text=status_text,
                    pos=(x, y - 0.002),
                    scale=0.019,
                    font=body_font(self.app),
                    align=TextNode.ACenter,
                    fg=status_fg,
                    parent=canvas,
                    mayChange=False,
                )
                self._rows.append(status)

                desc_line = desc[:48] if desc else ""
                if desc_line:
                    desc_text = OnscreenText(
                        text=desc_line,
                        pos=(x, y - 0.035),
                        scale=0.015,
                        font=body_font(self.app),
                        align=TextNode.ACenter,
                        fg=THEME["text_muted"],
                        parent=canvas,
                        mayChange=False,
                        wordwrap=14,
                    )
                    self._rows.append(desc_text)

                if missing:
                    req_text = OnscreenText(
                        text=f"Req: {', '.join(str(token).replace('_', ' ') for token in missing[:2])}",
                        pos=(x, y - 0.060),
                        scale=0.014,
                        font=body_font(self.app),
                        align=TextNode.ACenter,
                        fg=(0.74, 0.60, 0.50, 1.0),
                        parent=canvas,
                        mayChange=False,
                        wordwrap=15,
                    )
                    self._rows.append(req_text)

                if not unlocked:
                    btn = DirectButton(
                        parent=holder,
                        text="Unlock",
                        text_font=body_font(self.app),
                        text_scale=0.020,
                        frameSize=(-0.07, 0.07, -0.022, 0.028),
                        pos=(0.0, 0.0, -0.060),
                        frameColor=(0.72, 0.54, 0.22, 0.96) if can_unlock else (0.2, 0.2, 0.2, 0.6),
                        text_fg=THEME["text_main"],
                        command=self._handle_unlock_skill,
                        extraArgs=[node_id],
                        relief=1,
                    )
                    if not can_unlock:
                        btn["state"] = DGG.DISABLED
                    self._rows.append(btn)

            branch_top = min_y - branch_gap

        self.item_list["canvasSize"] = (-0.68, 0.68, min_y, 0)

    def _refresh_party(self):
        canvas = self._clear_rows()
        cm = getattr(self.app, "companion_mgr", None)
        if not cm or not hasattr(cm, "get_party_snapshot"):
            text = OnscreenText(
                text=self.app.data_mgr.t("ui.party_unavailable", "Party manager unavailable."),
                pos=(0, -0.08),
                scale=0.05,
                font=body_font(self.app),
                align=TextNode.ACenter,
                fg=THEME.get("text_body", THEME["text_muted"]),
                parent=canvas,
                mayChange=False,
            )
            self._rows.append(text)
            self.item_list["canvasSize"] = (-0.68, 0.68, -0.45, 0)
            self._set_inventory_status("")
            return

        try:
            snapshot = cm.get_party_snapshot() or {}
        except Exception:
            snapshot = {}

        active_companion_id = str(getattr(cm, "get_active_companion_id", lambda: "")() or "").strip().lower()
        active_pet_id = str(getattr(cm, "get_active_pet_id", lambda: "")() or "").strip().lower()

        rows = []
        for bucket_key in ("companions", "pets"):
            for row in snapshot.get(bucket_key, []) if isinstance(snapshot.get(bucket_key, []), list) else []:
                if isinstance(row, dict):
                    rows.append(dict(row))

        if not rows:
            text = OnscreenText(
                text=self.app.data_mgr.t("ui.party_empty", "No companions or pets recruited yet."),
                pos=(0, -0.08),
                scale=0.05,
                font=body_font(self.app),
                align=TextNode.ACenter,
                fg=THEME.get("text_body", THEME["text_muted"]),
                parent=canvas,
                mayChange=False,
            )
            self._rows.append(text)
            self.item_list["canvasSize"] = (-0.68, 0.68, -0.45, 0)
            self._set_inventory_status("")
            return

        def _sort_key(row):
            member_id = str(row.get("id", "") or "").strip().lower()
            is_active = member_id in {active_companion_id, active_pet_id}
            kind_order = 0 if str(row.get("kind", "") or "").strip().lower() == "companion" else 1
            return (0 if is_active else 1, kind_order, str(row.get("name", member_id)).lower())

        rows = sorted(rows, key=_sort_key)
        row_y = -0.05
        step = 0.18

        for idx, row in enumerate(rows):
            member_id = str(row.get("id", f"party_{idx}") or f"party_{idx}").strip().lower()
            name = str(row.get("name", member_id) or member_id).strip()
            kind = str(row.get("kind", "companion") or "companion").strip().lower()
            behavior = str(row.get("behavior", "follow") or "follow").strip().lower()
            is_active = member_id in {active_companion_id, active_pet_id}
            source = str(row.get("source", "") or "").strip().lower()
            accent = (0.28, 0.23, 0.18, 0.92) if is_active else (0.12, 0.10, 0.09, 0.68)

            holder = DirectFrame(
                parent=canvas,
                frameColor=accent,
                frameSize=(-0.66, 0.66, -0.07, 0.08),
                pos=(0.0, 0.0, row_y),
            )
            self._rows.append(holder)

            badge = DirectFrame(
                parent=holder,
                frameColor=(0.74, 0.62, 0.30, 0.94) if kind == "companion" else (0.76, 0.38, 0.24, 0.94),
                frameSize=(-0.06, 0.06, -0.04, 0.04),
                pos=(-0.58, 0.0, 0.0),
            )
            self._rows.append(badge)

            badge_text = OnscreenText(
                text="C" if kind == "companion" else "P",
                pos=(-0.58, -0.014),
                scale=0.04,
                font=title_font(self.app),
                align=TextNode.ACenter,
                fg=(0.10, 0.08, 0.05, 1.0),
                parent=holder,
                mayChange=False,
            )
            self._rows.append(badge_text)

            kind_label = self.app.data_mgr.t("ui.party_companion", "Companion") if kind == "companion" else self.app.data_mgr.t("ui.party_pet", "Pet")
            status = self.app.data_mgr.t("ui.party_active", "Active") if is_active else self.app.data_mgr.t("ui.party_ready", "Ready")
            title = OnscreenText(
                text=f"{name}  [{kind_label}]  {status}",
                pos=(-0.49, -0.016),
                scale=0.034,
                font=body_font(self.app),
                align=TextNode.ALeft,
                fg=THEME["gold_soft"] if is_active else THEME["text_main"],
                parent=holder,
                mayChange=False,
            )
            self._rows.append(title)

            detail_tokens = [
                self.app.data_mgr.t(f"ui.party_behavior_{behavior}", behavior.title()),
            ]
            if source:
                detail_tokens.append(source.replace("_", " ").title())
            assist = row.get("assist", {}) if isinstance(row.get("assist"), dict) else {}
            support = row.get("support", {}) if isinstance(row.get("support"), dict) else {}
            style_token = str(assist.get("combat_assist") or support.get("combat_assist") or support.get("utility") or "").strip()
            if style_token:
                detail_tokens.append(style_token.replace("_", " "))
            details = OnscreenText(
                text=" | ".join(detail_tokens[:3]),
                pos=(-0.49, -0.048),
                scale=0.022,
                font=body_font(self.app),
                align=TextNode.ALeft,
                fg=THEME["text_muted"],
                parent=holder,
                mayChange=False,
            )
            self._rows.append(details)

            button_specs = [
                (self.app.data_mgr.t("ui.party_follow", "Follow"), -0.02, self._handle_party_behavior, [member_id, "follow"]),
                (self.app.data_mgr.t("ui.party_stay", "Stay"), 0.20, self._handle_party_behavior, [member_id, "stay"]),
            ]
            for text, x_pos, cmd, extra_args in button_specs:
                btn = DirectButton(
                    parent=holder,
                    text=text,
                    text_font=body_font(self.app),
                    text_scale=0.026,
                    frameSize=(-0.09, 0.09, -0.024, 0.032),
                    pos=(x_pos, 0.0, 0.0),
                    frameColor=BUTTON_COLORS["normal"],
                    text_fg=THEME["text_main"],
                    command=cmd,
                    extraArgs=extra_args,
                    relief=1,
                )
                self._rows.append(btn)

            action_text = self.app.data_mgr.t("ui.party_dismiss", "Dismiss") if is_active else self.app.data_mgr.t("ui.party_activate", "Activate")
            action_cmd = self._handle_party_dismiss if is_active else self._handle_party_activate
            action_btn = DirectButton(
                parent=holder,
                text=action_text,
                text_font=body_font(self.app),
                text_scale=0.026,
                frameSize=(-0.10, 0.10, -0.024, 0.032),
                pos=(0.47, 0.0, 0.0),
                frameColor=THEME["danger"] if is_active else THEME["text_muted"],
                text_fg=THEME["text_main"],
                command=action_cmd,
                extraArgs=[member_id],
                relief=1,
            )
            self._rows.append(action_btn)
            row_y -= step

        self.item_list["canvasSize"] = (-0.68, 0.68, min(-0.62, row_y - 0.02), 0)
        self._set_inventory_status(self.app.data_mgr.t("ui.party_hint", "Commands update your active companion and pet immediately."))

    def _refresh_inventory(self):
        canvas = self._clear_rows()
        layout = self._item_list_row_layout or {
            "canvas_left": -0.68,
            "canvas_right": 0.68,
            "row_left": -0.66,
            "row_right": 0.66,
            "icon_x": -0.61,
            "text_x": -0.55,
            "desc_x": -0.55,
            "btn_x": 0.48,
        }

        profile_bag = {}
        if isinstance(getattr(self.app, "profile", None), dict):
            profile_bag = self.app.profile.get("items", {}) or {}

        items = []
        if isinstance(profile_bag, dict) and profile_bag:
            for item_id, qty in profile_bag.items():
                data = self.app.data_mgr.get_item(item_id) or {"id": item_id, "name": item_id}
                if not isinstance(data, dict):
                    data = {"id": item_id, "name": str(data)}
                row = dict(data)
                row["id"] = str(item_id)
                try:
                    row["quantity"] = max(0, int(qty or 0))
                except Exception:
                    row["quantity"] = 0
                items.append(row)
        else:
            for item_id, data in getattr(self.app.data_mgr, "items", {}).items():
                row = dict(data) if isinstance(data, dict) else {"id": str(item_id), "name": str(item_id)}
                row["id"] = str(item_id)
                row["quantity"] = 0
                items.append(row)

        def _sort_key(entry):
            if not isinstance(entry, dict):
                return ("zzzz", "zzzz")
            return (
                str(entry.get("type", "")).lower(),
                str(entry.get("name", entry.get("id", ""))).lower(),
            )
        items = sorted(items, key=_sort_key)
        equipped = self._equipment_state()
        self._refresh_equipment_showcase(equipped)

        if not items:
            empty_text = OnscreenText(
                text=self.app.data_mgr.t("ui.empty_inventory", "Inventory is empty"),
                pos=(0, -0.08),
                scale=0.05,
                font=body_font(self.app),
                align=TextNode.ACenter,
                fg=THEME.get("text_body", THEME["text_muted"]),
                parent=canvas,
                mayChange=False,
            )
            self._rows.append(empty_text)
            self.item_list["canvasSize"] = (layout["canvas_left"], layout["canvas_right"], -0.5, 0)
            return

        row_y = -0.05
        step = 0.13
        for idx, item in enumerate(items):
            row = item if isinstance(item, dict) else {"id": str(item), "name": str(item), "quantity": 0}
            item_id = str(row.get("id", f"item_{idx}"))
            name = str(row.get("name", item_id))
            slot = self._slot_alias(row.get("slot") or row.get("type"))
            qty = max(0, int(row.get("quantity", 0) or 0))
            is_equipped = bool(slot in equipped and equipped.get(slot) == item_id)

            holder = DirectFrame(
                parent=canvas,
                frameColor=(0.10, 0.09, 0.08, 0.62),
                frameSize=(layout["row_left"], layout["row_right"], -0.052, 0.052),
                pos=(0.0, 0.0, row_y),
            )
            self._rows.append(holder)

            icon = DirectFrame(
                parent=holder,
                frameColor=self._slot_color(slot),
                frameSize=(-0.035, 0.035, -0.035, 0.035),
                pos=(layout["icon_x"], 0.0, 0.0),
            )
            self._rows.append(icon)
            icon_char = name[:1].upper() if name else "?"
            icon_text = OnscreenText(
                text=icon_char,
                pos=(layout["icon_x"], -0.014),
                scale=0.04,
                font=title_font(self.app),
                align=TextNode.ACenter,
                fg=(0.10, 0.08, 0.05, 1.0),
                parent=holder,
                mayChange=False,
            )
            self._rows.append(icon_text)

            row_text = f"{name}"
            if qty > 1:
                row_text = f"{row_text} x{qty}"
            if is_equipped:
                row_text = f"{row_text}  [Equipped]"
            label = OnscreenText(
                text=row_text,
                pos=(layout["text_x"], -0.017),
                scale=0.036,
                font=body_font(self.app),
                align=TextNode.ALeft,
                fg=THEME["gold_soft"] if is_equipped else THEME["text_main"],
                parent=holder,
                mayChange=False,
            )
            self._rows.append(label)

            desc = str(row.get("description", "") or "").strip()
            if desc:
                desc_text = OnscreenText(
                    text=desc[:72],
                    pos=(layout["desc_x"], -0.043),
                    scale=0.024,
                    font=body_font(self.app),
                    align=TextNode.ALeft,
                    fg=THEME["text_muted"],
                    parent=holder,
                    mayChange=False,
                )
                self._rows.append(desc_text)

            if slot in {"weapon_main", "offhand", "chest", "trinket"}:
                action = "Unequip" if is_equipped else "Equip"
                cmd = self._handle_unequip if is_equipped else self._handle_equip
                args = [slot] if is_equipped else [item_id]
                btn = DirectButton(
                    parent=holder,
                    text=action,
                    text_font=body_font(self.app),
                    text_scale=0.032,
                    frameSize=(-0.11, 0.11, -0.03, 0.04),
                    pos=(layout["btn_x"], 0.0, 0.0),
                    frameColor=THEME["text_muted"] if is_equipped else BUTTON_COLORS["normal"],
                    text_fg=THEME["text_main"],
                    command=cmd,
                    extraArgs=args,
                    relief=1,
                )
                if qty <= 0 and (not is_equipped):
                    btn["state"] = DGG.DISABLED
                    btn["frameColor"] = (0.2, 0.2, 0.2, 0.6)
                self._rows.append(btn)
            elif slot == "consumable":
                btn = DirectButton(
                    parent=holder,
                    text="Use",
                    text_font=body_font(self.app),
                    text_scale=0.032,
                    frameSize=(-0.11, 0.11, -0.03, 0.04),
                    pos=(layout["btn_x"], 0.0, 0.0),
                    frameColor=BUTTON_COLORS["normal"],
                    text_fg=THEME["text_main"],
                    command=self._handle_use,
                    extraArgs=[item_id],
                    relief=1,
                )
                if qty <= 0:
                    btn["state"] = DGG.DISABLED
                    btn["frameColor"] = (0.2, 0.2, 0.2, 0.6)
                self._rows.append(btn)

            row_y -= step
        min_y = min(-0.6, row_y - 0.08)
        self.item_list["canvasSize"] = (layout["canvas_left"], layout["canvas_right"], min_y, 0)

    def _slot_alias(self, slot_token):
        token = str(slot_token or "").strip().lower()
        if token in {"weapon", "weapon_main", "mainhand", "main_hand"}:
            return "weapon_main"
        if token in {"offhand", "off_hand", "shield"}:
            return "offhand"
        if token in {"armor", "body", "chest"}:
            return "chest"
        if token in {"artifact", "trinket", "amulet"}:
            return "trinket"
        if token in {"consumable", "potion", "food"}:
            return "consumable"
        return token

    def _slot_color(self, slot_token):
        slot = self._slot_alias(slot_token)
        palette = {
            "weapon_main": (0.70, 0.65, 0.50, 0.96),
            "offhand": (0.58, 0.64, 0.72, 0.96),
            "chest": (0.48, 0.56, 0.66, 0.96),
            "trinket": (0.72, 0.62, 0.44, 0.96),
            "consumable": (0.46, 0.65, 0.48, 0.96),
        }
        return palette.get(slot, (0.42, 0.40, 0.36, 0.94))

    def _equipment_state(self):
        player = getattr(self.app, "player", None)
        if player and hasattr(player, "export_equipment_state"):
            try:
                payload = player.export_equipment_state() or {}
                if isinstance(payload, dict):
                    return dict(payload)
            except Exception:
                pass
        profile = getattr(self.app, "profile", {})
        if isinstance(profile, dict) and isinstance(profile.get("equipment_state"), dict):
            return dict(profile.get("equipment_state", {}))
        return {}

    def _set_inventory_status(self, text):
        self._inventory_status = str(text or "")
        self.inventory_status_text["text"] = self._inventory_status

    def _sync_profile_equipment(self):
        player = getattr(self.app, "player", None)
        profile = getattr(self.app, "profile", None)
        if not isinstance(profile, dict):
            return
        if player and hasattr(player, "export_equipment_state"):
            try:
                profile["equipment_state"] = player.export_equipment_state() or {}
            except Exception:
                pass

    def _handle_equip(self, item_id):
        item_id = str(item_id or "").strip()
        if not item_id:
            self._set_inventory_status("Equip failed: invalid item id.")
            return
        profile = getattr(self.app, "profile", {})
        bag = profile.get("items", {}) if isinstance(profile, dict) else {}
        qty = int(bag.get(item_id, 0) or 0) if isinstance(bag, dict) else 0
        if qty <= 0:
            self._set_inventory_status("Item is not in inventory.")
            return
        item_data = self.app.data_mgr.get_item(item_id) or {}
        player = getattr(self.app, "player", None)
        if not player or not hasattr(player, "equip_item"):
            self._set_inventory_status("Equip is unavailable right now.")
            return
        ok, reason = player.equip_item(item_id, item_data=item_data)
        if ok:
            self._sync_profile_equipment()
            name = item_data.get("name", item_id) if isinstance(item_data, dict) else item_id
            self._set_inventory_status(f"Equipped: {name}")
            self._refresh_inventory()
        else:
            self._set_inventory_status(f"Equip failed: {reason}")

    def _handle_unequip(self, slot):
        player = getattr(self.app, "player", None)
        if not player or not hasattr(player, "unequip_slot"):
            self._set_inventory_status("Unequip is unavailable right now.")
            return
        ok = bool(player.unequip_slot(slot))
        if not ok:
            self._set_inventory_status("Unequip failed.")
            return
        self._sync_profile_equipment()
        self._set_inventory_status(f"Unequipped slot: {self._slot_alias(slot)}")
        self._refresh_inventory()

    def _handle_use(self, item_id):
        item_id = str(item_id or "").strip()
        if not item_id:
            self._set_inventory_status("Use failed: invalid item id.")
            return
        profile = getattr(self.app, "profile", {})
        if not isinstance(profile, dict):
            self._set_inventory_status("Use failed: no profile.")
            return
        bag = profile.setdefault("items", {})
        qty = int(bag.get(item_id, 0) or 0)
        if qty <= 0:
            self._set_inventory_status("No items left to use.")
            return
        player = getattr(self.app, "player", None)
        item_data = self.app.data_mgr.get_item(item_id) or {}
        if not player or not hasattr(player, "use_item"):
            self._set_inventory_status("Use is unavailable right now.")
            return
        used = bool(player.use_item(item_id, item_data=item_data))
        if not used:
            self._set_inventory_status("Item cannot be used.")
            return
        qty -= 1
        if qty <= 0:
            bag.pop(item_id, None)
        else:
            bag[item_id] = qty
        name = item_data.get("name", item_id) if isinstance(item_data, dict) else item_id
        self._set_inventory_status(f"Used: {name}")
        self._refresh_inventory()

    def _handle_party_activate(self, member_id):
        cm = getattr(self.app, "companion_mgr", None)
        if not cm or not hasattr(cm, "activate_member"):
            self._set_inventory_status("Party activation is unavailable right now.")
            return
        ok = bool(cm.activate_member(member_id))
        if not ok:
            self._set_inventory_status("Could not activate that party member.")
            return
        behavior = getattr(cm, "get_behavior_state", lambda *_: "follow")(member_id)
        self._set_inventory_status(
            f"Activated {str(member_id).replace('_', ' ').title()} [{str(behavior).title()}]"
        )
        self._refresh_party()

    def _handle_party_behavior(self, member_id, behavior):
        cm = getattr(self.app, "companion_mgr", None)
        if not cm:
            self._set_inventory_status("Party manager unavailable.")
            return
        if hasattr(cm, "activate_member"):
            try:
                cm.activate_member(member_id)
            except Exception:
                pass
        if not hasattr(cm, "set_behavior_state") or not cm.set_behavior_state(member_id, behavior):
            self._set_inventory_status("Could not change party behavior.")
            return
        label = self.app.data_mgr.t(f"ui.party_behavior_{behavior}", str(behavior).title())
        self._set_inventory_status(f"{str(member_id).replace('_', ' ').title()} -> {label}")
        self._refresh_party()

    def _handle_party_dismiss(self, member_id):
        cm = getattr(self.app, "companion_mgr", None)
        token = str(member_id or "").strip().lower()
        if not cm or not token:
            self._set_inventory_status("Could not dismiss that party member.")
            return
        active_companion = str(getattr(cm, "get_active_companion_id", lambda: "")() or "").strip().lower()
        active_pet = str(getattr(cm, "get_active_pet_id", lambda: "")() or "").strip().lower()
        ok = False
        if token == active_companion and hasattr(cm, "dismiss_active_companion"):
            ok = bool(cm.dismiss_active_companion())
        elif token == active_pet and hasattr(cm, "dismiss_active_pet"):
            ok = bool(cm.dismiss_active_pet())
        if not ok:
            self._set_inventory_status("That member is not currently active.")
            return
        self._set_inventory_status(f"Dismissed {str(member_id).replace('_', ' ').title()}")
        self._refresh_party()

    def _handle_unlock_skill(self, node_id):
        token = str(node_id or "").strip().lower()
        if not token:
            self._skill_status = "Unlock failed: invalid skill id."
            self._refresh_skills()
            return
        skill_mgr = getattr(self.app, "skill_tree_mgr", None)
        if not skill_mgr or not hasattr(skill_mgr, "unlock"):
            self._skill_status = "Unlock failed: skill manager unavailable."
            self._refresh_skills()
            return
        ok, reason = skill_mgr.unlock(token)
        if ok:
            self._skill_status = reason or f"Unlocked: {token}"
        else:
            self._skill_status = reason or f"Unlock failed: {token}"
        self._refresh_skills()
