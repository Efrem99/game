
import os

path = r'C:/xampp/htdocs/king-wizard/src/entities/boss_manager.py'
with open(path, 'r', encoding='utf-8') as f:
    orig_content = f.read()

# 1. Initialize stealth variables in EnemyUnit.__init__
init_target = 'self.hp = self.max_hp'
init_replacement = """self.hp = self.max_hp
        self.awareness = "idle"  # idle, suspicious, alert
        self.stealth_meter = 0.0
        self.last_known_player_pos = None"""
content = orig_content.replace(init_target, init_replacement)

# 2. Add _update_stealth method to EnemyUnit
methods_addition = """
    def _update_stealth(self, dt, player_pos):
        if not player_pos or self.hp <= 0 or self._is_engaged:
            if self._is_engaged:
                self.awareness = "alert"
                self.stealth_meter = 1.0
            return

        pos = self.root.getPos(self.render)
        vec = player_pos - pos
        dist = vec.length()
        
        # Base detection parameters
        det_range = 24.0
        fov_cos = math.cos(math.radians(65.0)) # 130 deg total
        
        # Player stealth modifiers
        player = getattr(self.app, "player", None)
        crouch_mod = 0.45 if (player and getattr(player, "_stealth_crouch", False)) else 1.0
        
        in_fov = False
        if dist < det_range:
            fwd = self.root.getQuat(self.render).getForward()
            fwd.normalize()
            target_dir = vec / dist
            if fwd.dot(target_dir) > fov_cos:
                in_fov = True
            elif dist < 5.0 * crouch_mod: # Close proximity detection even if not in FOV
                in_fov = True

        if in_fov:
            # Detection speed depends on distance and crouch
            dist_factor = 1.0 - (dist / det_range)
            det_rate = (0.35 + (dist_factor * 1.5)) * (1.0 / crouch_mod)
            self.stealth_meter = min(1.0, self.stealth_meter + det_rate * dt)
            self.last_known_player_pos = player_pos
        else:
            # Decay detection meter if out of sight
            self.stealth_meter = max(0.0, self.stealth_meter - 0.25 * dt)

        # Update awareness state
        if self.stealth_meter >= 1.0:
            self.awareness = "alert"
            self.engaged_until = globalClock.getFrameTime() + 5.0
            self._is_engaged = True
        elif self.stealth_meter > 0.15:
            self.awareness = "suspicious"
            # Look towards suspicious noise/sight
            if self.last_known_player_pos:
                look_vec = self.last_known_player_pos - pos
                desired_h = math.degrees(math.atan2(look_vec.x, look_vec.y))
                current_h = self.root.getH(self.render)
                diff = ((desired_h - current_h + 180) % 360) - 180
                self.root.setH(self.render, current_h + (diff * min(1.0, dt * 2.0)))
        else:
            self.awareness = "idle"
"""

# Insert methods before 'def update(self, dt, player_pos):'
update_def = '    def update(self, dt, player_pos):'
u_idx = content.find(update_def)
if u_idx != -1:
    content = content[:u_idx] + methods_addition + content[u_idx:]

# 3. Call _update_stealth in update()
# Replace the aggro logic with stealth-aware logic
aggro_logic_pattern = 'if dist <= self._stat("aggro_range", 18.0):'
aggro_logic_replacement = """self._update_stealth(dt, player_pos)
        if dist <= self._stat("aggro_range", 6.0) and self.awareness != "alert": # Immediate aggro if very close
             self.stealth_meter = 1.0
             self.awareness = "alert"

        if self.awareness == "alert":"""

if aggro_logic_pattern in content:
    # Find the whole block from 'if dist <= ...' to 'self._is_engaged = ...'
    # Actually just replace the block directly if possible
    old_aggro_block = """        if dist <= self._stat("aggro_range", 18.0):
            self.engaged_until = max(self.engaged_until, now + self._ai("disengage_hold", 4.0))
        self._is_engaged = now < self.engaged_until"""
    
    new_aggro_block = """        self._update_stealth(dt, player_pos)
        if self.awareness == "alert":
            self.engaged_until = max(self.engaged_until, now + self._ai("disengage_hold", 6.0))
        self._is_engaged = now < self.engaged_until"""
    
    content = content.replace(old_aggro_block, new_aggro_block)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("BossManager Patched successfully with Stealth Logic")
