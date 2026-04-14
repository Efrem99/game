import os
import sys
import time
import json
import sqlite3
import msgpack
import threading
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from glob import glob


import customtkinter as ctk
from PIL import Image
from launchers.studio_manifest import load_studio_manifest

# Setup paths to ensure we can import king-wizard modules
ROOT_DIR = Path(__file__).parent.absolute()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the core logic (if available)
try:
    from dev.custom_debugger import (
        AutonomousQARunner,
        MockGameAdapter,
        build_default_scenarios,
        load_repo_video_scenarios,
        Scenario,
        ScenarioStep
    )
except ImportError as e:
    AutonomousQARunner = None

try:
    from dev.level_editor_window import LevelEditorWindow
    _LEVEL_EDITOR_OK = True
except Exception as _le_err:
    _LEVEL_EDITOR_OK = False
    LevelEditorWindow = None

try:
    from dev.studio_window import StudioShell
    _STUDIO_WINDOW_OK = True
except Exception:
    _STUDIO_WINDOW_OK = False
    StudioShell = None

class DevHub(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("King Wizard - Developer Hub")
        self.geometry("1400x950")
        
        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Application state
        self.config_path = ROOT_DIR / "dev" / "dev_hub_config.json"
        self.config_data = self._load_config()
        self.studio_manifest = load_studio_manifest(ROOT_DIR / "data" / "authoring_studios.json")
        self.available_scenarios: List[Scenario] = []
        self.available_pytest_groups: Dict[str, List[str]] = {}
        
        self.checkboxes = []
        self.running = False
        self.output_dir = ROOT_DIR / "tmp" / "dev_hub_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._load_test_data()
        self._build_ui()
        self._poll_latest_screenshot()
        self._poll_broken_anims()
        
        # Level Editor State
        self.inspector_data = {}
        self.last_inspector_eid = None
        self._level_preview_lbl = None
        self._level_preview_img = None
        self._level_editor_win  = None   # LevelEditorWindow instance
        self._studio_shell = None
        self._start_editor_polling()
        self._poll_level_preview()


    def _load_config(self) -> dict:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except:
                pass
        return {"actors": {}, "profiles": {}, "studio": {}}

    def _save_config(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(self.config_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            self.log(f"[Studio] Failed to save dev hub config: {exc}")

    def _load_test_data(self):
        # 1. Load Video Scenarios
        if AutonomousQARunner:
            try:
                self.available_scenarios = build_default_scenarios()
                scenario_path = ROOT_DIR / "test" / "tests" / "video_scenarios" / "scenarios.json"
                if scenario_path.exists():
                    self.available_scenarios.extend(load_repo_video_scenarios(str(scenario_path)))
            except Exception as e:
                self.log(f"Error loading scenarios: {e}")

        # 2. Discover Pytest scripts
        tests_dir = ROOT_DIR / "test" / "tests"
        if tests_dir.exists():
            for file in tests_dir.glob("test_*.py"):
                name = file.stem
                prefix = name.split('_')[1] if len(name.split('_')) > 1 else 'other'
                group = prefix.capitalize() + " Tests"
                if group not in self.available_pytest_groups:
                    self.available_pytest_groups[group] = []
                self.available_pytest_groups[group].append(str(file))

    def _build_ui(self):
        # Create Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="KING WIZARD HUB", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Categories
        self.btn_launch = ctk.CTkButton(self.sidebar_frame, text="Launch Control", command=lambda: self._show_category("Launch"))
        self.btn_launch.grid(row=1, column=0, padx=20, pady=10)

        self.btn_profiles = ctk.CTkButton(self.sidebar_frame, text="Testing Profiles", command=lambda: self._show_category("Profiles"))
        self.btn_profiles.grid(row=2, column=0, padx=20, pady=10)

        self.btn_assets = ctk.CTkButton(self.sidebar_frame, text="Asset Inspector", command=lambda: self._show_category("Assets"))
        self.btn_assets.grid(row=3, column=0, padx=20, pady=10)

        self.btn_env = ctk.CTkButton(self.sidebar_frame, text="World Editor", command=lambda: self._show_category("World"))
        self.btn_env.grid(row=4, column=0, padx=20, pady=10)

        self.btn_qa = ctk.CTkButton(self.sidebar_frame, text="QA & Automated Tests", command=lambda: self._show_category("QA"))
        self.btn_qa.grid(row=5, column=0, padx=20, pady=10)

        self.btn_visual = ctk.CTkButton(
            self.sidebar_frame,
            text="Visual Studio",
            fg_color="#e67e22",
            hover_color="#d35400",
            command=lambda: self._show_category("Visual Studio"),
        )
        self.btn_visual.grid(row=6, column=0, padx=20, pady=10)

        self.btn_logic = ctk.CTkButton(
            self.sidebar_frame,
            text="Logic Studio",
            fg_color="#8e44ad",
            hover_color="#7d3c98",
            command=lambda: self._show_category("Logic Studio"),
        )
        self.btn_logic.grid(row=7, column=0, padx=20, pady=10)

        self.btn_level = ctk.CTkButton(
            self.sidebar_frame, text="Level Design",
            fg_color="#e67e22", hover_color="#d35400",
            command=self._open_level_editor)
        self.btn_level.grid(row=8, column=0, padx=20, pady=10)

        # Main Workspace
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Top area (Title & Controls)
        self.top_frame = ctk.CTkFrame(self.main_frame)
        self.top_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

        self.lbl_category = ctk.CTkLabel(self.top_frame, text="Welcome", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_category.pack(side="left", padx=20, pady=15)

        # Content Frame (Dynamic)
        self.content_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.content_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Bottom Area (Console & Preview)
        self.bottom_frame = ctk.CTkFrame(self.main_frame, height=350)
        self.bottom_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.bottom_frame.grid_columnconfigure(0, weight=2)
        self.bottom_frame.grid_columnconfigure(1, weight=1)
        self.bottom_frame.grid_rowconfigure(1, weight=1)

        # Console Header
        self.console_header = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        self.console_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 0))
        
        ctk.CTkLabel(self.console_header, text="Unified Console Output", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        
        btn_copy = ctk.CTkButton(self.console_header, text="Copy Logs", width=80, height=24, 
                                 fg_color="#34495e", command=self._copy_console)
        btn_copy.pack(side="right", padx=5)

        btn_clear = ctk.CTkButton(self.console_header, text="Clear Logs", width=80, height=24,
                                  fg_color="#c0392b", hover_color="#a93226", command=self._clear_console)
        btn_clear.pack(side="right", padx=5)

        self.console = ctk.CTkTextbox(self.bottom_frame, font=ctk.CTkFont(family="Consolas", size=11))
        self.console.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.console.configure(state="disabled")

        self.preview_frame = ctk.CTkFrame(self.bottom_frame)
        self.preview_frame.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="nsew")
        
        self.preview_lbl = ctk.CTkLabel(self.preview_frame, text="Recent activity visualization...")
        self.preview_lbl.pack(expand=True, fill="both")

        self._show_category("Launch")

    def _show_category(self, category: str):
        self.lbl_category.configure(text=category)
        
        # Clear existing content
        for child in self.content_frame.winfo_children():
            child.destroy()
        self.checkboxes.clear()

        if category == "Launch":
            self._build_launch_tab()
        elif category == "Profiles":
            self._build_profiles_tab()
        elif category == "Assets":
            self._build_assets_tab()
        elif category == "World":
            self._build_world_tab()
        elif category == "QA":
            self._build_qa_tab()
        elif category == "Visual Studio":
            self._build_studio_tab("visual_studio")
        elif category == "Logic Studio":
            self._build_studio_tab("logic_studio")
        elif category == "Level Design":
            self._open_level_editor()

    def _focus_studio_path(self, studio_key: str, relative_path: str):
        category = "Visual Studio" if studio_key == "visual_studio" else "Logic Studio"
        if self.lbl_category.cget("text") != category or self._studio_shell is None or not self._studio_shell.winfo_exists():
            self._show_category(category)
        if self._studio_shell is not None and self._studio_shell.winfo_exists():
            self._studio_shell.switch_studio(studio_key)
            if str(relative_path or "").strip():
                self._studio_shell.focus_path(relative_path)
                self.log(f"[Studio] Focused {relative_path} in {studio_key}.")

    def _on_studio_session_change(self, session_payload: dict):
        self.config_data.setdefault("studio", {})
        self.config_data["studio"]["session"] = dict(session_payload or {})
        self._save_config()

    def _build_visual_studio_actions(self):
        return [
            {
                "label": "Open World Layout Editor",
                "description": "Launch the existing live world layout tool from inside the shared shell workflow.",
                "fg_color": "#e67e22",
                "hover_color": "#d35400",
                "command": self._open_level_editor,
            },
            {
                "label": "Focus Scene Data",
                "description": "Jump straight to canonical scene files inside the embedded studio layout.",
                "fg_color": "#16a085",
                "hover_color": "#138d75",
                "command": lambda: self._focus_studio_path("visual_studio", "data/scenes"),
            },
            {
                "label": "Focus UI Sources",
                "description": "Open the project UI scripts without leaving the shared studio shell.",
                "fg_color": "#3498db",
                "hover_color": "#2980b9",
                "command": lambda: self._focus_studio_path("visual_studio", "src/ui"),
            },
        ]

    def _build_logic_studio_actions(self):
        return [
            {
                "label": "Focus Dialogues",
                "description": "Jump directly into canonical dialogue graphs and source files.",
                "fg_color": "#8e44ad",
                "hover_color": "#7d3c98",
                "command": lambda: self._focus_studio_path("logic_studio", "data/dialogues"),
            },
            {
                "label": "Focus Quests",
                "description": "Open quest data in the same shared shell with structured inspectors.",
                "fg_color": "#6c5ce7",
                "hover_color": "#5b4bd6",
                "command": lambda: self._focus_studio_path("logic_studio", "data/quests"),
            },
            {
                "label": "Focus Scenes",
                "description": "Inspect scene flow and narrative context inside the shared layout.",
                "fg_color": "#2980b9",
                "hover_color": "#2471a3",
                "command": lambda: self._focus_studio_path("logic_studio", "data/scenes"),
            },
        ]

    def _build_studio_tab(self, studio_key: str):
        if not (_STUDIO_WINDOW_OK and StudioShell):
            self.log("[Studio] StudioShell unavailable - check dev/studio_window.py")
            return
        self._studio_shell = StudioShell(
            self.content_frame,
            ROOT_DIR,
            studio_manifest=self.studio_manifest,
            initial_studio_key=studio_key,
            log_fn=self.log,
            actions_by_key={
                "visual_studio": self._build_visual_studio_actions(),
                "logic_studio": self._build_logic_studio_actions(),
            },
            initial_session=dict((self.config_data.get("studio") or {}).get("session") or {}),
            on_session_change=self._on_studio_session_change,
        )
        self._studio_shell.pack(fill="both", expand=True, padx=8, pady=8)
        self.log(f"[Studio] Embedded shell ready for {studio_key}.")

    def _open_level_editor(self):
        """Open (or focus) the standalone Level Editor window."""
        db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
        if _LEVEL_EDITOR_OK and LevelEditorWindow:
            if self._level_editor_win is None or not (
                hasattr(self._level_editor_win, "_win")
                and self._level_editor_win._win
                and self._level_editor_win._win.winfo_exists()
            ):
                self._level_editor_win = LevelEditorWindow(ROOT_DIR, db_path, self.log)
            self._level_editor_win.open()
        else:
            self.log("[LevelEditor] LevelEditorWindow unavailable — check dev/level_editor_window.py")

    def _build_launch_tab(self):

        # Big Launch Buttons
        btn_game = ctk.CTkButton(self.content_frame, text="START REGULAR GAME", height=80, 
                                 font=ctk.CTkFont(size=16, weight="bold"), fg_color="#2ecc71", hover_color="#27ae60",
                                 command=lambda: self._launch_process([sys.executable, "run_game.pyw"], "Game"))
        btn_game.pack(fill="x", padx=40, pady=20)

        btn_viewer = ctk.CTkButton(self.content_frame, text="OPEN 3D ASSET VIEWER", height=80,
                                   font=ctk.CTkFont(size=16, weight="bold"), fg_color="#3498db", hover_color="#2980b9",
                                   command=lambda: self._launch_process([sys.executable, "scripts/asset_animation_viewer.py"], "Viewer"))
        btn_viewer.pack(fill="x", padx=40, pady=20)

        # Documentation
        lbl_docs = ctk.CTkLabel(self.content_frame, text="Documentation & Manuals", font=ctk.CTkFont(weight="bold"))
        lbl_docs.pack(pady=(20, 10))
        
        for doc in ["README.md", "docs/AGENT_GAMEPLAY_PLAYBOOK.md"]:
            btn_doc = ctk.CTkButton(self.content_frame, text=f"View {doc}", height=40,
                                    fg_color="transparent", border_width=1,
                                    command=lambda d=doc: os.startfile(ROOT_DIR / d))
            btn_doc.pack(fill="x", padx=60, pady=5)

    def _build_profiles_tab(self):
        profiles = self.config_data.get("profiles", {})
        if not profiles:
            ctk.CTkLabel(self.content_frame, text="No test profiles defined in config.").pack(pady=40)
            return

        for label, profile_key in profiles.items():
            frame = ctk.CTkFrame(self.content_frame)
            frame.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=20, pady=10)
            
            btn = ctk.CTkButton(frame, text="Run Profile", width=120, 
                                command=lambda k=profile_key: self._launch_process([sys.executable, "launcher_test_hub.py", "--test", k], f"Test:{k}"))
            btn.pack(side="right", padx=10, pady=5)

    def _build_assets_tab(self):
        categories = self.config_data.get("categories", {})
        if not categories:
            ctk.CTkLabel(self.content_frame, text="No categories defined in dev_hub_config.json").pack(pady=40)
            return

        # Main Tabview for Asset Categories
        self.asset_tabs = ctk.CTkTabview(self.content_frame, height=600)
        self.asset_tabs.pack(fill="both", expand=True, padx=10, pady=10)
        
        for cat_name in ["Characters", "Props", "Particles"]:
            tab = self.asset_tabs.add(cat_name)
            self._populate_asset_tab(tab, cat_name, categories.get(cat_name, {}))

        # Action Buttons Area (Static)
        self.asset_actions = ctk.CTkFrame(self.content_frame)
        self.asset_actions.pack(fill="x", padx=10, pady=(0, 10))
        
        self.btn_inspect = ctk.CTkButton(self.asset_actions, text="Launch Inspector", state="disabled", 
                                          height=40, command=self._inspect_asset)
        self.btn_inspect.pack(side="right", padx=10)

    def _build_world_tab(self):
        # 1. Location Presets
        presets_frame = ctk.CTkFrame(self.content_frame)
        presets_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(presets_frame, text="Location Presets", font=("", 14, "bold")).pack(pady=5)
        
        btn_f = ctk.CTkFrame(presets_frame, fg_color="transparent")
        btn_f.pack(pady=5)
        
        presets = [
            ("Default Forest", "default", "#2ecc71"),
            ("Kremora (Red)", "kremora", "#e74c3c"),
            ("Shadow Realm", "night", "#34495e"),
            ("Stormy Peaks", "storm", "#3498db")
        ]
        
        for text, key, color in presets:
            btn = ctk.CTkButton(btn_f, text=text, width=140, fg_color=color, hover_color=color,
                                command=lambda k=key: self._send_env_command({"preset": k}))
            btn.pack(side="left", padx=5)

        # 2. Real-time Controls
        ctrl_frame = ctk.CTkFrame(self.content_frame)
        ctrl_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(ctrl_frame, text="Environment Fine-Tuning", font=("", 14, "bold")).pack(pady=10)

        self._add_env_slider(ctrl_frame, "Time of Day", "time", 0.0, 1.0, 0.5)
        self._add_env_slider(ctrl_frame, "Fog Density", "fog_density", 0.0, 0.05, 0.005)
        self._add_env_slider(ctrl_frame, "Ambient Strength", "ambient", 0.0, 2.0, 1.0)
        self._add_env_slider(ctrl_frame, "Sun Intensity", "sun", 0.0, 3.0, 1.2)

    def _add_env_slider(self, parent, label, key, min_val, max_val, default):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(f, text=label, width=120, anchor="w").pack(side="left")
        slider = ctk.CTkSlider(f, from_=min_val, to=max_val, 
                               command=lambda v, k=key: self._send_env_command({k: v}))
        slider.set(default)
        slider.pack(side="left", fill="x", expand=True, padx=10)
        
        val_lbl = ctk.CTkLabel(f, text=f"{default:.3f}", width=50)
        val_lbl.pack(side="right")
        # Update label on change
        slider.configure(command=lambda v, k=key, l=val_lbl: [l.configure(text=f"{v:.3f}"), self._send_env_command({k: v})])

    def _send_env_command(self, data):
        """Writes environmental overrides to a shared JSON file for the game to pick up."""
        update_dir = ROOT_DIR / "dev"
        update_dir.mkdir(parents=True, exist_ok=True)
        update_path = update_dir / "dev_env_update.json"
        
        # Load existing if any, to merge
        current = {}
        if update_path.exists():
            try: current = json.loads(update_path.read_text())
            except: pass
            
        current.update(data)
        update_path.write_text(json.dumps(current, indent=4))
        self.log(f"Env Command Sent: {data}")

    def _render_asset_list(self, category, query):
        list_frame, assets = self.asset_lists[category]
        for child in list_frame.winfo_children():
            child.destroy()
            
        q = query.lower()
        for name, config in assets.items():
            if q and q not in name.lower(): continue
            
            btn = ctk.CTkButton(list_frame, text=name, height=36, anchor="w",
                                fg_color="transparent", border_width=1,
                                command=lambda n=name, c=config, t=category: self._on_asset_selected(t, n, c))
            btn.pack(fill="x", padx=5, pady=2)

    def _filter_assets(self, category, query):
        self._render_asset_list(category, query)

    def _on_asset_selected(self, category, name, config):
        self.log(f"Selected {category}: {name}")
        self.current_asset_cfg = config
        self.current_asset_name = name
        self.current_asset_type = category
        
        # Show path info
        model_path = config.get("model") or config.get("config")
        self.preview_lbl.configure(text=f"Asset: {name}\nPath: {model_path}")
        
        # Toggle Inspector
        self.btn_inspect.configure(state="normal", text=f"Inspect {name}")
        
        # If Character, show animation list in console or detail area
        if category == "Characters" and "anims" in config:
            self._load_character_anims(config["anims"])
        else:
            self.log(f"{category} asset has no associated animation list.")

    def _load_character_anims(self, anim_json_path):
        anim_path = ROOT_DIR / anim_json_path
        if anim_path.exists():
            try:
                data = json.loads(anim_path.read_text(encoding="utf-8"))
                sources = data.get("manifest", {}).get("sources", [])
                anims = [s.get("key") for s in sources if s.get("key")]
                self.log(f"Found {len(anims)} animations for character.")
                # We could show these in a separate list, but for now we log them
                # or put them in the console as a reference.
            except:
                pass

    def _inspect_asset(self):
        if not hasattr(self, "current_asset_cfg"): return
        config = self.current_asset_cfg
        name = self.current_asset_name
        category = self.current_asset_type
        
        model = config.get("model") or config.get("config")
        if not model: return

        # Characters use --start-model, Props use it too, Particles might need a different flag later
        cmd = [sys.executable, "scripts/asset_animation_viewer.py", "--start-model", str(model)]
        self._launch_process(cmd, f"Inspect:{name}")

    def _on_actor_changed(self, actor_name):
        actors = self.config_data.get("actors", {})
        cfg = actors.get(actor_name)
        if not cfg: return
        
        self.current_actor_cfg = cfg
        self.current_anims = []
        
        # Load anim names
        anim_path = ROOT_DIR / cfg.get("anims", "")
        if anim_path.exists():
            try:
                data = json.loads(anim_path.read_text(encoding="utf-8"))
                manifest = data.get("manifest", {})
                sources = manifest.get("sources", [])
                self.current_anims = [s.get("key") for s in sources if s.get("key")]
            except:
                pass
        
        self._filter_anims()
        self.btn_inspect.configure(state="normal")

    def _filter_anims(self, event=None):
        query = self.anim_search.get().lower()
        filtered = [a for a in self.current_anims if query in a.lower()]
        
        self.anim_list.configure(state="normal")
        self.anim_list.delete("1.0", "end")
        self.anim_list.insert("end", "\n".join(filtered))
        self.anim_list.configure(state="disabled")

    def _inspect_anim(self):
        actor = self.actor_dropdown.get()
        cfg = self.config_data.get("actors", {}).get(actor)
        if not cfg: return

        # Try to get currently highlighted anim from textbox cursor or just launch viewer
        cmd = [sys.executable, "scripts/asset_animation_viewer.py", "--start-model", cfg.get("model")]
        self._launch_process(cmd, f"Inspect:{actor}")

    def _build_env_tab(self):
        # Weather States
        ctk.CTkLabel(self.content_frame, text="Weather System", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        btn_frame = ctk.CTkFrame(self.content_frame)
        btn_frame.pack(fill="x", padx=20, pady=5)
        
        for state in ["Clear", "Rain", "Storm", "Snow"]:
            btn = ctk.CTkButton(btn_frame, text=state, width=100, 
                                command=lambda s=state.lower(): self._send_dev_command(f"weather set {s}"))
            btn.pack(side="left", padx=5)

        # Cursed Blend (Krimora Hue)
        ctk.CTkLabel(self.content_frame, text="Cursed (Krimora) Atmosphere Blend", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 10))
        self.cursed_slider = ctk.CTkSlider(self.content_frame, from_=0.0, to=1.0, 
                                          command=lambda v: self._send_dev_command(f"environment cursed {v:.2f}"))
        self.cursed_slider.pack(fill="x", padx=40, pady=10)
        self.cursed_slider.set(0.0)

        # Visual FX Sandbox
        ctk.CTkLabel(self.content_frame, text="Visual Effects Sandbox", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 10))
        vfx_btn = ctk.CTkButton(self.content_frame, text="LAUNCH VFX SANDBOX", height=40, fg_color="#9b59b6",
                               command=lambda: self._launch_process([sys.executable, "launcher_test_hub.py", "--test", "mechanics"], "VFX_Sandbox"))
        vfx_btn.pack(fill="x", padx=40, pady=10)

    def _send_dev_command(self, cmd: str):
        # In a real scenario, this would use a socket or IPC. 
        # For now, we log it and potentially write to a 'dev_actions.json' that the game polls.
        self.log(f"DevCommand: {cmd}")
        action_path = ROOT_DIR / "tmp" / "dev_actions.json"
        try:
            data = {"command": cmd, "timestamp": time.time()}
            action_path.write_text(json.dumps(data), encoding="utf-8")
        except:
            pass

    def _build_qa_tab(self):
        # Scenario Checklist
        lbl_s = ctk.CTkLabel(self.content_frame, text="Automated Video Scenarios", font=ctk.CTkFont(weight="bold"))
        lbl_s.pack(pady=10)
        
        for scenario in self.available_scenarios:
            cb = ctk.CTkCheckBox(self.content_frame, text=f"{scenario.name} ({len(scenario.steps)} steps)")
            cb.pack(anchor="w", padx=40, pady=2)
            cb._scenario = scenario
            self.checkboxes.append(cb)

        # Pytest Groups
        lbl_t = ctk.CTkLabel(self.content_frame, text="Engine Logic Tests", font=ctk.CTkFont(weight="bold"))
        lbl_t.pack(pady=(20, 10))
        
        for group, paths in self.available_pytest_groups.items():
            f = ctk.CTkFrame(self.content_frame)
            f.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(f, text=group).pack(side="left", padx=10)
            for p in paths:
                cb = ctk.CTkCheckBox(f, text=Path(p).name)
                cb.pack(side="left", padx=10)
                cb._test_path = p
                self.checkboxes.append(cb)

        # Run Button
        btn_run = ctk.CTkButton(self.content_frame, text="EXECUTE SELECTED QA TASKS", height=50, fg_color="green",
                                command=self._run_selected_qa)
        btn_run.pack(pady=20)

    def log(self, message: str):
        self.console.configure(state="normal")
        self.console.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.console.see("end")
        self.console.configure(state="disabled")

    def _copy_console(self):
        text = self.console.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("Console logs copied to clipboard.")

    def _clear_console(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")
        self.log("Console logs cleared.")

    def _launch_process(self, cmd: List[str], label: str):
        self.log(f"Launching {label}: {' '.join(cmd)}")
        def run():
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(ROOT_DIR))
                for line in proc.stdout:
                    self.log(f"[{label}] {line.rstrip()}")
                proc.wait()
                self.log(f"{label} process exited (code {proc.returncode})")
            except Exception as e:
                self.log(f"Error starting {label}: {e}")
        
        threading.Thread(target=run, daemon=True).start()

    def _run_selected_qa(self):
        selected = [cb for cb in self.checkboxes if cb.get()]
        if not selected:
            self.log("No QA tasks selected.")
            return

        # Execute scenarios and tests in separate threads...
        # Logic simplified from debugger_gui.pyw
        for cb in selected:
            if hasattr(cb, "_scenario"):
                self._launch_process([sys.executable, "dev/custom_debugger.py", "--scenario", cb._scenario.name], f"QA:{cb._scenario.name}")
            elif hasattr(cb, "_test_path"):
                self._launch_process([sys.executable, "-m", "pytest", cb._test_path], f"Test:{Path(cb._test_path).name}")

    def _poll_latest_screenshot(self):
        try:
            d = ROOT_DIR / "tmp"
            latest_file = None
            latest_time = 0
            for f in d.glob("*.png"):
                mtime = f.stat().st_mtime
                if mtime > latest_time:
                    latest_time = mtime
                    latest_file = f
            
            if latest_file and (not hasattr(self, "_last_img") or self._last_img != str(latest_file)):
                self._last_img = str(latest_file)
                img = Image.open(latest_file)
                img.thumbnail((300, 300))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(300, 200))
                self.preview_lbl.configure(image=ctk_img, text="")
                self.preview_lbl.image = ctk_img
        except:
            pass
        self.after(3000, self._poll_latest_screenshot)

    def _poll_broken_anims(self):
        log_path = ROOT_DIR / "dev" / "broken_anims.json"
        if log_path.exists():
            try:
                data = json.loads(log_path.read_text(encoding="utf-8"))
                if data and hasattr(self, "status_lbl"):
                    self.status_lbl.configure(text=f"⚠️ {len(data)} issues reported in broken_anims.json", text_color="#e74c3c")
            except:
                pass
        self.after(5000, self._poll_broken_anims)

    # --- Level Editor 2.0 Logic (SQLite + Msgpack) ---

    def _request_editor_screenshot(self):
        """Ask the running game to snapshot the current view and write it to the bridge."""
        db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
        try:
            packed = msgpack.packb({"trigger": True}, use_bin_type=True)
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)",
                         ("screenshot_request", sqlite3.Binary(packed)))
            conn.commit()
            conn.close()
            self.log("[Preview] Screenshot requested from engine.")
        except Exception as e:
            self.log(f"[Preview] Request failed: {e}")

    def _update_level_preview_placeholder(self):
        """Show a stylised placeholder when no screenshot is available yet."""
        if not self._level_preview_lbl:
            return
        # Try loading the most recent tmp/*.png as a fallback
        found = None
        for pat in ["tmp/editor_preview*.png", "tmp/*.png"]:
            hits = sorted((ROOT_DIR / "tmp").glob(pat.split("/")[1]),
                          key=lambda p: p.stat().st_mtime, reverse=True)
            if hits:
                found = hits[0]
                break
        if found:
            try:
                img = Image.open(found)
                self._show_level_preview_image(img, found.name)
                return
            except Exception:
                pass
        self._level_preview_lbl.configure(
            text="▶ Run the game and press 📸 Capture\nto see the location here.",
            image=None, font=("", 13, "italic"), text_color="#4a4a6a")

    def _show_level_preview_image(self, img: Image.Image, label: str = ""):
        """Resize and display a PIL image in the level preview panel."""
        if not self._level_preview_lbl:
            return
        try:
            w, h = 860, 320
            img = img.convert("RGB")
            img.thumbnail((w, h), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            self._level_preview_img = ctk_img
            self._level_preview_lbl.configure(image=ctk_img, text="")
            if hasattr(self, "preview_loc_label"):
                self.preview_loc_label.configure(text=label or "live", text_color="#2ecc71")
        except Exception as e:
            self.log(f"[Preview] Image update error: {e}")

    def _poll_level_preview(self):
        """Every 2 s: check the SQLite bridge for a new editor_screenshot blob."""
        db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
        if db_path.exists() and self._level_preview_lbl:
            try:
                conn = sqlite3.connect(db_path, timeout=1.0)
                row = conn.execute(
                    "SELECT payload FROM bridge WHERE key = 'editor_screenshot'"
                ).fetchone()
                conn.close()
                if row:
                    import io
                    data = msgpack.unpackb(bytes(row[0]), raw=False)
                    png_bytes = data.get("png")
                    location = data.get("location", "")
                    if png_bytes:
                        img = Image.open(io.BytesIO(bytes(png_bytes)))
                        self._show_level_preview_image(img, location)
            except Exception:
                pass
        self.after(2000, self._poll_level_preview)

    def _start_editor_polling(self):

        def poll_loop():
            db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
            while True:
                if db_path.exists():
                    try:
                        conn = sqlite3.connect(db_path)
                        row = conn.execute("SELECT payload FROM bridge WHERE key = ?", ("inspector_feedback",)).fetchone()
                        conn.close()
                        if row:
                            data = msgpack.unpackb(row[0], raw=False)
                            if data and data.get("selected") and data.get("entity_id") != self.last_inspector_eid:
                                self.inspector_data = data
                                self.last_inspector_eid = data.get("entity_id")
                                self.after(10, self._refresh_inspector_ui)
                    except Exception as e:
                        pass
                time.sleep(0.1)
        
        threading.Thread(target=poll_loop, daemon=True).start()

    def _build_level_design_tab(self):
        # ── LIVE LOCATION PREVIEW ──────────────────────────────────────────
        prev_outer = ctk.CTkFrame(self.content_frame, fg_color="#1a1a2e", corner_radius=12)
        prev_outer.pack(fill="x", padx=10, pady=(10, 4))

        prev_header = ctk.CTkFrame(prev_outer, fg_color="transparent")
        prev_header.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(prev_header, text="📷  LOCATION PREVIEW",
                     font=("", 13, "bold"), text_color="#e67e22").pack(side="left")
        self.preview_loc_label = ctk.CTkLabel(prev_header, text="— not connected —",
                                              font=("", 11), text_color="#7f8c8d")
        self.preview_loc_label.pack(side="left", padx=12)
        ctk.CTkButton(prev_header, text="📸 Capture", width=80, height=24,
                      fg_color="#2980b9", hover_color="#3498db",
                      command=self._request_editor_screenshot).pack(side="right", padx=4)

        self._level_preview_lbl = ctk.CTkLabel(prev_outer, text="",
                                               width=860, height=320,
                                               fg_color="#0d0d1a",
                                               corner_radius=8)
        self._level_preview_lbl.pack(padx=12, pady=(6, 12))
        # Show «waiting» placeholder immediately
        self._update_level_preview_placeholder()

        # ── HEADER / BAKE ──────────────────────────────────────────────────
        header = ctk.CTkFrame(self.content_frame)
        header.pack(fill="x", padx=10, pady=(4, 0))

        ctk.CTkLabel(header, text="ENTITY INSPECTOR", font=("", 16, "bold"), text_color="#e67e22").pack(side="left", padx=10)
        
        self.btn_save_world = ctk.CTkButton(header, text="BAKE WORLD CHANGES", fg_color="#27ae60", hover_color="#2ecc71",
                                           command=self._bake_world_changes)
        self.btn_save_world.pack(side="right", padx=10, pady=5)

        # 2. Main Inspector Area
        self.inspector_panel = ctk.CTkFrame(self.content_frame)
        self.inspector_panel.pack(fill="both", expand=True, padx=10, pady=10)
        
        if not self.inspector_data:
            ctk.CTkLabel(self.inspector_panel, text="Click an object in game to inspect it...", font=("", 14, "italic")).pack(pady=40)
            return

        # ID & Type
        row_id = ctk.CTkFrame(self.inspector_panel, fg_color="transparent")
        row_id.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(row_id, text=f"ID: {self.inspector_data.get('entity_id', 'N/A')}", font=("", 12, "bold")).pack(side="left")
        ctk.CTkLabel(row_id, text=f"Type: {self.inspector_data.get('type', 'Unknown')}", text_color="gray").pack(side="right")

        # Transform Sliders
        self.transform_widgets = {}
        for group in ["pos", "hpr", "scale"]:
            g_frame = ctk.CTkFrame(self.inspector_panel)
            g_frame.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(g_frame, text=group.upper(), width=60, font=("", 11, "bold")).pack(side="left", padx=5)
            
            vals = self.inspector_data.get(group, [0,0,0])
            for i, axis in enumerate(["X", "Y", "Z"] if group != "hpr" else ["H", "P", "R"]):
                f = ctk.CTkFrame(g_frame, fg_color="transparent")
                f.pack(side="left", fill="x", expand=True, padx=2)
                ctk.CTkLabel(f, text=axis, width=15).pack(side="left")
                
                # Dynamic range based on transform type
                rmin, rmax = (-100, 100) if group == "pos" else ((-360, 360) if group == "hpr" else (0.1, 10.0))
                
                slider = ctk.CTkSlider(f, from_=rmin, to=rmax, height=16,
                                       command=lambda v, g=group, idx=i: self._on_inspector_value_changed(g, idx, v))
                slider.set(vals[i])
                slider.pack(side="left", fill="x", expand=True)
                
                val_entry = ctk.CTkEntry(f, width=45, height=20, font=("", 10))
                val_entry.insert(0, f"{vals[i]:.2f}")
                val_entry.pack(side="right", padx=2)
                self.transform_widgets[f"{group}_{i}"] = (slider, val_entry)

        # 3. Placement Palette
        pal_frame = ctk.CTkFrame(self.content_frame)
        pal_frame.pack(fill="x", padx=10, pady=20)
        ctk.CTkLabel(pal_frame, text="PLACEMENT PALETTE", font=("", 14, "bold")).pack(pady=10)
        
        grid = ctk.CTkFrame(pal_frame, fg_color="transparent")
        grid.pack(pady=5)
        
        props = [
            ("Rock",       "rock",       "#7f8c8d"),
            ("Barrel",     "barrel",     "#e67e22"),
            ("Tree Trunk", "tree_trunk", "#27ae60"),
            ("Chest",      "chest",      "#f1c40f"),
        ]
        for i, (name, obj_type, color) in enumerate(props):
            btn = ctk.CTkButton(grid, text=name, width=110, fg_color=color, hover_color=color,
                                command=lambda t=obj_type, n=name: self._spawn_object(t, n))
            btn.grid(row=i//2, column=i%2, padx=5, pady=5)

        # 3b. Hazard Palette
        haz_frame = ctk.CTkFrame(self.content_frame)
        haz_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(haz_frame, text="HAZARD ZONES", font=("", 14, "bold"), text_color="#e74c3c").pack(pady=8)
        
        haz_grid = ctk.CTkFrame(haz_frame, fg_color="transparent")
        haz_grid.pack(pady=5)
        
        hazards = [
            ("🔥 Lava Pool",   "lava_pool",    "#c0392b"),
            ("🌿 Swamp Pool",  "swamp_pool",   "#27ae60"),
            ("💧 Water Pool",  "water_pool",   "#2980b9"),
            ("☠️ Poison Zone", "poison_cloud", "#8e44ad"),
            ("❄️ Blizzard",    "blizzard_zone","#5dade2"),
            ("🌋 Fire Area",   "fire_area",    "#e67e22"),
        ]
        for i, (name, hz_type, color) in enumerate(hazards):
            btn = ctk.CTkButton(haz_grid, text=name, width=130, fg_color=color, hover_color=color,
                                command=lambda t=hz_type, n=name: self._spawn_object(t, n))
            btn.grid(row=i//3, column=i%3, padx=5, pady=5)

        # 3c. Magic VFX Tester
        vfx_frame = ctk.CTkFrame(self.content_frame)
        vfx_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(vfx_frame, text="✨ MAGIC VFX TESTER", font=("", 14, "bold"), text_color="#9b59b6").pack(pady=8)
        
        vfx_inner = ctk.CTkFrame(vfx_frame, fg_color="transparent")
        vfx_inner.pack(fill="x", padx=20, pady=5)
        
        # Load spells from data file
        spell_names = self._load_spell_ids()
        self.vfx_spell_var = ctk.StringVar(value=spell_names[0] if spell_names else "fireball")
        
        ctk.CTkLabel(vfx_inner, text="Spell:", width=50).pack(side="left")
        spell_dropdown = ctk.CTkOptionMenu(vfx_inner, variable=self.vfx_spell_var, values=spell_names, width=200)
        spell_dropdown.pack(side="left", padx=5)
        
        vfx_pos_frame = ctk.CTkFrame(vfx_frame, fg_color="transparent")
        vfx_pos_frame.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(vfx_pos_frame, text="Target Pos:", width=80).pack(side="left")
        self.vfx_x = ctk.CTkEntry(vfx_pos_frame, width=55, placeholder_text="X")
        self.vfx_x.pack(side="left", padx=2)
        self.vfx_y = ctk.CTkEntry(vfx_pos_frame, width=55, placeholder_text="Y")
        self.vfx_y.pack(side="left", padx=2)
        self.vfx_z = ctk.CTkEntry(vfx_pos_frame, width=55, placeholder_text="Z")
        self.vfx_z.pack(side="left", padx=2)
        for e, v in [(self.vfx_x, "0"), (self.vfx_y, "0"), (self.vfx_z, "0")]:
            e.insert(0, v)
        
        ctk.CTkButton(vfx_frame, text="🎇 CAST SPELL (VFX TEST)",
                      fg_color="#8e44ad", hover_color="#9b59b6",
                      command=self._cast_vfx_spell).pack(pady=8)

        # 4. Terrain Sculpting
        terr_frame = ctk.CTkFrame(self.content_frame)
        terr_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(terr_frame, text="TERRAIN SCULPTING", font=("", 14, "bold"), text_color="#3498db").pack(pady=10)
        
        self.brush_mode_var = ctk.BooleanVar(value=False)
        cb_brush = ctk.CTkCheckBox(terr_frame, text="Enable Terrain Brush", variable=self.brush_mode_var,
                                   command=self._send_editor_settings)
        cb_brush.pack(pady=5)

        self.brush_type_var = ctk.StringVar(value="raise")
        b_types = ctk.CTkSegmentedButton(terr_frame, values=["raise", "lower", "flatten"],
                                         variable=self.brush_type_var, command=lambda _: self._send_editor_settings())
        b_types.pack(pady=5)

        self.brush_radius = 5.0
        self.brush_strength = 1.0
        
        # Radius Slider
        f_rad = ctk.CTkFrame(terr_frame, fg_color="transparent")
        f_rad.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(f_rad, text="Radius", width=60).pack(side="left")
        s_rad = ctk.CTkSlider(f_rad, from_=1.0, to=30.0, height=16, 
                              command=lambda v: [setattr(self, "brush_radius", v), self._send_editor_settings()])
        s_rad.set(self.brush_radius)
        s_rad.pack(side="left", fill="x", expand=True)

        # Strength Slider
        f_str = ctk.CTkFrame(terr_frame, fg_color="transparent")
        f_str.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(f_str, text="Strength", width=60).pack(side="left")
        s_str = ctk.CTkSlider(f_str, from_=0.1, to=10.0, height=16,
                              command=lambda v: [setattr(self, "brush_strength", v), self._send_editor_settings()])
        s_str.set(self.brush_strength)
        s_str.pack(side="left", fill="x", expand=True)

    def _send_editor_settings(self):
        db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
        try:
            data = {
                "brush_mode": self.brush_mode_var.get(),
                "brush": {
                    "type": self.brush_type_var.get(),
                    "radius": float(self.brush_radius),
                    "strength": float(self.brush_strength)
                }
            }
            packed = msgpack.packb(data, use_bin_type=True)
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)", ("editor_settings", sqlite3.Binary(packed)))
            conn.commit()
            conn.close()
        except Exception as e:
            self.log(f"Settings Hub Fail: {e}")

    def _refresh_inspector_ui(self):
        if self.lbl_category.cget("text") == "Level Design":
            self._show_category("Level Design")

    def _on_inspector_value_changed(self, group, index, value):
        if not self.inspector_data: return
        
        self.inspector_data[group][index] = value
        
        # Update entry widget if exists
        key = f"{group}_{index}"
        if key in self.transform_widgets:
            _, entry = self.transform_widgets[key]
            entry.delete(0, "end")
            entry.insert(0, f"{value:.2f}")

        # Send to game via SQLite
        db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
        try:
            update_data = {
                "entity_id": self.inspector_data["entity_id"],
                "pos": self.inspector_data["pos"],
                "hpr": self.inspector_data["hpr"],
                "scale": self.inspector_data["scale"]
            }
            packed = msgpack.packb(update_data, use_bin_type=True)
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)", ("level_update", sqlite3.Binary(packed)))
            conn.commit()
            conn.close()
        except Exception as e:
            self.log(f"Hub Sync Fail: {e}")

    def _spawn_object(self, obj_type: str, display_name: str):
        """Send a spawn request for a world object via the SQLite bridge."""
        db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
        try:
            # Use last known inspector position, or default to world center
            pos = self.inspector_data.get("pos", [0.0, 10.0, 0.0]) if self.inspector_data else [0.0, 10.0, 0.0]
            data = {"type": obj_type, "pos": pos, "pending": True}
            packed = msgpack.packb(data, use_bin_type=True)
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)",
                         ("spawn_request", sqlite3.Binary(packed)))
            conn.commit()
            conn.close()
            self.log(f"[Spawner] Requested: '{display_name}' at {[round(p,1) for p in pos]}")
        except Exception as e:
            self.log(f"[Spawner] Failed: {e}")

    def _cast_vfx_spell(self):
        """Send a spell cast test request via the SQLite bridge."""
        db_path = ROOT_DIR / "dev" / "dev_editor.sqlite3"
        try:
            spell_id = self.vfx_spell_var.get()
            pos = [
                float(self.vfx_x.get() or 0),
                float(self.vfx_y.get() or 0),
                float(self.vfx_z.get() or 0),
            ]
            data = {"spell_id": spell_id, "pos": pos, "pending": True}
            packed = msgpack.packb(data, use_bin_type=True)
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT OR REPLACE INTO bridge (key, payload) VALUES (?, ?)",
                         ("spell_cast_request", sqlite3.Binary(packed)))
            conn.commit()
            conn.close()
            self.log(f"[VFX] Cast '{spell_id}' at {pos}")
        except Exception as e:
            self.log(f"[VFX] Cast failed: {e}")

    def _load_spell_ids(self) -> list:
        """Load spell IDs from spells.json for the VFX dropdown."""
        paths = [
            ROOT_DIR / "data" / "spells.json",
            ROOT_DIR / "data" / "abilities" / "spells.json",
        ]
        for p in paths:
            if p.exists():
                try:
                    import json
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        return [str(s.get("id", s.get("key", s))) for s in data if isinstance(s, dict)]
                    elif isinstance(data, dict):
                        return list(data.keys())
                except Exception:
                    pass
        return ["fireball", "meteor", "lightning", "freeze", "poison_cloud", "heal_wave"]

    def _bake_world_changes(self):
        self.log("Baking all Level Editor changes into game data...")
        bake_script = ROOT_DIR / "dev" / "bake_level.py"
        if bake_script.exists():
            self._launch_process([sys.executable, str(bake_script)], "Bake")
        else:
            self.log("[Bake] bake_level.py not found — nothing to bake.")

if __name__ == "__main__":
    app = DevHub()
    app.mainloop()
