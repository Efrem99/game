import math

from direct.gui.DirectGui import DirectFrame, DirectScrolledFrame, OnscreenText, DirectButton, DGG
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import TextNode, TransparencyAttrib

from ui.design_system import (
    BUTTON_COLORS,
    THEME,
    ParchmentPanel,
    body_font,
    title_font,
    place_ui_on_top
)

class InventoryUI:
    def __init__(self, app):
        self.app = app
        self._rows = []
        self._current_tab = "inventory"  # "inventory", "map", "skills", "journal"
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

        asp = self.app.getAspectRatio()
        self.frame = DirectFrame(
            frameColor=(0, 0, 0, 0.4),
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
            command=self.hide,
            relief=1
        )

        self.hide()
        if hasattr(self.app, "taskMgr") and self.app.taskMgr:
            self.app.taskMgr.add(self._inventory_character_follow_task, "inventory_character_follow_task")

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
            frameSize=(-0.20, 0.20, -0.05, 0.06),
            pos=(-0.66, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["inventory"],
            relief=1
        )

        self.btn_map = DirectButton(
            parent=self.tabs_frame,
            text="Map",
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.20, 0.20, -0.05, 0.06),
            pos=(-0.22, 0, 0),
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
            frameSize=(-0.20, 0.20, -0.05, 0.06),
            pos=(0.22, 0, 0),
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
            frameSize=(-0.20, 0.20, -0.05, 0.06),
            pos=(0.66, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["journal"],
            relief=1
        )

    def _build_inventory_showcase(self):
        self.inventory_showcase = DirectFrame(
            frameColor=(0.08, 0.07, 0.06, 0.45),
            frameSize=(-0.74, 0.20, -0.52, 0.42),
            pos=(-0.05, 0.0, -0.01),
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

        self.character_plate = DirectFrame(
            frameColor=(0.12, 0.10, 0.09, 0.72),
            frameSize=(-0.18, 0.18, -0.34, 0.34),
            pos=(-0.27, 0.0, -0.06),
            parent=self.inventory_showcase,
        )
        self.character_plate_border = DirectFrame(
            frameColor=(0.64, 0.58, 0.45, 0.45),
            frameSize=(-0.184, 0.184, -0.344, 0.344),
            pos=(-0.27, 0.0, -0.06),
            parent=self.inventory_showcase,
        )
        self.character_plate_border.setTransparency(TransparencyAttrib.MAlpha)

        self.character_root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.001, 0.001, -0.001, 0.001),
            parent=self.character_plate,
        )
        self.character_torso = DirectFrame(
            frameColor=(0.35, 0.34, 0.42, 0.96),
            frameSize=(-0.055, 0.055, -0.14, 0.14),
            pos=(0.0, 0.0, -0.02),
            parent=self.character_root,
        )
        self.character_head = DirectFrame(
            frameColor=(0.92, 0.84, 0.72, 0.98),
            frameSize=(-0.048, 0.048, -0.048, 0.048),
            pos=(0.0, 0.0, 0.18),
            parent=self.character_root,
        )
        self.character_arm_l = DirectFrame(
            frameColor=(0.35, 0.34, 0.42, 0.96),
            frameSize=(-0.018, 0.018, -0.11, 0.11),
            pos=(-0.082, 0.0, -0.01),
            parent=self.character_root,
        )
        self.character_arm_r = DirectFrame(
            frameColor=(0.35, 0.34, 0.42, 0.96),
            frameSize=(-0.018, 0.018, -0.11, 0.11),
            pos=(0.082, 0.0, -0.01),
            parent=self.character_root,
        )
        self.character_leg_l = DirectFrame(
            frameColor=(0.24, 0.23, 0.30, 0.96),
            frameSize=(-0.020, 0.020, -0.12, 0.12),
            pos=(-0.028, 0.0, -0.25),
            parent=self.character_root,
        )
        self.character_leg_r = DirectFrame(
            frameColor=(0.24, 0.23, 0.30, 0.96),
            frameSize=(-0.020, 0.020, -0.12, 0.12),
            pos=(0.028, 0.0, -0.25),
            parent=self.character_root,
        )

        self._add_equipment_slot_widget("weapon_main", "Main Hand", (-0.56, 0.13))
        self._add_equipment_slot_widget("offhand", "Off Hand", (0.03, 0.13))
        self._add_equipment_slot_widget("chest", "Armor", (-0.56, -0.12))
        self._add_equipment_slot_widget("trinket", "Trinket", (0.03, -0.12))

    def _add_equipment_slot_widget(self, slot_id, title, pos_xy):
        x, z = pos_xy
        frame = DirectFrame(
            frameColor=(0.18, 0.16, 0.14, 0.82),
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

    def _inventory_character_follow_task(self, task):
        if self.frame.isHidden() or self._current_tab != "inventory":
            return task.cont

        mx = 0.0
        my = 0.0
        watcher = getattr(self.app, "mouseWatcherNode", None)
        if watcher and watcher.hasMouse():
            mouse = watcher.getMouse()
            mx = float(mouse.getX())
            my = float(mouse.getY())

        target_x = max(-0.06, min(0.06, mx * 0.05))
        target_z = max(-0.04, min(0.04, my * 0.04))
        self._char_follow_x += (target_x - self._char_follow_x) * 0.18
        self._char_follow_z += (target_z - self._char_follow_z) * 0.18

        t = float(globalClock.getFrameTime() or 0.0)
        breath = math.sin(t * 2.4) * 0.008
        arm_wave = math.sin(t * 3.2) * 5.0
        look_h = max(-14.0, min(14.0, mx * 18.0))

        self.character_root.setPos(self._char_follow_x, 0.0, self._char_follow_z + breath)
        self.character_root.setH(look_h)
        self.character_head.setZ(0.18 + (breath * 0.5))
        self.character_arm_l.setR(-arm_wave)
        self.character_arm_r.setR(arm_wave)
        return task.cont

    def _switch_tab(self, tab_id):
        self._current_tab = tab_id
        # Reset colors
        self.btn_inv["frameColor"] = THEME["bg_panel"]
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

    def show(self):
        self.frame.show()
        # Ensure aspect2d is visible
        if hasattr(self.app, 'aspect2d'):
            self.app.aspect2d.show()
        self._switch_tab(self._current_tab)

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
                self.app.state_mgr.set_state(self.app.GameState.INVENTORY)
                self.show()
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
        if tab in {"inventory", "map", "skills", "journal"}:
            self._current_tab = tab
        try:
            self._map_range = max(60.0, min(460.0, float(payload.get("range", self._map_range))))
        except Exception:
            pass

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

        row_y = -0.05
        step = 0.14
        prev_branch = None
        for row in rows:
            branch = str(row.get("branch_name", "") or "")
            if branch != prev_branch:
                if prev_branch is not None:
                    row_y -= 0.04
                branch_title = OnscreenText(
                    text=branch.upper(),
                    pos=(-0.63, row_y + 0.02),
                    scale=0.032,
                    font=title_font(self.app),
                    align=TextNode.ALeft,
                    fg=THEME["gold_soft"],
                    parent=canvas,
                    mayChange=False,
                )
                self._rows.append(branch_title)
                row_y -= 0.05
                prev_branch = branch

            node_id = str(row.get("id", "") or "")
            unlocked = bool(row.get("unlocked", False))
            can_unlock = bool(row.get("can_unlock", False))
            cost = int(row.get("cost", 1) or 1)
            title = str(row.get("name", node_id) or node_id)
            desc = str(row.get("description", "") or "")
            missing = row.get("missing", [])
            if not isinstance(missing, list):
                missing = []

            holder = DirectFrame(
                parent=canvas,
                frameColor=(0.10, 0.09, 0.08, 0.62),
                frameSize=(-0.66, 0.66, -0.055, 0.055),
                pos=(0.0, 0.0, row_y),
            )
            self._rows.append(holder)

            title_text = title
            if unlocked:
                title_text = f"{title}  [Unlocked]"
            elif missing:
                title_text = f"{title}  [Locked]"
            else:
                title_text = f"{title}  [Cost {cost}]"

            label = OnscreenText(
                text=title_text,
                pos=(-0.60, -0.018),
                scale=0.035,
                font=body_font(self.app),
                align=TextNode.ALeft,
                fg=THEME["gold_soft"] if unlocked else THEME["text_main"],
                parent=holder,
                mayChange=False,
            )
            self._rows.append(label)

            if desc:
                desc_text = OnscreenText(
                    text=desc[:84],
                    pos=(-0.60, -0.045),
                    scale=0.023,
                    font=body_font(self.app),
                    align=TextNode.ALeft,
                    fg=THEME["text_muted"],
                    parent=holder,
                    mayChange=False,
                )
                self._rows.append(desc_text)

            if not unlocked:
                btn = DirectButton(
                    parent=holder,
                    text="Unlock",
                    text_font=body_font(self.app),
                    text_scale=0.031,
                    frameSize=(-0.11, 0.11, -0.03, 0.04),
                    pos=(0.48, 0.0, 0.0),
                    frameColor=BUTTON_COLORS["normal"] if can_unlock else (0.2, 0.2, 0.2, 0.6),
                    text_fg=THEME["text_main"],
                    command=self._handle_unlock_skill,
                    extraArgs=[node_id],
                    relief=1,
                )
                if not can_unlock:
                    btn["state"] = DGG.DISABLED
                self._rows.append(btn)
            row_y -= step

        min_y = min(-0.6, row_y - 0.08)
        self.item_list["canvasSize"] = (-0.68, 0.68, min_y, 0)

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
