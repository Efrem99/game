"""Shared catalog + runtime helpers for the asset/animation viewer utility."""

import json
import math
from pathlib import Path

from entities.animation_manifest import alias_animation_key, normalize_anim_key


SUPPORTED_MODEL_EXTS = {".bam", ".glb", ".gltf", ".fbx", ".egg", ".obj"}
SUPPORTED_ANIM_EXTS = {".bam", ".glb", ".gltf", ".fbx", ".egg"}

DEFAULT_MODEL_SCAN_ROOTS = ("assets/models", "models")
DEFAULT_ANIM_SCAN_ROOTS = ("assets/anims", "models/animations", "assets/models/xbot")


def normalize_asset_token(value):
    return str(value or "").strip().replace("\\", "/")


def build_clip_option_labels(animation_keys):
    keys = list(animation_keys or [])
    width = max(2, len(str(len(keys))))
    labels = []
    for idx, key in enumerate(keys, start=1):
        labels.append(f"{idx:0{width}d}. {str(key)}")
    return labels


def option_index_for_anim_key(animation_keys, key):
    target = normalize_anim_key(key)
    if not target:
        return -1
    for idx, candidate in enumerate(animation_keys or []):
        if normalize_anim_key(candidate) == target:
            return idx
    return -1


def _read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _to_rel_token(project_root, path):
    try:
        return path.resolve().relative_to(project_root).as_posix()
    except Exception:
        return path.resolve().as_posix()


def _resolve_existing_asset_token(project_root, token, allowed_exts):
    raw = normalize_asset_token(token)
    if not raw:
        return ""
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    if not candidate.exists():
        return ""
    if allowed_exts and candidate.suffix.lower() not in allowed_exts:
        return ""
    return _to_rel_token(project_root, candidate)


def resolve_existing_asset_paths(project_root, path_tokens, allowed_exts=None):
    root = Path(project_root).resolve()
    ext_set = {str(ext).lower() for ext in (allowed_exts or (SUPPORTED_MODEL_EXTS | SUPPORTED_ANIM_EXTS))}
    rows = []
    seen = set()
    for token in path_tokens or []:
        rel = _resolve_existing_asset_token(root, token, ext_set)
        if not rel or rel in seen:
            continue
        seen.add(rel)
        rows.append(rel)
    return rows


def asset_load_candidates(project_root, token, allowed_exts=None):
    """Return existing load candidates in preferred order (bam first)."""
    root = Path(project_root).resolve()
    raw = normalize_asset_token(token)
    if not raw:
        return []
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    ext_set = {str(ext).lower() for ext in (allowed_exts or (SUPPORTED_MODEL_EXTS | SUPPORTED_ANIM_EXTS))}

    rows = []
    seen = set()

    def _push(candidate):
        if not candidate.exists():
            return
        if ext_set and candidate.suffix.lower() not in ext_set:
            return
        rel = _to_rel_token(root, candidate)
        if rel in seen:
            return
        seen.add(rel)
        rows.append(rel)

    if path.suffix.lower() != ".bam":
        _push(path.with_suffix(".bam"))
    _push(path)
    return rows


def _iter_files(root, allowed_exts):
    base = Path(root)
    if not base.exists():
        return []
    if base.is_file():
        return [base] if base.suffix.lower() in allowed_exts else []

    rows = []
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in allowed_exts:
            rows.append(path)
    rows.sort(key=lambda p: p.as_posix().lower())
    return rows


def _collect_player_cfg(project_root):
    payload = _read_json(Path(project_root) / "data" / "actors" / "player.json")
    node = payload.get("player", payload) if isinstance(payload, dict) else {}
    return node if isinstance(node, dict) else {}


def _append_unique(rows, token):
    key = normalize_asset_token(token)
    if not key:
        return
    if key not in rows:
        rows.append(key)


def build_default_model_list(project_root, scan_roots=None, limit=0):
    """Build viewer model candidates with player models first, then file scan."""
    root = Path(project_root).resolve()
    rows = []

    cfg = _collect_player_cfg(root)
    hints = []
    model_candidates = cfg.get("model_candidates")
    if isinstance(model_candidates, list):
        for item in model_candidates:
            hints.append(item)
    for key in ("model", "fallback_model"):
        token = cfg.get(key)
        if isinstance(token, str):
            hints.append(token)

    for rel in resolve_existing_asset_paths(root, hints, allowed_exts=SUPPORTED_MODEL_EXTS):
        _append_unique(rows, rel)

    roots = list(scan_roots) if scan_roots else list(DEFAULT_MODEL_SCAN_ROOTS)
    for token in roots:
        base = root / normalize_asset_token(token)
        for path in _iter_files(base, SUPPORTED_MODEL_EXTS):
            _append_unique(rows, _to_rel_token(root, path))

    if limit and int(limit) > 0:
        return rows[: int(limit)]
    return rows


def _insert_anim_clip(mapping, key, clip_path):
    if not clip_path:
        return
    norm_key = normalize_anim_key(key) if key else normalize_anim_key(Path(clip_path).stem)
    if not norm_key:
        norm_key = normalize_anim_key(Path(clip_path).name)
    if not norm_key:
        return

    current = mapping.get(norm_key)
    if current is None:
        mapping[norm_key] = clip_path
        return
    if current == clip_path:
        return

    idx = 2
    while True:
        candidate = f"{norm_key}_{idx}"
        current = mapping.get(candidate)
        if current is None:
            mapping[candidate] = clip_path
            return
        if current == clip_path:
            return
        idx += 1


def _manifest_sources(project_root):
    payload = _read_json(Path(project_root) / "data" / "actors" / "player_animations.json")
    if not isinstance(payload, dict):
        return []
    manifest = payload.get("manifest", {})
    if not isinstance(manifest, dict):
        return []
    sources = manifest.get("sources", [])
    return sources if isinstance(sources, list) else []


def build_default_animation_map(project_root, scan_roots=None, limit=0):
    """Build viewer animation mapping from base anims + manifest + scan roots."""
    root = Path(project_root).resolve()
    mapping = {}

    cfg = _collect_player_cfg(root)
    base_anims = cfg.get("base_anims", {})
    if isinstance(base_anims, dict):
        for key, token in base_anims.items():
            rel = _resolve_existing_asset_token(root, token, SUPPORTED_ANIM_EXTS)
            if rel:
                _insert_anim_clip(mapping, key, rel)

    for row in _manifest_sources(root):
        clip = ""
        key = ""
        if isinstance(row, str):
            clip = row
            key = alias_animation_key(Path(clip).stem)
        elif isinstance(row, dict):
            key = normalize_anim_key(row.get("key") or row.get("state") or row.get("id") or "")
            clip = normalize_asset_token(row.get("path") or row.get("file") or row.get("src") or "")
            if not key:
                key = alias_animation_key(Path(clip).stem)
        if not clip:
            continue
        rel = _resolve_existing_asset_token(root, clip, SUPPORTED_ANIM_EXTS)
        if not rel:
            continue
        _insert_anim_clip(mapping, key, rel)

    roots = list(scan_roots) if scan_roots else list(DEFAULT_ANIM_SCAN_ROOTS)
    for token in roots:
        base = root / normalize_asset_token(token)
        for path in _iter_files(base, SUPPORTED_ANIM_EXTS):
            rel = _to_rel_token(root, path)
            key = alias_animation_key(path.stem) or normalize_anim_key(path.stem)
            _insert_anim_clip(mapping, key, rel)

    if limit and int(limit) > 0:
        clipped = {}
        for idx, (key, value) in enumerate(mapping.items()):
            if idx >= int(limit):
                break
            clipped[key] = value
        return clipped
    return mapping


def run_asset_animation_viewer(
    project_root,
    model_paths,
    animation_map,
    *,
    start_model="",
    start_anim="",
    autoplay=False,
    clip_seconds=3.6,
    parkour_debug=False,
):
    """Open interactive Panda3D viewer for models + animation clips."""
    from direct.actor.Actor import Actor
    from direct.gui.DirectGui import DirectButton, DirectFrame, DirectOptionMenu, OnscreenText
    from direct.showbase.ShowBase import ShowBase
    from direct.showbase.ShowBaseGlobal import globalClock
    from panda3d.core import (
        AmbientLight,
        DirectionalLight,
        Filename,
        LineSegs,
        TextNode,
        getModelPath,
        loadPrcFileData,
        TransparencyAttrib,
    )
    import tkinter.simpledialog as sd

    loadPrcFileData("", "window-title King Wizard Asset + Animation Viewer")
    loadPrcFileData("", "win-size 1600 900")
    loadPrcFileData("", "show-frame-rate-meter 0")

    root = Path(project_root).resolve()
    model_path = getModelPath()
    for candidate in (root, root / "assets", root / "assets" / "models", root / "assets" / "anims", root / "models"):
        try:
            model_path.appendDirectory(Filename.from_os_specific(str(candidate)))
        except Exception:
            pass

    model_list = resolve_existing_asset_paths(root, model_paths, allowed_exts=SUPPORTED_MODEL_EXTS)
    if not model_list:
        raise RuntimeError("No valid model files found for viewer session.")

    ordered_animation = {}
    for key, token in (animation_map or {}).items():
        rel = _resolve_existing_asset_token(root, token, SUPPORTED_ANIM_EXTS)
        if rel:
            _insert_anim_clip(ordered_animation, key, rel)

    class _ViewerApp(ShowBase):
        def __init__(self):
            super().__init__()
            self.setBackgroundColor(0.09, 0.1, 0.12, 1.0)
            self.disableMouse()

            self._models = list(model_list)
            self._animations = dict(ordered_animation)
            self._animation_order = list(self._animations.keys())
            self._available_anims = []

            self._model_idx = 0
            self._anim_idx = 0
            self._loop = True
            self._playing = True
            self._autoplay = bool(autoplay)
            self._clip_seconds = max(0.4, float(clip_seconds))
            self._clip_timer = 0.0
            self._play_rate = 1.0
            self._status_note = "viewer ready"
            self._parkour_debug = bool(parkour_debug)
            self._parkour_debug_root = None
            self._parkour_debug_visible = bool(parkour_debug)
            self._preview_ik_enabled = bool(parkour_debug)
            self._preview_ik_alpha = 0.0
            self._preview_ik_controls = {}

            self._camera_angle_deg = -18.0
            self._camera_distance = 8.0
            self._camera_height = 2.2
            self._camera_target_z = 1.2
            self._camera_target_x = 0.0
            self._camera_target_y = 0.0
            self._follow_enabled = True
            self._follow_lerp_speed = 8.5
            self._mouse_drag_start = None
            self._mouse_drag_mode = None  # 1=rotate, 2=zoom, 3=pan

            self._model_root = None
            self._actor = None
            self._status_text = None
            self._help_text = None
            self._model_text = None
            self._speed_text = None
            self._anim_menu = None
            self._btn_play = None
            self._btn_loop = None
            self._btn_autoplay = None
            self._btn_follow = None
            self._btn_course = None
            self._btn_preview_ik = None
            self._btn_mark_broken = None

            self._build_lighting()
            self._build_grid()
            if self._parkour_debug:
                self._build_parkour_debug_course()
            self._build_ui()
            self._wire_keys()
            self._wire_mouse()
            self.taskMgr.add(self._on_tick, "asset-viewer-update")

            self._set_initial_indexes(start_model, start_anim)
            self._load_current_model()

        def _build_lighting(self):
            ambient = AmbientLight("viewer-ambient")
            ambient.setColor((0.62, 0.62, 0.67, 1.0))
            ambient_np = self.render.attachNewNode(ambient)
            self.render.setLight(ambient_np)

            key = DirectionalLight("viewer-key")
            key.setColor((0.92, 0.9, 0.84, 1.0))
            key_np = self.render.attachNewNode(key)
            key_np.setHpr(-32.0, -38.0, 0.0)
            self.render.setLight(key_np)

            fill = DirectionalLight("viewer-fill")
            fill.setColor((0.44, 0.5, 0.58, 1.0))
            fill_np = self.render.attachNewNode(fill)
            fill_np.setHpr(152.0, -18.0, 0.0)
            self.render.setLight(fill_np)

        def _build_grid(self):
            segs = LineSegs("viewer-grid")
            segs.setThickness(1.0)
            extent = 22
            for idx in range(-extent, extent + 1):
                tone = 0.24
                if idx == 0:
                    tone = 0.37
                segs.setColor(tone, tone, tone, 1.0)
                segs.moveTo(idx, -extent, 0.0)
                segs.drawTo(idx, extent, 0.0)
                segs.moveTo(-extent, idx, 0.0)
                segs.drawTo(extent, idx, 0.0)
            grid = self.render.attachNewNode(segs.create())
            grid.setPos(0.0, 0.0, 0.0)

        def _spawn_debug_box(self, name, sx, sy, sz, x, y, z, color):
            cube = self.loader.loadModel("models/misc/rgbCube")
            if not cube or cube.isEmpty():
                return None
            cube.setName(str(name))
            cube.reparentTo(self._parkour_debug_root)
            # rgbCube has side length 2, so use half extents as scale.
            cube.setScale(max(0.01, float(sx) * 0.5), max(0.01, float(sy) * 0.5), max(0.01, float(sz) * 0.5))
            cube.setPos(float(x), float(y), float(z))
            r, g, b, a = color
            cube.setColorScale(float(r), float(g), float(b), float(a))
            cube.setTransparency(TransparencyAttrib.MAlpha)
            cube.setBin("transparent", 20)
            try:
                cube.setShaderOff(1002)
            except Exception:
                pass
            return cube

        def _build_parkour_debug_course(self):
            self._parkour_debug_root = self.render.attachNewNode("parkour-debug-course")
            self._parkour_debug_root.setPos(0.0, 0.0, 0.0)

            # Ground slab.
            self._spawn_debug_box(
                "dbg_ground",
                34.0,
                22.0,
                0.08,
                0.0,
                0.0,
                0.04,
                (0.13, 0.16, 0.2, 0.74),
            )
            self._spawn_debug_box(
                "dbg_lane_center",
                34.0,
                0.10,
                0.04,
                0.0,
                0.0,
                0.07,
                (0.92, 0.84, 0.48, 0.85),
            )

            # Vault sequence (low → high).
            vault_steps = [
                (-8.0, 0.0, 1.0, "vault_low_a"),
                (-4.5, 0.0, 1.3, "vault_low_b"),
                (-0.8, 0.0, 1.8, "vault_high_a"),
            ]
            for px, py, h, token in vault_steps:
                self._spawn_debug_box(
                    f"dbg_{token}",
                    1.9,
                    0.55,
                    h,
                    px,
                    py,
                    h * 0.5,
                    (0.43, 0.66, 0.9, 0.94),
                )

            # Climb wall + ledge.
            self._spawn_debug_box(
                "dbg_climb_wall",
                0.9,
                3.8,
                3.6,
                6.6,
                1.8,
                1.8,
                (0.45, 0.58, 0.78, 0.96),
            )
            self._spawn_debug_box(
                "dbg_climb_ledge",
                2.5,
                1.4,
                0.35,
                7.5,
                1.8,
                3.78,
                (0.84, 0.75, 0.53, 0.94),
            )

            # Wallrun panel.
            self._spawn_debug_box(
                "dbg_wallrun_panel",
                0.8,
                7.0,
                4.6,
                11.5,
                -1.4,
                2.3,
                (0.54, 0.78, 0.62, 0.95),
            )

            # Marker posts.
            for idx in range(5):
                py = -7.0 + (idx * 3.5)
                self._spawn_debug_box(
                    f"dbg_marker_{idx}",
                    0.24,
                    0.24,
                    2.0,
                    -12.0,
                    py,
                    1.0,
                    (0.9, 0.88, 0.83, 0.72),
                )

            if not self._parkour_debug_visible:
                self._parkour_debug_root.hide()

        def _toggle_parkour_debug(self):
            if not self._parkour_debug_root:
                return
            self._parkour_debug_visible = not self._parkour_debug_visible
            if self._parkour_debug_visible:
                self._parkour_debug_root.show()
            else:
                self._parkour_debug_root.hide()
            self._set_status(f"parkour_debug={'on' if self._parkour_debug_visible else 'off'}")

        def _resolve_control_joint(self, names):
            actor = self._actor
            if not actor or not hasattr(actor, "controlJoint"):
                return None
            for bone in names:
                try:
                    node = actor.controlJoint(None, "modelRoot", bone)
                    if node and not node.isEmpty():
                        return node
                except Exception:
                    continue
            return None

        def _setup_preview_ik_controls(self):
            self._preview_ik_controls = {}
            if not self._preview_ik_enabled or not self._actor:
                return
            controls = {
                "right_hand": self._resolve_control_joint(["mixamorig:RightHand", "RightHand", "hand_r", "Hand_R"]),
                "left_hand": self._resolve_control_joint(["mixamorig:LeftHand", "LeftHand", "hand_l", "Hand_L"]),
                "right_foot": self._resolve_control_joint(["mixamorig:RightFoot", "RightFoot", "foot_r", "Foot_R"]),
                "left_foot": self._resolve_control_joint(["mixamorig:LeftFoot", "LeftFoot", "foot_l", "Foot_L"]),
                "spine": self._resolve_control_joint(["mixamorig:Spine2", "Spine2", "Spine", "spine_03"]),
            }
            self._preview_ik_controls = controls

        def _toggle_preview_ik(self):
            self._preview_ik_enabled = not self._preview_ik_enabled
            if not self._preview_ik_enabled:
                self._preview_ik_alpha = 0.0
            self._setup_preview_ik_controls()
            self._set_status(f"preview_ik={'on' if self._preview_ik_enabled else 'off'}")

        def _update_preview_ik(self, dt):
            controls = self._preview_ik_controls if isinstance(self._preview_ik_controls, dict) else {}
            if not controls:
                return
            anim = str(self._current_anim_key() or "").strip().lower()
            active = (
                "wallrun" in anim
                or "vault" in anim
                or "climb" in anim
                or "ledge" in anim
            )
            target_alpha = 1.0 if (self._preview_ik_enabled and active) else 0.0
            self._preview_ik_alpha += (target_alpha - self._preview_ik_alpha) * max(0.0, min(1.0, float(dt) * 8.0))
            alpha = float(self._preview_ik_alpha)

            def _set(name, h, p, r):
                node = controls.get(name)
                if not node:
                    return
                try:
                    node.setHpr(float(h) * alpha, float(p) * alpha, float(r) * alpha)
                except Exception:
                    pass

            if alpha <= 0.001:
                for key in ("right_hand", "left_hand", "right_foot", "left_foot", "spine"):
                    _set(key, 0.0, 0.0, 0.0)
                return

            t = float(globalClock.getFrameTime())
            if "wallrun" in anim:
                wave = math.sin(t * 8.4)
                _set("spine", 0.0, -8.0, 9.0)
                _set("right_hand", 0.0, -20.0 + (wave * 6.0), -7.0)
                _set("left_hand", 0.0, -20.0 - (wave * 6.0), 7.0)
                _set("right_foot", 0.0, 20.0 - (wave * 9.0), 0.0)
                _set("left_foot", 0.0, 14.0 + (wave * 9.0), 0.0)
            elif "climb" in anim or "ledge" in anim:
                phase = math.sin(t * 6.2)
                _set("spine", 0.0, -10.0, 0.0)
                _set("right_hand", 0.0, -33.0 + (phase * 14.0), 0.0)
                _set("left_hand", 0.0, -33.0 - (phase * 14.0), 0.0)
                _set("right_foot", 0.0, 24.0 - (phase * 12.0), 0.0)
                _set("left_foot", 0.0, 24.0 + (phase * 12.0), 0.0)
            elif "vault" in anim:
                arc = 0.5 + (0.5 * math.sin(t * 10.0))
                _set("spine", 0.0, -10.0 * arc, 0.0)
                _set("right_hand", 0.0, -54.0 * arc, 0.0)
                _set("left_hand", 0.0, -54.0 * arc, 0.0)
                _set("right_foot", 0.0, 32.0 * arc, 0.0)
                _set("left_foot", 0.0, 32.0 * arc, 0.0)

        def _build_ui(self):
            self._status_text = OnscreenText(
                text="",
                pos=(-1.31, 0.93),
                align=TextNode.ALeft,
                scale=0.047,
                fg=(0.98, 0.98, 0.99, 1.0),
                mayChange=True,
            )

            panel = DirectFrame(
                frameColor=(0.08, 0.11, 0.16, 0.83),
                frameSize=(-0.52, 0.52, -0.55, 0.55),
                pos=(1.07, 0.0, 0.0),
            )
            OnscreenText(
                parent=panel,
                text="Animation Controls",
                pos=(0.0, 0.47),
                align=TextNode.ACenter,
                scale=0.058,
                fg=(0.94, 0.9, 0.77, 1.0),
            )
            self._model_text = OnscreenText(
                parent=panel,
                text="Model: -",
                pos=(-0.48, 0.37),
                align=TextNode.ALeft,
                scale=0.041,
                fg=(0.9, 0.96, 0.99, 1.0),
                mayChange=True,
            )
            DirectButton(
                parent=panel,
                text="< Model",
                scale=0.05,
                frameSize=(-3.5, 3.5, -0.8, 1.2),
                frameColor=(0.18, 0.24, 0.33, 0.95),
                text_fg=(0.96, 0.96, 0.97, 1.0),
                pos=(-0.23, 0.0, 0.27),
                command=self._step_model,
                extraArgs=[-1],
            )
            DirectButton(
                parent=panel,
                text="Model >",
                scale=0.05,
                frameSize=(-3.5, 3.5, -0.8, 1.2),
                frameColor=(0.18, 0.24, 0.33, 0.95),
                text_fg=(0.96, 0.96, 0.97, 1.0),
                pos=(0.23, 0.0, 0.27),
                command=self._step_model,
                extraArgs=[1],
            )
            OnscreenText(
                parent=panel,
                text="Animation",
                pos=(0.0, 0.2),
                align=TextNode.ACenter,
                scale=0.046,
                fg=(0.88, 0.93, 0.97, 1.0),
            )
            self._anim_menu = DirectOptionMenu(
                parent=panel,
                items=["(no clips)"],
                scale=0.045,
                pos=(-0.46, 0.0, 0.11),
                frameColor=(0.16, 0.21, 0.3, 0.95),
                text_fg=(0.98, 0.98, 0.99, 1.0),
                highlightColor=(0.31, 0.41, 0.56, 1.0),
                command=self._on_anim_selected,
            )
            DirectButton(
                parent=panel,
                text="< Clip",
                scale=0.045,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.18, 0.24, 0.33, 0.95),
                text_fg=(0.96, 0.96, 0.97, 1.0),
                pos=(-0.22, 0.0, 0.01),
                command=self._step_anim,
                extraArgs=[-1],
            )
            DirectButton(
                parent=panel,
                text="Clip >",
                scale=0.045,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.18, 0.24, 0.33, 0.95),
                text_fg=(0.96, 0.96, 0.97, 1.0),
                pos=(0.22, 0.0, 0.01),
                command=self._step_anim,
                extraArgs=[1],
            )
            self._btn_play = DirectButton(
                parent=panel,
                text="Pause",
                scale=0.045,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.2, 0.27, 0.37, 0.95),
                text_fg=(0.97, 0.97, 0.98, 1.0),
                pos=(-0.22, 0.0, -0.11),
                command=self._toggle_pause,
            )
            self._btn_loop = DirectButton(
                parent=panel,
                text="Loop: ON",
                scale=0.045,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.2, 0.27, 0.37, 0.95),
                text_fg=(0.97, 0.97, 0.98, 1.0),
                pos=(0.22, 0.0, -0.11),
                command=self._toggle_loop,
            )
            self._btn_autoplay = DirectButton(
                parent=panel,
                text="Autoplay: OFF",
                scale=0.045,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.2, 0.27, 0.37, 0.95),
                text_fg=(0.97, 0.97, 0.98, 1.0),
                pos=(-0.22, 0.0, -0.23),
                command=self._toggle_autoplay,
            )
            self._btn_follow = DirectButton(
                parent=panel,
                text="Follow: ON",
                scale=0.045,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.2, 0.27, 0.37, 0.95),
                text_fg=(0.97, 0.97, 0.98, 1.0),
                pos=(0.22, 0.0, -0.23),
                command=self._toggle_camera_follow,
            )
            self._btn_course = DirectButton(
                parent=panel,
                text="Course: ON" if self._parkour_debug_visible else "Course: OFF",
                scale=0.043,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.2, 0.27, 0.37, 0.95),
                text_fg=(0.97, 0.97, 0.98, 1.0),
                pos=(-0.22, 0.0, -0.47),
                command=self._toggle_parkour_debug,
            )
            self._btn_preview_ik = DirectButton(
                parent=panel,
                text="IK: ON" if self._preview_ik_enabled else "IK: OFF",
                scale=0.043,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.2, 0.27, 0.37, 0.95),
                text_fg=(0.97, 0.97, 0.98, 1.0),
                pos=(0.22, 0.0, -0.47),
                command=self._toggle_preview_ik,
            )
            DirectButton(
                parent=panel,
                text="- Speed",
                scale=0.044,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.18, 0.24, 0.33, 0.95),
                text_fg=(0.96, 0.96, 0.97, 1.0),
                pos=(-0.22, 0.0, -0.35),
                command=self._change_speed,
                extraArgs=[-0.1],
            )
            DirectButton(
                parent=panel,
                text="+ Speed",
                scale=0.044,
                frameSize=(-3.2, 3.2, -0.8, 1.2),
                frameColor=(0.18, 0.24, 0.33, 0.95),
                text_fg=(0.96, 0.96, 0.97, 1.0),
                pos=(0.22, 0.0, -0.35),
                command=self._change_speed,
                extraArgs=[0.1],
            )
            self._speed_text = OnscreenText(
                parent=panel,
                text="Speed: 1.00x",
                pos=(0.0, -0.43),
                align=TextNode.ACenter,
                scale=0.043,
                fg=(0.89, 0.95, 0.99, 1.0),
                mayChange=True,
            )
            self._btn_mark_broken = DirectButton(
                parent=panel,
                text="MARK AS BROKEN",
                scale=0.05,
                frameSize=(-5.0, 5.0, -0.8, 1.2),
                frameColor=(0.42, 0.16, 0.16, 0.95),
                text_fg=(0.99, 0.9, 0.9, 1.0),
                pos=(0.0, 0.0, -0.5),
                command=self._mark_current_anim_broken,
            )
            self._help_text = OnscreenText(
                text=(
                    "Use right panel buttons (recommended) | Mouse: Left=Rotate, Middle=Zoom, Right=Pan\n"
                    "Keyboard: PgUp/PgDn model, [/ ] anim, Space pause, L loop, A autoplay, "
                    "-/= speed, arrows orbit, F follow, Esc exit"
                ),
                pos=(-1.31, -0.94),
                align=TextNode.ALeft,
                scale=0.038,
                fg=(0.76, 0.84, 0.97, 1.0),
                mayChange=False,
            )

        def _wire_keys(self):
            self.accept("escape", self.userExit)
            self.accept("page_down", self._step_model, [1])
            self.accept("page_up", self._step_model, [-1])
            self.accept("]", self._step_anim, [1])
            self.accept("[", self._step_anim, [-1])
            self.accept("space", self._toggle_pause)
            self.accept("l", self._toggle_loop)
            self.accept("a", self._toggle_autoplay)
            self.accept("f", self._toggle_camera_follow)
            self.accept("g", self._toggle_parkour_debug)
            self.accept("i", self._toggle_preview_ik)
            self.accept("-", self._change_speed, [-0.1])
            self.accept("=", self._change_speed, [0.1])
            self.accept("r", self._reload_current_model)
            self.accept("wheel_up", self._zoom_camera, [-0.5])
            self.accept("wheel_down", self._zoom_camera, [0.5])
            self.accept("arrow_left", self._rotate_camera, [-8.0])
            self.accept("arrow_right", self._rotate_camera, [8.0])
            self.accept("arrow_up", self._raise_camera, [0.22])
            self.accept("arrow_down", self._raise_camera, [-0.22])

        def _wire_mouse(self):
            self.accept("mouse1", self._on_mouse_down, [1])
            self.accept("mouse1-up", self._on_mouse_up)
            self.accept("mouse2", self._on_mouse_down, [2])
            self.accept("mouse2-up", self._on_mouse_up)
            self.accept("mouse3", self._on_mouse_down, [3])
            self.accept("mouse3-up", self._on_mouse_up)

        def _on_mouse_down(self, mode):
            if self.mouseWatcherNode.hasMouse():
                self._mouse_drag_start = (
                    self.mouseWatcherNode.getMouseX(),
                    self.mouseWatcherNode.getMouseY(),
                )
                self._mouse_drag_mode = mode

        def _on_mouse_up(self):
            self._mouse_drag_start = None
            self._mouse_drag_mode = None

        def _update_orbit_cam(self, dt):
            if self._mouse_drag_mode is None or not self.mouseWatcherNode.hasMouse():
                return

            mx = self.mouseWatcherNode.getMouseX()
            my = self.mouseWatcherNode.getMouseY()
            dx = mx - self._mouse_drag_start[0]
            dy = my - self._mouse_drag_start[1]
            self._mouse_drag_start = (mx, my)

            if self._mouse_drag_mode == 1:  # Rotate
                self._camera_angle_deg += dx * 180.0
                self._camera_height = max(
                    0.25, min(22.0, self._camera_height - dy * self._camera_distance * 1.5)
                )
            elif self._mouse_drag_mode == 2:  # Zoom
                self._camera_distance = max(2.0, min(60.0, self._camera_distance * (1.0 - dy * 2.0)))
            elif self._mouse_drag_mode == 3:  # Pan
                scale = self._camera_distance * 0.5
                angle_rad = math.radians(self._camera_angle_deg)
                self._camera_target_x -= (math.cos(angle_rad) * dx + math.sin(angle_rad) * dy * 0.5) * scale
                self._camera_target_y -= (math.sin(angle_rad) * dx - math.cos(angle_rad) * dy * 0.5) * scale
                self._camera_target_z += dy * scale * 0.5

            self._update_camera()

        def _set_initial_indexes(self, model_token, anim_token):
            model_norm = normalize_asset_token(model_token).lower()
            if model_norm:
                for idx, row in enumerate(self._models):
                    if normalize_asset_token(row).lower().endswith(model_norm):
                        self._model_idx = idx
                        break
            anim_norm = normalize_anim_key(anim_token)
            if anim_norm:
                for idx, key in enumerate(self._animation_order):
                    if normalize_anim_key(key) == anim_norm:
                        self._anim_idx = idx
                        break

        def _menu_index_from_label(self, label):
            raw = str(label or "").strip()
            if not raw:
                return -1
            num = raw.split(".", 1)[0].strip()
            if num.isdigit():
                idx = int(num) - 1
                if 0 <= idx < len(self._available_anims):
                    return idx
            idx = option_index_for_anim_key(self._available_anims, raw)
            return idx

        def _refresh_anim_menu(self):
            if self._anim_menu is None:
                return
            n_anims = len(self._available_anims)
            if n_anims == 0:
                self._anim_menu["items"] = ["(no clips)"]
                try:
                    self._anim_menu.set(0, fCommand=0)
                except Exception:
                    pass
                return
            labels = build_clip_option_labels(self._available_anims)
            self._anim_menu["items"] = labels
            self._anim_idx = self._anim_idx % n_anims
            try:
                self._anim_menu.set(self._anim_idx, fCommand=0)
            except Exception:
                pass

        def _refresh_ui_state(self):
            if self._model_text is not None and self._models:
                model = normalize_asset_token(self._models[self._model_idx])
                self._model_text.setText(f"Model: {self._short(model, max_len=62)}")
            if self._speed_text is not None:
                self._speed_text.setText(f"Speed: {self._play_rate:.2f}x")
            if self._btn_play is not None:
                self._btn_play["text"] = "Pause" if self._playing else "Play"
            if self._btn_loop is not None:
                self._btn_loop["text"] = f"Loop: {'ON' if self._loop else 'OFF'}"
            if self._btn_autoplay is not None:
                self._btn_autoplay["text"] = f"Autoplay: {'ON' if self._autoplay else 'OFF'}"
            if self._btn_follow is not None:
                self._btn_follow["text"] = f"Follow: {'ON' if self._follow_enabled else 'OFF'}"
            if self._btn_course is not None:
                self._btn_course["text"] = f"Course: {'ON' if self._parkour_debug_visible else 'OFF'}"
            if self._btn_preview_ik is not None:
                self._btn_preview_ik["text"] = f"IK: {'ON' if self._preview_ik_enabled else 'OFF'}"

        def _on_anim_selected(self, selected_label):
            if not self._available_anims:
                return
            idx = self._menu_index_from_label(selected_label)
            if idx < 0:
                return
            self._anim_idx = idx
            self._play_current_animation(restart=True)

        def _abs(self, rel_token):
            return (root / normalize_asset_token(rel_token)).resolve()

        def _to_filename(self, path_obj):
            return Filename.from_os_specific(str(Path(path_obj)))

        def _existing_candidates(self, rel_token, allowed_exts):
            rows = asset_load_candidates(root, rel_token, allowed_exts=allowed_exts)
            out = []
            for rel in rows:
                candidate = self._abs(rel)
                if candidate.exists():
                    out.append(candidate)
            if out:
                return out
            direct = self._abs(rel_token)
            return [direct] if direct.exists() else []

        def _set_status(self, note):
            self._status_note = str(note or "").strip() or self._status_note

        def _clear_loaded_model(self):
            self._preview_ik_controls = {}
            self._preview_ik_alpha = 0.0
            if self._actor is not None:
                try:
                    self._actor.cleanup()
                except Exception:
                    pass
                self._actor = None
            if self._model_root is not None:
                try:
                    self._model_root.removeNode()
                except Exception:
                    pass
                self._model_root = None

        def _load_current_model(self):
            self._clear_loaded_model()
            model_rel = self._models[self._model_idx]
            self._model_root = self.render.attachNewNode("viewer-model-root")
            self._actor = None
            self._available_anims = []
            self._clip_timer = 0.0

            model_candidates = self._existing_candidates(model_rel, SUPPORTED_MODEL_EXTS)
            if not model_candidates:
                self._set_status(f"model file missing: {model_rel}")
                self._refresh_anim_menu()
                self._refresh_ui_state()
                return

            actor_loaded = False
            actor_note = ""
            for model_abs in model_candidates:
                try:
                    actor = Actor(self._to_filename(model_abs))
                except Exception as exc:
                    actor_note = f"actor load failed: {exc}"
                    continue

                if actor.isEmpty():
                    actor_note = "actor load empty"
                    continue

                for key, anim_rel in self._animations.items():
                    anim_candidates = self._existing_candidates(anim_rel, SUPPORTED_ANIM_EXTS)
                    for anim_abs in anim_candidates:
                        try:
                            actor.loadAnims({key: self._to_filename(anim_abs)})
                            break
                        except Exception:
                            continue

                # Safety check: don't call getAnimNames if actor is not properly initialized
                # or has no geometry parts known to Actor class.
                names = set()
                try:
                    if hasattr(actor, 'getAnimNames'):
                        names = set(actor.getAnimNames())
                except Exception as e:
                    print(f"[Viewer] Warning: Model is not a character or has no joints: {e}")
                    actor_note = "Model is not a character (static mesh mode)"

                if names:
                    self._available_anims = [key for key in self._animation_order if key in names]
                else:
                    self._available_anims = []

                actor.reparentTo(self._model_root)
                self._actor = actor

                bounds = self._model_root.getTightBounds()
                if not bounds or len(bounds) != 2:
                    actor_note = "actor has no visible bounds"
                    try:
                        actor.cleanup()
                    except Exception:
                        pass
                    self._actor = None
                    self._available_anims = []
                    self._model_root.node().removeAllChildren()
                    continue

                actor_loaded = True
                self._set_status(
                    f"actor: {model_abs.name} | clips={len(self._available_anims)}"
                )
                self._setup_preview_ik_controls()
                break

            if not actor_loaded:
                static_loaded = False
                for model_abs in model_candidates:
                    try:
                        model = self.loader.loadModel(self._to_filename(model_abs))
                    except Exception:
                        continue
                    if not model or model.isEmpty():
                        continue
                    model.reparentTo(self._model_root)
                    static_loaded = True
                    self._set_status(f"static mesh: {model_abs.name} ({actor_note or 'no actor'})")
                    break

                if not static_loaded:
                    fallback = self.loader.loadModel("models/misc/rgbCube")
                    if fallback and not fallback.isEmpty():
                        fallback.setScale(0.7)
                        fallback.reparentTo(self._model_root)
                    self._set_status(f"placeholder mesh (failed model load: {actor_note or 'unknown'})")

            self._fit_scene_to_model()
            if self._available_anims:
                self._anim_idx = self._anim_idx % len(self._available_anims)
                self._play_current_animation(restart=True)
            else:
                self._playing = False
            self._refresh_anim_menu()
            self._refresh_ui_state()

        def _is_valid_pt(self, pt):
            return all(math.isfinite(float(v)) for v in (pt.x, pt.y, pt.z))

        def _fit_scene_to_model(self):
            bounds = self._model_root.getTightBounds()
            if not bounds or len(bounds) != 2:
                self._update_camera()
                return

            min_pt, max_pt = bounds
            if not self._is_valid_pt(min_pt) or not self._is_valid_pt(max_pt):
                self._update_camera()
                return

            center = (min_pt + max_pt) * 0.5
            self._model_root.setPos(self._model_root.getPos() - center)
            span = (max_pt - min_pt).length()
            span = max(1.2, float(span))
            
            # Additional safety for camera params
            if not math.isfinite(span): 
                span = 2.0

            self._camera_distance = max(4.5, span * 1.75)
            self._camera_height = max(1.25, span * 0.52)
            self._camera_target_z = max(0.9, span * 0.34)
            self._camera_target_x = 0.0
            self._camera_target_y = 0.0
            self._update_camera()

        def _update_follow_target(self, dt):
            if not self._follow_enabled or self._model_root is None:
                return
            bounds = self._model_root.getTightBounds()
            if not bounds or len(bounds) != 2:
                return
            min_pt, max_pt = bounds
            if not self._is_valid_pt(min_pt) or not self._is_valid_pt(max_pt):
                return
            center = (min_pt + max_pt) * 0.5
            desired_x = float(center.x)
            desired_y = float(center.y)
            desired_z = max(0.35, float(center.z))

            alpha = min(1.0, max(0.0, float(dt) * self._follow_lerp_speed))
            if math.isfinite(alpha):
                self._camera_target_x += (desired_x - self._camera_target_x) * alpha
                self._camera_target_y += (desired_y - self._camera_target_y) * alpha
                self._camera_target_z += (desired_z - self._camera_target_z) * alpha
                self._update_camera()

        def _update_camera(self):
            angle_rad = math.radians(self._camera_angle_deg)
            x = self._camera_target_x + math.sin(angle_rad) * self._camera_distance
            y = self._camera_target_y - math.cos(angle_rad) * self._camera_distance
            z = self._camera_target_z + self._camera_height
            self.camera.setPos(x, y, z)
            self.camera.lookAt(self._camera_target_x, self._camera_target_y, self._camera_target_z)

        def _rotate_camera(self, delta):
            self._camera_angle_deg += float(delta)
            self._update_camera()

        def _zoom_camera(self, delta):
            self._camera_distance = max(2.0, min(60.0, self._camera_distance + float(delta)))
            self._update_camera()

        def _raise_camera(self, delta):
            self._camera_height = max(0.25, min(22.0, self._camera_height + float(delta)))
            self._camera_target_z = max(0.35, self._camera_target_z + float(delta) * 0.4)
            self._update_camera()

        def _current_anim_key(self):
            if not self._available_anims:
                return ""
            return self._available_anims[self._anim_idx % len(self._available_anims)]

        def _play_current_animation(self, restart):
            anim = self._current_anim_key()
            if not self._actor or not anim:
                self._playing = False
                self._refresh_ui_state()
                return
            try:
                self._actor.stop(anim)
            except Exception:
                pass

            if self._loop:
                self._actor.loop(anim, restart=bool(restart))
            else:
                self._actor.play(anim)
            self._actor.setPlayRate(self._play_rate, anim)
            self._playing = True
            self._clip_timer = 0.0
            self._set_status(f"playing: {anim}")
            self._refresh_ui_state()
            self._refresh_anim_menu()

        def _toggle_pause(self):
            anim = self._current_anim_key()
            if not self._actor or not anim:
                return
            if self._playing:
                self._actor.stop(anim)
                self._playing = False
                self._set_status("paused")
                self._refresh_ui_state()
                return
            self._play_current_animation(restart=False)

        def _toggle_loop(self):
            self._loop = not self._loop
            self._set_status(f"loop={'on' if self._loop else 'off'}")
            if self._playing:
                self._play_current_animation(restart=True)
            self._refresh_ui_state()

        def _toggle_autoplay(self):
            self._autoplay = not self._autoplay
            self._clip_timer = 0.0
            self._set_status(f"autoplay={'on' if self._autoplay else 'off'}")
            self._refresh_ui_state()

        def _toggle_camera_follow(self):
            self._follow_enabled = not self._follow_enabled
            self._set_status(f"camera_follow={'on' if self._follow_enabled else 'off'}")
            self._refresh_ui_state()

        def _change_speed(self, delta):
            self._play_rate = max(0.1, min(3.5, self._play_rate + float(delta)))
            anim = self._current_anim_key()
            if self._actor and anim:
                self._actor.setPlayRate(self._play_rate, anim)
            self._set_status(f"play_rate={self._play_rate:.2f}")
            self._refresh_ui_state()

        def _step_model(self, step):
            if not self._models:
                return
            self._model_idx = (self._model_idx + int(step)) % len(self._models)
            self._load_current_model()

        def _step_anim(self, step):
            n_anims = len(self._available_anims)
            if n_anims == 0:
                return
            self._anim_idx = (self._anim_idx + int(step)) % n_anims
            self._play_current_animation(restart=True)
            self._refresh_anim_menu()

        def _mark_current_anim_broken(self):
            model_rel = self._models[self._model_idx] if self._models else "none"
            anim_key = self._current_anim_key()
            if not anim_key:
                self._set_status("no animation selected")
                return

            # Ask for reason
            reason = sd.askstring("Mark Broken", "Причина (Вывихнутые суставы / Дубликат / Клиппинг):", 
                                  initialvalue="Вывихнутые суставы")
            if reason is None: # Canceled
                return
            reason = reason.strip() or "No reason provided"

            anim_rel = self._animations.get(anim_key, "unknown")
            report = {
                "model": model_rel,
                "anim_key": anim_key,
                "anim_path": anim_rel,
                "reason": reason,
                "timestamp": str(globalClock.getFrameTime()),
            }

            log_path = Path(project_root) / "dev" / "broken_anims.json"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            data = []
            if log_path.exists():
                try:
                    data = json.loads(log_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            # Prevent duplicates - find and update or append
            found = False
            for i, entry in enumerate(data):
                if entry.get("model") == model_rel and entry.get("anim_key") == anim_key:
                    data[i] = report
                    found = True
                    break
            
            if not found:
                data.append(report)
            
            log_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self._set_status(f"REPORTED: {anim_key}")

        def _reload_current_model(self):
            self._set_status("reloading model")
            self._load_current_model()

        def _short(self, token, max_len=100):
            text = normalize_asset_token(token)
            if len(text) <= max_len:
                return text
            keep = max_len - 3
            return "..." + text[-keep:]

        def _update_status_text(self):
            model_rel = self._models[self._model_idx] if self._models else "-"
            model_display = self._short(model_rel)

            anim_key = self._current_anim_key()
            anim_rel = self._animations.get(anim_key, "") if anim_key else ""
            anim_display = self._short(anim_rel) if anim_rel else "-"

            lines = [
                f"Model [{self._model_idx + 1}/{len(self._models)}]: {model_display}",
                f"Anim [{(self._anim_idx + 1) if anim_key else 0}/{len(self._available_anims)}]: {anim_key or '(none)'}",
                f"Clip path: {anim_display}",
                (
                    f"State: {'playing' if self._playing else 'paused'} | loop={'on' if self._loop else 'off'} | "
                    f"autoplay={'on' if self._autoplay else 'off'} | follow={'on' if self._follow_enabled else 'off'} | "
                    f"rate={self._play_rate:.2f}"
                ),
                (
                    f"Parkour debug: {'on' if self._parkour_debug_visible else 'off'} | "
                    f"Preview IK: {'on' if self._preview_ik_enabled else 'off'}"
                ),
                f"Note: {self._status_note}",
            ]
            self._status_text.setText("\n".join(lines))
            self._refresh_ui_state()

        def _on_tick(self, task):
            dt = max(0.0, float(globalClock.getDt()))
            self._update_orbit_cam(dt)
            self._update_follow_target(dt)
            self._update_preview_ik(dt)
            if self._autoplay and self._playing and len(self._available_anims) > 1:
                self._clip_timer += dt
                if self._clip_timer >= self._clip_seconds:
                    self._clip_timer = 0.0
                    self._step_anim(1)
            self._update_status_text()
            return task.cont

    app = _ViewerApp()
    app.run()
    return 0
