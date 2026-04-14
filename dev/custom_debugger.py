from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import time
import unittest
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, cast

try:
    import msgpack  # type: ignore
except Exception:  # pragma: no cover
    msgpack = None


# ============================================================
# Core types
# ============================================================


def _str_int_dict() -> Dict[str, int]:
    return {}


def _str_list() -> List[str]:
    return []


def _str_any_dict() -> Dict[str, Any]:
    return {}


def _screenshot_list() -> List["ScreenshotArtifact"]:
    return []


def _pack_msgpack(payload: Dict[str, Any]) -> bytes:
    if msgpack is None:
        raise RuntimeError("msgpack is not available")
    packb = cast(Any, msgpack).packb
    return cast(bytes, packb(payload, use_bin_type=True))


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class BugType(str, Enum):
    NONE = "none"
    VISUAL_DESYNC = "visual_desync"
    FALSE_POSITIVE_STATE = "false_positive_state"
    PHYSICS_DESYNC = "physics_desync"
    ANIMATION_BUG = "animation_bug"
    INPUT_BUG = "input_bug"
    UI_BUG = "ui_bug"
    ROUTE_BUG = "route_bug"
    INTERACTION_BUG = "interaction_bug"
    MAGIC_BUG = "magic_bug"
    COMBAT_BUG = "combat_bug"
    PARTICLE_BUG = "particle_bug"
    EQUIPMENT_BUG = "equipment_bug"
    TRANSITION_BUG = "transition_bug"
    CUTSCENE_BUG = "cutscene_bug"
    LOADING_BUG = "loading_bug"
    COMPANION_BUG = "companion_bug"
    PERSISTENCE_BUG = "persistence_bug"
    EDGE_CASE_BUG = "edge_case_bug"
    PERFORMANCE_BUG = "performance_bug"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    RUN_VIDEO_SCENARIO = "run_video_scenario"
    MOVE_TO = "move_to"
    MOVE_ROUTE = "move_route"
    ROTATE_TO = "rotate_to"
    AIM_AT = "aim_at"
    INTERACT = "interact"
    OPEN_MENU = "open_menu"
    CLOSE_MENU = "close_menu"
    SCROLL_MENU = "scroll_menu"
    CLICK_BUTTON = "click_button"
    TALK_TO_NPC = "talk_to_npc"
    ADVANCE_DIALOGUE = "advance_dialogue"
    ATTACK_SWORD = "attack_sword"
    ATTACK_BOW = "attack_bow"
    CAST_MAGIC = "cast_magic"
    EQUIP_ITEM = "equip_item"
    UNEQUIP_ITEM = "unequip_item"
    CHECK_PARTICLES = "check_particles"
    MOUNT = "mount"
    DISMOUNT = "dismount"
    SWIM_TO = "swim_to"
    FLY_TO = "fly_to"
    TELEPORT = "teleport"
    TRANSITION_LOCATION = "transition_location"
    CHECK_CUTSCENE = "check_cutscene"
    CHECK_LOADING = "check_loading"
    CHECK_COMPANION = "check_companion"
    SAVE_GAME = "save_game"
    LOAD_GAME = "load_game"
    DIE_AND_RESPAWN = "die_and_respawn"
    ASSERT_STATE = "assert_state"
    WAIT = "wait"
    INPUT_STRESS = "input_stress"
    EDGE_CASE = "edge_case"


@dataclass
class PerfMetrics:
    fps: float = 0.0
    frame_time_ms: float = 0.0
    draw_calls: int = 0
    triangles: int = 0
    instances: int = 0
    lod_distribution: Dict[str, int] = field(default_factory=_str_int_dict)


@dataclass
class WorldState:
    scene_name: str = ""
    loading: bool = False
    loading_progress: float = 0.0
    player_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    player_rot: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    player_velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    current_animation: str = ""
    current_effects: List[str] = field(default_factory=_str_list)
    ui_stack: List[str] = field(default_factory=_str_list)
    input_enabled: bool = True
    control_locked: bool = False
    companion_state: Dict[str, Any] = field(default_factory=_str_any_dict)
    equipment_state: Dict[str, Any] = field(default_factory=_str_any_dict)
    object_states: Dict[str, Any] = field(default_factory=_str_any_dict)
    misc: Dict[str, Any] = field(default_factory=_str_any_dict)


@dataclass
class ScreenshotArtifact:
    label: str
    path: str


@dataclass
class StepResult:
    scenario_name: str
    step_index: int
    step_name: str
    action: str
    verdict: Verdict
    bug_type: BugType = BugType.NONE
    reason: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_sec: float = 0.0
    attempts: int = 1
    pre_state: Dict[str, Any] = field(default_factory=_str_any_dict)
    post_state: Dict[str, Any] = field(default_factory=_str_any_dict)
    perf: PerfMetrics = field(default_factory=PerfMetrics)
    screenshots: List[ScreenshotArtifact] = field(default_factory=_screenshot_list)
    evidence: Dict[str, Any] = field(default_factory=_str_any_dict)


@dataclass
class ScenarioStep:
    name: str
    action: ActionType
    target: Optional[str] = None
    route: Optional[str] = None
    menu: Optional[str] = None
    button: Optional[str] = None
    item: Optional[str] = None
    spell: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=_str_any_dict)
    expected: Dict[str, Any] = field(default_factory=_str_any_dict)
    timeout_sec: float = 8.0
    retries: int = 1
    checkpoint: Optional[str] = None


@dataclass
class Scenario:
    name: str
    steps: List[ScenarioStep]
    tags: List[str] = field(default_factory=_str_list)


# ============================================================
# Adapter protocol: implement this for your game
# ============================================================


class GameAdapter(Protocol):
    def get_state(self) -> WorldState: ...
    def get_perf_metrics(self) -> PerfMetrics: ...
    def capture_screenshot(self, label: str, out_dir: str) -> str: ...
    def move_to_target(self, target_id: str, timeout_sec: float) -> bool: ...
    def follow_route(self, route_id: str, timeout_sec: float) -> bool: ...
    def rotate_to(self, target_id: str, timeout_sec: float) -> bool: ...
    def aim_at(self, target_id: str, timeout_sec: float) -> bool: ...
    def interact(self, target_id: str) -> bool: ...
    def open_menu(self, menu_name: str) -> bool: ...
    def close_menu(self, menu_name: Optional[str] = None) -> bool: ...
    def scroll_menu(self, menu_name: str, direction: str, amount: int = 1) -> bool: ...
    def click_button(self, button_id: str) -> bool: ...
    def talk_to_npc(self, npc_id: str) -> bool: ...
    def advance_dialogue(self) -> bool: ...
    def attack_sword(self, target_id: Optional[str] = None, combo: int = 1) -> bool: ...
    def attack_bow(self, target_id: Optional[str] = None, charged: bool = False) -> bool: ...
    def cast_magic(self, spell_id: str, target_id: Optional[str] = None) -> bool: ...
    def equip_item(self, item_id: str) -> bool: ...
    def unequip_item(self, item_id: str) -> bool: ...
    def mount(self, mount_id: Optional[str] = None) -> bool: ...
    def dismount(self) -> bool: ...
    def swim_to(self, target_id: str, timeout_sec: float) -> bool: ...
    def fly_to(self, target_id: str, timeout_sec: float) -> bool: ...
    def teleport(self, target_id: str) -> bool: ...
    def transition_location(self, transition_id: str) -> bool: ...
    def trigger_cutscene(self, cutscene_id: str) -> bool: ...
    def save_game(self, slot: str) -> bool: ...
    def load_game(self, slot: str) -> bool: ...
    def kill_player(self) -> bool: ...
    def respawn_player(self) -> bool: ...
    def wait(self, seconds: float) -> None: ...
    def stop_all_input(self) -> None: ...
    def spam_input(self, inputs: List[str], duration_sec: float) -> bool: ...
    def interrupt_current_action(self) -> bool: ...
    def reset_to_checkpoint(self, checkpoint_id: str) -> bool: ...
    def query_distance_to(self, target_id: str) -> float: ...
    def is_prompt_visible(self, prompt_name: str) -> bool: ...
    def is_object_visible(self, target_id: str) -> bool: ...
    def did_particle_play(self, particle_id: Optional[str] = None) -> bool: ...
    def did_hit_connect(self, target_id: Optional[str] = None) -> bool: ...
    def did_projectile_spawn(self) -> bool: ...
    def did_damage_apply(self, target_id: Optional[str] = None) -> bool: ...
    def did_magic_effect_apply(self, spell_id: str, target_id: Optional[str] = None) -> bool: ...


# ============================================================
# Adapter protocol: implement this for your game
# ============================================================


class GameAdapter(Protocol):
    def get_state(self) -> WorldState: ...
    def get_perf_metrics(self) -> PerfMetrics: ...
    def capture_screenshot(self, label: str, out_dir: str) -> str: ...
    def move_to_target(self, target_id: str, timeout_sec: float) -> bool: ...
    def follow_route(self, route_id: str, timeout_sec: float) -> bool: ...
    def rotate_to(self, target_id: str, timeout_sec: float) -> bool: ...
    def aim_at(self, target_id: str, timeout_sec: float) -> bool: ...
    def interact(self, target_id: str) -> bool: ...
    def open_menu(self, menu_name: str) -> bool: ...
    def close_menu(self, menu_name: Optional[str] = None) -> bool: ...
    def scroll_menu(self, menu_name: str, direction: str, amount: int = 1) -> bool: ...
    def click_button(self, button_id: str) -> bool: ...
    def talk_to_npc(self, npc_id: str) -> bool: ...
    def advance_dialogue(self) -> bool: ...
    def attack_sword(self, target_id: Optional[str] = None, combo: int = 1) -> bool: ...
    def attack_bow(self, target_id: Optional[str] = None, charged: bool = False) -> bool: ...
    def cast_magic(self, spell_id: str, target_id: Optional[str] = None) -> bool: ...
    def equip_item(self, item_id: str) -> bool: ...
    def unequip_item(self, item_id: str) -> bool: ...
    def mount(self, mount_id: Optional[str] = None) -> bool: ...
    def dismount(self) -> bool: ...
    def swim_to(self, target_id: str, timeout_sec: float) -> bool: ...
    def fly_to(self, target_id: str, timeout_sec: float) -> bool: ...
    def teleport(self, target_id: str) -> bool: ...
    def transition_location(self, transition_id: str) -> bool: ...
    def trigger_cutscene(self, cutscene_id: str) -> bool: ...
    def save_game(self, slot: str) -> bool: ...
    def load_game(self, slot: str) -> bool: ...
    def kill_player(self) -> bool: ...
    def respawn_player(self) -> bool: ...
    def wait(self, seconds: float) -> None: ...
    def stop_all_input(self) -> None: ...
    def spam_input(self, inputs: List[str], duration_sec: float) -> bool: ...
    def interrupt_current_action(self) -> bool: ...
    def reset_to_checkpoint(self, checkpoint_id: str) -> bool: ...
    def query_distance_to(self, target_id: str) -> float: ...
    def is_prompt_visible(self, prompt_name: str) -> bool: ...
    def is_object_visible(self, target_id: str) -> bool: ...
    def did_particle_play(self, particle_id: Optional[str] = None) -> bool: ...
    def did_hit_connect(self, target_id: Optional[str] = None) -> bool: ...
    def did_projectile_spawn(self) -> bool: ...
    def did_damage_apply(self, target_id: Optional[str] = None) -> bool: ...
    def did_magic_effect_apply(self, spell_id: str, target_id: Optional[str] = None) -> bool: ...
    def is_cutscene_playing(self) -> bool: ...
    def is_loading_screen_visible(self) -> bool: ...
    def is_scene_ready(self) -> bool: ...
    def get_route_progress(self, route_id: str) -> float: ...
    def get_companion_snapshot(self) -> Dict[str, Any]: ...
    def log(self, message: str) -> None: ...
    def run_video_scenario(self, scenario_name: str, scenario_file: str, params: Dict[str, Any]) -> bool: ...


# ============================================================
# Utilities
# ============================================================


class JsonScenarioLoader:
    @staticmethod
    def load_file(path: str) -> List[Scenario]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        scenarios: List[Scenario] = []
        for raw_scenario in data["scenarios"]:
            steps: List[ScenarioStep] = []
            for step in raw_scenario["steps"]:
                steps.append(
                    ScenarioStep(
                        name=step["name"],
                        action=ActionType(step["action"]),
                        target=step.get("target"),
                        route=step.get("route"),
                        menu=step.get("menu"),
                        button=step.get("button"),
                        item=step.get("item"),
                        spell=step.get("spell"),
                        params=step.get("params", {}),
                        expected=step.get("expected", {}),
                        timeout_sec=float(step.get("timeout_sec", 8.0)),
                        retries=max(1, int(step.get("retries", 1))),
                        checkpoint=step.get("checkpoint"),
                    )
                )
            scenarios.append(Scenario(name=raw_scenario["name"], steps=steps, tags=raw_scenario.get("tags", [])))
        return scenarios


def is_truthy_failure(value: Any) -> bool:
    """Normalize evidence values to booleans for failure aggregation."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "0", "false", "no", "none", "pass", "ok"}:
            return False
        if normalized in {"1", "true", "yes", "fail", "failed", "error"}:
            return True
        return True
    if isinstance(value, dict):
        mapping = cast(Dict[str, Any], value)
        return bool(mapping)
    if isinstance(value, (list, tuple, set)):
        collection = cast(List[Any] | Tuple[Any, ...] | set[Any], value)
        return bool(collection)
    return bool(value)


class BugClassifier:
    @staticmethod
    def classify(step: ScenarioStep, state_before: WorldState, state_after: WorldState, evidence: Dict[str, Any]) -> BugType:
        if is_truthy_failure(evidence.get("loading_failed")):
            return BugType.LOADING_BUG
        if is_truthy_failure(evidence.get("cutscene_failed")):
            return BugType.CUTSCENE_BUG
        if is_truthy_failure(evidence.get("companion_failed")):
            return BugType.COMPANION_BUG
        if is_truthy_failure(evidence.get("persistence_failed")):
            return BugType.PERSISTENCE_BUG
        if is_truthy_failure(evidence.get("input_failed")):
            return BugType.INPUT_BUG
        if is_truthy_failure(evidence.get("route_failed")):
            return BugType.ROUTE_BUG
        if is_truthy_failure(evidence.get("interaction_failed")):
            return BugType.INTERACTION_BUG
        if is_truthy_failure(evidence.get("animation_failed")):
            return BugType.ANIMATION_BUG
        if is_truthy_failure(evidence.get("combat_failed")):
            return BugType.COMBAT_BUG
        if is_truthy_failure(evidence.get("magic_failed")):
            return BugType.MAGIC_BUG
        if is_truthy_failure(evidence.get("particle_failed")):
            return BugType.PARTICLE_BUG
        if is_truthy_failure(evidence.get("equipment_failed")):
            return BugType.EQUIPMENT_BUG
        if is_truthy_failure(evidence.get("performance_failed")):
            return BugType.PERFORMANCE_BUG
        if is_truthy_failure(evidence.get("visual_failed")) and not is_truthy_failure(evidence.get("state_failed")):
            return BugType.VISUAL_DESYNC
        if is_truthy_failure(evidence.get("state_failed")) and is_truthy_failure(evidence.get("visual_failed")):
            return BugType.FALSE_POSITIVE_STATE
        if is_truthy_failure(evidence.get("physics_failed")):
            return BugType.PHYSICS_DESYNC
        if is_truthy_failure(evidence.get("transition_failed")):
            return BugType.TRANSITION_BUG
        if is_truthy_failure(evidence.get("edge_case_failed")):
            return BugType.EDGE_CASE_BUG
        if is_truthy_failure(evidence.get("ui_failed")):
            return BugType.UI_BUG
        return BugType.UNKNOWN if any(is_truthy_failure(v) for v in evidence.values()) else BugType.NONE


class Storage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blob_dir = self.root / "blobs"
        self.blob_dir.mkdir(exist_ok=True)
        self.db_path = self.root / "qa.sqlite3"
        self._init_db()

    @staticmethod
    def _sanitize_blob_name(value: str) -> str:
        safe: List[str] = []
        for ch in str(value):
            if ch.isalnum() or ch in {"_", "-", "."}:
                safe.append(ch)
            else:
                safe.append("_")
        sanitized = "".join(safe).strip("._")
        return sanitized or "step"

    def _init_db(self) -> None:
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS step_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_name TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                step_name TEXT NOT NULL,
                action TEXT NOT NULL,
                verdict TEXT NOT NULL,
                bug_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL NOT NULL,
                duration_sec REAL NOT NULL,
                blob_path TEXT NOT NULL,
                fps REAL NOT NULL,
                frame_time_ms REAL NOT NULL,
                draw_calls INTEGER NOT NULL,
                triangles INTEGER NOT NULL,
                instances INTEGER NOT NULL
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_bug_type ON step_results (bug_type)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_verdict ON step_results (verdict)")
        self.conn.commit()

    def save_step_result(self, result: StepResult) -> None:
        blob_name = self._sanitize_blob_name(
            f"{result.scenario_name}_{result.step_index:04d}_{result.step_name}".replace(" ", "_")
        )
        payload: Dict[str, Any] = asdict(result)

        if msgpack is not None:
            blob_path = self.blob_dir / f"{blob_name}.msgpack"
            with open(blob_path, "wb") as f:
                packed = _pack_msgpack(payload)
                f.write(packed)
        else:
            blob_path = self.blob_dir / f"{blob_name}.json"
            with open(blob_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

        self.conn.execute(
            """
            INSERT INTO step_results (
                scenario_name, step_index, step_name, action, verdict, bug_type, reason,
                started_at, finished_at, duration_sec, blob_path,
                fps, frame_time_ms, draw_calls, triangles, instances
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.scenario_name,
                result.step_index,
                result.step_name,
                result.action,
                result.verdict.value,
                result.bug_type.value,
                result.reason,
                result.started_at,
                result.finished_at,
                result.duration_sec,
                str(blob_path),
                result.perf.fps,
                result.perf.frame_time_ms,
                result.perf.draw_calls,
                result.perf.triangles,
                result.perf.instances,
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


class HTMLReportWriter:
    def __init__(self, out_dir: str):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def write(self, results: List[StepResult]) -> str:
        report_path = self.out_dir / "report.html"
        rows: List[str] = []
        rows.append("<html><head><meta charset='utf-8'><title>QA Report</title>")
        rows.append(
            "<style>body{font-family:Arial;background:#111;color:#eee;padding:20px}.card{background:#1c1c1c;padding:16px;border-radius:12px;margin:12px 0}.pass{color:#6f6}.warn{color:#fd5}.fail{color:#f66}img{max-width:320px;margin-right:10px;border:1px solid #333}pre{white-space:pre-wrap;background:#0d0d0d;padding:12px;border-radius:8px}</style>"
        )
        rows.append("</head><body><h1>Autonomous QA Report</h1>")

        total = len(results)
        failed = sum(1 for r in results if r.verdict == Verdict.FAIL)
        warned = sum(1 for r in results if r.verdict == Verdict.WARN)
        rows.append(f"<div class='card'><b>Total steps:</b> {total}<br><b>Failed:</b> {failed}<br><b>Warnings:</b> {warned}</div>")

        for r in results:
            rows.append(f"<div class='card'><h2 class='{r.verdict.value}'>{r.scenario_name} :: {r.step_index} :: {r.step_name} :: {r.verdict.value}</h2>")
            rows.append(f"<p><b>Action:</b> {r.action} | <b>Bug:</b> {r.bug_type.value}</p>")
            rows.append(f"<p><b>Reason:</b> {r.reason or '-'} </p>")
            rows.append("<pre>" + json.dumps({
                "duration_sec": r.duration_sec,
                "perf": asdict(r.perf),
                "evidence": r.evidence,
            }, ensure_ascii=False, indent=2) + "</pre>")
            if r.screenshots:
                rows.append("<div>")
                for shot in r.screenshots:
                    rel = os.path.relpath(shot.path, self.out_dir).replace("\\", "/")
                    rows.append(f"<figure style='display:inline-block'><img src='{rel}'><figcaption>{shot.label}</figcaption></figure>")
                rows.append("</div>")
            rows.append("</div>")

        rows.append("</body></html>")
        report_path.write_text("\n".join(rows), encoding="utf-8")
        return str(report_path)


class MarkdownReportWriter:
    def __init__(self, out_dir: str):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def write(self, results: List[StepResult]) -> str:
        report_path = self.out_dir / "report.md"
        lines: List[str] = []
        total = len(results)
        failed = sum(1 for r in results if r.verdict == Verdict.FAIL)
        warned = sum(1 for r in results if r.verdict == Verdict.WARN)

        lines.append("# Autonomous QA Report")
        lines.append("")
        lines.append(f"- Total steps: {total}")
        lines.append(f"- Failed: {failed}")
        lines.append(f"- Warnings: {warned}")
        lines.append("")

        for r in results:
            lines.append(f"## {r.scenario_name} :: {r.step_index} :: {r.step_name}")
            lines.append("")
            lines.append(f"- Verdict: `{r.verdict.value}`")
            lines.append(f"- Action: `{r.action}`")
            lines.append(f"- Bug type: `{r.bug_type.value}`")
            lines.append(f"- Reason: {r.reason or '-'}")
            lines.append(f"- Duration: `{r.duration_sec:.3f}s`")
            lines.append(
                f"- Perf: fps=`{r.perf.fps}` draw_calls=`{r.perf.draw_calls}` frame_time_ms=`{r.perf.frame_time_ms}`"
            )
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps({
                "perf": asdict(r.perf),
                "evidence": r.evidence,
            }, ensure_ascii=False, indent=2))
            lines.append("```")
            if r.screenshots:
                lines.append("")
                lines.append("Screenshots:")
                for shot in r.screenshots:
                    rel = os.path.relpath(shot.path, self.out_dir).replace("\\", "/")
                    lines.append(f"- `{shot.label}`: `{rel}`")
            lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        return str(report_path)


# ============================================================
# Validators
# ============================================================


class Validators:
    @staticmethod
    def validate_perf(perf: PerfMetrics, max_draw_calls: int = 200, min_fps: float = 30.0) -> Dict[str, Any]:
        return {
            "performance_failed": perf.draw_calls > max_draw_calls or perf.fps < min_fps,
            "draw_calls": perf.draw_calls,
            "fps": perf.fps,
        }

    @staticmethod
    def validate_route(adapter: GameAdapter, route_id: str) -> Dict[str, Any]:
        progress = adapter.get_route_progress(route_id)
        return {
            "route_failed": progress < 0.99,
            "route_progress": progress,
        }

    @staticmethod
    def validate_loading(adapter: GameAdapter, timeout_sec: float = 12.0) -> Dict[str, Any]:
        start = time.time()
        saw_loading = False
        while time.time() - start < timeout_sec:
            if adapter.is_loading_screen_visible():
                saw_loading = True
            if saw_loading and adapter.is_scene_ready() and not adapter.is_loading_screen_visible():
                return {"loading_failed": False, "loading_seen": True}
            adapter.wait(0.1)
        return {"loading_failed": True, "loading_seen": saw_loading}

    @staticmethod
    def validate_cutscene(adapter: GameAdapter, timeout_sec: float = 15.0) -> Dict[str, Any]:
        start = time.time()
        saw_cutscene = False
        while time.time() - start < timeout_sec:
            state = adapter.get_state()
            if adapter.is_cutscene_playing():
                saw_cutscene = True
                if state.input_enabled and not state.control_locked:
                    return {"cutscene_failed": True, "reason": "Player retained control during cutscene"}
            if saw_cutscene and not adapter.is_cutscene_playing():
                post = adapter.get_state()
                if post.control_locked:
                    return {"cutscene_failed": True, "reason": "Control not restored after cutscene"}
                return {"cutscene_failed": False, "cutscene_seen": True}
            adapter.wait(0.1)
        return {"cutscene_failed": True, "reason": "Cutscene timeout or never ended"}

    @staticmethod
    def validate_companion(adapter: GameAdapter) -> Dict[str, Any]:
        snap = adapter.get_companion_snapshot()
        failed = False
        reason = ""
        if not snap:
            failed = True
            reason = "No companion snapshot"
        elif snap.get("stuck"):
            failed = True
            reason = "Companion stuck"
        elif snap.get("distance_to_player", 0.0) > snap.get("max_expected_distance", 8.0):
            failed = True
            reason = "Companion too far from player"
        elif snap.get("movement_desync"):
            failed = True
            reason = "Companion animation or movement desync"
        return {"companion_failed": failed, "companion_reason": reason, "companion_snapshot": snap}

    @staticmethod
    def validate_persistence(before: WorldState, after: WorldState, allowed_changes: Optional[List[str]] = None) -> Dict[str, Any]:
        allowed_changes = allowed_changes or []
        failures: List[str] = []

        def check(name: str, a: Any, b: Any) -> None:
            if name not in allowed_changes and a != b:
                failures.append(name)

        check("scene_name", before.scene_name, after.scene_name)
        check("equipment_state", before.equipment_state, after.equipment_state)
        check("object_states", before.object_states, after.object_states)
        check("current_effects", before.current_effects, after.current_effects)
        return {"persistence_failed": bool(failures), "persistence_mismatches": failures}

    @staticmethod
    def validate_animation(before: WorldState, after: WorldState, expected_animation: Optional[str] = None) -> Dict[str, Any]:
        failed = False
        if expected_animation and after.current_animation != expected_animation:
            failed = True
        if before.current_animation == after.current_animation and expected_animation:
            failed = True
        return {
            "animation_failed": failed,
            "animation_before": before.current_animation,
            "animation_after": after.current_animation,
            "expected_animation": expected_animation,
        }

    @staticmethod
    def validate_magic(adapter: GameAdapter, spell_id: str, target_id: Optional[str]) -> Dict[str, Any]:
        effect_applied = adapter.did_magic_effect_apply(spell_id, target_id)
        particle_ok = adapter.did_particle_play(None)
        return {
            "magic_failed": not effect_applied,
            "particle_failed": not particle_ok,
            "magic_effect_applied": effect_applied,
            "particle_seen": particle_ok,
        }

    @staticmethod
    def validate_melee(adapter: GameAdapter, target_id: Optional[str]) -> Dict[str, Any]:
        hit = adapter.did_hit_connect(target_id)
        dmg = adapter.did_damage_apply(target_id)
        return {"combat_failed": not (hit and dmg), "hit_connected": hit, "damage_applied": dmg}

    @staticmethod
    def validate_bow(adapter: GameAdapter, target_id: Optional[str]) -> Dict[str, Any]:
        projectile = adapter.did_projectile_spawn()
        dmg = adapter.did_damage_apply(target_id)
        return {"combat_failed": not (projectile and dmg), "projectile_spawned": projectile, "damage_applied": dmg}

    @staticmethod
    def validate_equipment(before: WorldState, after: WorldState, item_id: str) -> Dict[str, Any]:
        failed = item_id not in str(after.equipment_state)
        return {"equipment_failed": failed, "equipment_before": before.equipment_state, "equipment_after": after.equipment_state}

    @staticmethod
    def validate_input_stress(adapter: GameAdapter, expected_recovery_sec: float = 2.0) -> Dict[str, Any]:
        start = time.time()
        while time.time() - start < expected_recovery_sec:
            state = adapter.get_state()
            if state.input_enabled and not state.control_locked:
                return {"input_failed": False}
            adapter.wait(0.1)
        return {"input_failed": True, "reason": "Input not recovered after stress"}


# ============================================================
# Step executor
# ============================================================


class StepExecutor:
    def __init__(self, adapter: GameAdapter):
        self.adapter = adapter

    def execute(self, step: ScenarioStep) -> Tuple[bool, Dict[str, Any]]:
        action = step.action
        params = step.params
        evidence: Dict[str, Any] = {}

        if action == ActionType.MOVE_TO:
            ok = self.adapter.move_to_target(step.target or "", step.timeout_sec)
            if step.target:
                evidence["distance_after_move"] = self.adapter.query_distance_to(step.target)
            return ok, evidence

        if action == ActionType.MOVE_ROUTE:
            ok = self.adapter.follow_route(step.route or "", step.timeout_sec)
            if step.route:
                evidence.update(Validators.validate_route(self.adapter, step.route))
            return ok, evidence

        if action == ActionType.ROTATE_TO:
            return self.adapter.rotate_to(step.target or "", step.timeout_sec), evidence

        if action == ActionType.AIM_AT:
            return self.adapter.aim_at(step.target or "", step.timeout_sec), evidence

        if action == ActionType.INTERACT:
            ok = self.adapter.interact(step.target or "")
            evidence["interaction_failed"] = not ok
            return ok, evidence

        if action == ActionType.OPEN_MENU:
            ok = self.adapter.open_menu(step.menu or "")
            evidence["ui_failed"] = not ok
            return ok, evidence

        if action == ActionType.CLOSE_MENU:
            ok = self.adapter.close_menu(step.menu)
            evidence["ui_failed"] = not ok
            return ok, evidence

        if action == ActionType.SCROLL_MENU:
            ok = self.adapter.scroll_menu(step.menu or "", params.get("direction", "down"), int(params.get("amount", 1)))
            evidence["ui_failed"] = not ok
            return ok, evidence

        if action == ActionType.CLICK_BUTTON:
            ok = self.adapter.click_button(step.button or "")
            evidence["ui_failed"] = not ok
            return ok, evidence

        if action == ActionType.TALK_TO_NPC:
            ok = self.adapter.talk_to_npc(step.target or "")
            evidence["interaction_failed"] = not ok
            return ok, evidence

        if action == ActionType.ADVANCE_DIALOGUE:
            ok = self.adapter.advance_dialogue()
            evidence["interaction_failed"] = not ok
            return ok, evidence

        if action == ActionType.ATTACK_SWORD:
            ok = self.adapter.attack_sword(step.target, int(params.get("combo", 1)))
            evidence.update(Validators.validate_melee(self.adapter, step.target))
            return ok and not evidence["combat_failed"], evidence

        if action == ActionType.ATTACK_BOW:
            ok = self.adapter.attack_bow(step.target, bool(params.get("charged", False)))
            evidence.update(Validators.validate_bow(self.adapter, step.target))
            return ok and not evidence["combat_failed"], evidence

        if action == ActionType.CAST_MAGIC:
            ok = self.adapter.cast_magic(step.spell or "", step.target)
            evidence.update(Validators.validate_magic(self.adapter, spell_id=step.spell or "", target_id=step.target))
            return ok and not evidence["magic_failed"], evidence

        if action == ActionType.EQUIP_ITEM:
            ok = self.adapter.equip_item(step.item or "")
            evidence["equipment_failed"] = not ok
            return ok, evidence

        if action == ActionType.UNEQUIP_ITEM:
            ok = self.adapter.unequip_item(step.item or "")
            evidence["equipment_failed"] = not ok
            return ok, evidence

        if action == ActionType.CHECK_PARTICLES:
            seen = self.adapter.did_particle_play(params.get("particle_id"))
            evidence["particle_failed"] = not seen
            return seen, evidence

        if action == ActionType.MOUNT:
            ok = self.adapter.mount(step.target)
            evidence["transition_failed"] = not ok
            return ok, evidence

        if action == ActionType.DISMOUNT:
            ok = self.adapter.dismount()
            evidence["transition_failed"] = not ok
            return ok, evidence

        if action == ActionType.SWIM_TO:
            ok = self.adapter.swim_to(step.target or "", step.timeout_sec)
            evidence["transition_failed"] = not ok
            return ok, evidence

        if action == ActionType.FLY_TO:
            ok = self.adapter.fly_to(step.target or "", step.timeout_sec)
            evidence["transition_failed"] = not ok
            return ok, evidence

        if action == ActionType.TELEPORT:
            ok = self.adapter.teleport(step.target or "")
            evidence.update(Validators.validate_loading(self.adapter, timeout_sec=step.timeout_sec))
            evidence["transition_failed"] = (not ok) or is_truthy_failure(evidence.get("loading_failed"))
            return ok and not evidence["transition_failed"], evidence

        if action == ActionType.TRANSITION_LOCATION:
            ok = self.adapter.transition_location(step.target or "")
            evidence.update(Validators.validate_loading(self.adapter, timeout_sec=step.timeout_sec))
            evidence["transition_failed"] = (not ok) or is_truthy_failure(evidence.get("loading_failed"))
            return ok and not evidence["transition_failed"], evidence

        if action == ActionType.CHECK_CUTSCENE:
            ok = self.adapter.trigger_cutscene(step.target or "")
            evidence.update(Validators.validate_cutscene(self.adapter, timeout_sec=step.timeout_sec))
            return ok and not is_truthy_failure(evidence.get("cutscene_failed")), evidence

        if action == ActionType.CHECK_LOADING:
            evidence.update(Validators.validate_loading(self.adapter, timeout_sec=step.timeout_sec))
            return not is_truthy_failure(evidence.get("loading_failed")), evidence

        if action == ActionType.CHECK_COMPANION:
            evidence.update(Validators.validate_companion(self.adapter))
            return not is_truthy_failure(evidence.get("companion_failed")), evidence

        if action == ActionType.SAVE_GAME:
            ok = self.adapter.save_game(params.get("slot", "autoslot"))
            return ok, evidence

        if action == ActionType.LOAD_GAME:
            ok = self.adapter.load_game(params.get("slot", "autoslot"))
            evidence.update(Validators.validate_loading(self.adapter, timeout_sec=step.timeout_sec))
            return ok and not is_truthy_failure(evidence.get("loading_failed")), evidence

        if action == ActionType.DIE_AND_RESPAWN:
            ok = self.adapter.kill_player()
            if ok:
                self.adapter.wait(float(params.get("death_wait_sec", 1.5)))
                ok = self.adapter.respawn_player()
            evidence.update(Validators.validate_loading(self.adapter, timeout_sec=step.timeout_sec))
            return ok and not is_truthy_failure(evidence.get("loading_failed")), evidence

        if action == ActionType.ASSERT_STATE:
            state = self.adapter.get_state()
            expected = step.expected
            failed = False
            mismatches: Dict[str, Any] = {}
            for key, value in expected.items():
                current = getattr(state, key, state.misc.get(key))
                if current != value:
                    mismatches[key] = {"expected": value, "actual": current}
                    failed = True
            evidence["state_failed"] = failed
            evidence["state_mismatches"] = mismatches
            return not failed, evidence

        if action == ActionType.WAIT:
            self.adapter.wait(float(params.get("seconds", 1.0)))
            return True, evidence

        if action == ActionType.INPUT_STRESS:
            inputs = list(params.get("inputs", ["attack", "jump", "menu", "interact"]))
            ok = self.adapter.spam_input(inputs, float(params.get("duration_sec", 1.0)))
            evidence.update(Validators.validate_input_stress(self.adapter))
            return ok and not is_truthy_failure(evidence.get("input_failed")), evidence

        if action == ActionType.EDGE_CASE:
            ok = self.adapter.spam_input(list(params.get("inputs", ["attack", "interact", "menu"])), float(params.get("duration_sec", 1.0)))
            self.adapter.interrupt_current_action()
            stress = Validators.validate_input_stress(self.adapter)
            evidence.update(stress)
            evidence["edge_case_failed"] = is_truthy_failure(stress.get("input_failed"))
            return ok and not evidence["edge_case_failed"], evidence

        if action == ActionType.RUN_VIDEO_SCENARIO:
            scenario_name = str(params.get("scenario_name", "") or step.name)
            scenario_file = str(params.get("scenario_file", "") or "")
            ok = self.adapter.run_video_scenario(scenario_name, scenario_file, params)
            evidence["video_scenario_name"] = scenario_name
            evidence["video_scenario_file"] = scenario_file
            evidence["video_scenario_ok"] = ok
            return ok, evidence

        return False, {"reason": f"Unsupported action: {action.value}"}


# ============================================================
# Logger without background thread
# ============================================================


class RunnerLogger:
    def __init__(self, out_dir: Path, log_callback: Optional[Callable[[str], None]] = None):
        self.log_file = out_dir / "runner.log"
        out_dir.mkdir(parents=True, exist_ok=True)
        self.log_callback = log_callback

    def write(self, line: str) -> None:
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if self.log_callback:
            self.log_callback(line)


# ============================================================
# Autonomous runner
# ============================================================


class AutonomousQARunner:
    def __init__(
        self,
        adapter: GameAdapter,
        scenarios: List[Scenario],
        output_dir: str,
        hours: Optional[float] = None,
        random_edge_case_chance: float = 0.15,
        stop_on_fail: bool = False,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.adapter = adapter
        self.scenarios = scenarios
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.hours = hours
        self.random_edge_case_chance = random_edge_case_chance
        self.stop_on_fail = stop_on_fail
        self.executor = StepExecutor(adapter)
        self.storage = Storage(str(self.output_dir))
        self.reporter = HTMLReportWriter(str(self.output_dir))
        self.markdown_reporter = MarkdownReportWriter(str(self.output_dir))
        self.results: List[StepResult] = []
        self.logger = RunnerLogger(self.output_dir, log_callback=log_callback)

    def log(self, message: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {message}"
        self.logger.write(line)
        self.adapter.log(line)

    def run(self) -> Dict[str, Any]:
        start = time.time()
        deadline = start + self.hours * 3600 if self.hours else None

        try:
            while True:
                for scenario in self.scenarios:
                    self.log(f"RUN scenario={scenario.name}")
                    self._run_scenario(scenario)
                    recent = self.results[-len(scenario.steps):] if scenario.steps else []
                    if self.stop_on_fail and any(r.verdict == Verdict.FAIL for r in recent):
                        raise RuntimeError("Stopped on fail")
                    if deadline and time.time() >= deadline:
                        return self._finalize(start)
                if deadline is None:
                    break
        finally:
            self.storage.close()

        return self._finalize(start)

    def _run_scenario(self, scenario: Scenario) -> None:
        for index, step in enumerate(scenario.steps):
            result = self._run_step(scenario, index, step)
            self.results.append(result)
            self.storage.save_step_result(result)
            self.log(f"STEP {scenario.name}::{index}::{step.name} => {result.verdict.value} / {result.bug_type.value} / {result.reason}")
            if self.stop_on_fail and result.verdict == Verdict.FAIL:
                return
            if random.random() < self.random_edge_case_chance:
                edge_step = ScenarioStep(
                    name="auto_edge_case",
                    action=ActionType.EDGE_CASE,
                    params={"duration_sec": 1.2, "inputs": ["attack", "interact", "menu", "jump"]},
                    timeout_sec=3.0,
                    retries=1,
                )
                edge_result = self._run_step(scenario, index + 100000, edge_step)
                self.results.append(edge_result)
                self.storage.save_step_result(edge_result)

    def _run_step(self, scenario: Scenario, step_index: int, step: ScenarioStep) -> StepResult:
        out_dir = self.output_dir / "screenshots" / scenario.name / f"{step_index:04d}_{step.name}"
        out_dir.mkdir(parents=True, exist_ok=True)

        started = time.time()
        before = self.adapter.get_state()
        screenshots = [ScreenshotArtifact("before", self.adapter.capture_screenshot("before", str(out_dir)))]
        attempts = 0
        final_ok = False
        evidence: Dict[str, Any] = {}
        reason = ""

        for attempts in range(1, step.retries + 1):
            ok, raw_evidence = self.executor.execute(step)
            evidence.update(raw_evidence)

            after = self.adapter.get_state()
            perf = self.adapter.get_perf_metrics()
            evidence.update(Validators.validate_perf(perf))

            if step.action == ActionType.LOAD_GAME:
                evidence.update(Validators.validate_persistence(before, after, allowed_changes=["scene_name", "player_pos"]))
            elif step.action == ActionType.TELEPORT:
                evidence.update(Validators.validate_persistence(before, after, allowed_changes=["scene_name", "player_pos"]))
            elif step.action == ActionType.DIE_AND_RESPAWN:
                evidence.update(Validators.validate_persistence(before, after, allowed_changes=["player_pos", "current_effects"]))
            elif step.action == ActionType.EQUIP_ITEM and step.item:
                evidence.update(Validators.validate_equipment(before, after, step.item))

            expected_animation = step.expected.get("animation") if step.expected else None
            if expected_animation:
                evidence.update(Validators.validate_animation(before, after, expected_animation))

            expected_scene = step.expected.get("scene_name") if step.expected else None
            if expected_scene and after.scene_name != expected_scene:
                evidence["transition_failed"] = True
                reason = f"Expected scene {expected_scene}, got {after.scene_name}"

            expected_ui = step.expected.get("ui_contains") if step.expected else None
            if expected_ui and expected_ui not in after.ui_stack:
                evidence["ui_failed"] = True
                reason = reason or f"UI missing expected entry {expected_ui}"

            expected_distance_lte = step.expected.get("distance_lte") if step.expected else None
            if expected_distance_lte is not None and step.target:
                dist = self.adapter.query_distance_to(step.target)
                evidence["distance_value"] = dist
                if dist > float(expected_distance_lte):
                    evidence["route_failed"] = True
                    reason = reason or f"Distance check failed: {dist:.2f} > {expected_distance_lte}"

            visual_required = bool(step.expected.get("visible_target")) if step.expected else False
            if visual_required and step.target and not self.adapter.is_object_visible(step.target):
                evidence["visual_failed"] = True
                reason = reason or f"Target not visible: {step.target}"

            state_failed = is_truthy_failure(evidence.get("state_failed"))
            visual_failed = is_truthy_failure(evidence.get("visual_failed"))
            hard_failed = any(
                is_truthy_failure(evidence.get(key, False))
                for key in (
                    "loading_failed",
                    "cutscene_failed",
                    "companion_failed",
                    "persistence_failed",
                    "input_failed",
                    "route_failed",
                    "interaction_failed",
                    "animation_failed",
                    "combat_failed",
                    "magic_failed",
                    "particle_failed",
                    "equipment_failed",
                    "physics_failed",
                    "transition_failed",
                    "edge_case_failed",
                    "ui_failed",
                )
            )
            false_positive = state_failed and visual_failed
            if false_positive:
                evidence["false_positive_state"] = True

            if ok and not hard_failed and not false_positive:
                final_ok = True
                break

            if attempts < step.retries:
                self.log(f"RETRY {scenario.name}::{step.name} attempt={attempts}")
                self._recover(step)

        after = self.adapter.get_state()
        screenshots.append(ScreenshotArtifact("after", self.adapter.capture_screenshot("after", str(out_dir))))
        finished = time.time()
        perf = self.adapter.get_perf_metrics()

        bug_type = BugClassifier.classify(step, before, after, evidence)
        if final_ok:
            verdict = Verdict.WARN if is_truthy_failure(evidence.get("performance_failed")) else Verdict.PASS
        else:
            verdict = Verdict.FAIL
            if not reason:
                reason = self._reason_from_evidence(evidence)

        return StepResult(
            scenario_name=scenario.name,
            step_index=step_index,
            step_name=step.name,
            action=step.action.value,
            verdict=verdict,
            bug_type=bug_type,
            reason=reason,
            started_at=started,
            finished_at=finished,
            duration_sec=finished - started,
            attempts=attempts,
            pre_state=asdict(before),
            post_state=asdict(after),
            perf=perf,
            screenshots=screenshots,
            evidence=evidence,
        )

    def _recover(self, step: ScenarioStep) -> None:
        self.adapter.stop_all_input()
        self.adapter.wait(0.2)
        if step.checkpoint:
            self.adapter.reset_to_checkpoint(step.checkpoint)
        else:
            self.adapter.interrupt_current_action()
            self.adapter.wait(0.3)

    def _reason_from_evidence(self, evidence: Dict[str, Any]) -> str:
        ordered = [
            "loading_failed",
            "cutscene_failed",
            "companion_failed",
            "persistence_failed",
            "input_failed",
            "route_failed",
            "interaction_failed",
            "animation_failed",
            "combat_failed",
            "magic_failed",
            "particle_failed",
            "equipment_failed",
            "transition_failed",
            "performance_failed",
            "ui_failed",
            "visual_failed",
            "state_failed",
            "edge_case_failed",
        ]
        for key in ordered:
            if is_truthy_failure(evidence.get(key)):
                return key
        return str(evidence.get("reason", "step_failed"))

    def _finalize(self, start_time: float) -> Dict[str, Any]:
        report = self.reporter.write(self.results)
        markdown_report = self.markdown_reporter.write(self.results)
        total = len(self.results)
        failed = sum(1 for r in self.results if r.verdict == Verdict.FAIL)
        warned = sum(1 for r in self.results if r.verdict == Verdict.WARN)
        avg_fps = sum(r.perf.fps for r in self.results) / total if total else 0.0
        avg_draw_calls = sum(r.perf.draw_calls for r in self.results) / total if total else 0.0

        summary: Dict[str, Any] = {
            "started_at": start_time,
            "finished_at": time.time(),
            "total_steps": total,
            "failed_steps": failed,
            "warned_steps": warned,
            "avg_fps": avg_fps,
            "avg_draw_calls": avg_draw_calls,
            "report_path": report,
            "report_md_path": markdown_report,
            "output_dir": str(self.output_dir),
            "top_bug_types": self._top_bug_types(),
        }
        with open(self.output_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return summary

    def _top_bug_types(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            if r.bug_type != BugType.NONE:
                counts[r.bug_type.value] = counts.get(r.bug_type.value, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


# ============================================================
# Example scenario builder
# ============================================================


def build_default_scenarios() -> List[Scenario]:
    '''Build a baseline set of scenarios for smoke testing and regression.'''
    return [
        Scenario(
            name="smoke_test",
            steps=[
                ScenarioStep(name="init", action=ActionType.WAIT, timeout_sec=2.0),
                ScenarioStep(name="check_state", action=ActionType.ASSERT_STATE, expected={"input_enabled": True}),
            ],
            tags=["smoke", "core"],
        ),
        Scenario(
            name="inventory_workflow",
            steps=[
                ScenarioStep(name="open_inventory", action=ActionType.OPEN_MENU, menu="inventory"),
                ScenarioStep(name="wait_anim", action=ActionType.WAIT, timeout_sec=0.5),
                ScenarioStep(name="select_item", action=ActionType.SCROLL_MENU, params={"index": 0}),
                ScenarioStep(name="equip_item", action=ActionType.EQUIP_ITEM, params={"slot": "main_hand"}),
                ScenarioStep(name="close_inventory", action=ActionType.CLOSE_MENU, menu="inventory"),
                ScenarioStep(name="check_equipped", action=ActionType.ASSERT_STATE, expected={"equipment_state": {"main_hand": True}}),
            ],
            tags=["interaction", "workflow", "inventory"],
        ),
        Scenario(
            name="npc_interaction",
            steps=[
                ScenarioStep(name="find_npc", action=ActionType.MOVE_TO, target="npc_merchant"),
                ScenarioStep(name="face_npc", action=ActionType.ROTATE_TO, target="npc_merchant"),
                ScenarioStep(name="start_talk", action=ActionType.TALK_TO_NPC, target="npc_merchant"),
                ScenarioStep(name="wait_ui", action=ActionType.WAIT, timeout_sec=1.0),
                ScenarioStep(name="next_line", action=ActionType.ADVANCE_DIALOGUE),
                ScenarioStep(name="end_talk", action=ActionType.CLOSE_MENU, menu="dialogue"),
            ],
            tags=["interaction", "workflow", "npc"],
        ),
        Scenario(
            name="prop_toggle",
            steps=[
                ScenarioStep(name="approach_chest", action=ActionType.MOVE_TO, target="prop_chest_gold"),
                ScenarioStep(name="open_chest", action=ActionType.INTERACT, target="prop_chest_gold"),
                ScenarioStep(name="wait_vfx", action=ActionType.WAIT, timeout_sec=1.5),
                ScenarioStep(name="close_chest", action=ActionType.INTERACT, target="prop_chest_gold"),
            ],
            tags=["interaction", "workflow", "prop"],
        ),
        Scenario(
            name="town_smoke_run",
            tags=["smoke", "navigation", "ui", "interaction"],
            steps=[
                ScenarioStep(
                    name="route_market",
                    action=ActionType.MOVE_ROUTE,
                    route="market_route",
                    expected={"distance_lte": 1.5},
                    timeout_sec=20.0,
                    retries=2,
                    checkpoint="market_start",
                ),
                ScenarioStep(
                    name="open_main_menu",
                    action=ActionType.OPEN_MENU,
                    menu="main_menu",
                    expected={"ui_contains": "main_menu"},
                    retries=2,
                ),
                ScenarioStep(name="close_main_menu", action=ActionType.CLOSE_MENU, menu="main_menu", retries=2),
                ScenarioStep(
                    name="open_town_door",
                    action=ActionType.INTERACT,
                    target="door_townhall",
                    expected={"animation": "open_door", "visible_target": True, "distance_lte": 2.0},
                    retries=2,
                    checkpoint="townhall_entry",
                ),
                ScenarioStep(
                    name="talk_to_merchant",
                    action=ActionType.TALK_TO_NPC,
                    target="npc_merchant",
                    expected={"animation": "talk_start", "distance_lte": 2.5},
                    retries=2,
                ),
                ScenarioStep(name="advance_dialogue", action=ActionType.ADVANCE_DIALOGUE, retries=3),
                ScenarioStep(name="check_companion", action=ActionType.CHECK_COMPANION, retries=1),
            ],
        ),
        Scenario(
            name="combat_magic_run",
            tags=["combat", "magic", "particles", "equipment"],
            steps=[
                ScenarioStep(name="equip_sword", action=ActionType.EQUIP_ITEM, item="sword_iron_01", retries=2),
                ScenarioStep(
                    name="sword_combo",
                    action=ActionType.ATTACK_SWORD,
                    target="dummy_target_01",
                    params={"combo": 3},
                    expected={"animation": "sword_combo_1"},
                    retries=2,
                ),
                ScenarioStep(name="equip_bow", action=ActionType.EQUIP_ITEM, item="bow_hunter_01", retries=2),
                ScenarioStep(
                    name="bow_shot",
                    action=ActionType.ATTACK_BOW,
                    target="dummy_target_02",
                    params={"charged": True},
                    expected={"animation": "bow_release"},
                    retries=2,
                ),
                ScenarioStep(
                    name="cast_fire_spell",
                    action=ActionType.CAST_MAGIC,
                    spell="firebolt_01",
                    target="dummy_target_03",
                    expected={"animation": "cast_firebolt"},
                    retries=2,
                ),
                ScenarioStep(name="check_spell_particles", action=ActionType.CHECK_PARTICLES, params={"particle_id": "firebolt_impact"}, retries=2),
            ],
        ),
        Scenario(
            name="transition_persistence_run",
            tags=["loading", "transition", "persistence", "cutscene"],
            steps=[
                ScenarioStep(name="save_game", action=ActionType.SAVE_GAME, params={"slot": "qa_slot_01"}),
                ScenarioStep(name="load_game", action=ActionType.LOAD_GAME, params={"slot": "qa_slot_01"}, timeout_sec=12.0, retries=2),
                ScenarioStep(
                    name="teleport_to_forest",
                    action=ActionType.TELEPORT,
                    target="teleport_forest",
                    expected={"scene_name": "forest_scene"},
                    timeout_sec=12.0,
                    retries=2,
                ),
                ScenarioStep(name="check_loading_after_teleport", action=ActionType.CHECK_LOADING, timeout_sec=10.0),
                ScenarioStep(name="play_intro_cutscene", action=ActionType.CHECK_CUTSCENE, target="cutscene_forest_intro", timeout_sec=20.0),
                ScenarioStep(name="death_respawn_cycle", action=ActionType.DIE_AND_RESPAWN, timeout_sec=12.0, retries=1),
            ],
        ),
        Scenario(
            name="movement_modes_run",
            tags=["mount", "swim", "fly"],
            steps=[
                ScenarioStep(name="mount_horse", action=ActionType.MOUNT, target="mount_horse_01", retries=2),
                ScenarioStep(name="dismount_horse", action=ActionType.DISMOUNT, retries=2),
                ScenarioStep(name="swim_lake", action=ActionType.SWIM_TO, target="lake_exit_marker", timeout_sec=15.0, retries=2),
                ScenarioStep(name="fly_to_tower", action=ActionType.FLY_TO, target="tower_roof_marker", timeout_sec=20.0, retries=2),
            ],
        ),
        Scenario(
            name="edge_input_run",
            tags=["edge", "input", "stress"],
            steps=[
                ScenarioStep(name="input_stress_combo", action=ActionType.INPUT_STRESS, params={"inputs": ["attack", "jump", "menu", "interact"], "duration_sec": 1.5}, retries=2),
                ScenarioStep(name="edge_case_spam", action=ActionType.EDGE_CASE, params={"inputs": ["attack", "interact", "menu", "mount"], "duration_sec": 1.2}, retries=2),
            ],
        ),
    ]


# ============================================================
# Mock adapter example (for local dry runs / wiring tests)
# Replace with your Panda3D adapter.
# ============================================================


class MockGameAdapter:
    def __init__(self) -> None:
        self.state = WorldState(scene_name="town_scene", current_animation="idle")
        self.perf = PerfMetrics(fps=60.0, frame_time_ms=16.6, draw_calls=120, triangles=180000, instances=450)

    def get_state(self) -> WorldState:
        return self.state

    def get_perf_metrics(self) -> PerfMetrics:
        self.perf.fps = max(25.0, min(120.0, self.perf.fps + random.uniform(-3.0, 3.0)))
        self.perf.draw_calls = max(50, min(260, self.perf.draw_calls + random.randint(-10, 10)))
        return self.perf

    def capture_screenshot(self, label: str, out_dir: str) -> str:
        path = Path(out_dir) / f"{label}.txt"
        path.write_text(f"placeholder screenshot: {label}", encoding="utf-8")
        return str(path)

    def move_to_target(self, target_id: str, timeout_sec: float) -> bool:
        self.state.player_pos = (1.0, 2.0, 0.0)
        self.state.current_animation = "walk"
        time.sleep(0.001)
        return True

    def follow_route(self, route_id: str, timeout_sec: float) -> bool:
        self.state.current_animation = "run"
        time.sleep(0.001)
        return True

    def rotate_to(self, target_id: str, timeout_sec: float) -> bool:
        return True

    def aim_at(self, target_id: str, timeout_sec: float) -> bool:
        return True

    def interact(self, target_id: str) -> bool:
        self.state.current_animation = "open_door"
        self.state.object_states[target_id] = "opened"
        return True

    def open_menu(self, menu_name: str) -> bool:
        if menu_name not in self.state.ui_stack:
            self.state.ui_stack.append(menu_name)
        return True

    def close_menu(self, menu_name: Optional[str] = None) -> bool:
        if menu_name and menu_name in self.state.ui_stack:
            self.state.ui_stack.remove(menu_name)
        elif not menu_name and self.state.ui_stack:
            self.state.ui_stack.pop()
        return True

    def scroll_menu(self, menu_name: str, direction: str, amount: int = 1) -> bool:
        return True

    def click_button(self, button_id: str) -> bool:
        return True

    def talk_to_npc(self, npc_id: str) -> bool:
        self.state.current_animation = "talk_start"
        return True

    def advance_dialogue(self) -> bool:
        return True

    def attack_sword(self, target_id: Optional[str] = None, combo: int = 1) -> bool:
        self.state.current_animation = "sword_combo_1"
        return True

    def attack_bow(self, target_id: Optional[str] = None, charged: bool = False) -> bool:
        self.state.current_animation = "bow_release"
        return True

    def cast_magic(self, spell_id: str, target_id: Optional[str] = None) -> bool:
        self.state.current_animation = "cast_firebolt"
        self.state.current_effects = [spell_id]
        return True

    def equip_item(self, item_id: str) -> bool:
        self.state.equipment_state[item_id] = True
        return True

    def unequip_item(self, item_id: str) -> bool:
        self.state.equipment_state.pop(item_id, None)
        return True

    def mount(self, mount_id: Optional[str] = None) -> bool:
        self.state.misc["mounted"] = True
        return True

    def dismount(self) -> bool:
        self.state.misc["mounted"] = False
        return True

    def swim_to(self, target_id: str, timeout_sec: float) -> bool:
        self.state.current_animation = "swim_loop"
        return True

    def fly_to(self, target_id: str, timeout_sec: float) -> bool:
        self.state.current_animation = "flight_loop"
        return True

    def teleport(self, target_id: str) -> bool:
        self.state.loading = True
        self.state.scene_name = "forest_scene"
        time.sleep(0.001)
        self.state.loading = False
        return True

    def transition_location(self, transition_id: str) -> bool:
        self.state.loading = True
        time.sleep(0.001)
        self.state.loading = False
        return True

    def trigger_cutscene(self, cutscene_id: str) -> bool:
        self.state.control_locked = True
        self.state.input_enabled = False
        self.state.misc["cutscene"] = True
        time.sleep(0.001)
        self.state.misc["cutscene"] = False
        self.state.control_locked = False
        self.state.input_enabled = True
        return True

    def save_game(self, slot: str) -> bool:
        self.state.misc["save_slot"] = slot
        return True

    def load_game(self, slot: str) -> bool:
        self.state.misc["save_slot"] = slot
        self.state.loading = True
        time.sleep(0.001)
        self.state.loading = False
        return True

    def kill_player(self) -> bool:
        self.state.misc["dead"] = True
        return True

    def respawn_player(self) -> bool:
        self.state.misc["dead"] = False
        self.state.player_pos = (0.0, 0.0, 0.0)
        return True

    def wait(self, seconds: float) -> None:
        time.sleep(min(seconds, 0.001))

    def stop_all_input(self) -> None:
        return None

    def spam_input(self, inputs: List[str], duration_sec: float) -> bool:
        return True

    def interrupt_current_action(self) -> bool:
        self.state.current_animation = "idle"
        return True

    def reset_to_checkpoint(self, checkpoint_id: str) -> bool:
        self.state.player_pos = (0.0, 0.0, 0.0)
        return True

    def query_distance_to(self, target_id: str) -> float:
        return 1.0

    def is_prompt_visible(self, prompt_name: str) -> bool:
        return True

    def is_object_visible(self, target_id: str) -> bool:
        return True

    def did_particle_play(self, particle_id: Optional[str] = None) -> bool:
        return True

    def did_hit_connect(self, target_id: Optional[str] = None) -> bool:
        return True

    def did_projectile_spawn(self) -> bool:
        return True

    def did_damage_apply(self, target_id: Optional[str] = None) -> bool:
        return True

    def did_magic_effect_apply(self, spell_id: str, target_id: Optional[str] = None) -> bool:
        return True

    def is_cutscene_playing(self) -> bool:
        return bool(self.state.misc.get("cutscene", False))

    def is_loading_screen_visible(self) -> bool:
        return self.state.loading

    def is_scene_ready(self) -> bool:
        return not self.state.loading

    def get_route_progress(self, route_id: str) -> float:
        return 1.0

    def get_companion_snapshot(self) -> Dict[str, Any]:
        return {
            "stuck": False,
            "distance_to_player": 2.0,
            "max_expected_distance": 8.0,
            "movement_desync": False,
        }

    def log(self, message: str) -> None:
        print(message)

    def run_video_scenario(self, scenario_name: str, scenario_file: str, params: Dict[str, Any]) -> bool:
        self.state.misc["last_video_scenario"] = scenario_name
        return True


# ============================================================
# Repo video scenario loader
# ============================================================


def load_repo_video_scenarios(
    scenarios_file: str,
    scenario_names: Optional[List[str]] = None,
) -> List[Scenario]:
    '''Wrap entries from a repo video JSON file as debugger Scenario objects.'''
    with open(scenarios_file, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    raw_scenarios: Dict[str, Any] = data.get("scenarios", {})
    results: List[Scenario] = []

    for name, entry in raw_scenarios.items():
        if scenario_names is not None and name not in scenario_names:
            continue
        if not isinstance(entry, dict):
            continue

        game_env: Dict[str, Any] = entry.get("game_env", {})
        launcher_test = str(entry.get("launcher_test", "") or "")
        legacy_plan = str(game_env.get("XBOT_VIDEO_BOT_PLAN", launcher_test) or launcher_test)

        step_params: Dict[str, Any] = {
            "scenario_name": name,
            "scenario_file": scenarios_file,
            "launcher_test": launcher_test,
            "legacy_plan": legacy_plan,
            "game_env": dict(game_env),
        }
        for field_name in ("duration_sec", "fps", "output_dir", "window_title", "wait_ready_timeout_sec"):
            if field_name in entry:
                step_params[field_name] = entry[field_name]

        step = ScenarioStep(
            name=name,
            action=ActionType.RUN_VIDEO_SCENARIO,
            params=step_params,
        )
        results.append(Scenario(name=name, steps=[step], tags=entry.get("tags", [])))

    return results



# ============================================================
# Tests
# ============================================================


class AutonomousQARunnerTests(unittest.TestCase):
    def test_is_truthy_failure_normalizes_values(self) -> None:
        self.assertFalse(is_truthy_failure(None))
        self.assertFalse(is_truthy_failure("false"))
        self.assertFalse(is_truthy_failure("0"))
        self.assertFalse(is_truthy_failure([]))
        self.assertTrue(is_truthy_failure(True))
        self.assertTrue(is_truthy_failure("failed"))
        self.assertTrue(is_truthy_failure(["x"]))
        self.assertTrue(is_truthy_failure({"reason": "bad"}))

    def test_runner_works_without_background_threads(self) -> None:
        adapter = MockGameAdapter()
        scenarios = [Scenario(name="minimal", steps=[ScenarioStep(name="wait", action=ActionType.WAIT)])]
        out_dir = os.path.join(os.getcwd(), "qa_test_output_threads")
        runner = AutonomousQARunner(adapter=adapter, scenarios=scenarios, output_dir=out_dir, hours=None)
        summary = runner.run()
        self.assertEqual(summary["failed_steps"], 0)
        self.assertGreaterEqual(summary["total_steps"], 1)

    def test_bug_classifier_handles_non_boolean_evidence(self) -> None:
        step = ScenarioStep(name="x", action=ActionType.WAIT)
        before = WorldState()
        after = WorldState()
        evidence = {"route_failed": "failed"}
        bug = BugClassifier.classify(step, before, after, evidence)
        self.assertEqual(bug, BugType.ROUTE_BUG)

    def test_loading_validation_fails_when_loading_never_finishes(self) -> None:
        class StuckLoadingAdapter(MockGameAdapter):
            def is_loading_screen_visible(self) -> bool:
                return True

            def is_scene_ready(self) -> bool:
                return False

        adapter = StuckLoadingAdapter()
        result = Validators.validate_loading(adapter, timeout_sec=0.01)
        self.assertTrue(result["loading_failed"])


# ============================================================
# CLI entry
# ============================================================


def run_tests() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AutonomousQARunnerTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous QA Runner")
    parser.add_argument("--output-dir", default=os.path.join(os.getcwd(), "qa_run_output"))
    parser.add_argument("--hours", type=float, default=None, help="Run continuously for N hours")
    parser.add_argument("--run-tests", action="store_true", help="Run built-in tests and exit")
    args = parser.parse_args()

    if args.run_tests:
        raise SystemExit(run_tests())

    adapter = MockGameAdapter()
    scenarios = build_default_scenarios()
    runner = AutonomousQARunner(
        adapter=adapter,
        scenarios=scenarios,
        output_dir=args.output_dir,
        hours=args.hours,
        random_edge_case_chance=0.2,
        stop_on_fail=False,
    )
    summary = runner.run()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
