"""Data-driven skill tree runtime state and unlock logic."""


class SkillTreeManager:
    def __init__(self, app):
        self.app = app
        self._trees = {}
        self._nodes = {}
        self.reload_from_data()
        self._ensure_profile_state()

    def reload_from_data(self):
        payload = {}
        dm = getattr(self.app, "data_mgr", None)
        if dm and hasattr(dm, "get_skill_trees"):
            try:
                payload = dm.get_skill_trees()
            except Exception:
                payload = {}
        elif dm:
            payload = getattr(dm, "skill_trees", {}) or {}
        if not isinstance(payload, dict):
            payload = {}

        self._trees = {}
        self._nodes = {}
        for branch_key, row in payload.items():
            if not isinstance(row, dict):
                continue
            branch_id = str(row.get("id", branch_key) or branch_key).strip().lower()
            if not branch_id:
                continue
            branch_name = str(row.get("name", branch_id.title()) or branch_id.title())
            raw_nodes = row.get("nodes", [])
            if not isinstance(raw_nodes, list):
                raw_nodes = []
            nodes = []
            for item in raw_nodes:
                if not isinstance(item, dict):
                    continue
                node_id = str(item.get("id", "") or "").strip().lower()
                if not node_id:
                    continue
                requires = item.get("requires", [])
                if not isinstance(requires, list):
                    requires = []
                requires_clean = []
                for req in requires:
                    token = str(req or "").strip().lower()
                    if token:
                        requires_clean.append(token)
                unlock = item.get("unlock", [])
                if not isinstance(unlock, list):
                    unlock = []
                unlock_clean = []
                for nxt in unlock:
                    token = str(nxt or "").strip().lower()
                    if token:
                        unlock_clean.append(token)
                try:
                    cost = int(item.get("cost", 1) or 1)
                except Exception:
                    cost = 1
                node = {
                    "id": node_id,
                    "name": str(item.get("name", node_id.title()) or node_id.title()),
                    "description": str(item.get("description", "") or ""),
                    "cost": max(1, cost),
                    "requires": requires_clean,
                    "unlock": unlock_clean,
                    "icon": str(item.get("icon", "") or ""),
                    "branch_id": branch_id,
                    "branch_name": branch_name,
                    "grants_spell": str(item.get("grants_spell", "") or "").strip().lower(),
                }
                nodes.append(node)
                self._nodes[node_id] = node
            self._trees[branch_id] = {
                "id": branch_id,
                "name": branch_name,
                "nodes": nodes,
            }

    def _ensure_profile_state(self):
        profile = getattr(self.app, "profile", None)
        if not isinstance(profile, dict):
            profile = {}
            self.app.profile = profile

        state = profile.get("skills")
        if not isinstance(state, dict):
            state = {}
            profile["skills"] = state

        unlocked = state.get("unlocked")
        if not isinstance(unlocked, dict):
            unlocked = {}
            state["unlocked"] = unlocked

        clean_unlocked = {}
        for key, value in unlocked.items():
            token = str(key or "").strip().lower()
            if token and bool(value):
                clean_unlocked[token] = True
        state["unlocked"] = clean_unlocked

        if "points" not in state:
            base_points = profile.get("skill_points", 4)
            try:
                base_points = int(base_points)
            except Exception:
                base_points = 4
            state["points"] = max(0, base_points)
        else:
            try:
                state["points"] = max(0, int(state.get("points", 0)))
            except Exception:
                state["points"] = 0

        profile["skill_points"] = int(state["points"])
        return profile, state

    def get_points(self):
        _, state = self._ensure_profile_state()
        return int(state.get("points", 0))

    def grant_points(self, amount):
        _, state = self._ensure_profile_state()
        try:
            delta = int(amount)
        except Exception:
            delta = 0
        if delta <= 0:
            return int(state.get("points", 0))
        state["points"] = int(state.get("points", 0)) + delta
        self.app.profile["skill_points"] = int(state["points"])
        return int(state["points"])

    def is_unlocked(self, node_id):
        _, state = self._ensure_profile_state()
        token = str(node_id or "").strip().lower()
        if not token:
            return False
        return bool(state.get("unlocked", {}).get(token, False))

    def _missing_requirements(self, state, node):
        missing = []
        for req in node.get("requires", []):
            token = str(req or "").strip().lower()
            if token and not bool(state.get("unlocked", {}).get(token, False)):
                missing.append(token)
        return missing

    def can_unlock(self, node_id):
        _, state = self._ensure_profile_state()
        token = str(node_id or "").strip().lower()
        node = self._nodes.get(token)
        if not isinstance(node, dict):
            return False, "Skill not found.", []
        if bool(state.get("unlocked", {}).get(token, False)):
            return False, "Already unlocked.", []
        missing = self._missing_requirements(state, node)
        if missing:
            return False, "Missing prerequisites.", missing
        points = int(state.get("points", 0))
        cost = int(node.get("cost", 1))
        if points < cost:
            return False, "Not enough skill points.", []
        return True, "Can unlock.", []

    def unlock(self, node_id):
        profile, state = self._ensure_profile_state()
        token = str(node_id or "").strip().lower()
        node = self._nodes.get(token)
        if not isinstance(node, dict):
            return False, "Skill not found."

        ok, reason, missing = self.can_unlock(token)
        if not ok:
            if missing:
                return False, f"{reason} Need: {', '.join(missing)}."
            return False, reason

        cost = int(node.get("cost", 1))
        state["points"] = max(0, int(state.get("points", 0)) - cost)
        state.setdefault("unlocked", {})[token] = True
        profile["skill_points"] = int(state["points"])

        grants_spell = str(node.get("grants_spell", "") or "").strip().lower()
        if grants_spell:
            unlocked_spells = profile.get("unlocked_spells")
            if not isinstance(unlocked_spells, list):
                unlocked_spells = []
                profile["unlocked_spells"] = unlocked_spells
            if grants_spell not in unlocked_spells:
                unlocked_spells.append(grants_spell)

        return True, f"Unlocked: {node.get('name', token)}."

    def get_all_nodes(self):
        _, state = self._ensure_profile_state()
        out = []
        points = int(state.get("points", 0))
        for branch in self._trees.values():
            branch_name = str(branch.get("name", "") or "")
            branch_id = str(branch.get("id", "") or "")
            for node in branch.get("nodes", []):
                node_id = str(node.get("id", "") or "")
                unlocked = bool(state.get("unlocked", {}).get(node_id, False))
                missing = self._missing_requirements(state, node)
                cost = int(node.get("cost", 1))
                can_unlock = (not unlocked) and (not missing) and (points >= cost)
                out.append(
                    {
                        "id": node_id,
                        "name": str(node.get("name", node_id.title()) or node_id.title()),
                        "description": str(node.get("description", "") or ""),
                        "cost": cost,
                        "requires": list(node.get("requires", [])),
                        "unlock": list(node.get("unlock", [])),
                        "branch_id": branch_id,
                        "branch_name": branch_name,
                        "unlocked": unlocked,
                        "missing": missing,
                        "can_unlock": can_unlock,
                        "grants_spell": str(node.get("grants_spell", "") or ""),
                    }
                )
        out.sort(key=lambda row: (str(row.get("branch_name", "")), len(row.get("requires", [])), str(row.get("name", ""))))
        return out

    def export_state(self):
        _, state = self._ensure_profile_state()
        return {
            "points": int(state.get("points", 0)),
            "unlocked": dict(state.get("unlocked", {})),
        }

    def import_state(self, payload):
        if not isinstance(payload, dict):
            return False
        _, state = self._ensure_profile_state()
        try:
            points = int(payload.get("points", state.get("points", 0)))
        except Exception:
            points = int(state.get("points", 0))
        unlocked = payload.get("unlocked", {})
        if not isinstance(unlocked, dict):
            unlocked = {}
        clean_unlocked = {}
        for key, value in unlocked.items():
            token = str(key or "").strip().lower()
            if token and bool(value):
                clean_unlocked[token] = True
        state["points"] = max(0, points)
        state["unlocked"] = clean_unlocked
        self.app.profile["skill_points"] = int(state["points"])
        return True
