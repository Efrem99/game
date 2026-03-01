import json
import re
from pathlib import Path

class DataManager:
    def __init__(self):
        self.data_dir = Path("data")
        self.items = {}
        self.quests = {}
        self.spells = {}
        self.npcs = {}
        self.world_config = {}
        self.controls = {}
        self.ui_strings = {}
        self.locales = {}
        self.sound_config = {}
        self.language = "en"

        self.load_all()

    def load_all(self):
        # Modular recursive loading for major categories
        self.items = self._load_recursive(self.data_dir / "items")
        self.quests = self._load_recursive(self.data_dir / "quests")
        self.quests.update(self._normalize_quests(self._load_file("quests.json")))
        self.spells = self._load_recursive(self.data_dir / "spells")
        self.spells.update(self._normalize_spells(self._load_file("spells.json")))
        self.npcs = self._load_recursive(self.data_dir / "npcs")
        if not self.npcs: # Fallback to npcs.json if its a single file
             self.npcs = self._load_file("npcs.json")

        # Single file configs
        self.world_config = self._load_file("world_config.json")
        self.controls = self._load_file("controls.json")
        self.ui_strings = self._load_file("ui_strings.json")

        # Load additional root-level jsons if they exist in source
        self.water_config = self._load_file("water_config.json")
        self.graphics_settings = self._load_file("graphics_settings.json")
        self.audio_settings = self._load_file("audio_settings.json")
        self.sound_config = self._load_file("audio/sound_config.json")
        self.locales = {
            "en": self._load_file("locales/en.json"),
            "ru": self._load_file("locales/ru.json"),
        }
        self.language = (
            self.graphics_settings.get("language")
            or self.controls.get("language")
            or "en"
        )
        if self.language not in self.locales or not self.locales.get(self.language):
            self.language = "en"

        print(f"[DataManager] Loaded {len(self.items)} items, {len(self.quests)} quests, {len(self.spells)} spells.")
        print(f"[DataManager] Loaded {len(self.controls.get('bindings', {}))} bindings, {len(self.npcs)} NPCs.")

    def _load_recursive(self, directory):
        data_map = {}
        if not directory.exists():
            return data_map

        for json_file in directory.rglob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    # Use 'id' as key, fallback to filename
                    key = data.get("id") or json_file.stem
                    data_map[key] = data
            except Exception as e:
                print(f"[DataManager] Error loading {json_file}: {e}")
        return data_map

    def _load_file(self, filename):
        path = self.data_dir / filename
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception as e:
            print(f"[DataManager] Error loading {path}: {e}")
            return {}

    def save_settings(self, filename, data):
        path = self.data_dir / filename
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[DataManager] Error saving {path}: {e}")

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
        vehicles_cfg = self.controls.get("vehicles", {})
        if not isinstance(vehicles_cfg, dict):
            return default

        kind_cfg = vehicles_cfg.get(str(kind), {})
        default_cfg = vehicles_cfg.get("default", {})

        if isinstance(kind_cfg, dict) and param in kind_cfg:
            return kind_cfg.get(param, default)
        if isinstance(default_cfg, dict) and param in default_cfg:
            return default_cfg.get(param, default)
        return default

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
