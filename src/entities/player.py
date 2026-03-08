"""Player controller, animation driver, and equipment attachment logic."""

import json
import math
from datetime import datetime
from pathlib import Path

from direct.actor.Actor import Actor
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Texture,
    TransparencyAttrib,
)

try:
    import game_core as gc

    HAS_CORE = True
except ImportError:
    gc = None
    HAS_CORE = False

from entities.mannequin import create_procedural_actor
from entities.animation_manifest import (
    alias_animation_key as manifest_alias_animation_key,
    load_player_manifest_sources,
)
from entities.player_animation_config import (
    ANIM_TOKEN_ALIASES,
    STATE_ANIM_FALLBACK,
)
from entities.player_audio_mixin import PlayerAudioMixin
from entities.player_combat_mixin import PlayerCombatMixin
from entities.player_input_mixin import PlayerInputMixin
from entities.player_movement_mixin import PlayerMovementMixin
from entities.player_state_machine_mixin import PlayerStateMachineMixin
from entities.character_brain import CharacterBrain
from render.model_visuals import ensure_model_visual_defaults
from utils.logger import logger
from utils.runtime_paths import is_user_data_mode, runtime_file


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

        self.walk_speed = self.data_mgr.get_move_param("walk_speed") or 5.0
        self.run_speed = self.data_mgr.get_move_param("run_speed") or 9.0
        self.flight_speed = self.data_mgr.get_move_param("flight_speed") or 15.0

        self._anim_state = "idle"
        self._anim_clip = ""
        self._anim_blend_enabled = False
        self._anim_blend_duration = 0.18
        self._anim_blend_transition = None
        self._available_anims = set()
        self._state_anim_tokens = {}
        self._state_anim_overrides = {}
        self._manifest_anim_loop_hints = {}
        self._state_defs = {}
        self._state_transitions = []
        self._state_rules = []
        self._queued_state_triggers = []
        self._state_lock_until = 0.0
        self._last_landing_impact_speed = 0.0
        self._block_pressed = False
        self._was_wallrun = False
        self._state_anim_fallback = {
            key: list(value) for key, value in STATE_ANIM_FALLBACK.items()
        }
        self._anim_token_aliases = {
            key: list(value) for key, value in ANIM_TOKEN_ALIASES.items()
        }
        self._trail_id = -1
        self._was_in_water = False
        self._is_flying = False
        self._stealth_crouch = False
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
        self._has_weapon_visual = False
        self._has_offhand_visual = False
        self._anim_failed_once = set()
        self._anim_missing_state_once = set()
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

        self._keys = {}
        self._consumed = {}
        self._spell_cache = []
        self._active_spell_idx = 0
        self._ultimate_spell_idx = 0
        self._spell_cooldowns = {}
        self._spell_cast_lock_until = 0.0
        self._last_combat_event = None
        self._combo_chain = 0
        self._combo_deadline = 0.0
        self._combo_style = "unarmed"
        self._combo_kind = "melee"
        self._last_hp_observed = None
        self._pending_damage_ratio = 0.0
        if self.cs and hasattr(self.cs, "health"):
            try:
                self._last_hp_observed = float(self.cs.health)
            except Exception:
                self._last_hp_observed = None
        self._skill_wheel_open = False
        self._skill_wheel_hover_idx = None
        self._skill_wheel_preview_idx = None
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
        self._setup_sword_trail()
        self._setup_input()
        self._build_flight_vfx()
        self._refresh_spell_cache()

    def _alias_animation_key(self, stem):
        return manifest_alias_animation_key(stem)

    def _collect_optional_animation_sources(self):
        manifest_sources, strict_manifest = self._load_manifest_animation_sources()
        if strict_manifest:
            if not manifest_sources:
                logger.warning("[Anim] Strict manifest mode is enabled but no valid sources were found.")
            else:
                logger.info(f"[Anim] Loaded strict manifest animation sources: {len(manifest_sources)}")
            return manifest_sources

        candidates = dict(manifest_sources)
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
                    candidates.setdefault(key, path.as_posix())
        return candidates

    def _load_manifest_animation_sources(self):
        mapping, strict_mode, diagnostics = load_player_manifest_sources(
            "data/actors/player_animations.json",
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
            path = Path("data/actors/player.json")
            try:
                if path.exists():
                    payload = json.loads(path.read_text(encoding="utf-8-sig"))
                    if isinstance(payload, dict):
                        nested = payload.get("player", payload)
                        if isinstance(nested, dict):
                            cfg = nested
            except Exception as exc:
                logger.warning(f"[Player] Failed to read {path.as_posix()}: {exc}")
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

        existing = [path for path in candidates if Path(path).exists()]
        if existing:
            return existing
        return candidates

    def _resolve_player_scale(self):
        cfg = self._player_model_config()
        try:
            return max(0.05, min(10.0, float(cfg.get("scale", 1.0) or 1.0)))
        except Exception:
            return 1.0

    def _resolve_base_anims(self):
        defaults = {
            "idle": "assets/models/xbot/idle.glb",
            "walk": "assets/models/xbot/walk.glb",
            "run": "assets/models/xbot/run.glb",
        }
        cfg = self._player_model_config()
        raw = cfg.get("base_anims")
        if not isinstance(raw, dict):
            return defaults

        resolved = {}
        for key, value in raw.items():
            clip_key = str(key or "").strip().lower()
            clip_path = str(value or "").strip().replace("\\", "/")
            if not clip_key or not clip_path:
                continue
            resolved[clip_key] = clip_path
        if not resolved:
            return defaults
        return resolved

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
        if depth >= (width * 0.30):
            return

        target_depth = width * 0.34
        scale_y_mul = max(1.0, min(6.0, target_depth / max(depth, 1e-4)))
        if scale_y_mul <= 1.01:
            return

        try:
            self.actor.setSy(self.actor.getSy() * scale_y_mul)
            logger.warning(
                "[Player] Applied Sherward mesh depth correction: "
                f"sy*={scale_y_mul:.2f} (w={width:.3f}, d={depth:.3f}, h={height:.3f})"
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
            self._stabilize_actor_bounds(loaded_model_path)
            logger.info(f"[Player] Actor loaded: model={loaded_model_path}, scale={player_scale:.3f}")
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

        # Let the actor use the default panda3d shader pipeline (auto-shader or complexpbr)
        # instead of forcing the terrain shader, which caused the white silhouette issue.
        self.actor.set_shader_input("specular_factor", 0.5, priority=1000)
        self.actor.set_shader_input("roughness", 0.5, priority=1000)
        ensure_model_visual_defaults(
            self.actor,
            apply_skin=True,
            debug_label="player_actor",
        )
        # In Python-only mode we occasionally get overly dark skinned actors under PBR.
        # Force fixed-function rendering fallback for readability.
        if not HAS_CORE:
            try:
                self.actor.setShaderOff(1002)
            except Exception:
                pass
            try:
                self.actor.setColorScale(1.0, 1.0, 1.0, 1.0)
            except Exception:
                pass
            try:
                self.actor.setTwoSided(True)
            except Exception:
                pass

        self._resolve_attachment_nodes()
        self._build_equipment_visuals()
        self._init_animation_system()

    def _load_player_state_animation_tokens(self):
        path = Path("data/states/player_states.json")
        if not path.exists():
            self._state_defs = {}
            self._state_transitions = []
            self._state_rules = []
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            logger.warning(f"[Anim] Failed to load player_states.json: {exc}")
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
        path = Path("data/actors/player_animations.json")
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            logger.warning(f"[Anim] Failed to load player_animations.json: {exc}")
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
        path = Path("data/actors/player_animations.json")
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            logger.warning(f"[Anim] Failed to parse loop hints from player_animations.json: {exc}")
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
                if alias_key and alias_key not in hints:
                    hints[alias_key] = loop_value
        return hints

    def _normalize_anim_key(self, token):
        return "".join(ch for ch in str(token or "").lower() if ch.isalnum())

    def _init_animation_system(self):
        if not hasattr(self.actor, "loop"):
            return

        self._state_anim_tokens = self._load_player_state_animation_tokens()
        self._state_anim_overrides = self._load_actor_animation_overrides()
        self._manifest_anim_loop_hints = self._load_manifest_loop_hints()

        try:
            self._available_anims = {str(name) for name in self.actor.getAnimNames()}
        except Exception:
            self._available_anims = set()

        anim_cfg = self.data_mgr.controls.get("animation", {})
        if isinstance(anim_cfg, dict):
            try:
                raw = float(anim_cfg.get("blend_time", self._anim_blend_duration) or self._anim_blend_duration)
                self._anim_blend_duration = max(0.02, min(1.2, raw))
            except Exception:
                pass

        if hasattr(self.actor, "enableBlend") and hasattr(self.actor, "setControlEffect"):
            try:
                self.actor.enableBlend()
                self._anim_blend_enabled = True
            except Exception as exc:
                logger.warning(f"[Anim] Blend disabled: {exc}")
                self._anim_blend_enabled = False

        self._write_animation_coverage_report()
        self._set_anim("idle", loop=True, force=True)

    def _current_mount_anim_kind(self):
        kind = str(self._mount_anim_kind or "").strip().lower()
        if kind:
            return kind
        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if not vehicle_mgr or not getattr(vehicle_mgr, "is_mounted", False):
            return ""
        vehicle = vehicle_mgr.mounted_vehicle() if hasattr(vehicle_mgr, "mounted_vehicle") else None
        if not isinstance(vehicle, dict):
            return ""
        return str(vehicle.get("kind", "")).strip().lower()

    def _mount_state_context_tokens(self, state_key):
        key = str(state_key or "").strip().lower()
        if key not in {
            "mounting",
            "mounted_idle",
            "mounted_move",
            "mounted_ship_idle",
            "mounted_ship_move",
            "dismounting",
        }:
            return []
        kind = self._current_mount_anim_kind()
        if not kind:
            return []

        tokens = [f"{key}_{kind}", f"{kind}_{key}"]
        if key == "mounting":
            tokens.extend(
                [
                    f"mount_{kind}_start",
                    f"{kind}_mount_start",
                    f"mountstart_{kind}",
                ]
            )
        elif key in {"mounted_idle", "mounted_ship_idle"}:
            tokens.extend(
                [
                    f"mounted_{kind}_idle",
                    f"mount_{kind}_idle",
                ]
            )
        elif key in {"mounted_move", "mounted_ship_move"}:
            tokens.extend(
                [
                    f"mounted_{kind}_move",
                    f"mount_{kind}_move",
                ]
            )
        elif key == "dismounting":
            tokens.extend(
                [
                    f"dismount_{kind}",
                    f"dismount_{kind}_end",
                    f"{kind}_dismount",
                ]
            )
        return tokens

    def _iter_anim_candidates(
        self, state_name, include_state_fallback=True, include_global_fallback=True
    ):
        state = str(state_name or "idle").strip()
        state_key = state.lower()
        candidates = []

        for token in self._mount_state_context_tokens(state_key):
            candidates.append((token, "mount_context"))

        for token in self._state_anim_overrides.get(state_key, []):
            candidates.append((token, "player_animations"))

        state_token = self._state_anim_tokens.get(state_key)
        if state_token:
            candidates.append((state_token, "player_states"))

        candidates.append((state, "state_name"))
        if include_state_fallback:
            for token in self._state_anim_fallback.get(state_key, []):
                candidates.append((token, "state_fallback"))

        expanded = []
        for token, source in candidates:
            expanded.append((token, source))
            alias = self._anim_token_aliases.get(self._normalize_anim_key(token), [])
            for alias_token in alias:
                expanded.append((alias_token, f"alias:{source}"))

        if include_global_fallback:
            expanded.extend([("idle", "global_fallback"), ("walk", "global_fallback"), ("run", "global_fallback")])

        dedup = []
        seen = set()
        for token, source in expanded:
            key = str(token or "").strip()
            if not key:
                continue
            marker = key.lower()
            if marker in seen:
                continue
            seen.add(marker)
            dedup.append((key, source))
        return dedup

    def _resolve_anim_clip(
        self,
        state_name,
        include_state_fallback=True,
        include_global_fallback=True,
        with_meta=False,
    ):
        available = list(self._available_anims)
        available_lower = {name.lower(): name for name in available}
        available_norm = {self._normalize_anim_key(name): name for name in available}

        for candidate, source in self._iter_anim_candidates(
            state_name,
            include_state_fallback=include_state_fallback,
            include_global_fallback=include_global_fallback,
        ):
            if candidate in self._available_anims:
                if with_meta:
                    return candidate, source, candidate
                return candidate

            lower = candidate.lower()
            if lower in available_lower:
                match = available_lower[lower]
                if with_meta:
                    return match, source, candidate
                return match

            normalized = self._normalize_anim_key(candidate)
            if normalized in available_norm:
                match = available_norm[normalized]
                if with_meta:
                    return match, source, candidate
                return match

        if with_meta:
            return None, None, None
        return None

    def _state_loop_hint(self, state_name, resolved_clip=None):
        hints = getattr(self, "_manifest_anim_loop_hints", {})
        if not isinstance(hints, dict) or not hints:
            return None

        state_key = self._normalize_anim_key(state_name)
        if state_key in hints:
            return hints.get(state_key)

        clip_key = self._normalize_anim_key(resolved_clip)
        if clip_key in hints:
            return hints.get(clip_key)

        for token, _ in self._iter_anim_candidates(
            state_name,
            include_state_fallback=True,
            include_global_fallback=False,
        ):
            token_key = self._normalize_anim_key(token)
            if token_key in hints:
                return hints.get(token_key)
        return None

    def _resolved_clip_duration(self, clip_name):
        if not clip_name or not hasattr(self.actor, "getDuration"):
            return 0.0
        try:
            duration = float(self.actor.getDuration(clip_name) or 0.0)
        except Exception:
            return 0.0
        if not math.isfinite(duration):
            return 0.0
        return max(0.0, min(8.0, duration))

    def _write_animation_coverage_report(self):
        if is_user_data_mode():
            report_path = runtime_file("logs", "ANIMATION_COVERAGE.md")
        else:
            report_path = Path("data/states/ANIMATION_COVERAGE.md")
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

        states = sorted(self._state_defs.keys())
        if not states:
            return

        rows = []
        ok_count = 0
        fallback_count = 0
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

            strict_is_direct = bool(strict_clip) and not str(strict_source or "").startswith("alias:")
            if strict_is_direct:
                status = "OK"
                clip = strict_clip
                source = strict_source or "-"
                ok_count += 1
            elif resolved_clip:
                status = "FALLBACK"
                clip = resolved_clip
                source = resolved_source or "-"
                fallback_count += 1
            else:
                status = "MISSING"
                clip = "-"
                source = "-"
                missing_count += 1

            rows.append(f"| {state_name} | {status} | {clip} | {source} |")

        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = (
            f"- Total states: {len(states)}\n"
            f"- OK: {ok_count}\n"
            f"- Fallback: {fallback_count}\n"
            f"- Missing: {missing_count}\n"
        )

        content = [
            "# Player Animation Coverage",
            "",
            f"Generated: {generated}",
            "",
            summary,
            "| State | Status | Resolved Clip | Source |",
            "|---|---|---|---|",
            *rows,
            "",
        ]

        try:
            report_path.write_text("\n".join(content), encoding="utf-8")
            logger.info(
                f"[Anim] Coverage report written: {report_path.as_posix()} "
                f"(ok={ok_count}, fallback={fallback_count}, missing={missing_count})"
            )
        except Exception as exc:
            logger.warning(f"[Anim] Failed to write coverage report: {exc}")

    def _anim_play_rate(self, state_name):
        state = str(state_name or self._anim_state or "").lower()
        if not self.cs:
            return 1.0

        speed = math.sqrt((self.cs.velocity.x * self.cs.velocity.x) + (self.cs.velocity.y * self.cs.velocity.y))
        if state in {"walking", "walk", "swim", "mounted_move"}:
            ref = max(0.1, self.walk_speed)
            return max(0.72, min(1.35, speed / ref))
        if state in {"running", "run"}:
            ref = max(0.1, self.run_speed)
            return max(0.85, min(1.45, speed / ref))
        if state in {"flying", "fly"}:
            ref = max(0.1, self.flight_speed)
            return max(0.90, min(1.35, speed / ref))
        if state in {"attacking", "dodging"}:
            return 1.08
        if state in {"casting"}:
            return 1.0
        return 1.0

    def _play_actor_anim(self, clip, loop=True, state_name=None):
        if not clip or not hasattr(self.actor, "loop"):
            return False
        try:
            try:
                self.actor.setPlayRate(self._anim_play_rate(state_name), clip)
            except Exception:
                pass
            if loop:
                self.actor.loop(clip)
            else:
                self.actor.play(clip)
            return True
        except Exception as exc:
            marker = f"{clip}|{'loop' if loop else 'play'}"
            if marker not in self._anim_failed_once:
                self._anim_failed_once.add(marker)
                logger.warning(f"[Anim] Playback failed for '{clip}': {exc}")
            return False

    def _force_safe_idle_anim(self):
        fallback_states = ("idle", "walking", "running")
        for fallback_state in fallback_states:
            clip = self._resolve_anim_clip(
                fallback_state,
                include_state_fallback=True,
                include_global_fallback=False,
            )
            if not clip:
                continue
            if not self._play_actor_anim(clip, loop=True, state_name=fallback_state):
                continue

            self._anim_state = fallback_state
            self._anim_clip = clip
            self._anim_blend_transition = None
            if self._anim_blend_enabled:
                try:
                    for anim_name in self._available_anims:
                        self.actor.setControlEffect(anim_name, 0.0)
                    self.actor.setControlEffect(clip, 1.0)
                except Exception:
                    pass
            return True

        logger.warning("[Anim] Failed to recover with safe idle fallback (idle/walking/running).")
        return False

    def _set_anim(self, state_name, loop=True, blend_time=None, force=False):
        clip = self._resolve_anim_clip(state_name)
        target_state = str(state_name or "idle").lower()

        if not clip:
            if target_state not in self._anim_missing_state_once:
                self._anim_missing_state_once.add(target_state)
                candidates = [
                    token
                    for token, _ in self._iter_anim_candidates(
                        target_state,
                        include_state_fallback=True,
                        include_global_fallback=False,
                    )
                ]
                sample = ", ".join(candidates[:10]) if candidates else "-"
                logger.warning(
                    f"[Anim] No clip resolved for state '{target_state}'. "
                    f"Candidates: {sample}"
                )
            if self._force_safe_idle_anim():
                return False
            # Procedural fallback
            if target_state == "jumping":
                self.actor.setHpr(0, -15, 0)
                if hasattr(self, "_right_hand") and self._right_hand:
                    self._right_hand.setP(0)
            elif target_state == "attacking":
                self.actor.setHpr(0, 0, 0)
                if hasattr(self, "_right_hand") and self._right_hand:
                    self._right_hand.setP(-70)
            elif target_state in ("idle", "walking", "running", "swim", "flying", "fly"):
                self.actor.setHpr(0, 0, 0)
                if hasattr(self, "_right_hand") and self._right_hand:
                    self._right_hand.setP(0)
            return False

        if (
            not force
            and target_state == self._anim_state
            and clip == self._anim_clip
            and not self._anim_blend_transition
        ):
            return True

        old_clip = self._anim_clip or None
        old_state = str(self._anim_state or "idle").lower()
        self._anim_state = target_state
        self._anim_clip = clip

        if not self._anim_blend_enabled or not old_clip or old_clip == clip:
            ok = self._play_actor_anim(clip, loop=loop, state_name=target_state)
            if not ok:
                self._force_safe_idle_anim()
                return False
            if ok and self._anim_blend_enabled:
                try:
                    for anim_name in self._available_anims:
                        self.actor.setControlEffect(anim_name, 0.0)
                    self.actor.setControlEffect(clip, 1.0)
                except Exception:
                    pass
            self._anim_blend_transition = None
            return ok

        self._play_actor_anim(old_clip, loop=True, state_name=old_state)
        if not self._play_actor_anim(clip, loop=loop, state_name=target_state):
            self._force_safe_idle_anim()
            return False

        try:
            self.actor.setControlEffect(old_clip, 1.0)
            self.actor.setControlEffect(clip, 0.0)
        except Exception:
            self._anim_blend_transition = None
            return True

        duration = self._anim_blend_duration if blend_time is None else float(blend_time)
        self._anim_blend_transition = {
            "from": old_clip,
            "to": clip,
            "elapsed": 0.0,
            "duration": max(0.02, duration),
        }
        return True

    def _tick_anim_blend(self, dt):
        if not self._anim_blend_enabled:
            return
        transition = self._anim_blend_transition
        if not isinstance(transition, dict):
            return

        duration = max(0.02, float(transition.get("duration", self._anim_blend_duration)))
        elapsed = float(transition.get("elapsed", 0.0)) + max(0.0, float(dt))
        transition["elapsed"] = elapsed
        alpha = max(0.0, min(1.0, elapsed / duration))
        old_clip = transition.get("from")
        new_clip = transition.get("to")

        try:
            if old_clip:
                self.actor.setControlEffect(old_clip, 1.0 - alpha)
            if new_clip:
                self.actor.setControlEffect(new_clip, alpha)
        except Exception:
            self._anim_blend_transition = None
            return

        if alpha >= 1.0:
            try:
                if old_clip and old_clip != new_clip:
                    self.actor.setControlEffect(old_clip, 0.0)
                    self.actor.stop(old_clip)
                if new_clip:
                    self.actor.setControlEffect(new_clip, 1.0)
            except Exception:
                pass
            self._anim_blend_transition = None

    def _resolve_joint(self, names):
        for bone in names:
            try:
                np = self.actor.exposeJoint(None, "modelRoot", bone)
                if np and not np.isEmpty():
                    return np
            except Exception:
                continue
        return None

    def _resolve_attachment_nodes(self):
        self._right_hand = self._resolve_joint(
            ["mixamorig:RightHand", "RightHand", "hand_r", "Hand_R"]
        )
        self._left_hand = self._resolve_joint(
            ["mixamorig:LeftHand", "LeftHand", "hand_l", "Hand_L"]
        )
        self._left_hip = self._resolve_joint(
            ["mixamorig:LeftUpLeg", "LeftUpLeg", "LeftThigh", "thigh_l"]
        )
        self._spine_upper = self._resolve_joint(
            ["mixamorig:Spine2", "Spine2", "Spine", "spine_03"]
        )

        self._sword_hand_anchor = (self._right_hand or self.actor).attachNewNode(
            "sword_hand_anchor"
        )
        self._shield_hand_anchor = (self._left_hand or self.actor).attachNewNode(
            "shield_hand_anchor"
        )
        self._sword_sheath_anchor = (self._left_hip or self.actor).attachNewNode(
            "sword_sheath_anchor"
        )
        self._shield_sheath_anchor = (self._spine_upper or self.actor).attachNewNode(
            "shield_sheath_anchor"
        )

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

    def _build_equipment_visuals(self):
        self._sword_node = self.actor.attachNewNode("sword_visual")
        self._shield_node = self.actor.attachNewNode("shield_visual")
        self._build_sword(self._sword_node)
        self._build_shield(self._shield_node)
        self._armor_node = (self._spine_upper or self.actor).attachNewNode("armor_visual")
        self._trinket_node = (self._spine_upper or self.actor).attachNewNode("trinket_visual")
        self._build_armor(self._armor_node)
        self._build_trinket(self._trinket_node)
        ensure_model_visual_defaults(
            self._sword_node,
            force_two_sided=True,
            debug_label="player_sword_visual",
        )
        ensure_model_visual_defaults(
            self._shield_node,
            force_two_sided=True,
            debug_label="player_shield_visual",
        )
        ensure_model_visual_defaults(
            self._armor_node,
            force_two_sided=True,
            debug_label="player_armor_visual",
        )
        ensure_model_visual_defaults(
            self._trinket_node,
            force_two_sided=True,
            debug_label="player_trinket_visual",
        )
        self._apply_equipment_visuals()
        self._set_weapon_drawn(False, reset_timer=True)

    def _build_flight_vfx(self):
        self._flight_fx_root = self.actor.attachNewNode("flight_fx_root")
        self._flight_fx_root.setPos(0.0, -0.28, 1.05)
        self._flight_fx_root.hide()
        flare_tex = None
        try:
            flare_tex = self.loader.loadTexture("assets/textures/flare.png")
        except Exception:
            flare_tex = None

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
            fx.setTransparency(TransparencyAttrib.MAlpha)
            fx.setLightOff(1)
            fx.setTwoSided(True)
            fx.setShaderOff(1002)
            fx.setDepthWrite(False)
            fx.setBin("transparent", 35)
            if flare_tex:
                try:
                    fx.setTexture(flare_tex, 1)
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
            self.actor.setP(0.0)
            self.actor.setR(0.0)

    def _update_flight_pose_and_fx(self, move):
        self._set_flight_fx(True)
        if not hasattr(self, "_flight_fx_root"):
            return

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

    def _build_sword(self, parent):
        grip = self._make_box(parent, "sword_grip", 0.05, 0.05, 0.32, (0.16, 0.12, 0.09, 1.0))
        guard = self._make_box(parent, "sword_guard", 0.25, 0.06, 0.05, (0.75, 0.75, 0.78, 1.0))
        blade = self._make_box(parent, "sword_blade", 0.07, 0.02, 0.95, (0.90, 0.90, 0.95, 1.0))

        grip.setPos(0, 0, 0.16)
        guard.setPos(0, 0, 0.33)
        blade.setPos(0, 0, 0.82)

        glow = self._make_box(parent, "sword_glow", 0.08, 0.025, 0.95, (0.85, 0.80, 0.35, 0.28))
        glow.setPos(0, 0, 0.82)
        glow.setTransparency(TransparencyAttrib.MAlpha)
        glow.setLightOff(1)

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

    def _resolve_attach_point(self, token):
        key = str(token or "").strip().lower()
        if key in {"right_hand", "hand_r"}:
            return self._sword_hand_anchor
        if key in {"left_hand", "hand_l", "offhand"}:
            return self._shield_hand_anchor
        if key in {"left_hip", "hip_l", "sheathe"}:
            return self._sword_sheath_anchor
        if key in {"spine_upper", "spine", "chest", "back"}:
            return self._spine_upper or self.actor
        return self.actor

    def _apply_equipment_visuals(self):
        data_mgr = getattr(self, "data_mgr", None)

        weapon_item = data_mgr.get_item(self._equipment_state.get("weapon_main", "")) if data_mgr else None
        self._has_weapon_visual = isinstance(weapon_item, dict)
        if self._has_weapon_visual:
            visual = weapon_item.get("equip_visual", {})
            if not isinstance(visual, dict):
                visual = {}
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
            color = self._safe_color4(visual.get("color"), (0.36, 0.36, 0.42, 0.96))
            scale = max(0.72, min(1.35, float(visual.get("scale", 1.0) or 1.0)))
            self._armor_node.setColorScale(*color)
            self._armor_node.setScale(scale)
            attach = self._resolve_attach_point(chest_item.get("attach_point", "spine_upper"))
            self._armor_node.wrtReparentTo(attach)
            self._armor_node.setPos(0.0, 0.0, 0.20)
            self._armor_node.show()
        else:
            self._armor_node.hide()

        trinket_item = data_mgr.get_item(self._equipment_state.get("trinket", "")) if data_mgr else None
        if isinstance(trinket_item, dict):
            visual = trinket_item.get("equip_visual", {})
            if not isinstance(visual, dict):
                visual = {}
            color = self._safe_color4(visual.get("color"), (0.72, 0.86, 0.99, 0.95))
            scale = max(0.35, min(1.25, float(visual.get("scale", 0.75) or 0.75)))
            self._trinket_node.setColorScale(*color)
            self._trinket_node.setScale(scale)
            attach = self._resolve_attach_point(trinket_item.get("attach_point", "spine_upper"))
            self._trinket_node.wrtReparentTo(attach)
            self._trinket_node.setPos(0.0, 0.34, 0.98)
            self._trinket_node.show()
        else:
            self._trinket_node.hide()

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
                self._sword_node.wrtReparentTo(self._sword_hand_anchor)
                self._sword_node.setPos(0.02, 0.01, -0.16)
                self._sword_node.setHpr(-15, -15, 90)
                self._sword_node.show()
            if self._has_offhand_visual:
                self._shield_node.wrtReparentTo(self._shield_hand_anchor)
                self._shield_node.setPos(-0.03, -0.02, -0.08)
                self._shield_node.setHpr(0, 15, 92)
                self._shield_node.show()

            self._drawn_hold_timer = 2.4
            if has_visual and (not was_drawn):
                self._play_sfx("weapon_unsheathe", volume=0.95)
        else:
            if self._has_weapon_visual:
                self._sword_node.wrtReparentTo(self._sword_sheath_anchor)
                self._sword_node.setPos(-0.02, -0.08, 0.02)
                self._sword_node.setHpr(12, -65, -30)
                self._sword_node.show()
            else:
                self._sword_node.hide()

            if self._has_offhand_visual:
                self._shield_node.wrtReparentTo(self._shield_sheath_anchor)
                self._shield_node.setPos(-0.16, -0.10, -0.10)
                self._shield_node.setHpr(-35, 0, 92)
                self._shield_node.show()
            else:
                self._shield_node.hide()

            if reset_timer:
                self._drawn_hold_timer = 0.0

    def _setup_sword_trail(self):
        if self.particles and HAS_CORE:
            self._trail_id = self.particles.spawnSwordTrail(gc.Vec3(0, 0, 0), gc.Vec3(0, 1, 0))

    def _update_sword_trail(self):
        if not (self.particles and HAS_CORE and self._trail_id >= 0):
            return
        sword_world = self._sword_node.getPos(self.render)
        self.particles.setEmitterPos(self._trail_id, gc.Vec3(sword_world.x, sword_world.y, sword_world.z))

    def _try_vehicle_interact(self):
        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if not vehicle_mgr:
            return False
        was_mounted = bool(vehicle_mgr.is_mounted)
        previous_vehicle = vehicle_mgr.mounted_vehicle() if was_mounted and hasattr(vehicle_mgr, "mounted_vehicle") else None
        previous_kind = ""
        if isinstance(previous_vehicle, dict):
            previous_kind = str(previous_vehicle.get("kind", "")).strip().lower()
        try:
            ok = bool(vehicle_mgr.handle_interact(self))
        except Exception as exc:
            logger.warning(f"[Vehicle] Interact failed: {exc}")
            return False
        if not ok:
            return False

        is_mounted = bool(vehicle_mgr.is_mounted)
        if (not was_mounted) and is_mounted:
            mounted_vehicle = vehicle_mgr.mounted_vehicle() if hasattr(vehicle_mgr, "mounted_vehicle") else None
            if isinstance(mounted_vehicle, dict):
                self._mount_anim_kind = str(mounted_vehicle.get("kind", "")).strip().lower()
            self._queue_state_trigger("mount_start")
            self._enter_state("mounting")
            self._set_weapon_drawn(False, reset_timer=True)
            self._play_sfx("ui_click", volume=0.40)
        elif was_mounted and (not is_mounted):
            if previous_kind:
                self._mount_anim_kind = previous_kind
            self._queue_state_trigger("dismount_start")
            self._enter_state("dismounting")
            self._play_sfx("ui_click", volume=0.45)
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

    def _is_skill_wheel_held(self):
        if self._get_action("skill_wheel"):
            return True
        return False

    def _should_contextual_thrust(self):
        # Context-driven thrust: forward intent, grounded melee, and near target.
        try:
            if not bool(getattr(self.cs, "grounded", True)):
                return False
        except Exception:
            return False
        if bool(getattr(self, "_is_flying", False)):
            return False
        if bool(getattr(self, "_is_crouching", False)):
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
                if float(info.get("distance", 99.0) or 99.0) <= 3.8:
                    return True
            except Exception:
                pass
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
            self._play_sfx("ui_click", volume=0.38)

        if not self._skill_wheel_open:
            self._sync_skill_wheel_hud()
            return

        hovered = None
        if (
            hasattr(self.app, "hud")
            and self.app.hud
            and self.app.mouseWatcherNode.hasMouse()
        ):
            mx_ndc = self.app.mouseWatcherNode.getMouseX()
            my_ndc = self.app.mouseWatcherNode.getMouseY()
            hovered = self.app.hud.pick_skill_slot(mx_ndc, my_ndc)
            if hovered is not None and (hovered < 0 or hovered >= len(self._spell_cache)):
                hovered = None

        if hovered is not None and hovered != self._skill_wheel_hover_idx:
            self._play_sfx("ui_hover", volume=0.25)

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
            self._play_sfx("ui_click", volume=0.45)

        self._sync_skill_wheel_hud()

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
        intensity = max(0.25, min(1.8, (damage_ratio * 4.6) + (delta / 22.0)))
        self._pending_damage_ratio = max(float(getattr(self, "_pending_damage_ratio", 0.0) or 0.0), damage_ratio)

        director = getattr(getattr(self, "app", None), "camera_director", None)
        if director and hasattr(director, "emit_impact"):
            try:
                tag = "critical" if damage_ratio >= 0.18 else "hit"
                director.emit_impact(tag, intensity=intensity, direction_deg=180.0)
            except Exception:
                pass

    def _set_stealth_crouch(self, enabled):
        desired = bool(enabled)
        if desired == bool(getattr(self, "_stealth_crouch", False)):
            return
        self._stealth_crouch = desired
        if not desired:
            return
        # Crouch should not coexist with flight or mounted locomotion.
        self._is_flying = False

    def _sync_stealth_input(self):
        if self._once_action("crouch_toggle"):
            self._set_stealth_crouch(not bool(getattr(self, "_stealth_crouch", False)))

        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if vehicle_mgr and getattr(vehicle_mgr, "is_mounted", False):
            self._set_stealth_crouch(False)
        if bool(getattr(self, "_is_flying", False)):
            self._set_stealth_crouch(False)

        damage_ratio = float(getattr(self, "_pending_damage_ratio", 0.0) or 0.0)
        time_fx = getattr(getattr(self, "app", None), "time_fx", None)
        if damage_ratio > 0.0 and time_fx and hasattr(time_fx, "trigger"):
            try:
                if damage_ratio >= 0.20:
                    time_fx.trigger("hard_fall", duration=0.26)
                else:
                    time_fx.trigger("micro_hit", duration=0.12)
            except Exception:
                pass

        brain = getattr(self, "brain", None)
        if damage_ratio > 0.0 and brain and hasattr(brain, "register_injury"):
            # Keep injury updates lightweight: we track short-term trauma windows, not permanent wounds.
            severity = max(0.08, min(1.35, damage_ratio * 2.8))
            part = "head" if damage_ratio >= 0.22 else "torso"
            kind = "crush" if damage_ratio >= 0.22 else "bruise"
            try:
                brain.register_injury(part, kind, severity=severity)
            except Exception:
                pass
        self._pending_damage_ratio = 0.0

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
        stamina_ratio = 1.0
        hp_ratio = 1.0
        in_water = False
        parkour = bool(getattr(self, "_was_wallrun", False))
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
            try:
                hp_ratio = float(self.cs.health) / max(1.0, float(self.cs.maxHealth))
            except Exception:
                hp_ratio = 1.0
            try:
                stamina_ratio = float(self.cs.stamina) / max(1.0, float(self.cs.maxStamina))
            except Exception:
                stamina_ratio = 1.0
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
        if self._anim_state in {"attacking", "attack_light", "attack_heavy", "casting", "dodging", "blocking"}:
            combat_now = True

        yaw_radians = math.radians(cam_yaw)
        move_dx = (mx * math.cos(yaw_radians)) + (my * math.sin(yaw_radians))
        move_dy = (-mx * math.sin(yaw_radians)) + (my * math.cos(yaw_radians))
        move_mag = math.sqrt((move_dx * move_dx) + (move_dy * move_dy))
        turn_angle_deg = 0.0
        if move_mag > 1e-3:
            desired_h = 180.0 - math.degrees(math.atan2(move_dx, move_dy))
            turn_angle_deg = abs(((desired_h - heading + 180.0) % 360.0) - 180.0)

        sensors = {
            "x": x,
            "y": y,
            "speed": speed,
            "vertical_speed": vertical_speed,
            "on_ground": on_ground,
            "is_flying": bool(self._is_flying),
            "parkour": parkour,
            "combat": combat_now,
            "in_water": in_water,
            "is_crouched": bool(getattr(self, "_stealth_crouch", False)),
            "stealth_context": bool(getattr(self.app, "_stealth_state_cache", {}).get("context_override", "") == "stealth"),
            "fatigue": max(0.0, min(1.0, 1.0 - stamina_ratio)),
            "hp_ratio": max(0.0, min(1.0, hp_ratio)),
            "location_name": location_name,
        }
        intent = {
            "move_x": float(mx),
            "move_y": float(my),
            "turn_angle_deg": turn_angle_deg,
        }
        self._motion_plan = brain.evaluate(intent, sensors)

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
                self.app.state_mgr.set_state(self.app.GameState.PLAYING)
                self.app.inventory_ui.hide()
            elif self.app.state_mgr.current_state == self.app.GameState.PLAYING:
                self.app.state_mgr.set_state(self.app.GameState.INVENTORY)
                self.app.inventory_ui.show()

        self._update_skill_wheel_input()
        self._update_damage_feedback()

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
                story_handled = self._try_story_interact()
                if (not story_handled) and getattr(self.app, "quest_mgr", None):
                    self.app.quest_mgr.try_interact(self.actor.getPos())
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
            self._is_flying = not self._is_flying
            if self._is_flying:
                self._set_stealth_crouch(False)
            self.cs.velocity.z = 0

        if self._is_flying:
            self._update_flight(move)
        else:
            self._set_flight_fx(False)
            self._update_ground(dt, move)
        self._sync_wall_contact_state()

        if interacted and not handled_vehicle:
            story_handled = self._try_story_interact()
            if (not story_handled) and getattr(self.app, "quest_mgr", None):
                self.app.quest_mgr.try_interact(self.actor.getPos())

        self._update_combat(dt)
        self._final_step(dt)

    def _update_combat(self, dt):
        if self._skill_wheel_open:
            self.combat.update(dt, self.cs, self.enemies)
            self.magic.update(dt, self.enemies, lambda fx: self._on_spell_effect(fx))
            return

        action_used = False

        self._refresh_spell_cache()

        for i in range(min(7, len(self._spell_cache))):
            if self._once_action(f"spell_{i+1}"):
                self._active_spell_idx = i

        light_pressed = self._once_action("attack_light")
        thrust_pressed = self._once_action("attack_thrust")

        if light_pressed:
            if not self._cast_spell_by_index(self._active_spell_idx):
                use_thrust = bool(thrust_pressed or self._should_contextual_thrust())
                if use_thrust:
                    self._play_sfx("sword_swing", volume=0.84, rate=1.12)
                else:
                    self._play_sfx("sword_swing", volume=0.88, rate=1.04)
                self._on_hit(self.combat.startAttack(self.cs, gc.AttackType.Light, self.enemies))
                self._queue_state_trigger("attack_thrust" if use_thrust else "attack_light")
                self._queue_state_trigger("attack")
            action_used = True
        if self._once_action("attack_heavy"):
            self._play_sfx("sword_swing", volume=0.96, rate=0.92)
            self._on_hit(self.combat.startAttack(self.cs, gc.AttackType.Heavy, self.enemies))
            self._queue_state_trigger("attack_heavy")
            self._queue_state_trigger("attack")
            action_used = True

        if self._once_action("block"):
            self._play_sfx("sword_block", volume=0.82)
            self._cast_spell_by_index(self._ultimate_spell_idx)
            action_used = True

        self.combat.update(dt, self.cs, self.enemies)
        if hasattr(self, "_update_spell_casting"):
            self._update_spell_casting()
        self.magic.update(dt, self.enemies, lambda fx: self._on_spell_effect(fx))

        if action_used:
            self._set_weapon_drawn(True)
        elif hasattr(self.combat, "isAttacking") and self.combat.isAttacking():
            self._drawn_hold_timer = 1.0
