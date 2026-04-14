
import os
import re

def patch_body(path, start_marker, end_marker, new_body):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Use regex to find the method body starting from start_marker and ending at end_marker
    # We escape markers because they might contain special regex chars like ( )
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, start_marker + new_body + end_marker, content, flags=re.DOTALL)
        print(f"Patched body in {os.path.basename(path)}")
    else:
        print(f"FAILED to find body pattern in {os.path.basename(path)}")
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# Logic for EnemyUnit._update_stealth (with indentation)
bm_body = """
        if not player_pos or self.hp <= 0 or self._is_engaged:
            if self._is_engaged:
                self.awareness = "alert"
                self.stealth_meter = 1.0
            return

        ss = stealth_state if isinstance(stealth_state, dict) else {}
        pos = self.root.getPos(self.render)
        vec = player_pos - pos
        dist = vec.length()
        
        # Base detection parameters scaled by stealth manager
        radius_mult = float(ss.get("detection_radius_mult", 1.0))
        det_range = 24.0 * radius_mult
        fov_cos = math.cos(math.radians(65.0)) # 130 deg total
        
        in_fov = False
        if dist < det_range:
            fwd = self.root.getQuat(self.render).getForward()
            fwd.normalize()
            target_dir = vec / dist
            if fwd.dot(target_dir) > fov_cos:
                in_fov = True
            elif dist < 5.5 * float(ss.get("is_crouched", False) and 0.45 or 1.0): 
                in_fov = True

        if in_fov:
            # Detection speed depends on distance and stealth manager's gain mult
            dist_factor = 1.0 - (dist / det_range)
            gain_mult = float(ss.get("awareness_gain_mult", 1.0))
            det_rate = (0.32 + (dist_factor * 1.55)) * gain_mult
            self.stealth_meter = min(1.0, self.stealth_meter + det_rate * dt)
            self.last_known_player_pos = player_pos
        else:
            # Decay detection meter if out of sight
            decay_mult = float(ss.get("awareness_decay_mult", 1.0))
            self.stealth_meter = max(0.0, self.stealth_meter - 0.28 * decay_mult * dt)

        """

# Logic for DragonBoss._update_stealth
db_body = """
        if not player_pos or not self.root or self._is_engaged:
            if self._is_engaged:
                self.awareness = "alert"
                self.stealth_meter = 1.0
            return

        ss = stealth_state if isinstance(stealth_state, dict) else {}
        pos = self.root.getPos(self.render)
        vec = player_pos - pos
        dist = vec.length()
        
        # Dragon has acute senses scaled by stealth manager
        radius_mult = float(ss.get("detection_radius_mult", 1.0))
        det_range = 45.0 * radius_mult
        fov_cos = math.cos(math.radians(85.0)) # Wide FOV for dragon
        
        in_fov = False
        if dist < det_range:
            fwd = self.root.getQuat(self.render).getForward()
            fwd.normalize()
            target_dir = vec / dist
            if fwd.dot(target_dir) > fov_cos:
                in_fov = True
            elif dist < 9.0 * float(ss.get("is_crouched", False) and 0.55 or 1.0): 
                in_fov = True

        if in_fov:
            dist_factor = 1.0 - (dist / det_range)
            gain_mult = float(ss.get("awareness_gain_mult", 1.0))
            det_rate = (0.18 + (dist_factor * 1.25)) * gain_mult
            self.stealth_meter = min(1.0, self.stealth_meter + det_rate * dt)
            self.last_known_player_pos = player_pos
        else:
            decay_mult = float(ss.get("awareness_decay_mult", 1.0))
            self.stealth_meter = max(0.0, self.stealth_meter - 0.18 * decay_mult * dt)

        if self.stealth_meter >= 1.0:
            self.awareness = "alert"
            self._is_engaged = True
        elif self.stealth_meter > 0.1:
            self.awareness = "suspicious"
        else:
            self.awareness = "idle"
"""

bm_path = r"C:/xampp/htdocs/king-wizard/src/entities/boss_manager.py"
db_path = r"C:/xampp/htdocs/king-wizard/src/entities/dragon_boss.py"

# For Boss Manager, find the block between signature and Update awareness state
patch_body(bm_path, "def _update_stealth(self, dt, player_pos, stealth_state=None):", "        # Update awareness state", bm_body)

# For Dragon Boss, find the block between signature and _tick_state_machine
patch_body(db_path, "def _update_stealth(self, dt, player_pos, stealth_state=None):", "    def _tick_state_machine", db_body + "\n")
