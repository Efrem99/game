"""Player controller, animation driver, and equipment attachment logic."""

import json
import math
import os
import re
import struct
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from utils.core_runtime import gc, HAS_CORE
from direct.actor.Actor import Actor
from direct.showbase.ShowBaseGlobal import globalClock
from .procedural_builder import (
    mk_box,
    mk_cyl,
    mk_cone,
    mk_sphere,
    mk_plane,
    mk_mat,
)
from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Texture,
    TransparencyAttrib,
    LColor,
    Vec3,
)

from entities.mannequin import create_procedural_actor
from entities.animation_manifest import (
    alias_animation_key as manifest_alias_animation_key,
    load_player_manifest_sources,
)
from entities.player_animation_config import (
    ANIM_TOKEN_ALIASES,
    CLIP_START_FRAME_HINTS,
    STATE_ANIM_FALLBACK,
)
from entities.player_audio_mixin import PlayerAudioMixin
from entities.player_combat_mixin import PlayerCombatMixin
from entities.player_input_mixin import PlayerInputMixin
from entities.player_movement_mixin import PlayerMovementMixin
from entities.player_state_machine_mixin import PlayerStateMachineMixin
from entities.character_brain import CharacterBrain
from render.fx_policy import (
    is_melee_wheel_token,
    load_optional_texture,
    make_soft_disc_texture,
    should_cast_selected_spell,
)
from render.model_visuals import ensure_model_visual_defaults
from utils.asset_pathing import prefer_bam_path
from utils.logger import logger
from utils.runtime_paths import is_user_data_mode, runtime_file
from managers.runtime_data_access import load_data_file


@lru_cache(maxsize=32)
def _load_glb_json_payload(path_token):
    path = Path(str(path_token or "").strip())
    if (not path_token) or path.suffix.lower() != ".glb" or (not path.exists()):
        return {}
    try:
        with path.open("rb") as handle:
            _magic, _version, _length = struct.unpack("<III", handle.read(12))
            chunk_len, chunk_type = struct.unpack("<II", handle.read(8))
            if chunk_type != 0x4E4F534A:
                return {}
            return json.loads(handle.read(chunk_len).decode("utf-8"))
    except Exception:
        return {}


@lru_cache(maxsize=32)
def _glb_skin_joint_names(path_token):
    payload = _load_glb_json_payload(path_token)
    if not isinstance(payload, dict):
        return ()

    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    joint_names = []
    for skin in payload.get("skins", []) if isinstance(payload, dict) else []:
        if not isinstance(skin, dict):
            continue
        for index in skin.get("joints", []):
            if isinstance(index, int) and 0 <= index < len(nodes):
                name = str((nodes[index] or {}).get("name") or "").strip()
                if name:
                    joint_names.append(name)
    return tuple(joint_names)


@lru_cache(maxsize=32)
def _looks_like_blender_placeholder_export(path_token):
    payload = _load_glb_json_payload(path_token)
    if not isinstance(payload, dict):
        return False

    meshes = payload.get("meshes", [])
    accessors = payload.get("accessors", [])
    if not isinstance(meshes, list) or not isinstance(accessors, list):
        return False

    mesh_names = []
    pos_mins = []
    pos_maxs = []
    for mesh in meshes:
        if not isinstance(mesh, dict):
            continue
        mesh_name = str(mesh.get("name", "") or "").strip()
        if mesh_name:
            mesh_names.append(mesh_name)
        for prim in mesh.get("primitives", []) or []:
            if not isinstance(prim, dict):
                continue
            attrs = prim.get("attributes", {})
            if not isinstance(attrs, dict):
                continue
            pos_idx = attrs.get("POSITION")
            if not isinstance(pos_idx, int) or pos_idx < 0 or pos_idx >= len(accessors):
                continue
            accessor = accessors[pos_idx]
            if not isinstance(accessor, dict):
                continue
            mins = accessor.get("min")
            maxs = accessor.get("max")
            if isinstance(mins, list) and len(mins) >= 3:
                pos_mins.append(tuple(float(v) for v in mins[:3]))
            if isinstance(maxs, list) and len(maxs) >= 3:
                pos_maxs.append(tuple(float(v) for v in maxs[:3]))

    if not mesh_names or not pos_mins or not pos_maxs:
        return False

    size = []
    for axis in range(3):
        axis_min = min(v[axis] for v in pos_mins)
        axis_max = max(v[axis] for v in pos_maxs)
        size.append(max(0.0, float(axis_max - axis_min)))

    if not all(0.85 <= axis <= 1.15 for axis in size):
        return False

    markers = ("sphere", "cube", "plane", "сфера", "куб", "плоск")
    suspicious_name_hits = 0
    has_generic_mesh = False
    for raw_name in mesh_names:
        name = str(raw_name or "").strip().lower()
        if not name:
            continue
        if name.startswith("mesh"):
            has_generic_mesh = True
        if any(marker in name for marker in markers):
            suspicious_name_hits += 1

    if suspicious_name_hits <= 0:
        return False
    if has_generic_mesh and suspicious_name_hits < len(mesh_names):
        return False
    return suspicious_name_hits >= max(2, len(mesh_names) - 1)


def _glb_contains_xbot_skin(candidate_path, reference_path):
    candidate_joints = set(_glb_skin_joint_names(candidate_path))
    reference_joints = set(_glb_skin_joint_names(reference_path))
    if not candidate_joints or not reference_joints:
        return False
    return reference_joints.issubset(candidate_joints)


class Player(
    PlayerStateMachineMixin,
    PlayerMovementMixin,
    PlayerInputMixin,
    PlayerAudioMixin,
    PlayerCombatMixin,
):
    def __init__(
        self,
        app,
        render,
        loader,
        char_state,
        phys,
        combat,
        parkour,
        magic,
        particles,
        parkour_state,
    ):
        self.app = app
        self.render = render
        self.loader = loader
        self.data_mgr = app.data_mgr
        self.cs = char_state
        self.phys = phys
        self.combat = combat
        self.parkour = parkour
        self.magic = magic
        self.particles = particles
        self.ps = parkour_state
        self._debug_disable_player_animation = bool(
            getattr(app, "_debug_disable_player_animation", False)
        )


        self.walk_speed = self.data_mgr.get_move_param("walk_speed") or 5.0
        self.run_speed = self.data_mgr.get_move_param("run_speed") or 9.0
        self.flight_speed = self.data_mgr.get_move_param("flight_speed") or 15.0
        self.flight_shift_mult = self.data_mgr.get_move_param("flight_shift_mult") or 1.45

        self._anim_state = "idle"
        self._anim_clip = ""
        self._last_safe_anim_state = "idle"
        self._last_safe_anim_clip = ""
        self._anim_blend_enabled = False
        self._anim_blend_duration = 0.18
        self._anim_blend_transition = None
        self._anim_effect_clips = set()
        self._available_anims = set()
        self._broken_binding_anims = []
        self._state_anim_tokens = {}
        self._state_anim_overrides = {}
        self._state_anim_hints = {}
        self._manifest_anim_loop_hints = {}
        self._anim_resolution_mode = "uninitialized"
        self._anim_resolution_source = ""
        self._anim_resolution_requested_state = ""
        self._anim_resolution_clip = ""
        self._anim_degraded_once = set()
        self._anim_emergency_once = set()
        self._weapon_transition_missing_once = set()
        self._state_defs = {}
        self._state_transitions = []
        self._state_rules = []
        self._queued_state_triggers = []
        self._state_lock_until = 0.0
        self._last_landing_impact_speed = 0.0
        self._block_pressed = False
        self._was_wallrun = False
        self._parkour_last_action = ""
        self._parkour_exit_hint_until = 0.0
        self._parkour_ik_alpha = 0.0
        self._parkour_ik_controls = {}
        self._state_anim_fallback = {
            key: list(value) for key, value in STATE_ANIM_FALLBACK.items()
        }
        self._anim_token_aliases = {
            key: list(value) for key, value in ANIM_TOKEN_ALIASES.items()
        }
        self._trail_data = None

        self._dash_fx_until = 0.0
        self._dash_fx_alpha = 0.0
        self._dash_fx_heading = 0.0
        self._was_in_water = False
        self._is_flying = False
        self._flight_takeoff_until = 0.0
        self._flight_land_until = 0.0
        self._visual_height_offset = 0.0
        self._stealth_crouch = False
        self._stealth_crouch_hold_latched = False
        self._stealth_crouch_hold_prev = False
        self._weapon_drawn = False
        self._drawn_hold_timer = 0.0
        self._flight_fx_on = False
        self._footstep_timer = 0.0
        self._was_grounded = True
        self._mount_anim_kind = ""
        self._equipment_state = {
            "weapon_main": "",
            "offhand": "",
            "chest": "",
            "trinket": "",
        }

        # Economy & inventory
        self.gold = 100
        self.inventory = []  # List of item dicts from data/items/

        # Bone / Joint placeholders
        self._right_hand = None
        self._left_hand = None
        self._left_hip = None
        self._head = None
        self._spine_upper = None

        self._sword_hand_anchor = None
        self._shield_hand_anchor = None
        self._sword_sheath_anchor = None
        self._shield_sheath_anchor = None
        self._head_node = None
        self._armor_node = None
        self._sword_node = None
        self._shield_node = None
        self._trinket_node = None
        self._hips = None
        self._bodywear_node = None
        self._legwear_node = None

        self._has_weapon_visual = False
        self._has_offhand_visual = False
        self._weapon_visual_style = "blade"
        self._offhand_visual_style = "ward"
        self._armor_visual_style = "light"
        self._trinket_visual_style = "charm"
        self._anim_failed_once = set()
        self._anim_missing_state_once = set()
        self._anim_blend_skipped_once = set()
        self._anim_transition_logged = None
        self._anim_dropout_logged = None
        self._anim_no_clip_time = 0.0
        self._motion_plan = {}
        self._last_turn_trigger_time = 0.0
        self._brain_last_pos = None
        # ContextFlags (updated each FSM tick by _update_context_flags)
        self._context_flags: set = set()
        self._env_flags: set = set()   # injected by world/app for surface context
        # Pending spell staging (Prepare → Release)
        self._pending_spell = None
        self._pending_spell_release_time = 0.0

        self._shadow_mode = False
        self._shadow_aura_vfx = None

        self._keys = {}
        self._consumed = {}
        self._spell_cache = []
        self._active_spell_idx = 0
        self._ultimate_spell_idx = 0
        self._spell_cooldowns = {}
        self._spell_cast_lock_until = 0.0
        self._last_combat_event = None
        self._next_cast_hand = "right"
        self._next_weapon_hand = "right"
        self._combo_chain = 0
        self._combo_deadline = 0.0
        self._combo_style = "unarmed"
        self._combo_kind = "melee"
        self._last_hp_observed = None
        self._pending_damage_ratio = 0.0
        self._incoming_damage_type = ""
        self._incoming_damage_amount = 0.0
        self._damage_vignette_type = ""
        self._damage_vignette_intensity = 0.0
        self._dead_flag = False
        self._death_time = 0.0
        self._respawn_delay = 4.0
        self._respawn_requested = False
        if self.cs and hasattr(self.cs, "health"):
            try:
                self._last_hp_observed = float(self.cs.health)
            except Exception:
                self._last_hp_observed = None
        self._skill_wheel_open = False
        self._skill_wheel_hover_idx = None
        self._skill_wheel_preview_idx = None
        self._is_aiming = False
        self._aim_mode = ""
        skill_wheel_key = self.data_mgr.get_binding("skill_wheel") or "tab"
        self._skill_wheel_hint_key = str(skill_wheel_key).upper()
        self._spell_type_alias = {
            "fireball": "Fireball",
            "lightning": "LightningBolt",
            "lightningbolt": "LightningBolt",
            "ice": "IceShards",
            "iceshards": "IceShards",
            "nova": "ForceWave",
            "forcewave": "ForceWave",
            "ward": "HealingAura",
            "healing": "HealingAura",
            "healingaura": "HealingAura",
            "phase": "PhaseStep",
            "phasestep": "PhaseStep",
            "meteor": "MeteorStrike",
            "meteorstrike": "MeteorStrike",
        }
        self.brain = CharacterBrain(self.app, self)

        self._build_character()
        self._apply_starting_equipment()
        self._setup_sword_trail()
        self._setup_input()
        self._build_flight_vfx()
        self._build_dash_vfx()
        self._refresh_spell_cache()

    def set_shadow_mode(self, active=True):
        """Toggle Sherward's dark/shadow version."""
        if self._shadow_mode == active:
            return
            
        self._shadow_mode = active
        self._update_shadow_visuals()
        
        # Log the transformation
        mode_str = "SHADOW" if active else "NORMAL"
        logger.info(f"[Player] Sherward shifted to {mode_str} mode")

    def _update_shadow_visuals(self):
        """Apply visual changes for shadow mode (darkening + aura)."""
        if not self.actor:
            return
            
        if self._shadow_mode:
            # Shift to dark silhouette: nearly black with a slight purple/blue tint
            self.actor.setColorScale(0.12, 0.08, 0.18, 1.0)
            
            # Spawn shadowy aura if not already present
            if not self._shadow_aura_vfx and self.magic:
                self._shadow_aura_vfx = self.magic.spawn_shadow_aura_vfx(self.actor)
        else:
            # Revert to normal colors
            self.actor.clearColorScale()
            
            # Cleanup aura
            if self._shadow_aura_vfx:
                try:
                    self._shadow_aura_vfx.cleanup()
                except:
                    pass
                self._shadow_aura_vfx = None

    def _alias_animation_key(self, stem):
        return manifest_alias_animation_key(stem)

    def _collect_optional_animation_sources(self):
        manifest_mapping, strict_mode = self._load_manifest_animation_sources()
        candidates = dict(manifest_mapping)
        if strict_mode:
            return candidates
        search_dirs = [
            Path("assets/anims"),
            Path("assets/models/xbot"),
        ]
        patterns = ("*.glb", "*.gltf", "*.bam", "*.fbx")

        for directory in search_dirs:
            if not directory.exists():
                continue
            for pattern in patterns:
                for path in directory.glob(pattern):
                    if path.stem.lower() in {"xbot", "character"}:
                        continue
                    key = self._alias_animation_key(path.stem)
                    if not key or key in {"idle", "walk", "run"}:
                        continue
                    candidates.setdefault(key, prefer_bam_path(path.as_posix()))
        return candidates

    def _load_manifest_animation_sources(self):
        manifest_payload = {}
        getter = getattr(self.data_mgr, "get_player_animation_manifest", None)
        if callable(getter):
            try:
                value = getter()
                if isinstance(value, dict):
                    manifest_payload = value
            except Exception as exc:
                logger.warning(f"[Anim] Failed to read player animation manifest from DataManager: {exc}")
        mapping, strict_mode, diagnostics = load_player_manifest_sources(
            manifest_path="data/actors/player_animations.json",
            manifest_payload=manifest_payload if manifest_payload else None,
            require_existing_files=True,
        )
        for message in diagnostics:
            logger.warning(f"[Anim] {message}")
        return mapping, strict_mode

    def _player_model_config(self):
        cfg = {}
        getter = getattr(self.data_mgr, "get_player_config", None)
        if callable(getter):
            try:
                value = getter()
                if isinstance(value, dict):
                    cfg = value
            except Exception as exc:
                logger.warning(f"[Player] Failed to read player config from DataManager: {exc}")
        if not cfg:
            try:
                payload = load_data_file(self.app, "actors/player.json", default={})
                if isinstance(payload, dict):
                    nested = payload.get("player", payload)
                    if isinstance(nested, dict):
                        cfg = nested
            except Exception as exc:
                logger.warning(f"[Player] Failed to read actors/player.json via runtime data access: {exc}")
        return cfg if isinstance(cfg, dict) else {}

    def _resolve_player_model_candidates(self):
        cfg = self._player_model_config()
        raw_model = str(cfg.get("model", "") or "").strip()
        raw_fallback_model = str(cfg.get("fallback_model", "") or "").strip()
        raw_candidates = cfg.get("model_candidates")
        candidates = []

        def _add(path_token):
            token = str(path_token or "").strip().replace("\\", "/")
            if not token:
                return
            if token not in candidates:
                candidates.append(token)

        if isinstance(raw_candidates, list):
            for item in raw_candidates:
                _add(item)

        if raw_model:
            _add(raw_model)
            if raw_model.startswith("./"):
                _add(raw_model[2:])
            if raw_model.startswith("models/"):
                _add(f"assets/{raw_model}")
            if not raw_model.startswith("assets/"):
                _add(f"assets/{raw_model}")

            if Path(raw_model).name.lower() == "xbot.glb":
                _add("assets/models/xbot/Xbot.glb")

        if raw_fallback_model:
            _add(raw_fallback_model)
            if raw_fallback_model.startswith("./"):
                _add(raw_fallback_model[2:])
            if raw_fallback_model.startswith("models/"):
                _add(f"assets/{raw_fallback_model}")
            if not raw_fallback_model.startswith("assets/"):
                _add(f"assets/{raw_fallback_model}")

        _add("assets/models/xbot/Xbot.glb")

        def _is_xbot_candidate(path_token):
            token = str(path_token or "").strip().replace("\\", "/").lower()
            return ("xbot/" in token) or token.endswith("/xbot.glb") or token.endswith("xbot.glb")

        def _is_xbot_compatible_hero_candidate(path_token):
            token = str(path_token or "").strip().replace("\\", "/")
            if not token or _is_xbot_candidate(token):
                return False
            try:
                return _glb_contains_xbot_skin(token, "assets/models/xbot/Xbot.glb")
            except Exception:
                return False

        filtered_candidates = []
        rejected_placeholder_candidates = []
        for token in candidates:
            if _is_xbot_candidate(token):
                filtered_candidates.append(token)
                continue
            if _looks_like_blender_placeholder_export(token):
                rejected_placeholder_candidates.append(token)
                continue
            filtered_candidates.append(token)
        if filtered_candidates:
            candidates = filtered_candidates
        for token in rejected_placeholder_candidates:
            logger.warning(
                "[Player] Skipping suspicious hero runtime candidate that looks like a Blender "
                f"placeholder export: {token}"
            )

        explicit_hero_runtime = str(os.environ.get("XBOT_PREFER_HERO_RUNTIME_MODEL", "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        raw_base_anims = cfg.get("base_anims")
        base_anim_tokens = []
        if isinstance(raw_base_anims, dict):
            for value in raw_base_anims.values():
                token = str(value or "").strip().replace("\\", "/").lower()
                if token:
                    base_anim_tokens.append(token)
        uses_xbot_base_anims = any(("xbot/" in token) or token.endswith("/xbot.glb") or token.endswith("xbot.glb") for token in base_anim_tokens)

        has_xbot_candidate = any(_is_xbot_candidate(item) for item in candidates)
        has_xbot_compatible_hero_candidate = any(_is_xbot_compatible_hero_candidate(item) for item in candidates)
        should_prioritize_xbot = has_xbot_candidate and (
            uses_xbot_base_anims
            or ((not HAS_CORE) and has_xbot_candidate)
        )
        if should_prioritize_xbot and (not explicit_hero_runtime) and len(candidates) > 1:
            keep_hero_first = bool(HAS_CORE and uses_xbot_base_anims and has_xbot_compatible_hero_candidate)
            xbot_candidates = [token for token in candidates if _is_xbot_candidate(token)]
            other_candidates = [token for token in candidates if not _is_xbot_candidate(token)]
            if keep_hero_first and other_candidates:
                if not getattr(self, "_logged_xbot_runtime_priority", False):
                    logger.info(
                        "[Player] Keeping Sherward-compatible runtime model first because its skeleton contains "
                        "the full XBot animation rig. XBot remains as fallback if the hero actor still fails to load."
                    )
                    setattr(self, "_logged_xbot_runtime_priority", True)
            elif xbot_candidates and other_candidates:
                if not getattr(self, "_logged_xbot_runtime_priority", False):
                    if uses_xbot_base_anims:
                        logger.info(
                            "[Player] Using XBot runtime model because locomotion clips still come from XBot. "
                            "Set XBOT_PREFER_HERO_RUNTIME_MODEL=1 only for explicit hero-rig experiments."
                        )
                    elif not HAS_CORE:
                        logger.info(
                            "[Player] Using XBot runtime model because the compiled core is unavailable. "
                            "Set XBOT_PREFER_HERO_RUNTIME_MODEL=1 only for explicit hero-rig experiments."
                        )
                    setattr(self, "_logged_xbot_runtime_priority", True)
                candidates = xbot_candidates + other_candidates

        return candidates

    def _actor_bounds_metrics(self, actor_np):
        try:
            mins, maxs = actor_np.getTightBounds()
        except Exception:
            return None
        if mins is None or maxs is None:
            return None
        size = maxs - mins
        return (
            abs(float(size.x)),
            abs(float(size.y)),
            abs(float(size.z)),
        )

    def _is_actor_bounds_playable(self, model_path, actor_np):
        metrics = self._actor_bounds_metrics(actor_np)
        if metrics is None:
            return False
        width, depth, height = metrics
        if width <= 0.02 or depth <= 0.02 or height <= 0.20:
            return False

        token = str(model_path or "").replace("\\", "/").lower()
        # Sherward source can occasionally export as a near-flat ribbon mesh.
        # Reject this at load-time and continue to the next fallback candidate.
        if "hero/sherward" in token:
            if width < 0.45 or depth < 0.16:
                return False
        return True

    def _stabilize_actor_bounds(self, model_path):
        """Apply a conservative shape correction for heavily flattened hero meshes."""
        if not self.actor:
            return
        try:
            mins, maxs = self.actor.getTightBounds()
        except Exception:
            return
        if mins is None or maxs is None:
            return

        size = maxs - mins
        width = abs(float(size.x))
        depth = abs(float(size.y))
        height = abs(float(size.z))
        if width <= 1e-4 or depth <= 1e-4 or height <= 1e-4:
            return
        # Sherward export can come in overly flattened on Y, making the body nearly invisible
        # from gameplay camera angles. Keep this correction mild and bounded.
        is_sherward = "hero/sherward" in str(model_path or "").replace("\\", "/").lower()
        if not is_sherward:
            return

        # Apply a persistent visual height offset for Sherward variants.
        # This helps with models that have their pivot point at the base.
        try:
            self._visual_height_offset = 0.95
            self.actor.setZ(self.actor.getZ() + self._visual_height_offset)
            logger.info(
                "[Player] Applied Sherward mesh height correction: "
                f"visual_z+={self._visual_height_offset:.2f} (w={width:.3f}, d={depth:.3f}, h={height:.3f})"
            )
        except Exception:
            pass

    def _build_character(self):
        base_anims = self._resolve_base_anims()
        model_candidates = self._resolve_player_model_candidates()
        player_scale = self._resolve_player_scale()
        try:
            self.actor = None
            load_errors = []
            loaded_model_path = ""
            for model_path in model_candidates:
                try:
                    logger.info(f"[Player] Loading actor model: {model_path}")
                    candidate = Actor(model_path, base_anims)
                    if not self._is_actor_bounds_playable(model_path, candidate):
                        metrics = self._actor_bounds_metrics(candidate)
                        if hasattr(candidate, "cleanup"):
                            try:
                                candidate.cleanup()
                            except Exception:
                                pass
                        try:
                            candidate.removeNode()
                        except Exception:
                            pass
                        load_errors.append(
                            f"{model_path}: unusable bounds {metrics or '(none)'}"
                        )
                        logger.warning(
                            f"[Player] Rejected model due to unusable bounds: {model_path} metrics={metrics}"
                        )
                        continue
                    self.actor = candidate
                    loaded_model_path = model_path
                    break
                except Exception as exc:
                    load_errors.append(f"{model_path}: {exc}")
                    continue

            if self.actor is None:
                raise RuntimeError("; ".join(load_errors) if load_errors else "No model candidates available")

            self.actor.setScale(player_scale)
            self._loaded_player_model_path = str(loaded_model_path or "")
            self._stabilize_actor_bounds(loaded_model_path)
            logger.info(f"### [Player] Final Actor Loaded: model={loaded_model_path}, scale={player_scale:.3f} ###")
            optional_anims = self._collect_optional_animation_sources()
            if optional_anims:
                loaded = 0
                for anim_key, anim_path in optional_anims.items():
                    try:
                        self.actor.loadAnims({anim_key: anim_path})
                        loaded += 1
                    except Exception as exc:
                        logger.warning(
                            f"[Anim] Failed to load optional animation "
                            f"'{anim_key}' from '{anim_path}': {exc}"
                        )
                        continue
                if loaded:
                    logger.info(f"[Anim] Loaded optional external animations: {loaded}")
        except Exception as e:
            logger.error(f"Failed to load player actor model: {e}. Using procedural mannequin.")
            (
                self.actor,
                self._r_leg,
                self._l_leg,
                self._r_arm,
                self._l_arm,
                self._right_hand,
            ) = create_procedural_actor(self.render)
            self._proc_root = self.actor

        self.actor.reparentTo(self.render)
        
        # Let the actor use the default panda3d shader pipeline
        # instead of forcing the terrain shader, which caused the white silhouette issue.
        self.actor.set_shader_input("specular_factor", 0.28, priority=1000)
        self.actor.set_shader_input("roughness", 0.72, priority=1000)
        ensure_model_visual_defaults(
            self.actor,
            apply_skin=True,
            debug_label="player_actor",
        )
        # In Python-only mode we occasionally get overly dark skinned actors under PBR.
        # Keep animated actors skinned in Python-only mode.
        self._apply_non_core_actor_visual_fallback()

        self._resolve_attachment_nodes()
        self._build_equipment_visuals()
        self._init_animation_system()


    def _apply_non_core_actor_visual_fallback(self):
        if HAS_CORE or not getattr(self, "actor", None):
            return

        actor_np = self.actor
        is_animated_actor = False
        try:
            is_animated_actor = isinstance(actor_np, Actor)
        except Exception:
            is_animated_actor = False
        if not is_animated_actor:
            is_animated_actor = all(
                hasattr(actor_np, attr) for attr in ("getAnimNames", "loop", "play")
            )

        # Important: forcing ShaderOff on skinned actors can lock them in bind/T-pose.
        if not is_animated_actor:
            try:
                actor_np.setShaderOff(1002)
            except Exception:
                pass

        try:
            # Keep the actor readable. Darkening the whole runtime model makes
            # the player collapse into a silhouette against already broken
            # high-contrast scenes and gets mistaken for "shadow mode".
            actor_np.clearColorScale()
        except Exception:
            pass
        try:
            actor_np.setTwoSided(True)
        except Exception:
            pass

    def _load_player_state_animation_tokens(self):
        getter = getattr(self.data_mgr, "get_player_state_config", None)
        payload = {}
        if callable(getter):
            try:
                value = getter()
                if isinstance(value, dict):
                    payload = value
            except Exception as exc:
                logger.warning(f"[Anim] Failed to read player state config from DataManager: {exc}")
        if not payload:
            payload = load_data_file(self.app, "states/player_states.json", default={})
        if not isinstance(payload, dict) or not payload:
            self._state_defs = {}
            self._state_transitions = []
            self._state_rules = []
            return {}

        mapping = {}
        self._state_defs = {}
        states = payload.get("states", []) if isinstance(payload, dict) else []
        for entry in states:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip().lower()
            anim = str(entry.get("animation", "")).strip()
            if name and anim:
                mapping[name] = anim
            if name:
                self._state_defs[name] = dict(entry)

        transitions = payload.get("transitions", []) if isinstance(payload, dict) else []
        self._state_transitions = []
        for item in transitions:
            if not isinstance(item, dict):
                continue
            to_state = str(item.get("to", "")).strip().lower()
            if not to_state:
                continue
            from_states = item.get("from", [])
            if isinstance(from_states, str):
                from_list = [from_states.strip().lower()]
            elif isinstance(from_states, list):
                from_list = [str(v).strip().lower() for v in from_states if str(v).strip()]
            else:
                from_list = []

            trigger = item.get("trigger")
            condition = item.get("condition")
            rule = {"from": from_list, "to": to_state}
            if isinstance(trigger, str) and trigger.strip():
                rule["trigger"] = trigger.strip().lower()
            if isinstance(condition, str) and condition.strip():
                rule["condition"] = condition.strip()
            try:
                rule["priority"] = int(item.get("priority", 100))
            except Exception:
                rule["priority"] = 100
            if bool(item.get("force", False)):
                rule["force"] = True
            self._state_transitions.append(rule)

        rules = payload.get("rules", []) if isinstance(payload, dict) else []
        self._state_rules = []
        for item in rules:
            if not isinstance(item, dict):
                continue
            to_state = str(item.get("to", "")).strip().lower()
            if not to_state:
                continue
            from_states = item.get("from", ["*"])
            if isinstance(from_states, str):
                from_list = [from_states.strip().lower()]
            elif isinstance(from_states, list):
                from_list = [str(v).strip().lower() for v in from_states if str(v).strip()]
            else:
                from_list = ["*"]

            trigger = item.get("trigger")
            condition = item.get("condition")
            rule = {"from": from_list, "to": to_state}
            if isinstance(trigger, str) and trigger.strip():
                rule["trigger"] = trigger.strip().lower()
            if isinstance(condition, str) and condition.strip():
                rule["condition"] = condition.strip()
            try:
                rule["priority"] = int(item.get("priority", 100))
            except Exception:
                rule["priority"] = 100
            if bool(item.get("force", False)):
                rule["force"] = True
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                rule["name"] = name.strip()
            self._state_rules.append(rule)
        return mapping

    def _load_actor_animation_overrides(self):
        getter = getattr(self.data_mgr, "get_player_animation_manifest", None)
        payload = {}
        if callable(getter):
            try:
                value = getter()
                if isinstance(value, dict):
                    payload = value
            except Exception as exc:
                logger.warning(f"[Anim] Failed to read player animation manifest from DataManager: {exc}")
        if not payload:
            payload = load_data_file(self.app, "actors/player_animations.json", default={})
        if not isinstance(payload, dict) or not payload:
            return {}

        player_map = payload.get("player", {}) if isinstance(payload, dict) else {}
        if not isinstance(player_map, dict):
            return {}

        generic_tags = {
            "combat",
            "parkour",
            "magic",
            "shield",
            "social",
            "enemy",
            "character",
            "player",
        }

        mapping = {}
        for state_name, raw_value in player_map.items():
            state_key = str(state_name or "").strip().lower()
            if not state_key:
                continue

            candidates = []
            if isinstance(raw_value, str):
                candidates.append(raw_value)
            elif isinstance(raw_value, list):
                for item in raw_value:
                    if isinstance(item, str):
                        candidates.append(item)
            elif isinstance(raw_value, dict):
                for field in ("animation", "clip", "name", "id"):
                    value = raw_value.get(field)
                    if isinstance(value, str):
                        candidates.append(value)
                aliases = raw_value.get("aliases")
                if isinstance(aliases, list):
                    for item in aliases:
                        if isinstance(item, str):
                            candidates.append(item)

            cleaned = []
            seen = set()
            for candidate in candidates:
                token = str(candidate or "").strip()
                if not token:
                    continue
                marker = token.lower()
                if marker in seen:
                    continue
                seen.add(marker)
                cleaned.append(token)

            filtered = []
            for token in cleaned:
                compact = self._normalize_anim_key(token)
                if compact in generic_tags:
                    continue
                filtered.append(token)

            usable = filtered if filtered else cleaned
            if usable:
                mapping[state_key] = usable
        return mapping

    def _load_manifest_loop_hints(self):
        getter = getattr(self.data_mgr, "get_player_animation_manifest", None)
        payload = {}
        if callable(getter):
            try:
                value = getter()
                if isinstance(value, dict):
                    payload = value
            except Exception as exc:
                logger.warning(f"[Anim] Failed to read loop hints from DataManager: {exc}")
        if not payload:
            payload = load_data_file(self.app, "actors/player_animations.json", default={})
        if not isinstance(payload, dict) or not payload:
            return {}

        manifest = payload.get("manifest", {}) if isinstance(payload, dict) else {}
        sources = manifest.get("sources", []) if isinstance(manifest, dict) else []
        if not isinstance(sources, list):
            return {}

        hints = {}
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            loop_value = entry.get("loop")
            if not isinstance(loop_value, bool):
                continue

            key_raw = entry.get("key") or entry.get("state") or entry.get("id") or ""
            key = self._normalize_anim_key(key_raw)
            if key:
                hints[key] = loop_value

            clip_path = str(
                entry.get("path") or entry.get("file") or entry.get("src") or ""
            ).strip()
            if clip_path:
                stem_key = self._normalize_anim_key(Path(clip_path).stem)
                if stem_key and stem_key not in hints:
                    hints[stem_key] = loop_value
                alias_key = self._normalize_anim_key(self._alias_animation_key(Path(clip_path).stem))
                if (
                    alias_key
                    and alias_key not in hints
                    and not (
                        alias_key in {"idle", "walk", "run"}
                        and key
                        and alias_key != key
                    )
                ):
                    hints[alias_key] = loop_value
        return hints

    def _normalize_anim_key(self, token):
        return "".join(ch for ch in str(token or "").lower() if ch.isalnum())

    def _state_loop_hint(self, state_name, resolved_clip=""):
        hints = getattr(self, "_manifest_anim_loop_hints", {})
        if not isinstance(hints, dict) or not hints:
            return None

        probe_tokens = []

        clip_token = self._normalize_anim_key(resolved_clip)
        if clip_token:
            probe_tokens.append(clip_token)

        state_token = self._normalize_anim_key(state_name)
        if state_token:
            probe_tokens.append(state_token)

        state_anim_tokens = getattr(self, "_state_anim_tokens", {})
        if isinstance(state_anim_tokens, dict):
            mapped = state_anim_tokens.get(str(state_name or "").strip().lower())
            if isinstance(mapped, list):
                for item in mapped:
                    token = self._normalize_anim_key(item)
                    if token:
                        probe_tokens.append(token)
            else:
                token = self._normalize_anim_key(mapped)
                if token:
                    probe_tokens.append(token)

        seen = set()
        for token in probe_tokens:
            if not token or token in seen:
                continue
            seen.add(token)
            value = hints.get(token)
            if isinstance(value, bool):
                return value
        return None

    def _init_animation_system(self):
        if not hasattr(self.actor, "loop"):
            return

        self._state_anim_tokens = self._load_player_state_animation_tokens()
        self._state_anim_overrides = self._load_actor_animation_overrides()
        self._manifest_anim_loop_hints = self._load_manifest_loop_hints()

        try:
            declared_anims = [str(name) for name in self.actor.getAnimNames()]
        except Exception:
            declared_anims = []

        available_anims = set()
        broken_binding_anims = []
        self._anim_control_audit_deferred = self._should_defer_full_anim_control_audit(declared_anims)
        if self._anim_control_audit_deferred:
            available_anims = {
                str(anim_name or "").strip()
                for anim_name in declared_anims
                if str(anim_name or "").strip()
            }
            audit_targets = self._startup_anim_control_audit_targets(declared_anims)
            for anim_name in audit_targets:
                try:
                    control = self.actor.getAnimControl(anim_name)
                except Exception:
                    control = None
                if control:
                    available_anims.add(anim_name)
                else:
                    available_anims.discard(anim_name)
                    broken_binding_anims.append(anim_name)
            if audit_targets:
                logger.info(
                    "[Anim] Deferred full AnimControl audit for %d declared clips. "
                    "Probed %d startup-critical clips so the first gameplay frame does not stall.",
                    len(available_anims),
                    len(audit_targets),
                )
        else:
            for anim_name in declared_anims:
                token = str(anim_name or "").strip()
                if not token:
                    continue
                try:
                    control = self.actor.getAnimControl(token)
                except Exception:
                    control = None
                if control:
                    available_anims.add(token)
                else:
                    broken_binding_anims.append(token)
        self._available_anims = available_anims
        self._broken_binding_anims = broken_binding_anims
        if broken_binding_anims:
            preview = ", ".join(sorted(broken_binding_anims)[:8])
            more = max(0, len(broken_binding_anims) - 8)
            suffix = f" (+{more} more)" if more else ""
            logger.warning(
                "[Anim] Ignoring declared animation names that have no live AnimControl on the current actor: "
                f"{preview}{suffix}"
            )

        anim_cfg = self.data_mgr.controls.get("animation", {})
        if isinstance(anim_cfg, dict):
            try:
                raw = float(anim_cfg.get("blend_time", self._anim_blend_duration) or self._anim_blend_duration)
                self._anim_blend_duration = max(0.02, min(1.2, raw))
            except Exception:
                pass

        self._anim_blend_enabled = False
        if hasattr(self.actor, "enableBlend") and hasattr(self.actor, "setControlEffect"):
            try:
                self.actor.enableBlend()
                self._anim_blend_enabled = True
                if not getattr(self, "_logged_player_blend_enabled", False):
                    logger.info(
                        "[Anim] Player clip blending enabled. Runtime now crossfades between compatible clips "
                        "instead of snapping through bind pose."
                    )
                    self._logged_player_blend_enabled = True
            except Exception as exc:
                self._anim_blend_enabled = False
                logger.warning(
                    f"[Anim] Player blend playback could not be enabled, using direct clip playback instead: {exc}"
                )

        self._write_animation_coverage_report()
        playback_block_reason = self._noncore_animation_playback_block_reason()
        if playback_block_reason:
            logger.warning(f"[Anim] Player animation playback disabled: {playback_block_reason}")
            logger.info("[Anim] Player visual readiness reached, but gameplay reveal is still pending app finalization.")
            return
        if self._force_safe_idle_anim():
            logger.info("[Anim] Player idle fallback prepared successfully.")
        else:
            logger.info("[Anim] Player animation stack initialized without idle fallback.")

    def _should_defer_full_anim_control_audit(self, declared_anims):
        cleaned = [str(name or "").strip() for name in (declared_anims or []) if str(name or "").strip()]
        return len(cleaned) >= 48

    def _startup_anim_control_audit_targets(self, declared_anims):
        cleaned = [str(name or "").strip() for name in (declared_anims or []) if str(name or "").strip()]
        if not cleaned:
            return []

        available_lower = {name.lower(): name for name in cleaned}
        available_norm = {self._normalize_anim_key(name): name for name in cleaned}
        targets = []
        seen = set()

        def _push(raw_token):
            token = str(raw_token or "").strip()
            if not token:
                return
            resolved = available_lower.get(token.lower())
            if not resolved:
                resolved = available_norm.get(self._normalize_anim_key(token))
            if not resolved:
                return
            marker = resolved.lower()
            if marker in seen:
                return
            seen.add(marker)
            targets.append(resolved)

        for state_name in ("idle", "walking", "running"):
            _push(state_name)
            _push(getattr(self, "_state_anim_tokens", {}).get(state_name))

        for base_clip in ("idle", "walk", "run"):
            _push(base_clip)
        return targets

    def _classify_anim_resolution(self, source):
        token = str(source or "").strip().lower()
        if token in {"state_fallback", "global_fallback"}:
            return "degraded_single_clip"
        if token:
            return "ok"
        return "missing"

    def _record_anim_resolution(self, state_name, clip, source):
        target_state = str(state_name or "idle").strip().lower()
        resolved_clip = str(clip or "").strip()
        resolved_source = str(source or "").strip()
        mode = self._classify_anim_resolution(resolved_source)

        self._anim_resolution_mode = mode
        self._anim_resolution_source = resolved_source
        self._anim_resolution_requested_state = target_state
        self._anim_resolution_clip = resolved_clip

        if mode == "degraded_single_clip":
            marker = (target_state, resolved_clip, resolved_source)
            if marker not in self._anim_degraded_once:
                self._anim_degraded_once.add(marker)
                logger.warning(
                    "[Anim][DEGRADED] State '%s' has no dedicated compatible clip on the current actor. "
                    "Using single-clip recovery '%s' via %s. This does not count as healthy animation coverage.",
                    target_state,
                    resolved_clip or "-",
                    resolved_source or "unknown",
                )
        return mode

    def _record_anim_emergency_recovery(self, requested_state, recovered_state, recovered_clip, playback_mode):
        target_state = str(requested_state or "idle").strip().lower()
        safe_state = str(recovered_state or "idle").strip().lower()
        safe_clip = str(recovered_clip or "").strip()
        mode = "emergency_safe_clip"
        self._anim_resolution_mode = mode
        self._anim_resolution_source = str(playback_mode or "emergency_safe_idle").strip() or "emergency_safe_idle"
        self._anim_resolution_requested_state = target_state
        self._anim_resolution_clip = safe_clip

        marker = (target_state, safe_state, safe_clip, self._anim_resolution_source)
        if marker not in self._anim_emergency_once:
            self._anim_emergency_once.add(marker)
            logger.warning(
                "[Anim][EMERGENCY] State '%s' has no dedicated clip and no degraded single-clip recovery. "
                "Using emergency safe clip '%s' from state '%s' via %s only to avoid bind pose. "
                "This is not a working animation state.",
                target_state,
                safe_clip or "-",
                safe_state or "-",
                self._anim_resolution_source,
            )
        return mode

    def _force_safe_idle_anim(self, requested_state=None):
        """Ensure we play SOMETHING safe to avoid T-pose."""
        if not hasattr(self.actor, "getAnimControl"):
            return False
        requested_token = str(requested_state or "").strip().lower()

        def _record_recovery(recovered_state, recovered_clip, playback_mode):
            if requested_token:
                self._record_anim_emergency_recovery(
                    requested_token,
                    recovered_state,
                    recovered_clip,
                    playback_mode,
                )
                return
            self._anim_resolution_mode = "bootstrap_safe_clip"
            self._anim_resolution_source = str(playback_mode or "bootstrap").strip() or "bootstrap"
            self._anim_resolution_requested_state = str(recovered_state or "idle").strip().lower()
            self._anim_resolution_clip = str(recovered_clip or "").strip()

        # Try prioritized states
        for state in ["idle", "walking", "running", "walk", "run"]:
            try:
                # Resolve the actual clip name (handling aliases like walking -> walk)
                clip = self._resolve_anim_clip(state)
                if clip and self.actor.getAnimControl(clip):
                    self._arm_active_anim_control_effect(clip)
                    self.actor.loop(clip)
                    self._anim_state = state
                    self._anim_clip = clip
                    self._remember_safe_anim(state, clip)
                    _record_recovery(state, clip, "loop")
                    return True
            except Exception:
                continue

        last_safe_state = str(getattr(self, "_last_safe_anim_state", "") or "").strip().lower() or "idle"
        last_safe_clip = str(getattr(self, "_last_safe_anim_clip", "") or "").strip()
        if last_safe_clip and self.actor.getAnimControl(last_safe_clip):
            try:
                self._arm_active_anim_control_effect(last_safe_clip)
                self.actor.loop(last_safe_clip)
                self._anim_state = last_safe_state
                self._anim_clip = last_safe_clip
                self._remember_safe_anim(last_safe_state, last_safe_clip)
                _record_recovery(last_safe_state, last_safe_clip, "loop")
                return True
            except Exception:
                try:
                    self._arm_active_anim_control_effect(last_safe_clip)
                    self.actor.play(last_safe_clip)
                    self._anim_state = last_safe_state
                    self._anim_clip = last_safe_clip
                    self._remember_safe_anim(last_safe_state, last_safe_clip)
                    _record_recovery(last_safe_state, last_safe_clip, "single_play")
                    return True
                except Exception:
                    pass

        # Last ditch: try ANY available animation
        try:
            anims = self.actor.getAnimNames()
            if anims:
                clip = anims[0]
                self._arm_active_anim_control_effect(clip)
                self.actor.loop(clip)
                self._anim_state = "idle"
                self._anim_clip = clip
                self._remember_safe_anim("idle", clip)
                _record_recovery("idle", clip, "loop")
                return True
        except Exception:
            pass

        logger.warning("[Anim] Failed to recover with safe idle fallback (idle/walking/running).")
        return False

    def _weapon_transition_state_name(self, drawn):
        return "weapon_unsheathe" if bool(drawn) else "weapon_sheathe"

    def _trigger_weapon_ready_transition(self, drawn):
        state_name = self._weapon_transition_state_name(drawn)
        clip, source, _ = self._resolve_anim_clip(
            state_name,
            include_state_fallback=False,
            include_global_fallback=False,
            with_meta=True,
        )
        if not clip:
            marker = str(state_name or "").strip().lower()
            if marker and marker not in self._weapon_transition_missing_once:
                self._weapon_transition_missing_once.add(marker)
                logger.warning(
                    "[Anim][MISSING] Dedicated state '%s' has no compatible clip on the current actor. "
                    "Weapon draw/sheath will still move the item and play audio, but this animation coverage remains incomplete.",
                    state_name,
                )
            return False

        state_def = self._state_defs.get(state_name, {}) if isinstance(getattr(self, "_state_defs", None), dict) else {}
        duration = 0.0
        try:
            duration = float((state_def or {}).get("duration", 0.0) or 0.0)
        except Exception:
            duration = 0.0
        if duration <= 0.0:
            duration = 0.42 if bool(drawn) else 0.38

        blend_time = 0.08
        if isinstance(state_def, dict) and "blend_time" in state_def:
            try:
                blend_time = float(state_def.get("blend_time"))
            except Exception:
                blend_time = 0.08
        blend_time = max(0.02, min(1.2, float(blend_time or 0.08)))

        previous_clip = str(getattr(self, "_anim_clip", "") or "").strip()
        self._anim_state = state_name
        self._anim_clip = clip
        self._remember_safe_anim(state_name, clip)
        self._record_anim_resolution(state_name, clip, source)
        if self._begin_anim_blend_transition(
            previous_clip,
            clip,
            loop=False,
            blend_time=blend_time,
            state_name=state_name,
        ):
            try:
                self._state_lock_until = float(globalClock.getFrameTime()) + float(duration)
            except Exception:
                self._state_lock_until = float(duration)
            return True

        if not self._play_actor_anim(clip, loop=False, state_name=state_name):
            return False

        try:
            self._state_lock_until = float(globalClock.getFrameTime()) + float(duration)
        except Exception:
            self._state_lock_until = float(duration)
        return True

    def _remember_safe_anim(self, state, clip):
        self._last_safe_anim_state = state
        self._last_safe_anim_clip = clip

    def _is_anim_clip_actively_playing(self, clip):
        token = str(clip or "").strip()
        actor = getattr(self, "actor", None)
        if not token or actor is None or not hasattr(actor, "getAnimControl"):
            return False

        try:
            control = actor.getAnimControl(token)
        except Exception:
            control = None
        if not control:
            return False

        is_playing = getattr(control, "isPlaying", None)
        if callable(is_playing):
            try:
                return bool(is_playing())
            except Exception:
                pass

        get_current_anim = getattr(actor, "getCurrentAnim", None)
        if callable(get_current_anim):
            try:
                current = str(get_current_anim() or "").strip()
                if current and current.lower() == token.lower():
                    return True
            except Exception:
                pass
        return False

    def _arm_active_anim_control_effect(self, clip):
        if (
            not getattr(self, "_anim_blend_enabled", False)
            or not getattr(self, "actor", None)
            or not hasattr(self.actor, "setControlEffect")
        ):
            return

        active_clip = str(clip or "").strip()
        if not active_clip:
            return

        effect_names = getattr(self, "_anim_effect_clips", None)
        if not isinstance(effect_names, set):
            effect_names = set()
        effect_names.add(active_clip)

        if bool(getattr(self, "_anim_control_audit_deferred", False)):
            available = [
                str(name).strip()
                for name in sorted(effect_names)
                if str(name).strip()
            ]
        else:
            available = [
                str(name).strip()
                for name in list(getattr(self, "_available_anims", []) or [])
                if str(name).strip()
            ]
            for name in available:
                effect_names.add(name)
            if active_clip not in available:
                available.append(active_clip)

        for name in available:
            try:
                self.actor.setControlEffect(name, 1.0 if name == active_clip else 0.0)
            except Exception:
                continue
        self._anim_effect_clips = effect_names

    def _begin_anim_blend_transition(self, from_clip, to_clip, loop=True, blend_time=None, state_name=None):
        if (
            not getattr(self, "_anim_blend_enabled", False)
            or not getattr(self, "actor", None)
            or not hasattr(self.actor, "setControlEffect")
        ):
            return False

        source_clip = str(from_clip or "").strip()
        target_clip = str(to_clip or "").strip()
        if (not source_clip) or (not target_clip) or source_clip == target_clip:
            return False
        if not self._is_anim_clip_actively_playing(source_clip):
            marker = f"{source_clip}->{target_clip}"
            if marker not in self._anim_blend_skipped_once:
                self._anim_blend_skipped_once.add(marker)
                logger.info(
                    "[Anim] Blend start skipped for '%s' -> '%s' because the source clip is not actively playing yet. "
                    "Using direct playback to avoid a one-frame bind pose flash.",
                    source_clip,
                    target_clip,
                )
            return False

        duration = self._anim_blend_duration
        try:
            if blend_time is not None:
                duration = max(0.02, min(1.2, float(blend_time)))
        except Exception:
            duration = self._anim_blend_duration

        if not self._play_actor_anim(target_clip, loop=loop, state_name=state_name):
            return False

        try:
            self.actor.setControlEffect(source_clip, 1.0)
        except Exception:
            return False
        try:
            self.actor.setControlEffect(target_clip, 0.0)
        except Exception:
            return False
        tracked_effects = getattr(self, "_anim_effect_clips", None)
        if not isinstance(tracked_effects, set):
            tracked_effects = set()
        tracked_effects.add(source_clip)
        tracked_effects.add(target_clip)
        self._anim_effect_clips = tracked_effects

        self._anim_blend_transition = {
            "from_clip": source_clip,
            "to_clip": target_clip,
            "elapsed": 0.0,
            "duration": duration,
            "loop": bool(loop),
        }
        return True

    def _resolve_attachment_nodes(self):
        if not self.actor:
            return
        
        # Standard Mixamo rig bone names
        mapping = {
            "right_hand": "mixamorig:RightHand",
            "left_hand": "mixamorig:LeftHand",
            "left_hip": "mixamorig:LeftUpLeg",
            "hips": "mixamorig:Hips",
            "head": "mixamorig:Head",
            "spine_upper": "mixamorig:Spine2",
        }
        
        for attr, bone in mapping.items():
            joint = self.actor.exposeJoint(None, "modelRoot", bone)
            if joint:
                setattr(self, f"_{attr}", joint)
                logger.info(f"[Player] Exposed joint {bone} for {attr}")
            else:
                logger.warning(f"[Player] Could not expose joint {bone}")

    def _build_equipment_visuals(self):
        pass

    def _apply_starting_equipment(self):
        pass

    def _setup_sword_trail(self):
        pass

    def _setup_input(self):
        pass

    def _build_flight_vfx(self):
        pass

    def _build_dash_vfx(self):
        pass

    def _refresh_spell_cache(self):
        pass

    def _write_animation_coverage_report(self):
        pass

    def _noncore_animation_playback_block_reason(self):
        return None

    def _resolve_player_scale(self):
        cfg = self._player_model_config()
        try:
            return max(0.05, min(10.0, float(cfg.get("scale", 1.0) or 1.0)))
        except Exception:
            return 1.0

    def _resolve_xbot_runtime_anims(self):
        runtime_dir = "assets/models/xbot/runtime_clips"
        defaults = {
            "idle": f"{runtime_dir}/idle.glb",
            "walk": f"{runtime_dir}/walk.glb",
            "run": f"{runtime_dir}/run.glb",
        }
        resolved = {key: prefer_bam_path(value) for key, value in defaults.items()}

        manifest_mapping, _ = self._load_manifest_animation_sources()
        if not isinstance(manifest_mapping, dict):
            return resolved

        safe_runtime_keys = {
            "idle",
            "walk",
            "run",
            "jumping",
            "falling",
            "falling_hard",
            "landing",
            "dodging",
            "dodge_roll",
            "crouch_idle",
            "crouch_move",
            "sliding",
            "swim",
            "swim_loop",
            "vaulting",
            "vault_over",
            "climbing",
            "wallrun",
            "wallrun_side",
            "flying",
            "flying_loop",
            "flight_takeoff",
            "flight_hover",
            "flight_glide",
            "flight_dive",
            "flight_airdash",
            "flight_land",
            "block_guard",
            "casting",
            "cast_prepare",
            "cast_channel",
            "cast_release",
            "attacking",
            "blocking",
            "recovering",
            "run_blade",
            "weapon_unsheathe",
            "weapon_sheathe",
            "draw_sword",
            "unsheathe_sword",
            "sheath_sword",
            "sheath_sword_1",
            "sheath_sword_2",
        }
        safe_runtime_prefixes = (
            "attack_",
            "cast_",
            "weapon_",
        )
        for raw_key, raw_value in manifest_mapping.items():
            key = str(raw_key or "").strip().lower()
            if not key:
                continue
            if key not in safe_runtime_keys and not key.startswith(safe_runtime_prefixes):
                continue
            path_token = str(raw_value or "").strip().replace("\\", "/")
            if not path_token:
                continue
            resolved[key] = prefer_bam_path(path_token)
        return resolved

    def _uses_xbot_runtime_model(self):
        model_token = str(getattr(self, "_loaded_player_model_path", "") or "").strip().replace("\\", "/").lower()
        return "xbot" in model_token

    def _xbot_runtime_state_candidates(self, state_name):
        if not self._uses_xbot_runtime_model():
            return []

        state_key = str(state_name or "").strip().lower()
        if not state_key:
            return []

        running_chain = ["run_blade", "run"] if bool(getattr(self, "_weapon_drawn", False)) else ["run", "run_blade"]
        direct = {
            "idle": ["idle"],
            "walking": ["walk"],
            "walk": ["walk"],
            "running": running_chain,
            "run": running_chain,
            "jumping": ["jumping"],
            "falling": ["falling", "falling_hard"],
            "falling_hard": ["falling_hard", "falling"],
            "landing": ["landing"],
            "dodging": ["dodge_roll", "dodging", "dash_forward", "run"],
            "blocking": ["block_guard", "blocking"],
            "recovering": ["recovering", "landing"],
            "vaulting": ["vault_low", "vault_high", "vault_over"],
            "climbing": ["climb_fast", "climb_slow"],
            "wallrun": ["wallrun_side", "wallrun_start", "wallrun_exit"],
            "sliding": ["sliding", "dodging", "run"],
            "swim": ["swim_loop", "swim"],
            "flying": ["flying_loop", "flying", "flight_glide", "flight_hover"],
            "flight_takeoff": ["flight_takeoff", "flying"],
            "flight_hover": ["flying_loop", "flight_hover", "flying"],
            "flight_glide": ["flying_loop", "flight_glide", "flying"],
            "flight_dive": ["flight_dive", "flying", "falling"],
            "flight_airdash": ["flight_airdash", "flying_loop", "flying"],
            "flight_land": ["flight_land", "landing"],
            "weapon_unsheathe": ["weapon_unsheathe", "draw_sword", "unsheathe_sword"],
            "weapon_sheathe": ["weapon_sheathe", "sheath_sword", "sheath_sword_1", "sheath_sword_2"],
            "attacking": [
                "attack_light_right",
                "attack_light_left",
                "attack_right",
                "attack_left",
                "attacking",
            ],
            "casting": [
                "cast_fast",
                "cast_release",
                "cast_fire",
                "cast_ice",
                "cast_lightning",
                "casting",
            ],
        }
        return list(direct.get(state_key, []))

    def _xbot_runtime_blocked_state_tokens(self, state_name):
        if not self._uses_xbot_runtime_model():
            return set()
        # Curated XBot transition packs now publish dedicated state-named clips
        # such as `vaulting`, `climbing`, and `wallrun`. The old block list was
        # forcing those legitimate clips to degrade into `run`, which reintroduced
        # visible pose corruption and made coverage lie about healthy states.
        return set()

    def _clip_start_frame_hint(self, state_name, clip, loop):
        clip_token = str(clip or "").strip()
        state_token = str(state_name or "").strip()
        if (not clip_token) and (not state_token):
            return None

        normalized_tokens = []
        for token in (clip_token, state_token):
            normalized = self._normalize_anim_key(token)
            if normalized:
                normalized_tokens.append(normalized)

        explicit_short_clip_hints = {
            "jumping",
            "falling",
            "landing",
            "flightland",
            "flighttakeoff",
        }
        allow_hint = bool(loop) and self._uses_xbot_runtime_model()
        if not allow_hint:
            allow_hint = any(token in explicit_short_clip_hints for token in normalized_tokens)
        if not allow_hint:
            return None

        hint = 0
        for normalized in normalized_tokens:
            try:
                hint = max(hint, int(CLIP_START_FRAME_HINTS.get(normalized, 0) or 0))
            except Exception:
                continue

        if hint <= 0:
            return None

        actor = getattr(self, "actor", None)
        if actor is not None and hasattr(actor, "getAnimControl") and clip_token:
            try:
                control = actor.getAnimControl(clip_token)
            except Exception:
                control = None
            get_num_frames = getattr(control, "getNumFrames", None)
            if callable(get_num_frames):
                try:
                    total_frames = int(float(get_num_frames() or 0.0))
                    if total_frames > 0:
                        hint = min(hint, max(0, total_frames - 2))
                except Exception:
                    pass

        return int(hint) if hint > 0 else None

    def _resolve_base_anims(self):
        cfg = self._player_model_config()
        model_path = str(cfg.get("model", "")).lower()
        is_xbot = "xbot" in model_path

        if is_xbot:
            return self._resolve_xbot_runtime_anims()

        defaults = {
            "idle": "assets/models/xbot/idle.glb",
            "walk": "assets/models/xbot/walk.glb",
            "run": "assets/models/xbot/run.glb",
        }
        defaults = {key: prefer_bam_path(value) for key, value in defaults.items()}

        raw = cfg.get("base_anims")
        if not isinstance(raw, dict):
            return defaults

        resolved = {}
        for key, value in raw.items():
            clip_key = str(key or "").strip().lower()
            clip_path = str(value or "").strip().replace("\\", "/")
            if not clip_key or not clip_path:
                continue
            resolved[clip_key] = prefer_bam_path(clip_path)
        if not resolved:
            return defaults
        return resolved

    def _anim_play_rate(self, state_name):
        state = str(state_name or self._anim_state or "").lower()
        if not self.cs:
            return 1.0

        speed = math.sqrt((self.cs.velocity.x * self.cs.velocity.x) + (self.cs.velocity.y * self.cs.velocity.y))
        if state in {"walking", "walk", "swim", "mounted_move", "mounted_ship_move"}:
            ref = max(0.1, self.walk_speed)
            return max(0.72, min(1.35, speed / ref))
        if state in {"running", "run"}:
            ref = max(0.1, self.run_speed)
            return max(0.85, min(1.45, speed / ref))
        if state in {"flying", "fly", "flight_takeoff", "flight_hover", "flight_glide", "flight_dive", "flight_airdash"}:
            ref = max(0.1, self.flight_speed)
            return max(0.90, min(1.35, speed / ref))
        if state in {"attacking", "dodging"}:
            return 1.08
        return 1.0

    def _resolved_clip_duration(self, clip):
        token = str(clip or "").strip()
        actor = getattr(self, "actor", None)
        if not token or actor is None:
            return 0.0

        try:
            duration = float(actor.getDuration(token) or 0.0)
            if duration > 0.0:
                return duration
        except Exception:
            pass

        try:
            control = actor.getAnimControl(token)
        except Exception:
            control = None
        if control is None:
            return 0.0

        try:
            frame_rate = float(control.getFrameRate() or 0.0)
            frame_count = float(control.getNumFrames() or 0.0)
            if frame_rate > 0.0 and frame_count > 0.0:
                return frame_count / frame_rate
        except Exception:
            return 0.0
        return 0.0

    def _play_actor_anim(self, clip, loop=True, state_name=None):
        if not clip or not hasattr(self.actor, "loop"):
            return False
        try:
            try:
                self.actor.setPlayRate(self._anim_play_rate(state_name), clip)
            except Exception:
                pass
            start_frame = self._clip_start_frame_hint(state_name, clip, loop)
            if start_frame is not None:
                logged = getattr(self, "_anim_start_frame_logged_once", None)
                if not isinstance(logged, set):
                    logged = set()
                    self._anim_start_frame_logged_once = logged
                marker = f"{clip}|{int(start_frame)}"
                if marker not in logged:
                    logged.add(marker)
                    logger.info(
                        "[Anim] Starting clip '%s' from frame %d to skip bind-pose lead-in on the XBot runtime rig.",
                        clip,
                        int(start_frame),
                    )
            self._arm_active_anim_control_effect(clip)
            if loop:
                try:
                    if start_frame is not None:
                        self.actor.loop(clip, restart=1, fromFrame=int(start_frame))
                    else:
                        self.actor.loop(clip)
                except TypeError:
                    self.actor.loop(clip)
            else:
                try:
                    if start_frame is not None:
                        self.actor.play(clip, fromFrame=int(start_frame))
                    else:
                        self.actor.play(clip)
                except TypeError:
                    self.actor.play(clip)
            return True
        except Exception as exc:
            marker = f"{clip}|{'loop' if loop else 'play'}"
            if marker not in self._anim_failed_once:
                self._anim_failed_once.add(marker)
                logger.warning(f"[Anim] Playback failed for '{clip}': {exc}")
            return False

    def _resolve_anim_clip(
        self,
        state_name,
        include_state_fallback=True,
        include_global_fallback=True,
        with_meta=False,
    ):
        available = list(getattr(self, "_available_anims", []) or [])
        available_lower = {name.lower(): name for name in available}
        available_norm = {self._normalize_anim_key(name): name for name in available}

        state = str(state_name or "idle").strip()
        state_key = state.lower()
        candidates = []
        seen = set()
        blocked_norm = self._xbot_runtime_blocked_state_tokens(state_key)

        def _push(token, source):
            key = str(token or "").strip()
            if not key:
                return
            normalized_key = self._normalize_anim_key(key)
            if blocked_norm and normalized_key in blocked_norm:
                return
            marker = key.lower()
            if marker in seen:
                return
            seen.add(marker)
            candidates.append((key, source))

        for token in self._xbot_runtime_state_candidates(state_key):
            _push(token, "xbot_runtime")
        for token in getattr(self, "_state_anim_hints", {}).get(state_key, []):
            _push(token, "state_hint")
        for token in getattr(self, "_state_anim_overrides", {}).get(state_key, []):
            _push(token, "player_animations")
        state_token = getattr(self, "_state_anim_tokens", {}).get(state_key)
        if state_token:
            _push(state_token, "player_states")
        _push(state, "state_name")
        if include_state_fallback:
            for token in getattr(self, "_state_anim_fallback", {}).get(state_key, []):
                _push(token, "state_fallback")
        if include_global_fallback:
            for token in ("idle", "walk", "run"):
                _push(token, "global_fallback")

        for candidate, source in candidates:
            if candidate in getattr(self, "_available_anims", set()):
                return (candidate, source, candidate) if with_meta else candidate
            lower = candidate.lower()
            if lower in available_lower:
                match = available_lower[lower]
                return (match, source, candidate) if with_meta else match
            normalized = self._normalize_anim_key(candidate)
            if normalized in available_norm:
                match = available_norm[normalized]
                return (match, source, candidate) if with_meta else match

        return (None, None, None) if with_meta else ""

    def _set_anim(self, state_name, loop=True, blend_time=None, force=False):
        target_state = str(state_name or "idle").lower()
        clip, source, _ = self._resolve_anim_clip(target_state, with_meta=True)
        if not clip:
            if target_state not in self._anim_missing_state_once:
                self._anim_missing_state_once.add(target_state)
                logger.warning(
                    "[Anim][EMERGENCY] No compatible clip resolved for state '%s'. "
                    "Trying emergency safe clip to avoid bind pose. This does not count as working coverage.",
                    target_state,
                )
            return self._force_safe_idle_anim(requested_state=target_state)
        self._record_anim_resolution(target_state, clip, source)
        transition_marker = (
            target_state,
            str(clip or "").strip(),
            str(source or "").strip(),
            bool(loop),
        )
        if transition_marker != getattr(self, "_anim_transition_logged", None):
            self._anim_transition_logged = transition_marker
            logger.info(
                "[Anim] Request state='%s' clip='%s' source='%s' loop=%s previous_state='%s' previous_clip='%s'",
                target_state,
                clip,
                source or "unknown",
                bool(loop),
                str(getattr(self, "_anim_state", "") or "").strip().lower() or "-",
                str(getattr(self, "_anim_clip", "") or "").strip() or "-",
            )

        if (
            not force
            and target_state == self._anim_state
            and clip == self._anim_clip
            and not self._anim_blend_transition
        ):
            self._arm_active_anim_control_effect(clip)
            return True

        previous_clip = str(getattr(self, "_anim_clip", "") or "").strip()
        self._anim_state = target_state
        self._anim_clip = clip
        self._remember_safe_anim(target_state, clip)
        if self._begin_anim_blend_transition(
            previous_clip,
            clip,
            loop=loop,
            blend_time=blend_time,
            state_name=target_state,
        ):
            return True
        return self._play_actor_anim(clip, loop=loop, state_name=target_state)

    def _tick_anim_blend(self, dt):
        transition = getattr(self, "_anim_blend_transition", None)
        if not isinstance(transition, dict):
            return None
        if not getattr(self, "_anim_blend_enabled", False):
            self._anim_blend_transition = None
            return None

        from_clip = str(transition.get("from_clip", "") or "").strip()
        to_clip = str(transition.get("to_clip", "") or "").strip()
        duration = max(0.02, float(transition.get("duration", self._anim_blend_duration) or self._anim_blend_duration))
        elapsed = float(transition.get("elapsed", 0.0) or 0.0) + max(0.0, float(dt or 0.0))
        alpha = max(0.0, min(1.0, elapsed / duration))

        try:
            if from_clip:
                self.actor.setControlEffect(from_clip, max(0.0, 1.0 - alpha))
            if to_clip:
                self.actor.setControlEffect(to_clip, alpha)
        except Exception as exc:
            logger.warning(f"[Anim] Blend transition failed and was cancelled: {exc}")
            self._anim_blend_transition = None
            self._arm_active_anim_control_effect(to_clip or from_clip)
            return None

        if alpha >= 1.0:
            self._anim_blend_transition = None
            self._arm_active_anim_control_effect(to_clip)
            return None

        transition["elapsed"] = elapsed
        self._anim_blend_transition = transition
        return None

    def _write_animation_coverage_report(self):
        if is_user_data_mode():
            report_path = runtime_file("logs", "ANIMATION_COVERAGE.md")
        else:
            report_path = Path("data/states/ANIMATION_COVERAGE.md")
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

        states = sorted(getattr(self, "_state_defs", {}).keys())
        if not states:
            return

        rows = []
        ok_count = 0
        degraded_count = 0
        missing_count = 0
        for state_name in states:
            strict_clip, strict_source, _ = self._resolve_anim_clip(
                state_name,
                include_state_fallback=False,
                include_global_fallback=False,
                with_meta=True,
            )
            resolved_clip, resolved_source, _ = self._resolve_anim_clip(
                state_name,
                include_state_fallback=True,
                include_global_fallback=True,
                with_meta=True,
            )
            if strict_clip:
                status = "OK"
                clip = strict_clip
                source = strict_source or "-"
                ok_count += 1
            elif resolved_clip:
                status = "DEGRADED_SINGLE_CLIP"
                clip = resolved_clip
                source = resolved_source or "-"
                degraded_count += 1
            else:
                status = "MISSING"
                clip = "-"
                source = "-"
                missing_count += 1
            rows.append(f"| {state_name} | {status} | {clip} | {source} |")

        content = [
            "# Player Animation Coverage",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"- Total states: {len(states)}",
            f"- OK: {ok_count}",
            f"- Degraded single clip: {degraded_count}",
            f"- Missing: {missing_count}",
            "",
            "States marked `DEGRADED_SINGLE_CLIP` are explicit substitute-clip recoveries.",
            "They prevent bind pose, but they are not healthy animation coverage.",
            "",
            "| State | Status | Resolved Clip | Source |",
            "|---|---|---|---|",
            *rows,
            "",
        ]
        try:
            report_path.write_text("\n".join(content), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"[Anim] Failed to write coverage report: {exc}")

    def _make_box(self, parent, name, sx, sy, sz, color):
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vwriter = GeomVertexWriter(vdata, "vertex")
        nwriter = GeomVertexWriter(vdata, "normal")
        cwriter = GeomVertexWriter(vdata, "color")

        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        faces = [
            ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
            ((0, 0, -1), [(-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz)]),
            ((1, 0, 0), [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)]),
            ((-1, 0, 0), [(-hx, hy, -hz), (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz)]),
            ((0, 1, 0), [(-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz)]),
            ((0, -1, 0), [(-hx, -hy, hz), (hx, -hy, hz), (hx, -hy, -hz), (-hx, -hy, -hz)]),
        ]

        for normal, verts in faces:
            for vx, vy, vz in verts:
                vwriter.addData3f(vx, vy, vz)
                nwriter.addData3f(*normal)
                cwriter.addData4f(*color)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(6):
            base = i * 4
            tris.addVertices(base, base + 1, base + 2)
            tris.addVertices(base, base + 2, base + 3)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        return parent.attachNewNode(node)

    def _clear_visual_children(self, parent):
        if not parent:
            return
        try:
            children = list(parent.getChildren())
        except Exception:
            children = list(getattr(parent, "children", [])) if hasattr(parent, "children") else []
        for child in children:
            try:
                child.removeNode()
            except Exception:
                pass

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
        return token

    def _safe_color4(self, value, fallback):
        if isinstance(value, (list, tuple)) and len(value) >= 4:
            try:
                return (
                    float(value[0]),
                    float(value[1]),
                    float(value[2]),
                    float(value[3]),
                )
            except Exception:
                return fallback
        return fallback

    def _coerce_equipment_visual_style(self, payload, slot_name):
        slot = self._slot_alias(slot_name)
        item = payload if isinstance(payload, dict) else {}
        visual = item.get("equip_visual", {})
        if not isinstance(visual, dict):
            visual = {}

        token = str(
            visual.get("style")
            or item.get("weapon_class")
            or item.get("weapon_type")
            or item.get("type")
            or slot
            or ""
        ).strip().lower()

        aliases = {
            "sword": "blade",
            "dagger": "blade",
            "axe": "blade",
            "mace": "blade",
            "staff": "magic",
            "crossbow": "magic",
            "shield": "ward",
            "offhand": "ward",
            "artifact": "charm",
            "amulet": "charm",
            "accessory": "charm",
            "body": "light",
            "armor": "medium",
        }
        token = aliases.get(token, token)

        if slot == "weapon_main":
            return token if token in {"blade", "bow", "magic"} else "blade"
        if slot == "offhand":
            return "ward"
        if slot == "chest":
            return token if token in {"light", "medium", "heavy"} else "medium"
        if slot == "trinket":
            return "charm"
        return token

    def _build_sword(self, parent):
        grip = self._make_box(parent, "sword_grip", 0.05, 0.05, 0.32, (0.18, 0.14, 0.11, 1.0))
        guard = self._make_box(parent, "sword_guard", 0.25, 0.06, 0.05, (0.70, 0.72, 0.76, 1.0))
        blade = self._make_box(parent, "sword_blade", 0.07, 0.02, 0.95, (0.82, 0.85, 0.90, 1.0))
        pommel = self._make_box(parent, "sword_pommel", 0.08, 0.08, 0.08, (0.68, 0.70, 0.74, 1.0))

        grip.setPos(0, 0, 0.16)
        guard.setPos(0, 0, 0.33)
        blade.setPos(0, 0, 0.82)
        pommel.setPos(0, 0, -0.02)

    def _build_shield(self, parent):
        base = self._make_box(parent, "shield_base", 0.42, 0.08, 0.52, (0.45, 0.31, 0.17, 1.0))
        rim = self._make_box(parent, "shield_rim_top", 0.44, 0.09, 0.06, (0.75, 0.74, 0.72, 1.0))
        boss = self._make_box(parent, "shield_boss", 0.14, 0.10, 0.14, (0.70, 0.68, 0.62, 1.0))

        base.setPos(0, 0, 0)
        rim.setPos(0, 0, 0.22)
        boss.setPos(0, 0.04, 0)

    def _build_armor(self, parent):
        plate = self._make_box(parent, "armor_plate", 0.74, 0.28, 0.84, (0.34, 0.34, 0.38, 0.96))
        collar = self._make_box(parent, "armor_collar", 0.42, 0.24, 0.18, (0.68, 0.68, 0.72, 0.98))
        plate.setPos(0.0, 0.10, 0.18)
        collar.setPos(0.0, 0.22, 0.62)
        parent.setPos(0.0, 0.0, 0.20)

    def _build_trinket(self, parent):
        gem = self._make_box(parent, "trinket_core", 0.12, 0.05, 0.16, (0.70, 0.84, 0.98, 0.95))
        loop = self._make_box(parent, "trinket_loop", 0.08, 0.03, 0.04, (0.86, 0.82, 0.54, 0.98))
        gem.setPos(0.0, 0.08, -0.04)
        loop.setPos(0.0, 0.05, 0.06)
        parent.setPos(0.0, 0.34, 0.98)

    def _build_weapon_visual(self, parent, style="blade"):
        token = str(style or "blade").strip().lower()
        if token == "bow":
            grip = self._make_box(parent, "bow_grip", 0.05, 0.07, 0.52, (0.34, 0.22, 0.12, 1.0))
            limb_top = self._make_box(parent, "bow_limb_top", 0.05, 0.03, 0.52, (0.48, 0.34, 0.18, 1.0))
            limb_bottom = self._make_box(parent, "bow_limb_bottom", 0.05, 0.03, 0.52, (0.48, 0.34, 0.18, 1.0))
            string = self._make_box(parent, "bow_string", 0.01, 0.01, 0.96, (0.86, 0.84, 0.76, 0.95))
            rest = self._make_box(parent, "bow_arrow_rest", 0.12, 0.02, 0.04, (0.70, 0.58, 0.42, 1.0))
            grip.setPos(0.0, 0.0, 0.26)
            limb_top.setPos(0.0, 0.07, 0.54)
            limb_bottom.setPos(0.0, -0.07, 0.02)
            string.setPos(0.0, 0.0, 0.48)
            rest.setPos(0.05, 0.0, 0.26)
            return
        if token == "magic":
            haft = self._make_box(parent, "magic_haft", 0.06, 0.06, 0.70, (0.30, 0.24, 0.18, 1.0))
            focus_ring = self._make_box(parent, "magic_focus_ring", 0.24, 0.04, 0.24, (0.70, 0.72, 0.86, 0.96))
            focus_core = self._make_box(parent, "magic_focus_core", 0.12, 0.08, 0.16, (0.62, 0.86, 1.0, 0.96))
            vane_l = self._make_box(parent, "magic_vane_l", 0.06, 0.18, 0.04, (0.78, 0.78, 0.88, 0.92))
            vane_r = self._make_box(parent, "magic_vane_r", 0.06, 0.18, 0.04, (0.78, 0.78, 0.88, 0.92))
            haft.setPos(0.0, 0.0, 0.30)
            focus_ring.setPos(0.0, 0.0, 0.72)
            focus_core.setPos(0.0, 0.0, 0.72)
            vane_l.setPos(-0.08, 0.0, 0.72)
            vane_r.setPos(0.08, 0.0, 0.72)
            return
        self._build_sword(parent)

    def _build_offhand_visual(self, parent, style="ward"):
        _ = style
        self._build_shield(parent)
        crest = self._make_box(parent, "shield_crest", 0.18, 0.04, 0.20, (0.78, 0.76, 0.72, 1.0))
        crest.setPos(0.0, 0.06, 0.02)

    def _build_armor_visual(self, parent, style="medium"):
        token = str(style or "medium").strip().lower()
        if token == "light":
            jerkin = self._make_box(parent, "armor_jerkin", 0.66, 0.22, 0.74, (0.42, 0.32, 0.22, 0.96))
            strap_l = self._make_box(parent, "armor_strap_l", 0.10, 0.05, 0.68, (0.24, 0.18, 0.12, 1.0))
            strap_r = self._make_box(parent, "armor_strap_r", 0.10, 0.05, 0.68, (0.24, 0.18, 0.12, 1.0))
            collar = self._make_box(parent, "armor_collar", 0.34, 0.18, 0.12, (0.62, 0.54, 0.42, 0.96))
            jerkin.setPos(0.0, 0.08, 0.16)
            strap_l.setPos(-0.20, 0.18, 0.18)
            strap_r.setPos(0.20, 0.18, 0.18)
            collar.setPos(0.0, 0.18, 0.54)
        elif token == "heavy":
            cuirass = self._make_box(parent, "armor_cuirass", 0.78, 0.30, 0.88, (0.50, 0.52, 0.58, 0.98))
            collar = self._make_box(parent, "armor_collar", 0.46, 0.24, 0.18, (0.74, 0.74, 0.80, 0.98))
            pauldron_l = self._make_box(parent, "armor_pauldron_l", 0.24, 0.22, 0.18, (0.76, 0.76, 0.82, 0.98))
            pauldron_r = self._make_box(parent, "armor_pauldron_r", 0.24, 0.22, 0.18, (0.76, 0.76, 0.82, 0.98))
            tasset_l = self._make_box(parent, "armor_tasset_l", 0.18, 0.12, 0.30, (0.62, 0.62, 0.68, 0.96))
            tasset_r = self._make_box(parent, "armor_tasset_r", 0.18, 0.12, 0.30, (0.62, 0.62, 0.68, 0.96))
            cuirass.setPos(0.0, 0.10, 0.18)
            collar.setPos(0.0, 0.22, 0.62)
            pauldron_l.setPos(-0.42, 0.10, 0.56)
            pauldron_r.setPos(0.42, 0.10, 0.56)
            tasset_l.setPos(-0.18, 0.10, -0.18)
            tasset_r.setPos(0.18, 0.10, -0.18)
        else:
            self._build_armor(parent)
        parent.setPos(0.0, 0.0, 0.20)

    def _build_trinket_visual(self, parent, style="charm"):
        _ = style
        gem = self._make_box(parent, "trinket_core", 0.12, 0.05, 0.16, (0.70, 0.84, 0.98, 0.95))
        loop = self._make_box(parent, "trinket_loop", 0.08, 0.03, 0.04, (0.86, 0.82, 0.54, 0.98))
        plate = self._make_box(parent, "trinket_rune_plate", 0.14, 0.03, 0.10, (0.72, 0.74, 0.86, 0.96))
        tassel = self._make_box(parent, "trinket_tassel", 0.03, 0.03, 0.16, (0.66, 0.54, 0.34, 0.94))
        gem.setPos(0.0, 0.08, -0.04)
        loop.setPos(0.0, 0.05, 0.06)
        plate.setPos(0.0, 0.06, -0.02)
        tassel.setPos(0.0, 0.08, -0.18)
        parent.setPos(0.0, 0.34, 0.98)

    def _build_runtime_bodywear_visual(self, parent):
        tunic = self._make_box(parent, "bodywear_tunic", 0.74, 0.20, 0.96, (0.36, 0.34, 0.30, 0.98))
        collar = self._make_box(parent, "bodywear_collar", 0.30, 0.18, 0.12, (0.66, 0.60, 0.52, 0.96))
        sash = self._make_box(parent, "bodywear_sash", 0.78, 0.06, 0.12, (0.24, 0.20, 0.18, 0.96))
        tunic.setPos(0.0, 0.06, 0.12)
        collar.setPos(0.0, 0.14, 0.56)
        sash.setPos(0.0, 0.12, -0.04)
        parent.setPos(0.0, 0.0, 0.16)

    def _build_runtime_legwear_visual(self, parent):
        trousers = self._make_box(parent, "legwear_trousers", 0.56, 0.14, 0.86, (0.22, 0.22, 0.24, 0.98))
        hem = self._make_box(parent, "legwear_hem", 0.60, 0.12, 0.10, (0.46, 0.40, 0.34, 0.96))
        belt = self._make_box(parent, "legwear_belt", 0.62, 0.06, 0.10, (0.18, 0.14, 0.12, 0.98))
        trousers.setPos(0.0, 0.02, -0.10)
        hem.setPos(0.0, 0.02, -0.50)
        belt.setPos(0.0, 0.10, 0.28)
        parent.setPos(0.0, 0.0, 0.84)

    def _apply_runtime_clothing_visuals(self):
        bodywear_node = getattr(self, "_bodywear_node", None)
        legwear_node = getattr(self, "_legwear_node", None)
        if not bodywear_node or not legwear_node:
            return

        model_token = str(getattr(self, "_loaded_player_model_path", "") or "").strip().replace("\\", "/").lower()
        use_xbot_overlay = "xbot" in model_token

        if not use_xbot_overlay:
            self._clear_visual_children(bodywear_node)
            self._clear_visual_children(legwear_node)
            bodywear_node.hide()
            legwear_node.hide()
            return

        if len(bodywear_node.getChildren()) == 0:
            self._build_runtime_bodywear_visual(bodywear_node)
        if len(legwear_node.getChildren()) == 0:
            self._build_runtime_legwear_visual(legwear_node)

        bodywear_attach = self._spine_upper or self.actor
        legwear_attach = self._hips or self.actor
        bodywear_node.wrtReparentTo(bodywear_attach)
        legwear_node.wrtReparentTo(legwear_attach)
        if not getattr(self, "_logged_runtime_clothing_baseline", False):
            logger.info(
                "[Player] Applying readable baseline clothing to the XBot runtime model until the Sherward rig "
                "and textured hero path are animation-safe."
            )
            self._logged_runtime_clothing_baseline = True
        try:
            bodywear_node.setLightOff(1)
        except Exception:
            pass
        try:
            legwear_node.setLightOff(1)
        except Exception:
            pass
        bodywear_node.setColorScale(0.58, 0.56, 0.52, 1.0)
        legwear_node.setColorScale(0.44, 0.44, 0.48, 1.0)
        bodywear_node.show()
        legwear_node.show()

    def _refresh_equipment_visual_geometry(self, slot_name, parent, style):
        slot = self._slot_alias(slot_name)
        token = str(style or "").strip().lower()
        style_attr = {
            "weapon_main": "_weapon_visual_style",
            "offhand": "_offhand_visual_style",
            "chest": "_armor_visual_style",
            "trinket": "_trinket_visual_style",
        }.get(slot, "")
        if not style_attr or not parent:
            return

        current = str(getattr(self, style_attr, "") or "").strip().lower()
        if current == token and len(getattr(parent, "getChildren", lambda: [])()) > 0:
            return

        self._clear_visual_children(parent)
        if slot == "weapon_main":
            self._build_weapon_visual(parent, token)
        elif slot == "offhand":
            self._build_offhand_visual(parent, token)
        elif slot == "chest":
            self._build_armor_visual(parent, token)
        elif slot == "trinket":
            self._build_trinket_visual(parent, token)
        setattr(self, style_attr, token)

    def _resolve_attach_point(self, token):
        key = str(token or "").strip().lower()
        if key in {"right_hand", "hand_r"}:
            return self._sword_hand_anchor or self.actor
        if key in {"left_hand", "hand_l", "offhand"}:
            return self._shield_hand_anchor or self.actor
        if key in {"left_hip", "hip_l", "sheathe"}:
            return self._sword_sheath_anchor or self.actor
        if key in {"spine_upper", "spine", "chest", "back"}:
            return self._spine_upper or self._shield_sheath_anchor or self.actor
        return self.actor

    def _equipment_pose_profile(self, slot_name, style, drawn):
        slot = self._slot_alias(slot_name)
        token = str(style or "").strip().lower()
        active = bool(drawn)

        if slot == "weapon_main":
            if token == "bow":
                if active:
                    return ("right_hand", (0.06, -0.02, -0.22), (18.0, -8.0, 96.0))
                return ("back", (-0.18, -0.14, 0.08), (18.0, 18.0, 102.0))
            if token == "magic":
                if active:
                    return ("right_hand", (0.04, 0.02, -0.14), (-8.0, 24.0, 92.0))
                return ("back", (-0.08, -0.14, 0.02), (10.0, 10.0, 96.0))
            if active:
                return ("right_hand", (0.02, 0.01, -0.16), (-15.0, -15.0, 90.0))
            return ("left_hip", (-0.20, -0.12, 0.04), (18.0, -24.0, -68.0))

        if slot == "offhand":
            if active:
                return ("left_hand", (-0.03, -0.02, -0.08), (0.0, 15.0, 92.0))
            return ("back", (-0.16, -0.10, -0.10), (-35.0, 0.0, 92.0))

        return ("spine_upper", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def _build_equipment_visuals(self):
        if not getattr(self, "_sword_hand_anchor", None):
            self._sword_hand_anchor = (self._right_hand or self.actor).attachNewNode("sword_hand_anchor")
        if not getattr(self, "_shield_hand_anchor", None):
            self._shield_hand_anchor = (self._left_hand or self.actor).attachNewNode("shield_hand_anchor")
        if not getattr(self, "_sword_sheath_anchor", None):
            self._sword_sheath_anchor = (self._hips or self._left_hip or self.actor).attachNewNode("sword_sheath_anchor")
        if not getattr(self, "_shield_sheath_anchor", None):
            self._shield_sheath_anchor = (self._spine_upper or self.actor).attachNewNode("shield_sheath_anchor")

        self._sword_node = self.actor.attachNewNode("sword_visual")
        self._shield_node = self.actor.attachNewNode("shield_visual")
        self._armor_node = (self._spine_upper or self.actor).attachNewNode("armor_visual")
        self._trinket_node = (self._spine_upper or self.actor).attachNewNode("trinket_visual")
        self._bodywear_node = (self._spine_upper or self.actor).attachNewNode("bodywear_visual")
        self._legwear_node = (self._hips or self.actor).attachNewNode("legwear_visual")
        self._weapon_visual_style = "blade"
        self._offhand_visual_style = "ward"
        self._armor_visual_style = "light"
        self._trinket_visual_style = "charm"
        self._refresh_equipment_visual_geometry("weapon_main", self._sword_node, self._weapon_visual_style)
        self._refresh_equipment_visual_geometry("offhand", self._shield_node, self._offhand_visual_style)
        self._refresh_equipment_visual_geometry("chest", self._armor_node, self._armor_visual_style)
        self._refresh_equipment_visual_geometry("trinket", self._trinket_node, self._trinket_visual_style)
        ensure_model_visual_defaults(self._sword_node, force_two_sided=True, debug_label="player_sword_visual")
        ensure_model_visual_defaults(self._shield_node, force_two_sided=True, debug_label="player_shield_visual")
        ensure_model_visual_defaults(self._armor_node, force_two_sided=True, debug_label="player_armor_visual")
        ensure_model_visual_defaults(self._trinket_node, force_two_sided=True, debug_label="player_trinket_visual")
        ensure_model_visual_defaults(self._bodywear_node, force_two_sided=True, debug_label="player_bodywear_visual")
        ensure_model_visual_defaults(self._legwear_node, force_two_sided=True, debug_label="player_legwear_visual")
        self._apply_equipment_visuals()
        self._apply_runtime_clothing_visuals()
        self._set_weapon_drawn(False, reset_timer=True)

    def _apply_equipment_visuals(self):
        data_mgr = getattr(self, "data_mgr", None)

        weapon_item = data_mgr.get_item(self._equipment_state.get("weapon_main", "")) if data_mgr else None
        self._has_weapon_visual = isinstance(weapon_item, dict)
        if self._has_weapon_visual:
            visual = weapon_item.get("equip_visual", {})
            if not isinstance(visual, dict):
                visual = {}
            self._refresh_equipment_visual_geometry(
                "weapon_main",
                self._sword_node,
                self._coerce_equipment_visual_style(weapon_item, "weapon_main"),
            )
            scale = max(0.5, min(1.8, float(visual.get("scale", 1.0) or 1.0)))
            color = self._safe_color4(visual.get("color"), (0.90, 0.90, 0.95, 1.0))
            self._sword_node.setScale(scale)
            self._sword_node.setColorScale(*color)
            self._sword_node.show()
        else:
            self._sword_node.hide()

        offhand_item = data_mgr.get_item(self._equipment_state.get("offhand", "")) if data_mgr else None
        self._has_offhand_visual = isinstance(offhand_item, dict)
        if self._has_offhand_visual:
            visual = offhand_item.get("equip_visual", {})
            if not isinstance(visual, dict):
                visual = {}
            self._refresh_equipment_visual_geometry(
                "offhand",
                self._shield_node,
                self._coerce_equipment_visual_style(offhand_item, "offhand"),
            )
            scale = max(0.5, min(1.8, float(visual.get("scale", 1.0) or 1.0)))
            color = self._safe_color4(visual.get("color"), (0.75, 0.74, 0.72, 1.0))
            self._shield_node.setScale(scale)
            self._shield_node.setColorScale(*color)
            self._shield_node.show()
        else:
            self._shield_node.hide()

        chest_item = data_mgr.get_item(self._equipment_state.get("chest", "")) if data_mgr else None
        if isinstance(chest_item, dict):
            visual = chest_item.get("equip_visual", {})
            if not isinstance(visual, dict):
                visual = {}
            armor_style = self._coerce_equipment_visual_style(chest_item, "chest")
            self._refresh_equipment_visual_geometry("chest", self._armor_node, armor_style)
            color = self._safe_color4(visual.get("color"), (0.36, 0.36, 0.42, 0.96))
            scale = max(0.72, min(1.35, float(visual.get("scale", 1.0) or 1.0)))
            self._armor_node.setColorScale(*color)
            self._armor_node.setScale(scale)
            attach = self._resolve_attach_point(chest_item.get("attach_point", "spine_upper"))
            self._armor_node.wrtReparentTo(attach)
            if armor_style == "heavy":
                self._armor_node.setPos(0.0, -0.02, 0.22)
            elif armor_style == "light":
                self._armor_node.setPos(0.0, 0.02, 0.18)
            else:
                self._armor_node.setPos(0.0, 0.0, 0.20)
            self._armor_node.show()
        else:
            self._armor_node.hide()

        trinket_item = data_mgr.get_item(self._equipment_state.get("trinket", "")) if data_mgr else None
        if isinstance(trinket_item, dict):
            visual = trinket_item.get("equip_visual", {})
            if not isinstance(visual, dict):
                visual = {}
            trinket_style = self._coerce_equipment_visual_style(trinket_item, "trinket")
            self._refresh_equipment_visual_geometry("trinket", self._trinket_node, trinket_style)
            color = self._safe_color4(visual.get("color"), (0.72, 0.86, 0.99, 0.95))
            scale = max(0.35, min(1.25, float(visual.get("scale", 0.75) or 0.75)))
            self._trinket_node.setColorScale(*color)
            self._trinket_node.setScale(scale)
            attach = self._resolve_attach_point(trinket_item.get("attach_point", "spine_upper"))
            self._trinket_node.wrtReparentTo(attach)
            self._trinket_node.setPos(0.0, 0.30, 0.96)
            self._trinket_node.show()
        else:
            self._trinket_node.hide()

    def _apply_starting_equipment(self):
        cfg = self._player_model_config()
        raw_items = cfg.get("starting_items", [])
        if isinstance(raw_items, str):
            raw_items = [raw_items]
        if not isinstance(raw_items, list):
            return []

        equipped = []
        for entry in raw_items:
            token = str(entry or "").strip()
            if not token:
                continue
            try:
                ok, _reason = self.equip_item(token)
            except Exception:
                ok = False
            if ok:
                equipped.append(token)
        return equipped

    def export_equipment_state(self):
        return dict(self._equipment_state)

    def import_equipment_state(self, payload):
        if not isinstance(payload, dict):
            return
        for key in list(self._equipment_state.keys()):
            val = payload.get(key, "")
            self._equipment_state[key] = str(val).strip() if isinstance(val, str) else ""
        self._apply_equipment_visuals()
        self._set_weapon_drawn(self._weapon_drawn, reset_timer=False)

    def equip_item(self, item_id, item_data=None):
        token = str(item_id or "").strip()
        if not token:
            return False, "invalid_item"
        payload = item_data if isinstance(item_data, dict) else (self.data_mgr.get_item(token) or {})
        if not isinstance(payload, dict):
            return False, "missing_item_data"
        slot = self._slot_alias(payload.get("slot") or payload.get("type"))
        if slot in {"consumable", "quest", "material", "none", ""}:
            return False, "not_equippable"
        if slot not in self._equipment_state:
            return False, "unsupported_slot"

        self._equipment_state[slot] = token
        self._apply_equipment_visuals()
        self._set_weapon_drawn(self._weapon_drawn, reset_timer=False)
        return True, slot

    def unequip_slot(self, slot):
        key = self._slot_alias(slot)
        if key not in self._equipment_state:
            return False
        self._equipment_state[key] = ""
        self._apply_equipment_visuals()
        self._set_weapon_drawn(self._weapon_drawn, reset_timer=False)
        return True

    def apply_effect(self, effect_type, amount):
        token = str(effect_type or "").strip().lower()
        if not token:
            return False
        try:
            raw_amount = float(amount or 0.0)
        except Exception:
            raw_amount = 0.0
        if raw_amount <= 0.0:
            return False

        def _resolve_delta(current_value, max_value):
            current = max(0.0, float(current_value or 0.0))
            ceiling = max(1.0, float(max_value or current or 1.0))
            delta = raw_amount * ceiling if 0.0 < raw_amount <= 1.0 else raw_amount
            return current, ceiling, max(0.0, float(delta))

        cs = getattr(self, "cs", None)
        if token in {"heal", "health", "hp"}:
            if cs and hasattr(cs, "health"):
                current, max_hp, delta = _resolve_delta(
                    getattr(cs, "health", 0.0),
                    getattr(cs, "maxHealth", getattr(cs, "health", 100.0)),
                )
                cs.health = min(max_hp, current + delta)
                self._last_hp_observed = float(cs.health)
                return True
            if hasattr(self, "hp"):
                current, max_hp, delta = _resolve_delta(
                    getattr(self, "hp", 0.0),
                    getattr(self, "max_hp", getattr(self, "hp", 100.0)),
                )
                self.hp = min(max_hp, current + delta)
                return True
            return False

        if token == "mana":
            if cs and hasattr(cs, "mana"):
                current, max_mana, delta = _resolve_delta(
                    getattr(cs, "mana", 0.0),
                    getattr(cs, "maxMana", getattr(cs, "mana", 100.0)),
                )
                cs.mana = min(max_mana, current + delta)
                return True
            return False

        if token == "stamina":
            if cs and hasattr(cs, "stamina"):
                current, max_stamina, delta = _resolve_delta(
                    getattr(cs, "stamina", 0.0),
                    getattr(cs, "maxStamina", getattr(cs, "stamina", 100.0)),
                )
                cs.stamina = min(max_stamina, current + delta)
                return True
            return False

        return False

    def use_item(self, item_id, item_data=None):
        token = str(item_id or "").strip()
        payload = item_data if isinstance(item_data, dict) else (self.data_mgr.get_item(token) or {})
        if not isinstance(payload, dict):
            return False
        effect = payload.get("use_effect", {})
        if not isinstance(effect, dict):
            return False
        if not self.cs:
            return False

        effect_type = str(effect.get("type", "") or "").strip().lower()
        amount = max(0.0, float(effect.get("amount", 0.0) or 0.0))
        if amount <= 0.0:
            return False
        if effect_type == "heal" and hasattr(self.cs, "health"):
            max_hp = float(getattr(self.cs, "maxHealth", getattr(self.cs, "health", 100.0)))
            self.cs.health = min(max_hp, float(self.cs.health) + amount)
            return True
        if effect_type == "mana" and hasattr(self.cs, "mana"):
            max_mana = float(getattr(self.cs, "maxMana", getattr(self.cs, "mana", 100.0)))
            self.cs.mana = min(max_mana, float(self.cs.mana) + amount)
            return True
        if effect_type == "stamina" and hasattr(self.cs, "stamina"):
            max_stamina = float(getattr(self.cs, "maxStamina", getattr(self.cs, "stamina", 100.0)))
            self.cs.stamina = min(max_stamina, float(self.cs.stamina) + amount)
            return True
        return False

    def take_damage(self, amount, damage_type="physical", source=None):
        del source
        try:
            raw_damage = float(amount or 0.0)
        except Exception:
            raw_damage = 0.0
        if raw_damage <= 0.0:
            return False

        applied = False
        remaining_hp = None
        cs = getattr(self, "cs", None)
        if cs and hasattr(cs, "health"):
            previous_hp = max(0.0, float(getattr(cs, "health", 0.0) or 0.0))
            remaining_hp = max(0.0, previous_hp - raw_damage)
            cs.health = remaining_hp
            applied = remaining_hp < previous_hp
        elif hasattr(self, "hp"):
            previous_hp = max(0.0, float(getattr(self, "hp", 0.0) or 0.0))
            remaining_hp = max(0.0, previous_hp - raw_damage)
            self.hp = remaining_hp
            applied = remaining_hp < previous_hp

        if not applied:
            return False

        try:
            self.register_incoming_damage(raw_damage, damage_type=damage_type)
        except Exception:
            pass

        if remaining_hp is not None and remaining_hp <= 0.0:
            self._dead_flag = True
            try:
                self._death_time = float(globalClock.getFrameTime())
            except Exception:
                self._death_time = 0.0
            self._respawn_requested = False
        return True

    def _set_weapon_drawn(self, drawn, reset_timer=False):
        was_drawn = bool(self._weapon_drawn)
        target = bool(drawn)
        if target == self._weapon_drawn and not reset_timer:
            if target:
                self._drawn_hold_timer = max(self._drawn_hold_timer, 1.8)
            return
        self._weapon_drawn = target
        if self._weapon_drawn:
            has_visual = bool(self._has_weapon_visual or self._has_offhand_visual)
            if self._has_weapon_visual:
                weapon_anchor, weapon_pos, weapon_hpr = self._equipment_pose_profile(
                    "weapon_main",
                    getattr(self, "_weapon_visual_style", "blade"),
                    True,
                )
                self._sword_node.wrtReparentTo(self._resolve_attach_point(weapon_anchor))
                self._sword_node.setPos(*weapon_pos)
                self._sword_node.setHpr(*weapon_hpr)
                self._sword_node.show()
            if self._has_offhand_visual:
                offhand_anchor, offhand_pos, offhand_hpr = self._equipment_pose_profile(
                    "offhand",
                    getattr(self, "_offhand_visual_style", "ward"),
                    True,
                )
                self._shield_node.wrtReparentTo(self._resolve_attach_point(offhand_anchor))
                self._shield_node.setPos(*offhand_pos)
                self._shield_node.setHpr(*offhand_hpr)
                self._shield_node.show()

            self._drawn_hold_timer = 2.4
            if has_visual and (not was_drawn):
                try:
                    self._play_sfx("weapon_unsheathe", volume=0.95)
                except Exception:
                    pass
            if not reset_timer:
                try:
                    self._trigger_weapon_ready_transition(True)
                except Exception as exc:
                    logger.warning(
                        "[Anim] Weapon unsheathe transition request failed unexpectedly: %s",
                        exc,
                    )
        else:
            if self._has_weapon_visual:
                weapon_anchor, weapon_pos, weapon_hpr = self._equipment_pose_profile(
                    "weapon_main",
                    getattr(self, "_weapon_visual_style", "blade"),
                    False,
                )
                self._sword_node.wrtReparentTo(self._resolve_attach_point(weapon_anchor))
                self._sword_node.setPos(*weapon_pos)
                self._sword_node.setHpr(*weapon_hpr)
                self._sword_node.show()
            else:
                self._sword_node.hide()

            if self._has_offhand_visual:
                offhand_anchor, offhand_pos, offhand_hpr = self._equipment_pose_profile(
                    "offhand",
                    getattr(self, "_offhand_visual_style", "ward"),
                    False,
                )
                self._shield_node.wrtReparentTo(self._resolve_attach_point(offhand_anchor))
                self._shield_node.setPos(*offhand_pos)
                self._shield_node.setHpr(*offhand_hpr)
                self._shield_node.show()
            else:
                self._shield_node.hide()

            if (not reset_timer) and was_drawn:
                try:
                    self._trigger_weapon_ready_transition(False)
                except Exception as exc:
                    logger.warning(
                        "[Anim] Weapon sheathe transition request failed unexpectedly: %s",
                        exc,
                    )
            if reset_timer:
                self._drawn_hold_timer = 0.0

    def _setup_sword_trail(self):
        magic_vfx = getattr(getattr(self, "app", None), "magic_vfx", None)
        if magic_vfx and hasattr(magic_vfx, "spawn_sword_trail"):
            try:
                self._trail_data = magic_vfx.spawn_sword_trail()
                return
            except Exception:
                self._trail_data = None
        if self.particles and HAS_CORE:
            try:
                self._trail_id = self.particles.spawnSwordTrail(gc.Vec3(0, 0, 0), gc.Vec3(0, 1, 0))
            except Exception:
                self._trail_id = -1

    def _update_sword_trail(self, dt=0.0):
        magic_vfx = getattr(getattr(self, "app", None), "magic_vfx", None)
        if magic_vfx and hasattr(magic_vfx, "update_sword_trail") and getattr(self, "_trail_data", None):
            if not getattr(self, "_weapon_drawn", False):
                return
            sword_node = getattr(self, "_sword_node", None)
            render = getattr(self, "render", None)
            if not sword_node or (hasattr(sword_node, "isEmpty") and sword_node.isEmpty()):
                return
            base_pos = sword_node.getPos(render)
            if render and hasattr(render, "getRelativePoint"):
                tip_pos = render.getRelativePoint(sword_node, Vec3(0, 0, 1.1))
            else:
                tip_pos = Vec3(base_pos.x, base_pos.y, base_pos.z + 1.1)
            magic_vfx.update_sword_trail(self._trail_data, tip_pos, base_pos, float(dt or 0.0))
            return
        trail_id = int(getattr(self, "_trail_id", -1) or -1)
        if not (self.particles and HAS_CORE and trail_id >= 0):
            return
        sword_world = self._sword_node.getPos(self.render)
        self.particles.setEmitterPos(trail_id, gc.Vec3(sword_world.x, sword_world.y, sword_world.z))

    def _setup_input(self):
        return PlayerInputMixin._setup_input(self)

    def _refresh_spell_cache(self):
        return PlayerCombatMixin._refresh_spell_cache(self)

    def _build_flight_vfx(self):
        self._flight_fx_root = self.actor.attachNewNode("flight_fx_root")
        self._flight_fx_root.setPos(0.0, -0.28, 1.05)
        self._flight_fx_root.hide()
        self._flight_left = self._make_box(
            self._flight_fx_root, "flight_fx_left", 0.24, 0.02, 0.52, (0.40, 0.75, 1.0, 0.55)
        )
        self._flight_right = self._make_box(
            self._flight_fx_root, "flight_fx_right", 0.24, 0.02, 0.52, (0.40, 0.75, 1.0, 0.55)
        )
        self._flight_center = self._make_box(
            self._flight_fx_root, "flight_fx_center", 0.12, 0.02, 0.28, (0.60, 0.85, 1.0, 0.60)
        )

        self._flight_left.setPos(-0.24, 0.0, 0.06)
        self._flight_left.setHpr(-24, 0, 18)
        self._flight_right.setPos(0.24, 0.0, 0.06)
        self._flight_right.setHpr(24, 0, -18)
        self._flight_center.setPos(0.0, 0.0, 0.02)

        for fx in (self._flight_left, self._flight_right, self._flight_center):
            try:
                fx.setTransparency(TransparencyAttrib.MAlpha)
                fx.setLightOff(1)
                fx.setTwoSided(True)
                fx.setShaderOff(1002)
                fx.setDepthWrite(False)
                fx.setBin("transparent", 35)
            except Exception:
                pass

    def _set_flight_fx(self, active):
        state = bool(active)
        if state == self._flight_fx_on:
            return
        self._flight_fx_on = state
        if not hasattr(self, "_flight_fx_root"):
            return
        if state:
            self._flight_fx_root.show()
        else:
            self._flight_fx_root.hide()
            try:
                self.actor.setP(0.0)
                self.actor.setR(0.0)
            except Exception:
                pass

    def _update_flight_pose_and_fx(self, move):
        self._set_flight_fx(True)
        if not hasattr(self, "_flight_fx_root"):
            return

        speed_2d = 0.0
        if self.cs:
            speed_2d = math.sqrt((self.cs.velocity.x * self.cs.velocity.x) + (self.cs.velocity.y * self.cs.velocity.y))
        normalized_speed = min(1.0, speed_2d / max(1.0, self.flight_speed * 2.0))
        t = globalClock.getFrameTime()

        flap = math.sin(t * (8.0 + (normalized_speed * 5.0)))
        wing_pitch = 12.0 + (8.0 * flap)
        self._flight_left.setP(wing_pitch)
        self._flight_right.setP(-wing_pitch)

        glow = 0.45 + (0.25 * (0.5 + (0.5 * math.sin(t * 6.0))))
        self._flight_fx_root.setColorScale(0.9 + (0.2 * normalized_speed), 1.0, 1.0, glow)

        if move.len() > 0.01:
            self.actor.setP(-8.0 - (normalized_speed * 6.0))
            self.actor.setR(max(-14.0, min(14.0, move.x * 8.0)))
        else:
            self.actor.setP(-4.0)
            self.actor.setR(0.0)

    def _build_dash_vfx(self):
        self._dash_fx_root = self.render.attachNewNode("dash_fx_root")
        self._dash_fx_root.hide()
        self._dash_fx_center = self._make_box(
            self._dash_fx_root, "dash_fx_center", 0.20, 0.02, 1.06, (0.72, 0.88, 1.0, 0.36)
        )
        self._dash_fx_left = self._make_box(
            self._dash_fx_root, "dash_fx_left", 0.12, 0.02, 0.84, (0.62, 0.82, 1.0, 0.30)
        )
        self._dash_fx_right = self._make_box(
            self._dash_fx_root, "dash_fx_right", 0.12, 0.02, 0.84, (0.62, 0.82, 1.0, 0.30)
        )

        self._dash_fx_center.setPos(0.0, -0.46, 0.10)
        self._dash_fx_left.setPos(-0.20, -0.34, 0.02)
        self._dash_fx_right.setPos(0.20, -0.34, 0.02)
        self._dash_fx_left.setHpr(0.0, 0.0, 10.0)
        self._dash_fx_right.setHpr(0.0, 0.0, -10.0)

        for fx in (self._dash_fx_root, self._dash_fx_center, self._dash_fx_left, self._dash_fx_right):
            try:
                fx.setTransparency(TransparencyAttrib.MAlpha)
                fx.setLightOff(1)
                fx.setTwoSided(True)
                fx.setShaderOff(1002)
                fx.setDepthWrite(False)
                fx.setBin("transparent", 34)
            except Exception:
                pass

    def _trigger_dash_blur_fx(self, move_vec=None, intensity=1.0):
        root = getattr(self, "_dash_fx_root", None)
        if not root:
            return

        strength = max(0.35, min(1.15, float(intensity or 1.0)))
        now = float(globalClock.getFrameTime())
        self._dash_fx_until = max(float(getattr(self, "_dash_fx_until", 0.0) or 0.0), now + (0.14 + (0.10 * strength)))
        self._dash_fx_alpha = max(float(getattr(self, "_dash_fx_alpha", 0.0) or 0.0), 0.48 + (0.36 * strength))

        heading = 0.0
        actor = getattr(self, "actor", None)
        if actor and hasattr(actor, "getH"):
            try:
                heading = float(actor.getH(getattr(self, "render", None)))
            except Exception:
                try:
                    heading = float(actor.getH())
                except Exception:
                    heading = 0.0
        try:
            mx = float(getattr(move_vec, "x", 0.0) or 0.0)
            my = float(getattr(move_vec, "y", 0.0) or 0.0)
            if abs(mx) > 1e-4 or abs(my) > 1e-4:
                heading = 180.0 - math.degrees(math.atan2(mx, my))
        except Exception:
            pass
        self._dash_fx_heading = heading
        try:
            root.show()
        except Exception:
            pass

    def _update_dash_blur_fx(self, dt=0.0):
        root = getattr(self, "_dash_fx_root", None)
        actor = getattr(self, "actor", None)
        if not root or not actor:
            return

        now = float(globalClock.getFrameTime())
        remaining = max(0.0, float(getattr(self, "_dash_fx_until", 0.0) or 0.0) - now)
        state = str(getattr(self, "_anim_state", "") or "").strip().lower()
        dash_states = {
            "dodging",
            "dash_forward",
            "dash_back",
            "dash_left",
            "dash_right",
            "attack_dash",
            "jump_dash",
            "flight_airdash",
        }
        target_alpha = max(remaining / 0.24, 1.0 if state in dash_states else 0.0)
        current_alpha = float(getattr(self, "_dash_fx_alpha", 0.0) or 0.0)
        if target_alpha >= current_alpha:
            alpha = target_alpha
        else:
            blend = max(0.0, min(1.0, float(dt or 0.0) * 8.5))
            alpha = (current_alpha + ((target_alpha - current_alpha) * blend)) if blend > 0.0 else target_alpha

        alpha = max(0.0, min(1.0, alpha))
        self._dash_fx_alpha = alpha
        if alpha <= 0.05 and target_alpha <= 0.0:
            self._dash_fx_alpha = 0.0
            try:
                root.hide()
            except Exception:
                pass
            return

        try:
            pos = actor.getPos(getattr(self, "render", None))
        except Exception:
            pos = actor.getPos() if hasattr(actor, "getPos") else None
        if pos is not None:
            try:
                root.setPos(float(pos.x), float(pos.y), float(pos.z) + 0.94)
            except Exception:
                pass

        heading = float(getattr(self, "_dash_fx_heading", 0.0) or 0.0)
        try:
            root.setH(heading)
            root.setScale(0.76 + (alpha * 0.22), 0.92 + (alpha * 1.85), 0.78 + (alpha * 0.26))
            root.setColorScale(0.76 + (alpha * 0.12), 0.88 + (alpha * 0.08), 1.0, 0.08 + (alpha * 0.42))
            root.show()
        except Exception:
            pass

    def _try_vehicle_interact(self):
        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if not vehicle_mgr:
            return False
        was_mounted = bool(getattr(vehicle_mgr, "is_mounted", False))
        try:
            ok = bool(vehicle_mgr.handle_interact(self))
        except Exception as exc:
            logger.warning(f"[Vehicle] Interact failed: {exc}")
            return False
        if not ok:
            return False
        if (not was_mounted) and bool(getattr(vehicle_mgr, "is_mounted", False)):
            mounted_vehicle = vehicle_mgr.mounted_vehicle() if hasattr(vehicle_mgr, "mounted_vehicle") else None
            if isinstance(mounted_vehicle, dict):
                self._mount_anim_kind = str(mounted_vehicle.get("kind", "")).strip().lower()
            self._queue_state_trigger("mount_start")
            self._set_weapon_drawn(False, reset_timer=True)
        elif was_mounted and (not bool(getattr(vehicle_mgr, "is_mounted", False))):
            self._queue_state_trigger("dismount_start")
        return True

    def _try_story_interact(self):
        manager = getattr(self.app, "story_interaction", None)
        if not manager or not hasattr(manager, "try_interact"):
            return False
        try:
            return bool(manager.try_interact(self.actor.getPos(self.render)))
        except Exception as exc:
            logger.debug(f"[StoryInteraction] Interact failed: {exc}")
            return False

    def _try_npc_interact(self):
        manager = getattr(self.app, "npc_interaction", None)
        if not manager or not hasattr(manager, "try_interact"):
            return False
        try:
            return bool(manager.try_interact())
        except Exception as exc:
            logger.debug(f"[NPCInteraction] Interact failed: {exc}")
            return False

    def _is_skill_wheel_held(self):
        return bool(self._get_action("skill_wheel"))

    def _should_contextual_thrust(self):
        try:
            if not bool(getattr(self.cs, "grounded", True)):
                return False
        except Exception:
            return False
        if bool(getattr(self, "_is_flying", False)):
            return False

        mx, my = self._get_move_axes()
        if float(my) < 0.58 or abs(float(mx)) > 0.42:
            return False

        style = "unarmed"
        if hasattr(self, "_weapon_combo_style"):
            try:
                style = str(self._weapon_combo_style() or "unarmed").strip().lower()
            except Exception:
                style = "unarmed"
        if style not in {"sword", "staff", "unarmed"}:
            return False

        info = getattr(getattr(self, "app", None), "_aim_target_info", None)
        if isinstance(info, dict):
            try:
                return float(info.get("distance", 99.0) or 99.0) <= 3.8
            except Exception:
                return False
        return False

    def _sync_skill_wheel_hud(self):
        hud = getattr(self.app, "hud", None)
        if not hud or not hasattr(hud, "set_skill_wheel_visible"):
            return
        wheel_key = str(self.data_mgr.get_binding("skill_wheel") or "tab").strip()
        if wheel_key:
            self._skill_wheel_hint_key = wheel_key.upper()
        try:
            hud.set_skill_wheel_visible(
                self._skill_wheel_open,
                hovered_idx=self._skill_wheel_hover_idx,
                preview_idx=self._skill_wheel_preview_idx,
                hint_key=self._skill_wheel_hint_key,
            )
        except Exception:
            pass

    def _update_skill_wheel_input(self):
        self._refresh_spell_cache()
        held = self._is_skill_wheel_held()

        if held and not self._skill_wheel_open:
            self._skill_wheel_open = True
            self._skill_wheel_hover_idx = None
            self._skill_wheel_preview_idx = int(self._active_spell_idx)
            try:
                self._play_sfx("ui_click", volume=0.38)
            except Exception:
                pass

        if not self._skill_wheel_open:
            self._sync_skill_wheel_hud()
            return

        hovered = None
        input_locked = bool(
            getattr(getattr(self, "app", None), "_video_bot_enabled", False)
            and getattr(getattr(self, "app", None), "_video_bot_capture_input", False)
        )
        if hasattr(self.app, "hud") and self.app.hud:
            if input_locked:
                mx_ndc, my_ndc = getattr(self.app, "_video_bot_cursor_pos", (0.0, 0.0))
            elif getattr(self.app, "mouseWatcherNode", None) and self.app.mouseWatcherNode.hasMouse():
                mx_ndc = self.app.mouseWatcherNode.getMouseX()
                my_ndc = self.app.mouseWatcherNode.getMouseY()
            else:
                mx_ndc = None
                my_ndc = None
            if mx_ndc is not None and my_ndc is not None:
                hovered = self.app.hud.pick_skill_slot(mx_ndc, my_ndc)
                if hovered is not None and (hovered < 0 or hovered >= len(self._spell_cache)):
                    hovered = None

        if hovered is not None and hovered != self._skill_wheel_hover_idx:
            try:
                self._play_sfx("ui_hover", volume=0.25)
            except Exception:
                pass

        self._skill_wheel_hover_idx = hovered
        if hovered is not None:
            self._skill_wheel_preview_idx = int(hovered)

        if not held:
            idx = self._skill_wheel_preview_idx
            if isinstance(idx, int) and 0 <= idx < len(self._spell_cache):
                self.set_active_spell_index(idx)
            self._skill_wheel_open = False
            self._skill_wheel_hover_idx = None
            self._skill_wheel_preview_idx = None
            try:
                self._play_sfx("ui_click", volume=0.45)
            except Exception:
                pass

        self._sync_skill_wheel_hud()

    def register_incoming_damage(self, amount=0.0, damage_type="physical"):
        try:
            dmg = max(0.0, float(amount or 0.0))
        except Exception:
            dmg = 0.0
        dtype = str(damage_type or "physical").strip().lower() or "physical"
        if dmg > 0.0:
            self._incoming_damage_amount = max(float(getattr(self, "_incoming_damage_amount", 0.0) or 0.0), dmg)
            self._incoming_damage_type = dtype

    def get_damage_vignette_state(self):
        return {
            "type": str(getattr(self, "_damage_vignette_type", "") or "").strip().lower(),
            "intensity": max(0.0, min(1.0, float(getattr(self, "_damage_vignette_intensity", 0.0) or 0.0))),
        }

    def _tick_damage_vignette_state(self, dt):
        try:
            decay = max(0.0, float(dt or 0.0)) * 1.85
        except Exception:
            decay = 0.0
        self._damage_vignette_intensity = max(
            0.0,
            float(getattr(self, "_damage_vignette_intensity", 0.0) or 0.0) - decay,
        )
        if self._damage_vignette_intensity <= 0.001:
            self._damage_vignette_intensity = 0.0
            self._damage_vignette_type = ""

    def _update_damage_feedback(self):
        cs = getattr(self, "cs", None)
        if not cs or (not hasattr(cs, "health")):
            return
        try:
            current_hp = float(cs.health)
        except Exception:
            return
        prev_hp = getattr(self, "_last_hp_observed", None)
        self._last_hp_observed = current_hp
        if prev_hp is None:
            return
        delta = float(prev_hp) - current_hp
        if delta <= 0.35:
            return

        max_hp = max(1.0, float(getattr(cs, "maxHealth", 100.0) or 100.0))
        damage_ratio = max(0.0, min(1.0, delta / max_hp))
        self._pending_damage_ratio = max(float(getattr(self, "_pending_damage_ratio", 0.0) or 0.0), damage_ratio)
        incoming_type = str(getattr(self, "_incoming_damage_type", "") or "").strip().lower()
        if not incoming_type:
            incoming_type = "crush" if damage_ratio >= 0.20 else "physical"
        vignette_intensity = max(
            0.10,
            min(
                1.0,
                (damage_ratio * 3.5) + (min(delta, max_hp * 0.45) / max(14.0, max_hp * 0.36)),
            ),
        )
        self._damage_vignette_type = incoming_type
        self._damage_vignette_intensity = max(
            float(getattr(self, "_damage_vignette_intensity", 0.0) or 0.0),
            vignette_intensity,
        )
        self._incoming_damage_type = ""
        self._incoming_damage_amount = 0.0

    def _set_stealth_crouch(self, enabled):
        desired = bool(enabled)
        if desired == bool(getattr(self, "_stealth_crouch", False)):
            return
        self._stealth_crouch = desired
        if desired:
            self._is_flying = False

    def _sync_stealth_input(self):
        if self._once_action("crouch_toggle"):
            self._set_stealth_crouch(not bool(getattr(self, "_stealth_crouch", False)))
            self._stealth_crouch_hold_latched = False
            self._stealth_crouch_hold_prev = False

        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        mounted = bool(vehicle_mgr and getattr(vehicle_mgr, "is_mounted", False))
        flying = bool(getattr(self, "_is_flying", False))

        hold_pressed = bool(self._get_action("crouch_hold"))
        if hold_pressed and (not mounted) and (not flying):
            if not bool(getattr(self, "_stealth_crouch_hold_latched", False)):
                self._stealth_crouch_hold_prev = bool(getattr(self, "_stealth_crouch", False))
            self._set_stealth_crouch(True)
            self._stealth_crouch_hold_latched = True
        elif bool(getattr(self, "_stealth_crouch_hold_latched", False)):
            restore = bool(getattr(self, "_stealth_crouch_hold_prev", False))
            self._stealth_crouch_hold_latched = False
            self._stealth_crouch_hold_prev = False
            self._set_stealth_crouch(restore)

        if mounted or flying:
            self._stealth_crouch_hold_latched = False
            self._stealth_crouch_hold_prev = False
            self._set_stealth_crouch(False)

    def _update_brain_runtime(self, mx, my, cam_yaw):
        brain = getattr(self, "brain", None)
        if not brain:
            return

        actor = getattr(self, "actor", None)
        x = y = 0.0
        heading = 0.0
        if actor:
            try:
                pos = actor.getPos(self.render)
            except Exception:
                pos = actor.getPos()
            x = float(pos.x)
            y = float(pos.y)
            heading = float(actor.getH())

        speed = 0.0
        vertical_speed = 0.0
        on_ground = True
        in_water = False
        combat_now = False
        location_name = str(getattr(getattr(self.app, "world", None), "active_location", "") or "")

        if self.cs:
            try:
                vx = float(getattr(self.cs.velocity, "x", 0.0) or 0.0)
                vy = float(getattr(self.cs.velocity, "y", 0.0) or 0.0)
                speed = math.sqrt((vx * vx) + (vy * vy))
                vertical_speed = float(getattr(self.cs.velocity, "z", 0.0) or 0.0)
            except Exception:
                speed = 0.0
                vertical_speed = 0.0
            on_ground = bool(getattr(self.cs, "grounded", True))
            in_water = bool(getattr(self.cs, "inWater", False))
        else:
            if self._brain_last_pos is None and actor:
                self._brain_last_pos = actor.getPos(self.render)
            if actor and self._brain_last_pos is not None:
                now_pos = actor.getPos(self.render)
                delta = now_pos - self._brain_last_pos
                dt = max(1e-3, float(globalClock.getDt()))
                speed = float(math.sqrt((delta.x * delta.x) + (delta.y * delta.y)) / dt)
                vertical_speed = float(delta.z / dt)
                self._brain_last_pos = now_pos
            on_ground = bool(getattr(self, "_py_grounded", True))

        if self.combat and hasattr(self.combat, "isAttacking"):
            try:
                combat_now = bool(self.combat.isAttacking())
            except Exception:
                combat_now = False

        yaw_radians = math.radians(cam_yaw)
        move_dx = (mx * math.cos(yaw_radians)) + (my * math.sin(yaw_radians))
        move_dy = (-mx * math.sin(yaw_radians)) + (my * math.cos(yaw_radians))
        turn_angle_deg = 0.0
        if abs(move_dx) > 1e-3 or abs(move_dy) > 1e-3:
            desired_h = 180.0 - math.degrees(math.atan2(move_dx, move_dy))
            turn_angle_deg = abs(((desired_h - heading + 180.0) % 360.0) - 180.0)

        sensors = {
            "x": x,
            "y": y,
            "speed": speed,
            "vertical_speed": vertical_speed,
            "on_ground": on_ground,
            "is_flying": bool(self._is_flying),
            "parkour": bool(getattr(self, "_was_wallrun", False)),
            "combat": combat_now,
            "in_water": in_water,
            "is_crouched": bool(getattr(self, "_stealth_crouch", False)),
            "stealth_context": bool(getattr(self.app, "_stealth_state_cache", {}).get("context_override", "") == "stealth"),
            "fatigue": 0.0,
            "hp_ratio": 1.0,
            "location_name": location_name,
        }
        intent = {
            "move_x": float(mx),
            "move_y": float(my),
            "turn_angle_deg": turn_angle_deg,
        }
        try:
            self._motion_plan = brain.evaluate(intent, sensors)
        except Exception:
            self._motion_plan = {}

    def update(self, dt, cam_yaw):
        director = getattr(self.app, "camera_director", None)
        cutscene_active = False
        if director and hasattr(director, "is_cutscene_active"):
            try:
                cutscene_active = bool(director.is_cutscene_active())
            except Exception:
                cutscene_active = False

        if self._once_action("inventory") and (not cutscene_active):
            if self.app.state_mgr.current_state == self.app.GameState.INVENTORY:
                if hasattr(self.app, "_hide_inventory_ui"):
                    self.app._hide_inventory_ui()
                else:
                    self.app.state_mgr.set_state(self.app.GameState.PLAYING)
                    self.app.inventory_ui.hide()
            elif self.app.state_mgr.current_state == self.app.GameState.PLAYING:
                if hasattr(self.app, "_show_inventory_ui"):
                    self.app._show_inventory_ui(tab="inventory")
                else:
                    self.app.state_mgr.set_state(self.app.GameState.INVENTORY)
                    self.app.inventory_ui.show()

        self._update_skill_wheel_input()
        self._update_damage_feedback()
        self._tick_damage_vignette_state(dt)

        if self.app.state_mgr.current_state == self.app.GameState.INVENTORY:
            if self._skill_wheel_open:
                self._skill_wheel_open = False
                self._skill_wheel_hover_idx = None
                self._skill_wheel_preview_idx = None
                self._sync_skill_wheel_hud()
            return

        mx, my = self._get_move_axes()
        self._sync_stealth_input()
        self._sync_block_state_edges()
        interacted = self._once_action("interact")
        handled_vehicle = False
        if interacted:
            handled_vehicle = self._try_vehicle_interact()

        if not self.cs or not HAS_CORE:
            self._update_brain_runtime(mx, my, cam_yaw)
            if self._update_vehicle_control(dt, cam_yaw, mx, my):
                return
            if interacted and not handled_vehicle:
                interaction_handled = self._try_npc_interact()
                if not interaction_handled:
                    interaction_handled = self._try_story_interact()
                if (not interaction_handled) and getattr(self.app, "quest_mgr", None):
                    self.app.quest_mgr.try_interact(self.actor.getPos())
            self._update_combat(dt)
            self._proc_animate(dt)
            self._update_python_movement(dt, cam_yaw, mx=mx, my=my)
            return

        yaw_radians = math.radians(cam_yaw)
        move = gc.Vec3(
            mx * math.cos(yaw_radians) + my * math.sin(yaw_radians),
            -mx * math.sin(yaw_radians) + my * math.cos(yaw_radians),
            0,
        )
        self._update_brain_runtime(mx, my, cam_yaw)

        if self._update_vehicle_control(dt, cam_yaw, mx, my):
            return

        if self._once_action("flight_toggle"):
            now = float(globalClock.getFrameTime())
            self._is_flying = not self._is_flying
            if self._is_flying:
                self._set_stealth_crouch(False)
                self._flight_takeoff_until = now + 0.42
                self._flight_land_until = 0.0
            elif bool(getattr(self.cs, "grounded", False)):
                self._flight_land_until = now + 0.34
                self._flight_takeoff_until = 0.0
            self.cs.velocity.z = 0

        if self._is_flying:
            self._update_flight(move)
        else:
            self._set_flight_fx(False)
            self._update_ground(dt, move)
        self._sync_wall_contact_state()

        if interacted and not handled_vehicle:
            interaction_handled = self._try_npc_interact()
            if not interaction_handled:
                interaction_handled = self._try_story_interact()
            if (not interaction_handled) and getattr(self.app, "quest_mgr", None):
                self.app.quest_mgr.try_interact(self.actor.getPos())

        self._update_combat(dt)
        self._final_step(dt)

    def _update_combat(self, dt):
        combat_system = getattr(self, "combat", None)
        magic_system = getattr(self, "magic", None)

        if self._skill_wheel_open:
            self._is_aiming = False
            self._aim_mode = ""
            if combat_system and hasattr(combat_system, "update"):
                try:
                    combat_system.update(dt, self.cs, self.enemies)
                except Exception:
                    pass
            if magic_system and hasattr(magic_system, "update"):
                try:
                    magic_system.update(dt, self.enemies, lambda fx: self._on_spell_effect(fx))
                except Exception:
                    pass
            return

        action_used = False
        self._refresh_spell_cache()

        spell_indices = [
            idx
            for idx, key in enumerate(self._spell_cache)
            if not is_melee_wheel_token(key)
        ]
        for i in range(min(7, len(spell_indices))):
            if self._once_action(f"spell_{i+1}"):
                self._active_spell_idx = spell_indices[i]

        light_pressed = self._once_action("attack_light")
        explicit_cast_pressed = self._once_action("spell_cast")
        thrust_pressed = self._once_action("attack_thrust")
        selected_label = ""
        if 0 <= int(self._active_spell_idx) < len(self._spell_cache):
            selected_label = self._spell_cache[int(self._active_spell_idx)]
        aim_pressed = bool(self._get_action("aim"))
        if hasattr(self, "_sync_aim_mode"):
            try:
                self._sync_aim_mode(selected_label=selected_label, aim_pressed=aim_pressed)
            except Exception:
                self._is_aiming = False
                self._aim_mode = ""

        if light_pressed:
            cast_requested = should_cast_selected_spell(
                light_pressed=light_pressed,
                selected_label=selected_label,
                explicit_cast=explicit_cast_pressed,
            )
            casted = self._cast_spell_by_index(self._active_spell_idx) if cast_requested else False
            ranged_shot = False
            if (not casted) and hasattr(self, "_is_ranged_weapon_equipped") and self._is_ranged_weapon_equipped():
                ranged_shot = bool(self._perform_ranged_attack("light"))
            if not casted and (not ranged_shot):
                use_thrust = bool(thrust_pressed or self._should_contextual_thrust())
                try:
                    self._play_sfx("sword_swing", volume=0.84 if use_thrust else 0.88, rate=1.12 if use_thrust else 1.04)
                except Exception:
                    pass
                if HAS_CORE and gc and combat_system and self.cs and hasattr(combat_system, "startAttack"):
                    self._on_hit(combat_system.startAttack(self.cs, gc.AttackType.Light, self.enemies))
                else:
                    self._push_combat_event("physical", 10, source_label="melee")
                attack_kind = "thrust" if use_thrust else "light"
                attack_triggers = self._resolve_weapon_attack_triggers(attack_kind)
                self._apply_state_anim_hint_tokens("attacking", attack_triggers)
                for trigger in attack_triggers:
                    self._queue_state_trigger(trigger)
                if hasattr(self, "_force_action_state"):
                    self._force_action_state("attacking")
            action_used = True
        elif thrust_pressed:
            if not (hasattr(self, "_is_ranged_weapon_equipped") and self._is_ranged_weapon_equipped()):
                try:
                    self._play_sfx("sword_swing", volume=0.84, rate=1.12)
                except Exception:
                    pass
                if HAS_CORE and gc and combat_system and self.cs and hasattr(combat_system, "startAttack"):
                    self._on_hit(combat_system.startAttack(self.cs, gc.AttackType.Light, self.enemies))
                else:
                    self._push_combat_event("physical", 10, source_label="melee")
                attack_triggers = self._resolve_weapon_attack_triggers("thrust")
                self._apply_state_anim_hint_tokens("attacking", attack_triggers)
                for trigger in attack_triggers:
                    self._queue_state_trigger(trigger)
                if hasattr(self, "_force_action_state"):
                    self._force_action_state("attacking")
                action_used = True
        elif explicit_cast_pressed:
            if self._cast_spell_by_index(self._active_spell_idx):
                action_used = True
        if self._once_action("attack_heavy"):
            if hasattr(self, "_is_ranged_weapon_equipped") and self._is_ranged_weapon_equipped():
                self._perform_ranged_attack("heavy")
            else:
                try:
                    self._play_sfx("sword_swing", volume=0.96, rate=0.92)
                except Exception:
                    pass
                if HAS_CORE and gc and combat_system and self.cs and hasattr(combat_system, "startAttack"):
                    self._on_hit(combat_system.startAttack(self.cs, gc.AttackType.Heavy, self.enemies))
                else:
                    self._push_combat_event("physical", 16, source_label="melee")
                heavy_triggers = self._resolve_weapon_attack_triggers("heavy")
                self._apply_state_anim_hint_tokens("attacking", heavy_triggers)
                for trigger in heavy_triggers:
                    self._queue_state_trigger(trigger)
                if hasattr(self, "_force_action_state"):
                    self._force_action_state("attacking")
            action_used = True

        if combat_system and hasattr(combat_system, "update"):
            try:
                combat_system.update(dt, self.cs, self.enemies)
            except Exception:
                pass
        if hasattr(self, "_update_spell_casting"):
            self._update_spell_casting()
        if magic_system and hasattr(magic_system, "update"):
            try:
                magic_system.update(dt, self.enemies, lambda fx: self._on_spell_effect(fx))
            except Exception:
                pass

        if action_used:
            self._set_weapon_drawn(True)
        elif combat_system and hasattr(combat_system, "isAttacking"):
            try:
                if combat_system.isAttacking():
                    self._drawn_hold_timer = 1.0
            except Exception:
                pass
