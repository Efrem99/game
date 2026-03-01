class QuestManager:
    def __init__(self, app, quests_data):
        self.app = app
        if isinstance(quests_data, dict):
            self.quests_data = list(quests_data.values())
        elif isinstance(quests_data, list):
            self.quests_data = quests_data
        else:
            self.quests_data = []
        self.active_quests = {} # quest_id -> current_objective_index
        self.completed_quests = set()
        # Temporary interaction anchors until NPC/world query integration.
        self.interaction_targets = {
            "miner0": (5.0, 45.0, 0.0),
        }

    def _find_quest(self, quest_id):
        return next((q for q in self.quests_data if q.get('id') == quest_id), None)

    def _distance(self, player_pos, target):
        dx = player_pos.x - target[0]
        dy = player_pos.y - target[1]
        dz = player_pos.z - target[2]
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def _resolve_objective_target(self, objective):
        if not isinstance(objective, dict):
            return None
        target = objective.get("target")
        if isinstance(target, (list, tuple)) and len(target) >= 3:
            try:
                return (float(target[0]), float(target[1]), float(target[2]))
            except Exception:
                return None
        if isinstance(target, str):
            return self.interaction_targets.get(target)
        return None

    def _objective_desc(self, objective):
        if not isinstance(objective, dict):
            return "Objective"
        return (
            objective.get("description")
            or objective.get("desc")
            or objective.get("id")
            or "Objective"
        )

    def start_quest(self, quest_id):
        if quest_id in self.completed_quests or quest_id in self.active_quests:
            return False

        # Check if quest exists
        quest = self._find_quest(quest_id)
        if quest:
            self.active_quests[quest_id] = 0
            print(f"[QuestManager] Started quest: {quest['title']}")
            return True
        return False

    def update(self, player_pos):
        for quest_id, obj_idx in list(self.active_quests.items()):
            quest = self._find_quest(quest_id)
            if not quest:
                continue
            objectives = quest.get('objectives', [])

            if obj_idx >= len(objectives):
                continue

            current_obj = objectives[obj_idx]
            obj_type = str(current_obj.get("type", "")).strip().lower()
            target = self._resolve_objective_target(current_obj)
            if not target:
                continue

            if obj_type == "reach_location":
                dist = self._distance(player_pos, target)
                radius = float(current_obj.get('radius', 4.0))
                if dist < radius:
                    self._advance_quest(quest_id)

    def _advance_quest(self, quest_id):
        quest = self._find_quest(quest_id)
        if not quest:
            return
        self.active_quests[quest_id] += 1

        if self.active_quests[quest_id] >= len(quest['objectives']):
            print(f"[QuestManager] Completed quest: {quest['title']}")
            del self.active_quests[quest_id]
            self.completed_quests.add(quest_id)
            self._give_rewards(quest['rewards'])
        else:
            print(f"[QuestManager] Objective updated for: {quest['title']}")

    def _give_rewards(self, rewards):
        if hasattr(self.app, "grant_rewards"):
            self.app.grant_rewards(rewards)
        print(f"[QuestManager] Rewards given: {rewards}")

    def get_hud_data(self, player_pos=None):
        # Return active objectives with tracking information.
        data = []
        for quest_id, obj_idx in self.active_quests.items():
            quest = self._find_quest(quest_id)
            if not quest:
                continue
            objectives = quest.get('objectives', [])
            if obj_idx < len(objectives):
                objective = objectives[obj_idx]
                desc = self._objective_desc(objective)
                obj_type = str(objective.get("type", "")).strip().lower()
                target = self._resolve_objective_target(objective)
                radius = float(objective.get("radius", 4.0) or 4.0)
                distance = None
                if player_pos is not None and target:
                    try:
                        distance = float(self._distance(player_pos, target))
                    except Exception:
                        distance = None
                status = "Objective"
                if obj_type == "reach_location":
                    status = "Reach"
                elif obj_type == "interact":
                    status = "Interact"
                data.append({
                    "quest_id": str(quest.get("id") or quest_id),
                    "title": quest.get("title", str(quest_id)),
                    "objective": desc,
                    "objective_type": obj_type or "unknown",
                    "objective_index": int(obj_idx) + 1,
                    "objective_total": max(1, len(objectives)),
                    "status": status,
                    "target": [target[0], target[1], target[2]] if target else None,
                    "distance": distance,
                    "radius": radius,
                })
        data.sort(key=lambda item: float(item.get("distance") or 999999.0))
        return data

    def try_interact(self, player_pos):
        # In a real game, we'd check for the nearest NPC via a physics query or spatial hash.
        # For this prototype, we'll simulate proximity checks for quest-related interaction targets.
        for quest_id, obj_idx in list(self.active_quests.items()):
            quest = self._find_quest(quest_id)
            if not quest:
                continue
            if obj_idx >= len(quest['objectives']):
                continue

            current_obj = quest['objectives'][obj_idx]
            if current_obj.get('type') == 'interact':
                target = self._resolve_objective_target(current_obj)
                if target:
                    dist = self._distance(player_pos, target)
                    if dist < 5.0:
                        print(f"[QuestManager] Interacted with {current_obj.get('target')}!")
                        self._advance_quest(quest_id)
