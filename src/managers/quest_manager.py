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

    def _find_quest(self, quest_id):
        return next((q for q in self.quests_data if q.get('id') == quest_id), None)

    def _distance(self, player_pos, target):
        dx = player_pos.x - target[0]
        dy = player_pos.y - target[1]
        dz = player_pos.z - target[2]
        return (dx * dx + dy * dy + dz * dz) ** 0.5

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

            if current_obj.get('type') == 'reach_location':
                target = current_obj.get('target')
                if not isinstance(target, (list, tuple)) or len(target) < 3:
                    continue
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

    def get_hud_data(self):
        # Return a list of active quest titles and current objectives
        data = []
        for quest_id, obj_idx in self.active_quests.items():
            quest = self._find_quest(quest_id)
            if not quest:
                continue
            objectives = quest.get('objectives', [])
            if obj_idx < len(objectives):
                objective = objectives[obj_idx]
                desc = objective.get('description') or objective.get('desc') or objective.get('id') or "Objective"
                data.append({
                    "title": quest['title'],
                    "objective": desc
                })
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
                # Simplified proximity check for the 'target' entity.
                # Here we assume 'miner0' is at a specific logic-defined location.
                if current_obj.get('target') == 'miner0':
                    miner_pos = (5, 45, 0) # Location near the mine entrance from quests.json
                    dist = self._distance(player_pos, miner_pos)
                    if dist < 5.0:
                        print(f"[QuestManager] Interacted with {current_obj.get('target')}!")
                        self._advance_quest(quest_id)
