from __future__ import annotations

from copy import deepcopy


def _clean_token(value):
    return str(value or "").strip().lower()


def _normalize_behavior(value, default="follow"):
    token = _clean_token(value)
    if token in {"follow", "stay"}:
        return token
    return _clean_token(default) or "follow"


class CompanionManager:
    """Tracks recruited pets and companions in the player profile."""

    def __init__(self, app, definitions=None):
        self.app = app
        source = definitions
        if source is None:
            source = getattr(getattr(app, "data_mgr", None), "companions", {})
        self._definitions = self._normalize_definitions(source)
        self._members = self._definitions
        self._ensure_party_profile()

    def _normalize_definitions(self, payload):
        out = {}
        if not isinstance(payload, dict):
            return out
        for member_id, raw in payload.items():
            token = _clean_token(member_id)
            if not token or not isinstance(raw, dict):
                continue
            kind = _clean_token(raw.get("kind"))
            if kind not in {"pet", "companion"}:
                continue
            recruitment = raw.get("recruitment", {})
            support = raw.get("support", {})
            assist = raw.get("assist", {})
            out[token] = {
                "id": token,
                "name": str(raw.get("name", member_id) or member_id).strip(),
                "kind": kind,
                "recruitment": dict(recruitment) if isinstance(recruitment, dict) else {},
                "support": dict(support) if isinstance(support, dict) else {},
                "assist": dict(assist) if isinstance(assist, dict) else {},
            }
        return out

    def _profile(self):
        profile = getattr(self.app, "profile", None)
        if not isinstance(profile, dict):
            profile = {}
            self.app.profile = profile
        return profile

    def _ensure_party_bucket(self, key):
        profile = self._profile()
        party = profile.get("party")
        if not isinstance(party, dict):
            party = {}
            profile["party"] = party
        bucket = party.get(key)
        if not isinstance(bucket, dict):
            bucket = {}
            party[key] = bucket
        owned = bucket.get("owned")
        if not isinstance(owned, dict):
            owned = {}
            bucket["owned"] = owned
        active_id = bucket.get("active_id")
        if not isinstance(active_id, str):
            bucket["active_id"] = ""
        return bucket

    def _ensure_party_profile(self):
        self._ensure_party_bucket("companions")
        self._ensure_party_bucket("pets")
        return self._profile().get("party", {})

    def _owned_entry(self, member_id):
        token = _clean_token(member_id)
        key, bucket = self._bucket_for_member(token)
        if not key or not isinstance(bucket, dict):
            return None, None, None
        entry = bucket.get("owned", {}).get(token)
        if not isinstance(entry, dict):
            return key, bucket, None
        entry["behavior"] = _normalize_behavior(entry.get("behavior"))
        return key, bucket, entry

    def get_definition(self, member_id):
        return self._definitions.get(_clean_token(member_id))

    def is_owned(self, member_id):
        return self.has_companion(member_id) or self.has_pet(member_id)

    def has_companion(self, member_id):
        token = _clean_token(member_id)
        bucket = self._ensure_party_bucket("companions")
        return token in bucket.get("owned", {})

    def has_pet(self, member_id):
        token = _clean_token(member_id)
        bucket = self._ensure_party_bucket("pets")
        return token in bucket.get("owned", {})

    def get_active_companion_id(self):
        bucket = self._ensure_party_bucket("companions")
        return _clean_token(bucket.get("active_id"))

    def get_active_pet_id(self):
        bucket = self._ensure_party_bucket("pets")
        return _clean_token(bucket.get("active_id"))

    def _bucket_key_for_kind(self, kind):
        return "pets" if _clean_token(kind) == "pet" else "companions"

    def _bucket_for_member(self, member_id):
        definition = self.get_definition(member_id)
        if not isinstance(definition, dict):
            return None, None
        key = self._bucket_key_for_kind(definition.get("kind"))
        return key, self._ensure_party_bucket(key)

    def _gold(self):
        profile = self._profile()
        try:
            return int(profile.get("gold", 0) or 0)
        except Exception:
            return 0

    def _cost_for(self, definition):
        recruitment = definition.get("recruitment", {}) if isinstance(definition, dict) else {}
        try:
            return max(0, int(recruitment.get("cost", 0) or 0))
        except Exception:
            return 0

    def can_recruit(self, member_id, source=None):
        definition = self.get_definition(member_id)
        if not isinstance(definition, dict):
            return False
        token = _clean_token(member_id)
        recruitment = definition.get("recruitment", {})
        method = _clean_token(recruitment.get("method"))
        source_token = _clean_token(source) or method
        if not method or source_token != method:
            return False
        if self.is_owned(token):
            return False
        if method == "hire":
            return self._gold() >= self._cost_for(definition)
        return True

    def acquire_member(self, member_id, source=None, activate=True):
        definition = self.get_definition(member_id)
        if not isinstance(definition, dict):
            return False
        source_token = _clean_token(source) or _clean_token(definition.get("recruitment", {}).get("method"))
        if not self.can_recruit(member_id, source=source_token):
            return False

        if source_token == "hire":
            profile = self._profile()
            profile["gold"] = self._gold() - self._cost_for(definition)

        entry = {
            "id": definition["id"],
            "name": definition["name"],
            "kind": definition["kind"],
            "source": source_token,
            "behavior": "follow",
            "support": deepcopy(definition.get("support", {})),
            "assist": deepcopy(definition.get("assist", {})),
        }
        bucket_key = self._bucket_key_for_kind(definition.get("kind"))
        bucket = self._ensure_party_bucket(bucket_key)
        bucket["owned"][definition["id"]] = entry
        if activate:
            bucket["active_id"] = definition["id"]
        self._mark_codex(entry)
        return True

    def activate_member(self, member_id):
        key, bucket = self._bucket_for_member(member_id)
        token = _clean_token(member_id)
        if not key or not isinstance(bucket, dict):
            return False
        if token not in bucket.get("owned", {}):
            return False
        bucket["active_id"] = token
        return True

    def dismiss_active_companion(self):
        bucket = self._ensure_party_bucket("companions")
        bucket["active_id"] = ""
        return True

    def dismiss_active_pet(self):
        bucket = self._ensure_party_bucket("pets")
        bucket["active_id"] = ""
        return True

    def get_behavior_state(self, member_id, default="follow"):
        _, _, entry = self._owned_entry(member_id)
        if not isinstance(entry, dict):
            return _normalize_behavior(default)
        return _normalize_behavior(entry.get("behavior"), default=default)

    def set_behavior_state(self, member_id, state):
        """Persist behavior state (follow, stay) and reflect it in runtime if active."""
        token = _clean_token(member_id)
        behavior = _normalize_behavior(state)
        _, _, entry = self._owned_entry(token)
        if not isinstance(entry, dict):
            return False
        entry["behavior"] = behavior

        app = getattr(self, "app", None)
        if app and hasattr(app, "_active_party"):
            unit = app._active_party.get(token)
            if unit:
                try:
                    if hasattr(unit, "set_behavior_state"):
                        unit.set_behavior_state(behavior)
                    else:
                        unit.data = dict(getattr(unit, "data", {}) or {})
                        unit.data["behavior"] = behavior
                        unit.state = behavior
                except Exception:
                    pass
        return True

    def _active_entry(self, bucket_key):
        bucket = self._ensure_party_bucket(bucket_key)
        token = _clean_token(bucket.get("active_id"))
        if not token:
            return None
        row = bucket.get("owned", {}).get(token)
        if not isinstance(row, dict):
            return None
        row["behavior"] = _normalize_behavior(row.get("behavior"))
        return deepcopy(row)

    def get_party_snapshot(self):
        companions = self._ensure_party_bucket("companions").get("owned", {})
        pets = self._ensure_party_bucket("pets").get("owned", {})

        def _rows(payload):
            rows = []
            for _, row in sorted(payload.items()):
                if not isinstance(row, dict):
                    continue
                row["behavior"] = _normalize_behavior(row.get("behavior"))
                rows.append(deepcopy(row))
            return rows

        return {
            "active_companion": self._active_entry("companions"),
            "active_pet": self._active_entry("pets"),
            "companions": _rows(companions),
            "pets": _rows(pets),
        }

    def get_runtime_member_data(self, member_id):
        definition = self.get_definition(member_id)
        if not isinstance(definition, dict):
            return {}
        token = _clean_token(member_id)
        bucket_key = self._bucket_key_for_kind(definition.get("kind"))
        bucket = self._ensure_party_bucket(bucket_key)
        owned = bucket.get("owned", {}).get(token, {})
        payload = deepcopy(definition)
        if isinstance(owned, dict):
            payload.update(deepcopy(owned))
        payload["behavior"] = _normalize_behavior(payload.get("behavior"))
        payload["active"] = _clean_token(bucket.get("active_id")) == token
        return payload

    def _mark_codex(self, entry):
        mark = getattr(self.app, "_codex_mark", None)
        if not callable(mark) or not isinstance(entry, dict):
            return
        token = str(entry.get("id", "") or "").strip()
        name = str(entry.get("name", token) or token).strip()
        kind = _clean_token(entry.get("kind"))
        if token and name:
            mark("characters", token, name)
            if kind == "companion":
                mark("npcs", token, name)
