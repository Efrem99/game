import os
import sys
import time
import json
import threading
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from glob import glob

import customtkinter as ctk
from PIL import Image

# Setup paths to ensure we can import king-wizard modules
ROOT_DIR = Path(__file__).parent.parent.absolute()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the core logic
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
    print(f"Failed to import from dev.custom_debugger: {e}")
    sys.exit(1)


class DebuggerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("King Wizard QA Debugger Hub")
        self.geometry("1400x900")
        
        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Application state
        self.test_directories = {
            "Engine Tests": ROOT_DIR / "test" / "tests",
        }
        self.available_scenarios: List[Scenario] = []
        self.available_pytest_groups: Dict[str, List[str]] = {}
        
        self.current_tests = []
        self.checkboxes = []
        self.running = False
        self.output_dir = ROOT_DIR / "tmp" / "gui_debugger_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._load_test_data()
        self._build_ui()
        self._poll_latest_screenshot()

    def _load_test_data(self):
        # 1. Load Video Scenarios
        try:
            self.available_scenarios = build_default_scenarios()
            scenario_path = ROOT_DIR / "test" / "tests" / "video_scenarios" / "scenarios.json"
            if scenario_path.exists():
                self.available_scenarios.extend(load_repo_video_scenarios(str(scenario_path)))
        except Exception as e:
            self.log(f"Error loading scenarios: {e}")

        # 2. Discover Pytest scripts
        tests_dir = self.test_directories["Engine Tests"]
        if tests_dir.exists():
            for file in tests_dir.glob("test_*.py"):
                name = file.stem
                # Group logically
                prefix = name.split('_')[1] if len(name.split('_')) > 1 else 'other'
                group = prefix.capitalize() + " Tests"
                
                if group not in self.available_pytest_groups:
                    self.available_pytest_groups[group] = []
                self.available_pytest_groups[group].append(str(file))

    def _build_ui(self):
        # Create Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="King Wizard QA", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Categories
        self.btn_scenarios = ctk.CTkButton(self.sidebar_frame, text="Video Scenarios", command=lambda: self._show_category("Scenarios"))
        self.btn_scenarios.grid(row=1, column=0, padx=20, pady=10)

        self.btn_tests = ctk.CTkButton(self.sidebar_frame, text="Engine Tests", command=lambda: self._show_category("Tests"))
        self.btn_tests.grid(row=2, column=0, padx=20, pady=10)

        # Main Workspace
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Top area of Main workspace (List & Controls)
        self.controls_frame = ctk.CTkFrame(self.main_frame)
        self.controls_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")

        self.lbl_category = ctk.CTkLabel(self.controls_frame, text="Select Category", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_category.pack(side="left", padx=10, pady=10)

        self.btn_run = ctk.CTkButton(self.controls_frame, text="Run Selected", command=self._run_selected, fg_color="green")
        self.btn_run.pack(side="right", padx=10, pady=10)
        
        self.btn_toggle_all = ctk.CTkButton(self.controls_frame, text="Toggle All", command=self._toggle_all)
        self.btn_toggle_all.pack(side="right", padx=10, pady=10)

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self.controls_frame, mode="indeterminate")
        self.progress_bar.pack(side="right", padx=10, pady=10)
        self.progress_bar.set(0)

        # Checklist Area
        self.list_frame = ctk.CTkScrollableFrame(self.main_frame, height=250)
        self.list_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        # Bottom Area
        self.bottom_frame = ctk.CTkFrame(self.main_frame)
        self.bottom_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.bottom_frame.grid_columnconfigure(0, weight=2) # Console gets more space
        self.bottom_frame.grid_columnconfigure(1, weight=1) # Screenshot
        self.bottom_frame.grid_rowconfigure(0, weight=1)

        # Console Log
        self.console = ctk.CTkTextbox(self.bottom_frame, state="disabled", font=("Consolas", 12))
        self.console.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Screenshot Viewer
        self.screenshot_lbl = ctk.CTkLabel(self.bottom_frame, text="Waiting for Screenshots...")
        self.screenshot_lbl.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    def _show_category(self, category: str):
        self.lbl_category.configure(text=category)
        
        # Clear existing checkboxes
        for cb in self.checkboxes:
            cb.destroy()
        self.checkboxes.clear()
        self.current_tests.clear()

        if category == "Scenarios":
            self.current_tests = self.available_scenarios
            for i, scenario in enumerate(self.available_scenarios):
                cb = ctk.CTkCheckBox(self.list_frame, text=f"{scenario.name} ({len(scenario.steps)} steps)")
                cb.grid(row=i, column=0, padx=10, pady=5, sticky="w")
                self.checkboxes.append(cb)
                
        elif category == "Tests":
            row = 0
            for group_name, tests in self.available_pytest_groups.items():
                lbl = ctk.CTkLabel(self.list_frame, text=group_name, font=ctk.CTkFont(weight="bold"))
                lbl.grid(row=row, column=0, padx=10, pady=(15, 5), sticky="w")
                row += 1
                for test_path in tests:
                    name = Path(test_path).name
                    cb = ctk.CTkCheckBox(self.list_frame, text=name)
                    # Store path as an attribute
                    cb._test_path = test_path
                    cb.grid(row=row, column=0, padx=25, pady=2, sticky="w")
                    self.checkboxes.append(cb)
                    row += 1
            self.current_tests = self.checkboxes # Proxy for actual test paths

    def _toggle_all(self):
        # Check first checkbox state
        if not self.checkboxes: return
        target_state = not self.checkboxes[0].get()
        for cb in self.checkboxes:
            if target_state:
                cb.select()
            else:
                cb.deselect()

    def log(self, message: str):
        self.console.configure(state="normal")
        self.console.insert("end", message + "\n")
        self.console.see("end")
        self.console.configure(state="disabled")

    def _run_selected(self):
        if self.running: return
        selected = [cb for cb in self.checkboxes if cb.get()]
        if not selected:
            self.log("No tests selected.")
            return

        category = self.lbl_category.cget("text")
        
        self.btn_run.configure(state="disabled", text="Running...")
        self.progress_bar.start()
        self.running = True
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

        if category == "Scenarios":
            # Map selected checkboxes back to Scenario objects
            selected_names = [cb.cget("text").split(" ")[0] for cb in selected]
            scenarios_to_run = [s for s in self.available_scenarios if s.name in selected_names]
            threading.Thread(target=self._execute_scenarios_thread, args=(scenarios_to_run,), daemon=True).start()
        elif category == "Tests":
            test_paths = [getattr(cb, "_test_path") for cb in selected]
            threading.Thread(target=self._execute_pytest_thread, args=(test_paths,), daemon=True).start()

    def _execute_scenarios_thread(self, scenarios: List[Scenario]):
        try:
            adapter = MockGameAdapter()
            runner = AutonomousQARunner(
                adapter=adapter,
                scenarios=scenarios,
                output_dir=str(self.output_dir),
                log_callback=self._log_from_thread,
            )
            self._log_from_thread("=== Starting Autonomous QA Runner ===")
            summary = runner.run()
            self._log_from_thread("=== Runner Completed ===")
            self._log_from_thread(json.dumps(summary, indent=2))
        except Exception as e:
            self._log_from_thread(f"Error in runner: {e}")
        finally:
            self._on_run_completed()

    def _execute_pytest_thread(self, test_paths: List[str]):
        try:
            cmd = [sys.executable, "-m", "pytest", "-v"] + test_paths
            self._log_from_thread(f"=== Running Pytest ===")
            self._log_from_thread(f"Cmd: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(ROOT_DIR))
            
            for line in process.stdout:
                self._log_from_thread(line.rstrip())
                
            process.wait()
            self._log_from_thread(f"=== Pytest Finished with code {process.returncode} ===")
        except Exception as e:
            self._log_from_thread(f"Exception launching pytest: {e}")
        finally:
            self._on_run_completed()

    def _humanize_log_line(self, line: str) -> str:
        # Ignore empty lines
        if not line.strip():
            return line

        text = line
        # Pytest translations
        if "test session starts" in text:
            return "🚀 Запуск пакета тестов..."
        if "collecting ..." in text:
            return "🔍 Поиск тестов..."
        if "=============================" in text or "-----------------------------" in text:
            return "" # Filter out noise
        
        # Parse PASSED / FAILED lines
        if " PASSED " in text:
            parts = text.split(" PASSED ")
            test_name = parts[0].split("::")[-1] if "::" in parts[0] else parts[0]
            return f"✅ Успешно: {test_name.strip()}"
            
        if " FAILED " in text:
            parts = text.split(" FAILED ")
            test_name = parts[0].split("::")[-1] if "::" in parts[0] else parts[0]
            return f"❌ Ошибка в тесте: {test_name.strip()}"

        if "=== Running Pytest ===" in text:
            return "🔥 Готовимся к запуску тестов (Pytest)..."
            
        if "=== Pytest Finished" in text:
            return f"🏁 {text.replace('=== Pytest Finished with code', 'Тестирование завершено, код возврата:')}"

        # QA Runner translations
        if "RUN scenario=" in text:
            return text.replace("RUN scenario=", "🎬 Запуск видео-сценария: ")
            
        if "step=" in text and "verdict=" in text:
            if "verdict=PASS" in text:
                return f"✅ Шаг пройден: {text.split('step=')[-1].split(' ')[0]}"
            elif "verdict=FAIL" in text:
                return f"❌ Шаг провален: {text.split('step=')[-1].split(' ')[0]}"

        # Standard return for everything else
        return text

    def _log_from_thread(self, message: str):
        human_text = self._humanize_log_line(message)
        if human_text:
            # We must use `after` to interact with GUI from a different thread
            self.after(0, self.log, human_text)

    def _on_run_completed(self):
        self.running = False
        def reset_ui():
            self.progress_bar.stop()
            self.progress_bar.set(0)
            self.btn_run.configure(state="normal", text="Run Selected")
        self.after(0, reset_ui)

    def _poll_latest_screenshot(self):
        # Periodically scan tmp folders for new .png files to show
        try:
            screenshot_dirs = [
                self.output_dir,
                ROOT_DIR / "tmp" / "gui_debugger_output",
                ROOT_DIR / "tmp",
            ]
            latest_file = None
            latest_time = 0
            
            for d in screenshot_dirs:
                if not d.exists(): continue
                for f in d.glob("*.png"):
                    mtime = f.stat().st_mtime
                    if mtime > latest_time:
                        latest_time = mtime
                        latest_file = f
                for f in d.glob("*.jpg"):
                    mtime = f.stat().st_mtime
                    if mtime > latest_time:
                        latest_time = mtime
                        latest_file = f

            if latest_file and hasattr(self, "_last_shown_image") and self._last_shown_image == str(latest_file):
                pass # Already showing this image
            elif latest_file:
                self._show_image(latest_file)
                self._last_shown_image = str(latest_file)
        except Exception as e:
            pass
            
        # Poll every 2 seconds
        self.after(2000, self._poll_latest_screenshot)
        
    def _show_image(self, img_path: Path):
        try:
            # Resize image to fit nicely
            img = Image.open(img_path)
            # Maintain aspect ratio
            width, height = img.size
            max_size = 400
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
                
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(new_width, new_height))
            self.screenshot_lbl.configure(image=ctk_img, text=f"Last Output: {img_path.name}")
            self.screenshot_lbl.image = ctk_img
        except Exception as e:
            self.log(f"Failed to load preview image {img_path}: {e}")

if __name__ == "__main__":
    app = DebuggerGUI()
    app.mainloop()
