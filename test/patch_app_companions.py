
import os

app_path = r'C:\xampp\htdocs\king-wizard\src\app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    # Import
    if 'from entities.boss_manager import BossManager' in line:
        new_lines.append('from entities.companion_unit import CompanionUnit\n')
    
    # Init
    if 'self.story_interaction = StoryInteractionManager(self)' in line:
        new_lines.append('        self._active_party = {}\n')
        new_lines.append('        self._party_sync_timer = 0.0\n')
    
    # Update loop
    if 'is_playing = bool(self.state_mgr.is_playing())' in line:
        new_lines.append('        if is_playing:\n')
        new_lines.append('            self._update_party_units(dt_world)\n')

# Methods
methods = """
    def _update_party_units(self, dt):
        \"\"\"Tick active companions and ensure runtime matches manager state.\"\"\"
        self._party_sync_timer += dt
        if self._party_sync_timer >= 1.0:
            self._party_sync_timer = 0.0
            self._sync_party_runtime()

        if not self.player or not self.player.actor:
            return
            
        p_pos = self.player.actor.getPos(self.render)
        for unit in self._active_party.values():
            try:
                unit.update(dt, p_pos)
            except Exception as e:
                logger.debug(f"[App] Companion update failed: {e}")

    def _sync_party_runtime(self):
        \"\"\"Spawn or despawn companion actors to match CompanionManager's active state.\"\"\"
        cm = getattr(self, "companion_mgr", None)
        if not cm: return
        
        active_ids = []
        if hasattr(cm, "get_active_companion_id"):
            cid = cm.get_active_companion_id()
            if cid: active_ids.append(cid)
        if hasattr(cm, "get_active_pet_id"):
            pid = cm.get_active_pet_id()
            if pid: active_ids.append(pid)
            
        for mid in list(self._active_party.keys()):
            if mid not in active_ids:
                unit = self._active_party.pop(mid)
                unit.despawn()
                logger.info(f"[App] Despawned companion {mid}")

        for mid in active_ids:
            if mid not in self._active_party:
                data = cm._members.get(mid) or {}
                unit = CompanionUnit(self, mid, data)
                start_pos = Vec3(0,0,0)
                if self.player and self.player.actor:
                    start_pos = self.player.actor.getPos(self.render) + Vec3(random.random()*4-2, random.random()*4-2, 1)
                unit.spawn(start_pos)
                self._active_party[mid] = unit
                logger.info(f"[App] Spawned companion {mid}")
"""
new_lines.append(methods)

with open(app_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Patched app.py")
