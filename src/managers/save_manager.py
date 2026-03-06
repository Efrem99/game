import json
from datetime import datetime, timezone
from pathlib import Path

from utils.logger import logger


class SaveManager:
    """Persists lightweight runtime state for continue/load flows."""

    SLOT_COUNT = 3
    SAVE_VERSION = 3

    def __init__(self, app, save_dir="saves"):
        self.app = app
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.autosave_path = self.save_dir / "autosave.json"
        self.latest_path = self.save_dir / "latest.json"
        self.slot_paths = {
            idx: self.save_dir / f"slot{idx}.json"
            for idx in range(1, self.SLOT_COUNT + 1)
        }
        # Backward-compatible alias used by older code paths.
        self.slot1_path = self.slot_paths[1]

    def has_save(self, slot_index=None):
        if slot_index is not None:
            try:
                return self.slot_path(slot_index).exists()
            except Exception:
                return False

        paths = [self.autosave_path, self.latest_path] + list(self.slot_paths.values())
        return any(path.exists() for path in paths)

    def slot_path(self, slot_index):
        idx = self._normalize_slot_index(slot_index)
        return self.slot_paths[idx]

    def list_slots(self):
        return [self.slot_meta(idx) for idx in range(1, self.SLOT_COUNT + 1)]

    def slot_meta(self, slot_index):
        path = self.slot_path(slot_index)
        meta = {
            "slot": self._normalize_slot_index(slot_index),
            "path": str(path),
            "exists": path.exists(),
            "saved_at_utc": None,
            "xp": 0,
            "gold": 0,
            "location": None,
        }
        if not path.exists():
            return meta

        payload = self._read_json(path)
        if not isinstance(payload, dict):
            return meta

        payload_meta = payload.get("meta", {})
        if not isinstance(payload_meta, dict):
            payload_meta = {}
        summary = payload_meta.get("summary", {})
        if not isinstance(summary, dict):
            summary = {}

        meta["saved_at_utc"] = payload_meta.get("saved_at_utc")
        meta["xp"] = self._as_int(summary.get("xp", 0))
        meta["gold"] = self._as_int(summary.get("gold", 0))
        meta["location"] = summary.get("location")
        return meta

    def get_latest_existing_path(self):
        candidates = [
            path
            for path in [self.latest_path, self.autosave_path] + list(self.slot_paths.values())
            if path.exists()
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    def save_autosave(self):
        payload = self._build_payload(save_kind="autosave")
        self._write_json(self.autosave_path, payload)
        self._write_json(self.latest_path, payload)
        return self.autosave_path

    def save_slot(self, slot_index):
        path = self.slot_path(slot_index)
        payload = self._build_payload(save_kind="slot", slot_index=slot_index)
        self._write_json(path, payload)
        self._write_json(self.latest_path, payload)
        return path

    def load_latest(self):
        path = self.get_latest_existing_path()
        if not path:
            return False
        payload = self._read_json(path)
        if not isinstance(payload, dict):
            return False
        payload, migrated = self._migrate_payload(payload)
        if migrated:
            self._write_json(path, payload)
            if path != self.latest_path:
                self._write_json(self.latest_path, payload)
        self._apply_payload(payload)
        logger.info(f"[SaveManager] Loaded save: {path}")
        return True

    def load_slot(self, slot_index):
        path = self.slot_path(slot_index)
        if not path.exists():
            return False
        payload = self._read_json(path)
        if not isinstance(payload, dict):
            return False
        payload, migrated = self._migrate_payload(payload)
        if migrated:
            self._write_json(path, payload)
            self._write_json(self.latest_path, payload)
        self._apply_payload(payload)
        logger.info(f"[SaveManager] Loaded slot {self._normalize_slot_index(slot_index)}: {path}")
        return True

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_json(self, path):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            logger.warning(f"[SaveManager] Failed to read {path}: {exc}")
            return None

    def _build_payload(self, save_kind="manual", slot_index=None):
        player_pos = self._resolve_player_pos()
        char_state = self._capture_char_state()
        profile = dict(getattr(self.app, "profile", {}))
        active_location = getattr(getattr(self.app, "world", None), "active_location", None)
        language = "en"
        data_mgr = getattr(self.app, "data_mgr", None)
        if data_mgr and hasattr(data_mgr, "get_language"):
            try:
                value = data_mgr.get_language()
                if isinstance(value, str) and value.strip():
                    language = value
            except Exception as exc:
                logger.warning(f"[SaveManager] Failed to read language from data manager: {exc}")
        combat_state = {}
        player = getattr(self.app, "player", None)
        if player and hasattr(player, "export_combat_runtime_state"):
            try:
                combat_state = player.export_combat_runtime_state() or {}
            except Exception:
                combat_state = {}
        equipment_state = {}
        if player and hasattr(player, "export_equipment_state"):
            try:
                equipment_state = player.export_equipment_state() or {}
            except Exception:
                equipment_state = {}
        vehicles_state = {}
        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if vehicle_mgr and hasattr(vehicle_mgr, "export_state"):
            try:
                vehicles_state = vehicle_mgr.export_state()
            except Exception:
                vehicles_state = {}
        ui_map_state = {}
        inventory_ui = getattr(self.app, "inventory_ui", None)
        if inventory_ui and hasattr(inventory_ui, "export_map_state"):
            try:
                ui_map_state = inventory_ui.export_map_state() or {}
            except Exception:
                ui_map_state = {}
        tutorial_state = {}
        tutorial_mgr = getattr(self.app, "movement_tutorial", None)
        if tutorial_mgr and hasattr(tutorial_mgr, "export_state"):
            try:
                tutorial_state = tutorial_mgr.export_state() or {}
            except Exception:
                tutorial_state = {}
        slot_idx = None
        if slot_index is not None:
            try:
                slot_idx = self._normalize_slot_index(slot_index)
            except Exception:
                slot_idx = None

        mount_state = {}
        vehicle_positions = {}
        vehicle_rows = []
        mounted_vehicle_id = None
        if isinstance(vehicles_state, dict):
            if isinstance(vehicles_state.get("mount_state"), dict):
                mount_state = dict(vehicles_state.get("mount_state", {}))
            if isinstance(vehicles_state.get("vehicle_positions"), dict):
                vehicle_positions = dict(vehicles_state.get("vehicle_positions", {}))
            if isinstance(vehicles_state.get("vehicles"), list):
                vehicle_rows = list(vehicles_state.get("vehicles", []))
            token = vehicles_state.get("mounted_vehicle_id")
            if isinstance(token, str) and token.strip():
                mounted_vehicle_id = token.strip()

        return {
            "meta": {
                "version": self.SAVE_VERSION,
                "saved_at_utc": datetime.now(timezone.utc).isoformat(),
                "kind": str(save_kind),
                "slot": slot_idx,
                "summary": {
                    "xp": self._as_int(profile.get("xp", 0)),
                    "gold": self._as_int(profile.get("gold", 0)),
                    "location": active_location,
                },
            },
            "player": {
                "position": player_pos,
                "state": char_state,
                "combat": combat_state,
                "equipment_state": equipment_state,
            },
            "progression": {
                "profile": profile,
                "active_quests": dict(getattr(self.app.quest_mgr, "active_quests", {})),
                "completed_quests": sorted(list(getattr(self.app.quest_mgr, "completed_quests", set()))),
                "language": language,
                "tutorial": tutorial_state,
            },
            "world": {
                "active_location": active_location,
                "mounted_vehicle_id": mounted_vehicle_id,
                "mount_state": mount_state,
                "vehicle_positions": vehicle_positions,
                "vehicles": vehicle_rows,
            },
            "ui": {
                "map_state": ui_map_state,
            },
        }

    def _migrate_payload(self, payload):
        if not isinstance(payload, dict):
            return {}, False

        migrated = dict(payload)
        changed = False

        meta = migrated.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}
            changed = True
        version = self._as_int(meta.get("version", 1), default=1)

        progression = migrated.get("progression", {})
        if not isinstance(progression, dict):
            progression = {}
            changed = True
        player = migrated.get("player", {})
        if not isinstance(player, dict):
            player = {}
            changed = True
        world = migrated.get("world", {})
        if not isinstance(world, dict):
            world = {}
            changed = True
        ui = migrated.get("ui", {})
        if not isinstance(ui, dict):
            ui = {}
            changed = True

        if version < self.SAVE_VERSION:
            # Migration guardrails: carry forward old save keys into v3 schema.
            eq_state = player.get("equipment_state")
            if not isinstance(eq_state, dict):
                raw = progression.get("equipment_state")
                if isinstance(raw, dict):
                    eq_state = dict(raw)
                else:
                    profile = progression.get("profile", {})
                    if isinstance(profile, dict) and isinstance(profile.get("equipment"), dict):
                        eq_state = dict(profile.get("equipment"))
            if isinstance(eq_state, dict):
                if player.get("equipment_state") != eq_state:
                    player["equipment_state"] = eq_state
                    changed = True

            legacy_vehicles = world.get("vehicles")
            if isinstance(legacy_vehicles, dict):
                mount_state = legacy_vehicles.get("mount_state")
                if isinstance(mount_state, dict) and not isinstance(world.get("mount_state"), dict):
                    world["mount_state"] = dict(mount_state)
                    changed = True

                positions = legacy_vehicles.get("vehicle_positions")
                if isinstance(positions, dict) and not isinstance(world.get("vehicle_positions"), dict):
                    world["vehicle_positions"] = dict(positions)
                    changed = True

                mounted_id = legacy_vehicles.get("mounted_vehicle_id")
                if isinstance(mounted_id, str) and mounted_id.strip() and not str(world.get("mounted_vehicle_id", "")).strip():
                    world["mounted_vehicle_id"] = mounted_id.strip()
                    changed = True

                rows = legacy_vehicles.get("vehicles")
                if isinstance(rows, list):
                    world["vehicles"] = list(rows)
                    changed = True
                elif not isinstance(world.get("vehicles"), list):
                    world["vehicles"] = []
                    changed = True
            elif isinstance(legacy_vehicles, list):
                world["vehicles"] = list(legacy_vehicles)
                changed = True
            elif not isinstance(world.get("vehicles"), list):
                world["vehicles"] = []
                changed = True

            if not isinstance(world.get("mount_state"), dict):
                world["mount_state"] = {}
                changed = True
            if not isinstance(world.get("vehicle_positions"), dict):
                world["vehicle_positions"] = {}
                changed = True

            map_state = ui.get("map_state")
            if not isinstance(map_state, dict):
                legacy_map = progression.get("ui_map_state")
                if isinstance(legacy_map, dict):
                    map_state = dict(legacy_map)
                else:
                    map_state = {}
                ui["map_state"] = map_state
                changed = True

            if "tab" not in ui.get("map_state", {}):
                ui.setdefault("map_state", {})["tab"] = "inventory"
                changed = True
            if "range" not in ui.get("map_state", {}):
                ui.setdefault("map_state", {})["range"] = 180.0
                changed = True

            if version != self.SAVE_VERSION:
                meta["version"] = self.SAVE_VERSION
                changed = True

        migrated["meta"] = meta
        migrated["progression"] = progression
        migrated["player"] = player
        migrated["world"] = world
        migrated["ui"] = ui
        return migrated, changed

    def _normalize_slot_index(self, slot_index):
        idx = int(slot_index)
        if idx < 1 or idx > self.SLOT_COUNT:
            raise ValueError(f"Invalid slot index: {slot_index}")
        return idx

    def _as_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return int(default)

    def _resolve_player_pos(self):
        if getattr(self.app, "player", None) and getattr(self.app.player, "actor", None):
            p = self.app.player.actor.getPos()
            return [float(p.x), float(p.y), float(p.z)]

        cs = getattr(self.app, "char_state", None)
        if cs and hasattr(cs, "position"):
            pos = cs.position
            return [float(getattr(pos, "x", 0.0)), float(getattr(pos, "y", 0.0)), float(getattr(pos, "z", 0.0))]

        return [0.0, 0.0, 0.0]

    def _capture_char_state(self):
        cs = getattr(self.app, "char_state", None)
        if not cs:
            return {}
        fields = [
            "health",
            "maxHealth",
            "stamina",
            "maxStamina",
            "mana",
            "maxMana",
            "grounded",
            "inWater",
            "yaw",
        ]
        out = {}
        for name in fields:
            if hasattr(cs, name):
                try:
                    out[name] = getattr(cs, name)
                except Exception:
                    continue
        return out

    def _apply_payload(self, payload):
        payload, _ = self._migrate_payload(payload)
        progression = payload.get("progression", {})
        profile = progression.get("profile", {})
        if isinstance(profile, dict):
            base = getattr(self.app, "profile", {})
            if not isinstance(base, dict):
                base = {}
            base.update(profile)
            self.app.profile = base

        lang = progression.get("language")
        data_mgr = getattr(self.app, "data_mgr", None)
        if isinstance(lang, str) and data_mgr and hasattr(data_mgr, "set_language"):
            try:
                data_mgr.set_language(lang)
            except Exception as exc:
                logger.warning(f"[SaveManager] Failed to apply language '{lang}': {exc}")

        active_quests = progression.get("active_quests")
        if isinstance(active_quests, dict):
            normalized = {}
            for qid, idx in active_quests.items():
                try:
                    normalized[str(qid)] = int(idx)
                except Exception:
                    continue
            self.app.quest_mgr.active_quests = normalized

        completed_quests = progression.get("completed_quests")
        if isinstance(completed_quests, list):
            self.app.quest_mgr.completed_quests = {str(q) for q in completed_quests}

        tutorial_state = progression.get("tutorial")
        tutorial_mgr = getattr(self.app, "movement_tutorial", None)
        if isinstance(tutorial_state, dict) and tutorial_mgr and hasattr(tutorial_mgr, "import_state"):
            try:
                tutorial_mgr.import_state(tutorial_state)
            except Exception as exc:
                logger.warning(f"[SaveManager] Tutorial state import failed: {exc}")

        player = payload.get("player", {})
        position = player.get("position")
        if isinstance(position, list) and len(position) >= 3:
            self._apply_position(position)

        state = player.get("state", {})
        if isinstance(state, dict):
            self._apply_char_state(state)
        combat = player.get("combat", {})
        if isinstance(combat, dict):
            p = getattr(self.app, "player", None)
            if p and hasattr(p, "import_combat_runtime_state"):
                try:
                    p.import_combat_runtime_state(combat)
                except Exception:
                    pass
        equipment_state = player.get("equipment_state", {})
        if isinstance(equipment_state, dict):
            p = getattr(self.app, "player", None)
            if p and hasattr(p, "import_equipment_state"):
                try:
                    p.import_equipment_state(equipment_state)
                except Exception as exc:
                    logger.warning(f"[SaveManager] Equipment state import failed: {exc}")

        world_state = payload.get("world", {})
        if isinstance(world_state, dict):
            vehicles_state = {}
            if isinstance(world_state.get("vehicles"), list):
                vehicles_state["vehicles"] = list(world_state.get("vehicles", []))
            legacy = world_state.get("vehicles")
            if isinstance(legacy, dict):
                vehicles_state.update(legacy)
            if isinstance(world_state.get("mount_state"), dict):
                vehicles_state["mount_state"] = dict(world_state.get("mount_state", {}))
            if isinstance(world_state.get("vehicle_positions"), dict):
                vehicles_state["vehicle_positions"] = dict(world_state.get("vehicle_positions", {}))
            mounted_vehicle_id = world_state.get("mounted_vehicle_id")
            if isinstance(mounted_vehicle_id, str) and mounted_vehicle_id.strip():
                vehicles_state["mounted_vehicle_id"] = mounted_vehicle_id.strip()
            vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
            if isinstance(vehicles_state, dict) and vehicle_mgr and hasattr(vehicle_mgr, "import_state"):
                try:
                    vehicle_mgr.import_state(vehicles_state, player=getattr(self.app, "player", None))
                except Exception as exc:
                    logger.warning(f"[SaveManager] Vehicle state import failed: {exc}")

        ui_state = payload.get("ui", {})
        if isinstance(ui_state, dict):
            map_state = ui_state.get("map_state")
            inventory_ui = getattr(self.app, "inventory_ui", None)
            if isinstance(map_state, dict) and inventory_ui and hasattr(inventory_ui, "import_map_state"):
                try:
                    inventory_ui.import_map_state(map_state)
                except Exception as exc:
                    logger.warning(f"[SaveManager] UI map state import failed: {exc}")

    def _apply_position(self, position):
        x, y, z = float(position[0]), float(position[1]), float(position[2])

        if getattr(self.app, "player", None) and getattr(self.app.player, "actor", None):
            self.app.player.actor.setPos(x, y, z)

        cs = getattr(self.app, "char_state", None)
        if hasattr(cs, "position"):
            try:
                cs.position.x = x
                cs.position.y = y
                cs.position.z = z
            except Exception:
                pass

    def _apply_char_state(self, state):
        cs = getattr(self.app, "char_state", None)
        if not cs:
            return
        for key, value in state.items():
            if hasattr(cs, key):
                try:
                    setattr(cs, key, value)
                except Exception:
                    continue
