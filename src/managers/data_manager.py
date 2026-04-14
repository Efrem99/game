import re
from pathlib import Path

from managers.data_backend import create_data_backend
from utils.logger import logger


class DataManager:
    _RECURSIVE_RESOURCES = {
        "items": "items",
        "quests": "quests",
        "spells": "spells",
        "npcs": "npcs",
        "vehicle_configs": "vehicles",
        "skill_trees": "skills",
    }

    _FILE_RESOURCES = {
        "companions": "companions.json",
        "world_config": "world_config.json",
        "controls": "controls.json",
        "ui_strings": "ui_strings.json",
        "water_config": "water_config.json",
        "graphics_settings": "graphics_settings.json",
        "audio_settings": "audio_settings.json",
        "sound_config": "audio/sound_config.json",
        "camera_profiles": "camera_profiles.json",
        "cutscene_triggers": "cutscene_triggers.json",
        "player_config": "actors/player.json",
        "player_state_config": "states/player_states.json",
        "player_animation_manifest": "actors/player_animations.json",
        "sky_config": "sky_config.json",
        "world_layout": "world/layout.json",
        "location_meshes_config": "world/location_meshes.json",
        "prop_rules_config": "world/prop_rules.json",
        "test_scenarios": "world/test_scenarios.json",
        "character_logic": "logic/character_brain.json",
        "combat_styles": "combat/styles.json",
        "loading_screen_config": "loading_screen.json",
        "asset_multifiles_config": "asset_multifiles.json",
        "boss_roster_config": "enemies/boss_roster.json",
        "enemy_state_maps": "enemies/state_maps.json",
        "dragon_enemy_config": "enemies/dragon.json",
        "dragon_animation_manifest": "actors/dragon_animations.json",
        "dragon_state_config": "states/dragon_states.json",
    }

    _LOCALE_FILES = {
        "en": "locales/en.json",
        "ru": "locales/ru.json",
    }

    def __init__(self, data_dir=None, backend_config=None, backend=None):
        self.data_dir = Path(data_dir) if data_dir is not None else Path("data")
        self.backend = backend if backend is not None else create_data_backend(self.data_dir, backend_config=backend_config)
        self.backend_name = str(getattr(self.backend, "name", "json") or "json")
        for attr_name in set(self._RECURSIVE_RESOURCES) | set(self._FILE_RESOURCES) | {"locales"}:
            setattr(self, attr_name, {})
        self.language = "en"

        self.load_all()

    def load_all(self):
        for attr_name, rel_dir in self._RECURSIVE_RESOURCES.items():
            setattr(self, attr_name, self._load_recursive(self.data_dir / rel_dir))

        self.quests.update(self._normalize_quests(self._load_file("quests.json")))
        self.spells.update(self._normalize_spells(self._load_file("spells.json")))

        if not self.npcs:  # Fallback to npcs.json if it's a single file.
            self.npcs = self._load_file("npcs.json")

        for attr_name, rel_path in self._FILE_RESOURCES.items():
            setattr(self, attr_name, self._load_file(rel_path))

        self.locales = {
            lang: self._load_file(rel_path)
            for lang, rel_path in self._LOCALE_FILES.items()
        }
        self.language = (
            self.graphics_settings.get("language")
            or self.controls.get("language")
            or "en"
        )
        if self.language not in self.locales or not self.locales.get(self.language):
            self.language = "en"

        logger.info(
            f"[DataManager] Loaded {len(self.items)} items, {len(self.quests)} quests, "
            f"{len(self.spells)} spells, {len(self.vehicle_configs)} vehicle configs, "
            f"{len(self.skill_trees)} skill trees. Backend={self.backend_name}."
        )
        logger.info(
            f"[DataManager] Loaded {len(self.controls.get('bindings', {}))} bindings, "
            f"{len(self.npcs)} NPCs, {len(self.companions) if isinstance(self.companions, dict) else 0} companion defs."
        )

    def _load_recursive(self, directory):
        try:
            rel_dir = Path(directory).relative_to(self.data_dir).as_posix()
        except Exception:
            rel_dir = Path(directory).as_posix()
        payload = self.backend.load_recursive(rel_dir)
        return payload if isinstance(payload, dict) else {}

    def _load_file(self, filename):
        try:
            payload = self.backend.load_file(filename)
            return payload if isinstance(payload, (dict, list)) else {}
        except Exception as e:
            logger.error(f"[DataManager] Error loading {self.data_dir / filename}: {e}")
            return {}

    def save_settings(self, filename, data):
        try:
            self.backend.save_file(filename, data)
        except Exception as e:
            logger.error(f"[DataManager] Error saving {self.data_dir / filename}: {e}")

    def _normalize_spells(self, raw_spells):
        normalized = {}
        if not isinstance(raw_spells, dict):
            return normalized
        for spell_key, payload in raw_spells.items():
            if not isinstance(payload, dict):
                continue
            spell_data = dict(payload)
            spell_data.setdefault("id", spell_key)
            spell_data.setdefault("name", spell_key)
            normalized[spell_data["id"]] = spell_data
        return normalized

    def _normalize_quests(self, raw_quests):
        normalized = {}
        if isinstance(raw_quests, list):
            iterable = raw_quests
        elif isinstance(raw_quests, dict):
            iterable = []
            for quest_id, payload in raw_quests.items():
                if isinstance(payload, dict):
                    q = dict(payload)
                    q.setdefault("id", quest_id)
                    iterable.append(q)
        else:
            return normalized

        for quest in iterable:
            if not isinstance(quest, dict):
                continue
            quest_id = quest.get("id")
            if not quest_id:
                continue
            fixed = dict(quest)
            objectives = fixed.get("objectives")
            if isinstance(objectives, list):
                fixed_objectives = []
                for obj in objectives:
                    if not isinstance(obj, dict):
                        continue
                    obj_fixed = dict(obj)
                    if "description" not in obj_fixed and "desc" in obj_fixed:
                        obj_fixed["description"] = obj_fixed["desc"]
                    fixed_objectives.append(obj_fixed)
                fixed["objectives"] = fixed_objectives
            normalized[quest_id] = fixed
        return normalized

    def get_binding(self, action):
        return self.controls.get("bindings", {}).get(action)

    def get_move_param(self, param):
        return self.controls.get("movement", {}).get(param)

    def get_vehicle_param(self, kind, param, default=None):
        kind_key = str(kind or "").strip().lower()
        # Primary source: dedicated data/vehicles/*.json configs.
        if isinstance(self.vehicle_configs, dict) and self.vehicle_configs:
            kind_cfg = self.vehicle_configs.get(kind_key, {})
            default_cfg = self.vehicle_configs.get("default", {})
            if isinstance(kind_cfg, dict) and param in kind_cfg:
                return kind_cfg.get(param, default)
            if isinstance(default_cfg, dict) and param in default_cfg:
                return default_cfg.get(param, default)

            # Also support nested "tuning" sections in vehicle configs.
            if isinstance(kind_cfg, dict):
                tuning = kind_cfg.get("tuning", {})
                if isinstance(tuning, dict) and param in tuning:
                    return tuning.get(param, default)
            if isinstance(default_cfg, dict):
                tuning = default_cfg.get("tuning", {})
                if isinstance(tuning, dict) and param in tuning:
                    return tuning.get(param, default)

        # Backward-compatible source: controls.json vehicles block.
        vehicles_cfg = self.controls.get("vehicles", {})
        if not isinstance(vehicles_cfg, dict):
            return default

        kind_cfg = vehicles_cfg.get(kind_key, {})
        default_cfg = vehicles_cfg.get("default", {})

        if isinstance(kind_cfg, dict) and param in kind_cfg:
            return kind_cfg.get(param, default)
        if isinstance(default_cfg, dict) and param in default_cfg:
            return default_cfg.get(param, default)
        return default

    def get_vehicle_config(self, kind):
        token = str(kind or "").strip().lower()
        if not token:
            return {}
        if not isinstance(self.vehicle_configs, dict):
            return {}
        payload = self.vehicle_configs.get(token, {})
        if isinstance(payload, dict):
            return dict(payload)
        return {}

    def get_skill_trees(self):
        payload = self.skill_trees if isinstance(self.skill_trees, dict) else {}
        out = {}
        for key, row in payload.items():
            if isinstance(row, dict):
                out[str(key)] = dict(row)
        return out

    def get_world_layout(self):
        payload = self.world_layout if isinstance(self.world_layout, dict) else {}
        return dict(payload)

    def get_test_scenarios(self):
        payload = self.test_scenarios
        if isinstance(payload, dict):
            rows = payload.get("scenarios", [])
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        out = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    out.append(dict(row))
        return out

    def get_character_logic_config(self):
        payload = self.character_logic if isinstance(self.character_logic, dict) else {}
        return dict(payload)

    def get_combat_style(self, style_name):
        payload = self.combat_styles if isinstance(self.combat_styles, dict) else {}
        styles = payload.get("styles", {}) if isinstance(payload, dict) else {}
        if not isinstance(styles, dict):
            return {}
        token = str(style_name or "").strip().lower()
        row = styles.get(token, {})
        return dict(row) if isinstance(row, dict) else {}

    def get_ui_str(self, section, key):
        fallback = self.ui_strings.get(section, {}).get(key)
        if fallback:
            return fallback
        return self.t(f"{section}.{key}", key)

    def get_available_languages(self):
        return [k for k, v in self.locales.items() if isinstance(v, dict) and v]

    def get_language(self):
        return self.language

    def set_language(self, lang):
        if lang in self.locales and isinstance(self.locales.get(lang), dict) and self.locales.get(lang):
            self.language = lang
            return True
        return False

    def t(self, key, default=None, lang=None):
        language = lang or self.language or "en"
        value = self._lookup_locale(language, key)
        if value is None and language != "en":
            value = self._lookup_locale("en", key)
        if value is None:
            value = self._lookup_legacy(key)
        if value is None:
            value = default if default is not None else key
        if isinstance(value, (dict, list)):
            return default if default is not None else key
        return str(value)

    def _lookup_locale(self, lang, key):
        root = self.locales.get(lang, {})
        if not isinstance(root, dict):
            return None
        node = root
        for part in str(key).split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    def _lookup_legacy(self, key):
        parts = str(key).split(".")
        if len(parts) == 2:
            return self.ui_strings.get(parts[0], {}).get(parts[1])
        if len(parts) == 1 and "ui" in self.ui_strings:
            return self.ui_strings.get("ui", {}).get(parts[0])
        return None

    def get_spell(self, name):
        return self.spells.get(name)

    def get_spellbook_keys(self):
        if not isinstance(self.spells, dict) or not self.spells:
            return []

        by_norm = {}

        for raw_key, payload in self.spells.items():
            if not isinstance(payload, dict):
                continue
            key = str(raw_key or "").strip()
            if not key:
                continue
            sid = str(payload.get("id") or key).strip()
            norm = re.sub(r"[^a-z0-9]+", "", sid.lower())
            if not norm:
                continue
            score = self._spell_entry_score(key, sid, payload)
            entry = {"key": key, "id": sid, "score": score, "payload": payload}
            prev = by_norm.get(norm)
            if prev is None or score > prev["score"]:
                by_norm[norm] = entry

        if not by_norm:
            return []

        preferred_order = [
            "fireball",
            "lightning",
            "meteor",
            "nova",
            "ward",
        ]
        order_index = {token: idx for idx, token in enumerate(preferred_order)}

        def _sort_key(entry):
            sid = re.sub(r"[^a-z0-9]+", "", str(entry.get("id", "")).lower())
            token = order_index.get(sid, 999)
            return (
                token,
                0 if str(entry.get("id", "")).islower() else 1,
                str(entry.get("id", "")).lower(),
            )

        ordered = sorted(by_norm.values(), key=_sort_key)
        return [entry["key"] for entry in ordered]

    def _spell_entry_score(self, key, spell_id, payload):
        score = 0
        if str(key) == str(spell_id):
            score += 2
        if str(spell_id).islower():
            score += 2
        if str(key).islower():
            score += 1
        if "cast_time" in payload:
            score += 2
        if "effect" in payload or "projectile" in payload:
            score += 1
        if "runtime" in payload:
            score += 1
        return score

    def get_item(self, item_id):
        return self.items.get(item_id)

    def get_biome(self, name):
        # Biomes are usually in world/biomes.json
        biomes = self.world_config.get("biomes", {})
        if not biomes:
             # Try searching in other world files
             biomes = self._load_file("world/biomes.json")
        return biomes.get(name, {})

    def get_player_config(self):
        payload = self.player_config if isinstance(self.player_config, dict) else {}
        player = payload.get("player", payload)
        if not isinstance(player, dict):
            return {}
        return dict(player)

    def get_player_state_config(self):
        payload = self.player_state_config if isinstance(self.player_state_config, dict) else {}
        return dict(payload)

    def get_player_animation_manifest(self):
        payload = self.player_animation_manifest if isinstance(self.player_animation_manifest, dict) else {}
        return dict(payload)

    def get_location_meshes_config(self):
        payload = self.location_meshes_config if isinstance(self.location_meshes_config, dict) else {}
        return dict(payload)

    def get_prop_rules_config(self):
        payload = self.prop_rules_config if isinstance(self.prop_rules_config, dict) else {}
        return dict(payload)

    def get_boss_roster_config(self):
        payload = self.boss_roster_config if isinstance(self.boss_roster_config, dict) else {}
        return dict(payload)

    def get_enemy_state_maps(self):
        payload = self.enemy_state_maps if isinstance(self.enemy_state_maps, dict) else {}
        return dict(payload)

    def get_dragon_config_bundle(self):
        enemy = self.dragon_enemy_config if isinstance(self.dragon_enemy_config, dict) else {}
        anim = self.dragon_animation_manifest if isinstance(self.dragon_animation_manifest, dict) else {}
        state = self.dragon_state_config if isinstance(self.dragon_state_config, dict) else {}
        return {
            "enemy": dict(enemy),
            "anim": dict(anim),
            "state": dict(state),
        }
