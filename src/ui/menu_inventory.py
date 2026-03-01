from direct.gui.DirectGui import DirectFrame, DirectScrolledFrame, OnscreenText, DirectButton
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
        self._current_tab = "inventory"  # "inventory", "map", "journal"

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

        self.map_text = OnscreenText(
            text="Map coming soon",
            pos=(0, 0),
            scale=0.06,
            font=body_font(self.app),
            fg=THEME["text_muted"],
            parent=self.content_frame
        )

        self.journal_text = OnscreenText(
            text="Journal empty",
            pos=(-0.66, 0.35),
            scale=0.042,
            font=body_font(self.app),
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            wordwrap=34,
            parent=self.content_frame
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
            frameSize=(-0.25, 0.25, -0.05, 0.06),
            pos=(-0.55, 0, 0),
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
            frameSize=(-0.25, 0.25, -0.05, 0.06),
            pos=(0, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["map"],
            relief=1
        )

        self.btn_journal = DirectButton(
            parent=self.tabs_frame,
            text="Journal",
            text_font=body_font(self.app),
            text_scale=0.045,
            frameSize=(-0.25, 0.25, -0.05, 0.06),
            pos=(0.55, 0, 0),
            frameColor=THEME["bg_panel"],
            text_fg=THEME["text_main"],
            command=self._switch_tab,
            extraArgs=["journal"],
            relief=1
        )

    def _switch_tab(self, tab_id):
        self._current_tab = tab_id
        # Reset colors
        self.btn_inv["frameColor"] = THEME["bg_panel"]
        self.btn_map["frameColor"] = THEME["bg_panel"]
        self.btn_journal["frameColor"] = THEME["bg_panel"]

        # Highlight active
        active_color = THEME["text_muted"]
        if tab_id == "inventory":
            self.btn_inv["frameColor"] = active_color
            self.item_list.show()
            self.map_text.hide()
            self.journal_text.hide()
            self._refresh_inventory()
        elif tab_id == "map":
            self.btn_map["frameColor"] = active_color
            self.item_list.hide()
            self.map_text.show()
            self.journal_text.hide()
        elif tab_id == "journal":
            self.btn_journal["frameColor"] = active_color
            self.item_list.hide()
            self.map_text.hide()
            self.journal_text.show()
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

    def _refresh_journal(self):
        quest_mgr = getattr(self.app, "quest_mgr", None)
        active = getattr(quest_mgr, "active_quests", {}) if quest_mgr else {}
        completed = sorted(
            list(getattr(quest_mgr, "completed_quests", set()) or set())
        ) if quest_mgr else []
        codex = self._format_journal_codex()
        lines = []

        lines.append(self.app.data_mgr.t("ui.active_quests_header", "Active Quests:"))
        if not active:
            lines.append("- " + self.app.data_mgr.t("ui.no_active_quests", "No active quests."))
        else:
            for q_id, objective_idx in active.items():
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
                obj_total = len(objectives) if isinstance(objectives, list) else 0
                try:
                    idx = int(objective_idx)
                except Exception:
                    idx = -1
                objective_text = ""
                if isinstance(objectives, list) and 0 <= idx < len(objectives):
                    objective = objectives[idx]
                    if isinstance(objective, dict):
                        objective_text = (
                            objective.get("description")
                            or objective.get("desc")
                            or objective.get("id")
                            or ""
                        )
                progress = f"[{max(1, idx + 1)}/{max(1, obj_total)}]" if obj_total else ""
                lines.append(f"- {title} {progress}".strip())
                if objective_text:
                    lines.append(f"  {objective_text}")

        lines.append("")
        lines.append(self.app.data_mgr.t("ui.completed_quests_header", "Completed Quests:"))
        if completed:
            shown = completed[-8:]
            for q_id in shown:
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
                lines.append(f"- {title}")
        else:
            lines.append("- " + self.app.data_mgr.t("ui.no_completed_quests", "No completed quests yet."))

        if codex:
            lines.append("")
            lines.append(codex)

        self.journal_text["text"] = "\n".join(lines)

    def _format_journal_codex(self):
        payload = {}
        dm = getattr(self.app, "data_mgr", None)
        if dm and hasattr(dm, "_load_file"):
            try:
                payload = dm._load_file("journal_entries.json")
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            return ""
        sections = payload.get("sections", [])
        if not isinstance(sections, list) or not sections:
            return ""

        lines = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            title = str(section.get("title") or "").strip()
            entries = section.get("entries", [])
            if not title or not isinstance(entries, list):
                continue
            lines.append(f"{title}:")
            for item in entries:
                text = str(item or "").strip()
                if text:
                    lines.append(f"- {text}")
            lines.append("")
        return "\n".join(lines).strip()

    def _refresh_inventory(self):
        canvas = self.item_list.getCanvas()
        for row in self._rows:
            try:
                row.destroy()
            except Exception:
                pass
        self._rows = []

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
                row["id"] = item_id
                row["quantity"] = int(qty or 1)
                items.append(row)
        else:
            item_ids = list(self.app.data_mgr.items.keys())
            items = [self.app.data_mgr.get_item(item_id) or {"id": item_id} for item_id in item_ids]

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
            self.item_list["canvasSize"] = (-0.68, 0.68, -0.5, 0)
            return

        row_y = -0.05
        step = 0.08
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                label = str(item)
                qty = 1
            else:
                label = item.get("name") or item.get("id") or f"Item {idx + 1}"
                qty = int(item.get("quantity", 1))

            row_text = f"{label}"
            if qty > 1:
                row_text = f"{row_text} x{qty}"

            text_node = OnscreenText(
                text=row_text,
                pos=(-0.64, row_y),
                scale=0.05,
                font=body_font(self.app),
                align=TextNode.ALeft,
                fg=THEME["gold_soft"],
                parent=canvas,
                mayChange=False,
            )
            self._rows.append(text_node)
        min_y = min(-0.6, row_y - 0.08)
        self.item_list["canvasSize"] = (-0.68, 0.68, min_y, 0)
