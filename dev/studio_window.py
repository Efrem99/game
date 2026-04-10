"""Embedded shared authoring studio shell used by the developer hub."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from launchers.studio_docking import move_panel, normalize_studio_dock_layout
from launchers.studio_logic_graph import (
    apply_logic_focus_patch,
    build_logic_focus_from_preview,
    build_logic_graph_from_preview,
    create_logic_node_from_preview,
    delete_logic_node_from_preview,
)
from launchers.studio_manifest import get_studio_definition, list_studio_keys, resolve_studio_key
from launchers.studio_preview import load_preview, save_preview_text
from launchers.studio_story_inspector import apply_story_focus_patch, build_story_focus_from_preview, build_story_graph_from_preview

PANEL_TITLES = {"navigator": "Workspace Browser", "graph": "Flow Graph", "overview": "Overview", "source": "Source"}
PANEL_HINTS = {
    "navigator": "Drag this panel between docks to change the authoring layout.",
    "graph": "Dialogue trees render here as visual flow graphs inside the shared studio shell.",
    "overview": "Flow summaries, cards, and structured inspectors render here.",
    "source": "Canonical source text stays editable here.",
}
ZONE_TITLES = {"left": "Left Dock", "top": "Top Dock", "bottom": "Bottom Dock"}


def _build_authoring_graph(preview: dict | None):
    if not isinstance(preview, dict):
        return None
    return build_logic_graph_from_preview(preview) or build_story_graph_from_preview(preview)


class StudioShell(ctk.CTkFrame):
    def __init__(self, parent, root_dir: Path, *, studio_manifest: dict, initial_studio_key: str, log_fn: Callable[[str], None], actions_by_key: Optional[dict] = None):
        super().__init__(parent)
        self._root_dir = Path(root_dir)
        self._studio_manifest = dict(studio_manifest or {})
        self._studio_key = resolve_studio_key(self._studio_manifest, initial_studio_key)
        self._log = log_fn
        self._actions_by_key = dict(actions_by_key or {})
        self._active_path = None
        self._active_preview = None
        self._active_graph = None
        self._selected_graph_node_id = None
        self._dock_layout = normalize_studio_dock_layout({})
        self._dragging_panel_key = None
        self._mode_label_to_key = {}
        self._mode_key_to_label = {}
        self._graph_inspector_fields = {}
        self._story_inspector_fields = {}
        self._zone_frames = {}
        self._panel_frames = {}
        self._build_shell()
        self.switch_studio(self._studio_key)
        self._log(f"[Studio] Embedded studio shell ready in mode {self._studio_key}.")

    def switch_studio(self, studio_key: str):
        self._studio_key = resolve_studio_key(self._studio_manifest, studio_key)
        label = self._mode_key_to_label.get(self._studio_key)
        if getattr(self, "_mode_switch", None) is not None and label:
            self._mode_switch.set(label)
        self._apply_studio(self._studio_key)

    def focus_path(self, relative_path: str):
        rel_path = str(relative_path or "").strip()
        if not rel_path:
            return
        preview = load_preview(self._root_dir, rel_path)
        self._active_path = rel_path
        self._active_preview = preview
        self._active_graph = _build_authoring_graph(preview)
        self._selected_graph_node_id = self._active_graph.get("root_id") if self._active_graph else None
        self._set_preview_state(preview.get("title") or rel_path, f"{preview.get('kind', 'preview').upper()} | {preview.get('relative_path', rel_path)}", "Editable inside shared studio shell." if preview.get("editable") else "Preview available inside shared studio shell.", bool(preview.get("editable")))
        self._render_graph(preview)
        self._render_overview(preview)
        self._render_source(preview)

    def _build_shell(self):
        hero = ctk.CTkFrame(self)
        hero.pack(fill="x", padx=8, pady=(8, 12))
        self._hero_title_lbl = ctk.CTkLabel(hero, text="Studio", font=ctk.CTkFont(size=28, weight="bold"))
        self._hero_title_lbl.pack(anchor="w", padx=18, pady=(18, 6))
        self._hero_summary_lbl = ctk.CTkLabel(hero, text="", justify="left", wraplength=1080, text_color="#c9cad7")
        self._hero_summary_lbl.pack(anchor="w", padx=18, pady=(0, 8))
        self._hero_status_lbl = ctk.CTkLabel(hero, text="", justify="left", wraplength=1080, text_color="#8ea5ff")
        self._hero_status_lbl.pack(anchor="w", padx=18, pady=(0, 18))
        keys = list_studio_keys(self._studio_manifest)
        if len(keys) > 1:
            mode_frame = ctk.CTkFrame(self)
            mode_frame.pack(fill="x", padx=8, pady=(0, 12))
            ctk.CTkLabel(mode_frame, text="Mode", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(14, 8))
            labels = []
            for key in keys:
                title = get_studio_definition(self._studio_manifest, key).get("title", key.replace("_", " ").title())
                labels.append(title)
                self._mode_label_to_key[title] = key
                self._mode_key_to_label[key] = title
            self._mode_switch = ctk.CTkSegmentedButton(mode_frame, values=labels, command=lambda label: self.switch_studio(self._mode_label_to_key.get(label, self._studio_key)))
            self._mode_switch.pack(anchor="w", padx=18, pady=(0, 14))
        self._actions_container = ctk.CTkFrame(self)
        self._actions_container.pack(fill="x", padx=8, pady=(0, 12))
        domain_frame = ctk.CTkFrame(self)
        domain_frame.pack(fill="x", padx=8, pady=(0, 12))
        ctk.CTkLabel(domain_frame, text="Owned Domains", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(14, 10))
        self._domains_lbl = ctk.CTkLabel(domain_frame, text="", justify="left", wraplength=1080, text_color="#b7b7c5")
        self._domains_lbl.pack(anchor="w", padx=18, pady=(0, 14))
        selection = ctk.CTkFrame(self)
        selection.pack(fill="x", padx=8, pady=(0, 12))
        text_frame = ctk.CTkFrame(selection, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True, padx=(14, 0), pady=12)
        self._preview_title_lbl = ctk.CTkLabel(text_frame, text="No file selected", font=ctk.CTkFont(size=18, weight="bold"))
        self._preview_title_lbl.pack(anchor="w")
        self._preview_kind_lbl = ctk.CTkLabel(text_frame, text="Choose a workspace path to start authoring.", text_color="#a8a8b6")
        self._preview_kind_lbl.pack(anchor="w", pady=(2, 2))
        self._preview_status_lbl = ctk.CTkLabel(text_frame, text="All major panels stay in one window. Drag panel headers to re-dock them inline.", text_color="#6f7084")
        self._preview_status_lbl.pack(anchor="w")
        actions = ctk.CTkFrame(selection, fg_color="transparent")
        actions.pack(side="right", padx=14, pady=12)
        self._reload_btn = ctk.CTkButton(actions, text="Reload", width=110, command=self._reload_current_path)
        self._reload_btn.pack(side="left", padx=(0, 8))
        self._save_btn = ctk.CTkButton(actions, text="Save", width=110, fg_color="#27ae60", hover_color="#229954", command=self._save_current_file)
        self._save_btn.pack(side="left")
        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        left_zone = self._build_zone(body, "left")
        left_zone.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_stack = ctk.CTkFrame(body, fg_color="transparent")
        right_stack.grid(row=0, column=1, sticky="nsew")
        right_stack.grid_rowconfigure(0, weight=1)
        right_stack.grid_rowconfigure(1, weight=1)
        right_stack.grid_columnconfigure(0, weight=1)
        top_zone = self._build_zone(right_stack, "top")
        top_zone.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        bottom_zone = self._build_zone(right_stack, "bottom")
        bottom_zone.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._zone_frames = {"left": left_zone, "top": top_zone, "bottom": bottom_zone}
        for panel_key in ("navigator", "graph", "overview", "source"):
            self._create_panel(body, panel_key)
        self._render_dock_layout()

    def _build_zone(self, parent, zone_key: str):
        frame = ctk.CTkFrame(parent)
        ctk.CTkLabel(frame, text=ZONE_TITLES[zone_key], font=ctk.CTkFont(size=13, weight="bold"), text_color="#7f8ea3").pack(anchor="w", padx=12, pady=(12, 4))
        return frame

    def _create_panel(self, parent, panel_key: str):
        panel = ctk.CTkFrame(parent)
        header = ctk.CTkFrame(panel)
        header.pack(fill="x", padx=8, pady=(8, 4))
        handle = ctk.CTkLabel(header, text="::", width=24, text_color="#f39c12")
        handle.pack(side="left", padx=(8, 8), pady=8)
        title_wrap = ctk.CTkFrame(header, fg_color="transparent")
        title_wrap.pack(side="left", fill="x", expand=True, pady=8)
        ctk.CTkLabel(title_wrap, text=PANEL_TITLES[panel_key], font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_wrap, text=PANEL_HINTS[panel_key], text_color="#8c97a7").pack(anchor="w")
        for widget in (header, handle, title_wrap):
            widget.bind("<ButtonPress-1>", lambda event, key=panel_key: self._on_panel_drag_start(key, event))
            widget.bind("<B1-Motion>", lambda event, key=panel_key: self._on_panel_drag_motion(key, event))
            widget.bind("<ButtonRelease-1>", lambda event, key=panel_key: self._on_panel_drag_release(key, event))
        host = ctk.CTkFrame(panel, fg_color="transparent")
        host.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._panel_frames[panel_key] = panel
        if panel_key == "navigator":
            self._navigator = ctk.CTkScrollableFrame(host)
            self._navigator.pack(fill="both", expand=True)
        elif panel_key == "graph":
            wrap = ctk.CTkFrame(host)
            wrap.pack(fill="both", expand=True)
            self._graph_canvas = tk.Canvas(wrap, bg="#101522", highlightthickness=0, borderwidth=0)
            self._graph_canvas.grid(row=0, column=0, sticky="nsew")
            ctk.CTkScrollbar(wrap, orientation="vertical", command=self._graph_canvas.yview).grid(row=0, column=1, sticky="ns")
            ctk.CTkScrollbar(wrap, orientation="horizontal", command=self._graph_canvas.xview).grid(row=1, column=0, sticky="ew")
            wrap.grid_rowconfigure(0, weight=1)
            wrap.grid_columnconfigure(0, weight=1)
        elif panel_key == "overview":
            self._overview_frame = ctk.CTkScrollableFrame(host)
            self._overview_frame.pack(fill="both", expand=True)
        else:
            self._source_text = ctk.CTkTextbox(host, font=ctk.CTkFont(family="Consolas", size=12))
            self._source_text.pack(fill="both", expand=True)

    def _apply_studio(self, studio_key: str):
        studio = get_studio_definition(self._studio_manifest, studio_key)
        self._hero_title_lbl.configure(text=studio.get("title", "Studio"))
        self._hero_summary_lbl.configure(text=studio.get("summary", ""))
        self._hero_status_lbl.configure(text=f"Status: {studio.get('status', '')}".strip())
        self._domains_lbl.configure(text=" | ".join(studio.get("domains", [])))
        self._rebuild_actions(studio_key)
        self._rebuild_workspace_browser(studio)
        self._load_initial_preview(studio)

    def _rebuild_actions(self, studio_key: str):
        for child in self._actions_container.winfo_children():
            child.destroy()
        actions = list(self._actions_by_key.get(studio_key, []) or [])
        ctk.CTkLabel(self._actions_container, text="Primary Actions", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(14, 10))
        for action in actions:
            ctk.CTkButton(self._actions_container, text=action.get("label", "Action"), height=46, fg_color=action.get("fg_color"), hover_color=action.get("hover_color"), command=action.get("command")).pack(fill="x", padx=18, pady=6)
            if action.get("description"):
                ctk.CTkLabel(self._actions_container, text=action["description"], justify="left", wraplength=1080, text_color="#a8a8b6").pack(anchor="w", padx=20, pady=(0, 4))

    def _rebuild_workspace_browser(self, studio: dict):
        for child in self._navigator.winfo_children():
            child.destroy()
        ctk.CTkLabel(self._navigator, text="Workspace Browser", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))
        for workspace in list(studio.get("workspaces", []) or []):
            card = ctk.CTkFrame(self._navigator)
            card.pack(fill="x", padx=6, pady=6)
            ctk.CTkLabel(card, text=workspace.get("title", "Workspace"), font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(14, 4))
            for raw_path in list(workspace.get("paths", []) or []):
                rel_path = str(raw_path or "").strip()
                if rel_path:
                    ctk.CTkButton(card, text=rel_path, anchor="w", fg_color="transparent", border_width=1, command=lambda p=rel_path: self.focus_path(p)).pack(fill="x", padx=18, pady=4)
            ctk.CTkLabel(card, text="Select a canonical file or folder to preview and edit it inside this studio.", justify="left", wraplength=300, text_color="#6f7084").pack(anchor="w", padx=18, pady=(8, 14))

    def _load_initial_preview(self, studio: dict):
        self._active_path = None
        self._active_preview = None
        for workspace in list(studio.get("workspaces", []) or []):
            for raw_path in list(workspace.get("paths", []) or []):
                rel_path = str(raw_path or "").strip()
                if rel_path:
                    self.focus_path(rel_path)
                    return

    def _set_preview_state(self, title: str, subtitle: str, status: str, editable: bool):
        self._preview_title_lbl.configure(text=title)
        self._preview_kind_lbl.configure(text=subtitle)
        self._preview_status_lbl.configure(text=status)
        self._save_btn.configure(state="normal" if editable else "disabled")

    def _current_preview_from_source_buffer(self):
        if not self._active_preview:
            return None
        preview = dict(self._active_preview)
        if self._source_text is not None and preview.get("editable"):
            preview["raw_text"] = self._source_text.get("1.0", "end-1c")
        return preview

    def _render_graph(self, preview: dict):
        canvas = self._graph_canvas
        if canvas is None:
            return
        graph = self._active_graph
        canvas.delete("all")
        if not graph:
            message = "Open a canonical dialogue, quest, or scene JSON to see its flow graph here." if self._studio_key == "logic_studio" else "Open a supported scene, quest, or dialogue file to get an inline graph in this shared shell."
            canvas.create_text(28, 28, anchor="nw", width=760, text=message, fill="#7f8ea3", font=("Segoe UI", 13))
            return
        if not self._selected_graph_node_id:
            self._selected_graph_node_id = graph.get("root_id")
        positions = {}
        nodes = sorted(list(graph.get("nodes", []) or []), key=lambda item: (item.get("depth", 0), item.get("lane", 0), item.get("order", 0)))
        canvas.create_text(28, 24, anchor="nw", text=f"{graph.get('title', 'Dialogue')} | {graph['stats']['node_count']} nodes | {graph['stats']['edge_count']} links | {graph['stats']['terminal_count']} exits", fill="#d4d9f0", font=("Segoe UI", 13, "bold"))
        for node in nodes:
            x1 = 28 + int(node.get("depth", 0)) * 346
            y1 = 78 + int(node.get("lane", 0)) * 166
            positions[node["id"]] = (x1, y1, x1 + 250, y1 + 122)
        for edge in list(graph.get("edges", []) or []):
            sb, tb = positions.get(edge["source"]), positions.get(edge["target"])
            if not sb or not tb:
                continue
            sx, sy, tx, ty = sb[2], (sb[1] + sb[3]) / 2.0, tb[0], (tb[1] + tb[3]) / 2.0
            mx = sx + max(40, (tx - sx) / 2.0)
            color = "#6fb3ff" if edge.get("kind") == "next" else "#f6c46a"
            canvas.create_line(sx, sy, mx, sy, mx, ty, tx, ty, fill=color, width=2, smooth=True, arrow=tk.LAST)
        for node in nodes:
            x1, y1, x2, y2 = positions[node["id"]]
            selected = node["id"] == self._selected_graph_node_id
            fill, outline = ("#3b2857", "#e3a8ff") if selected else ("#143454", "#4da3ff") if node.get("is_root") else ("#17392d", "#48d597") if node.get("is_terminal") else ("#1a2233", "#6b7a92")
            tag = f"graph-node::{node['id']}"
            header_text = str(node.get("header") or f"{node.get('speaker', 'Unknown')} | {node.get('title', node['id'])}")
            footer_text = str(node.get("footer") or (("ROOT" if node.get("is_root") else "EXIT" if node.get("is_terminal") else f"{node.get('choice_count', 0)} choices") + f" | Depth {node.get('depth', 0)}"))
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=3 if selected else 2, tags=("graph-node", tag))
            canvas.create_text(x1 + 14, y1 + 12, anchor="nw", text=header_text, fill="#f2f4ff", font=("Segoe UI", 11, "bold"), width=222, tags=("graph-node", tag))
            canvas.create_text(x1 + 14, y1 + 40, anchor="nw", text=str(node.get("text") or ""), fill="#c9cfdf", font=("Segoe UI", 10), width=222, tags=("graph-node", tag))
            canvas.create_text(x1 + 14, y2 - 16, anchor="sw", text=footer_text, fill="#e3a8ff" if selected else "#95a1b3", font=("Segoe UI", 9, "bold"), width=222, tags=("graph-node", tag))
            canvas.tag_bind(tag, "<Button-1>", lambda _event, node_id=node["id"]: self._select_graph_node(node_id))
        canvas.configure(scrollregion=(0, 0, max((box[2] for box in positions.values()), default=900) + 60, max((box[3] for box in positions.values()), default=180) + 40))

    def _select_graph_node(self, node_id: str):
        if self._active_graph and node_id in {node["id"] for node in self._active_graph.get("nodes", [])}:
            self._selected_graph_node_id = node_id
            self._render_graph(self._active_preview)
            self._render_overview(self._active_preview)
            self._render_source(self._active_preview)
            self._preview_status_lbl.configure(text=f"Selected graph node: {node_id}")

    def _render_overview(self, preview: dict):
        for child in self._overview_frame.winfo_children():
            child.destroy()
        self._graph_inspector_fields = {}
        self._story_inspector_fields = {}
        graph_focus = build_logic_focus_from_preview(preview, self._selected_graph_node_id) if self._selected_graph_node_id else None
        story_focus = build_story_focus_from_preview(preview, self._selected_graph_node_id)
        cards = []
        if graph_focus:
            self._render_graph_inspector(graph_focus)
            cards.extend(list(graph_focus.get("cards", []) or []))
        elif story_focus:
            self._render_story_inspector(story_focus)
            cards.extend(list(story_focus.get("cards", []) or []))
        cards.extend(list(preview.get("cards", []) or []))
        for index, card in enumerate(cards):
            panel = ctk.CTkFrame(self._overview_frame)
            panel.pack(fill="x", padx=6, pady=6)
            if graph_focus and index < len(graph_focus.get("cards", [])):
                panel.configure(border_width=1, border_color="#915eff")
            if story_focus and index < len(story_focus.get("cards", [])):
                panel.configure(border_width=1, border_color="#16a085")
            ctk.CTkLabel(panel, text=card.get("title", "Card"), font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
            ctk.CTkLabel(panel, text=card.get("body", ""), justify="left", wraplength=700, text_color="#b7b7c5").pack(anchor="w", padx=14, pady=(0, 12))

    def _render_graph_inspector(self, graph_focus: dict):
        raw = dict((graph_focus.get("node") or {}).get("raw") or {})
        panel = ctk.CTkFrame(self._overview_frame)
        panel.pack(fill="x", padx=6, pady=6)
        panel.configure(border_width=1, border_color="#915eff")
        ctk.CTkLabel(panel, text=f"Node Inspector | {graph_focus.get('node_id', 'node')}", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))
        speaker = ctk.CTkEntry(panel); speaker.pack(fill="x", padx=14, pady=(0, 8)); speaker.insert(0, str(raw.get("speaker") or ""))
        next_node = ctk.CTkEntry(panel); next_node.pack(fill="x", padx=14, pady=(0, 8)); next_node.insert(0, str(raw.get("next_node") or ""))
        text_box = ctk.CTkTextbox(panel, height=120); text_box.pack(fill="x", padx=14, pady=(0, 10)); text_box.insert("1.0", str(raw.get("text") or ""))
        ctk.CTkLabel(panel, text="Choice Links\nUse one line per choice: `Choice text -> target_node | if condition | do action`", justify="left", wraplength=700, text_color="#7f8ea3").pack(anchor="w", padx=14, pady=(0, 8))
        choices = ctk.CTkTextbox(panel, height=120); choices.pack(fill="x", padx=14, pady=(0, 10)); choices.insert("1.0", str(graph_focus.get("choice_lines") or ""))
        ops = ctk.CTkFrame(panel, fg_color="transparent"); ops.pack(fill="x", padx=14, pady=(0, 8))
        new_node_id = ctk.CTkEntry(ops, width=180, placeholder_text="new_node_id"); new_node_id.pack(side="left", padx=(0, 8))
        link_text = ctk.CTkEntry(ops, placeholder_text="Link text"); link_text.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(ops, text="Create Linked Node", width=170, fg_color="#6c5ce7", hover_color="#5b4bd6", command=self._create_linked_graph_node).pack(side="left")
        ctk.CTkButton(panel, text="Delete Node", fg_color="#c0392b", hover_color="#a93226", command=self._delete_graph_node).pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(panel, text="Apply Node Changes", fg_color="#8e44ad", hover_color="#7d3c98", command=self._apply_graph_node_changes).pack(fill="x", padx=14, pady=(0, 12))
        self._graph_inspector_fields = {"speaker": speaker, "next_node": next_node, "text": text_box, "choices_text": choices, "new_node_id": new_node_id, "new_link_text": link_text}

    def _render_story_inspector(self, story_focus: dict):
        panel = ctk.CTkFrame(self._overview_frame)
        panel.pack(fill="x", padx=6, pady=6)
        panel.configure(border_width=1, border_color="#16a085")
        title_map = {
            "quest": "Quest Inspector",
            "quest_objective": "Objective Inspector",
            "quest_rewards": "Rewards Inspector",
            "quest_prerequisites": "Prerequisites Inspector",
            "scene": "Scene Inspector",
            "scene_environment": "Environment Inspector",
            "scene_spawn_point": "Spawn Point Inspector",
            "scene_group": "Scene Group Inspector",
        }
        ctk.CTkLabel(panel, text=title_map.get(story_focus.get("kind"), "Story Inspector"), font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))
        fields = {}
        for field_name, value in story_focus.get("fields", {}).items():
            ctk.CTkLabel(panel, text=field_name.replace("_", " ").title(), text_color="#7f8ea3").pack(anchor="w", padx=14, pady=(0, 4))
            multiline = field_name in {"description", "items_text", "prerequisites_text"} or ("\n" in str(value or ""))
            widget = ctk.CTkTextbox(panel, height=90) if multiline else ctk.CTkEntry(panel)
            widget.pack(fill="x", padx=14, pady=(0, 10))
            if isinstance(widget, ctk.CTkTextbox):
                widget.insert("1.0", str(value or ""))
            else:
                widget.insert(0, str(value or ""))
            fields[field_name] = widget
        ctk.CTkButton(panel, text="Apply Story Changes", fg_color="#16a085", hover_color="#138d75", command=self._apply_story_changes).pack(fill="x", padx=14, pady=(0, 12))
        self._story_inspector_fields = {"fields": fields}

    def _apply_graph_node_changes(self):
        fields = dict(self._graph_inspector_fields or {})
        if not (self._selected_graph_node_id and fields):
            return
        patch = {"speaker": fields["speaker"].get(), "text": fields["text"].get("1.0", "end-1c"), "next_node": fields["next_node"].get(), "choices_text": fields["choices_text"].get("1.0", "end-1c")}
        self._apply_preview_text(apply_logic_focus_patch(self._current_preview_from_source_buffer(), self._selected_graph_node_id, patch), "Applied node changes to the shared source buffer. Save to persist.")

    def _create_linked_graph_node(self):
        fields = dict(self._graph_inspector_fields or {})
        if not (self._selected_graph_node_id and fields):
            return
        new_node_id = fields["new_node_id"].get().strip()
        updated = create_logic_node_from_preview(self._current_preview_from_source_buffer(), self._selected_graph_node_id, new_node_id, link_text=fields["new_link_text"].get().strip() or "Continue")
        if self._apply_preview_text(updated, f"Created linked node {new_node_id}. Save to persist."):
            self._selected_graph_node_id = new_node_id
            self._render_graph(self._active_preview); self._render_overview(self._active_preview); self._render_source(self._active_preview)

    def _delete_graph_node(self):
        if not self._selected_graph_node_id:
            return
        deleting = self._selected_graph_node_id
        if self._apply_preview_text(delete_logic_node_from_preview(self._current_preview_from_source_buffer(), deleting), f"Deleted node {deleting}. Save to persist.") and self._active_graph:
            self._selected_graph_node_id = self._active_graph.get("root_id")
            self._render_graph(self._active_preview); self._render_overview(self._active_preview); self._render_source(self._active_preview)

    def _apply_story_changes(self):
        fields = dict((self._story_inspector_fields or {}).get("fields") or {})
        if not fields:
            return
        patch = {name: widget.get("1.0", "end-1c") if isinstance(widget, ctk.CTkTextbox) else widget.get() for name, widget in fields.items()}
        self._apply_preview_text(apply_story_focus_patch(self._current_preview_from_source_buffer(), patch, node_id=self._selected_graph_node_id), "Applied structured story changes to the shared source buffer. Save to persist.")

    def _apply_preview_text(self, updated_text: str | None, success_status: str):
        if updated_text is None:
            self._preview_status_lbl.configure(text="Couldn't apply changes. Check that the source buffer still contains valid canonical JSON.")
            return False
        updated_preview = dict(self._current_preview_from_source_buffer() or self._active_preview or {})
        updated_preview["raw_text"] = updated_text
        self._active_preview = updated_preview
        self._active_graph = _build_authoring_graph(updated_preview)
        if self._active_graph and self._selected_graph_node_id not in {node["id"] for node in self._active_graph.get("nodes", [])}:
            self._selected_graph_node_id = self._active_graph.get("root_id")
        self._render_graph(updated_preview); self._render_overview(updated_preview); self._render_source(updated_preview)
        self._preview_status_lbl.configure(text=success_status)
        return True

    def _render_source(self, preview: dict):
        raw_text = preview.get("raw_text", "") or ("\n".join(child.get("relative_path", "") for child in preview.get("children", [])) if preview.get("children") else "")
        if not raw_text:
            raw_text = f"# No source text available for {preview.get('title', 'selection')}"
        self._source_text.delete("1.0", "end")
        self._source_text.insert("1.0", raw_text)
        self._source_text.tag_remove("graph-focus", "1.0", "end")
        self._source_text.tag_config("graph-focus", background="#3b2857", foreground="#f7e9ff")
        graph_focus = build_logic_focus_from_preview(preview, self._selected_graph_node_id) if self._selected_graph_node_id else None
        story_focus = build_story_focus_from_preview(preview, self._selected_graph_node_id)
        source_anchor = graph_focus.get("source_anchor") if graph_focus else story_focus.get("source_anchor") if story_focus else None
        if source_anchor:
            start = self._source_text.search(source_anchor, "1.0", stopindex="end")
            if start:
                self._source_text.tag_add("graph-focus", start, f"{start}+{len(source_anchor)}c")
                self._source_text.see(start)

    def _reload_current_path(self):
        if self._active_path:
            self.focus_path(self._active_path)

    def _save_current_file(self):
        if self._active_preview and self._active_preview.get("editable") and self._active_path:
            save_preview_text(self._root_dir, self._active_path, self._source_text.get("1.0", "end-1c"))
            self.focus_path(self._active_path)
            self._preview_status_lbl.configure(text="Saved to canonical source file.")

    def _render_dock_layout(self):
        for panel in self._panel_frames.values():
            panel.pack_forget()
        for zone_key, panel_keys in self._dock_layout.items():
            for panel_key in panel_keys:
                self._panel_frames[panel_key].pack(in_=self._zone_frames[zone_key], fill="both", expand=True, padx=8, pady=8)

    def _move_panel(self, panel_key: str, target_zone: str, target_index: int | None = None):
        self._dock_layout = move_panel(self._dock_layout, panel_key, target_zone, target_index)
        self._render_dock_layout()

    def _on_panel_drag_start(self, panel_key: str, _event):
        self._dragging_panel_key = panel_key

    def _on_panel_drag_motion(self, panel_key: str, event):
        if self._dragging_panel_key != panel_key:
            return
        zone_key, _ = self._locate_drop_target(event.x_root, event.y_root, panel_key)
        if zone_key:
            self._preview_status_lbl.configure(text=f"Dragging {PANEL_TITLES[panel_key]} over {ZONE_TITLES[zone_key]}.")

    def _on_panel_drag_release(self, panel_key: str, event):
        if self._dragging_panel_key != panel_key:
            return
        zone_key, target_index = self._locate_drop_target(event.x_root, event.y_root, panel_key)
        self._dragging_panel_key = None
        if zone_key:
            self._move_panel(panel_key, zone_key, target_index)
            self._preview_status_lbl.configure(text=f"{PANEL_TITLES[panel_key]} docked into {ZONE_TITLES[zone_key]}.")

    def _locate_drop_target(self, x_root: int, y_root: int, panel_key: str):
        for zone_key, zone_frame in self._zone_frames.items():
            left = zone_frame.winfo_rootx(); top = zone_frame.winfo_rooty(); right = left + zone_frame.winfo_width(); bottom = top + zone_frame.winfo_height()
            if left <= x_root <= right and top <= y_root <= bottom:
                return zone_key, self._compute_insert_index(zone_key, y_root, panel_key)
        return None, None

    def _compute_insert_index(self, zone_key: str, y_root: int, panel_key: str):
        target_keys = [key for key in self._dock_layout.get(zone_key, []) if key != panel_key]
        for index, key in enumerate(target_keys):
            frame = self._panel_frames[key]
            if y_root < frame.winfo_rooty() + (frame.winfo_height() / 2.0):
                return index
        return len(target_keys)
