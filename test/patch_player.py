
import os

path = r'C:/xampp/htdocs/king-wizard/src/entities/player.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace legacy register_incoming_damage and following reactive methods with cleaner versions
legacy_start = 'def register_incoming_damage(self, amount=0.0, damage_type="physical"):'
# Find the end of _update_damage_feedback logic
fb_logic = 'self._damage_vignette_intensity = max('
fb_end = 'vignette_intensity,'

# Since matching a large block is hard, I'll identify the start index and then look for the next method or end of the class
start_idx = content.rfind(legacy_start) # Use rfind to get the late one (reactive logic)

if start_idx != -1:
    # Target methods to replace: register_incoming_damage, get_damage_vignette_state, _tick_damage_vignette_state, _update_damage_feedback
    # I'll just find the next 'def ' after '_update_damage_feedback'
    search_from = content.find('def _update_damage_feedback(self):', start_idx)
    next_def = content.find('    def ', search_from + 30)
    
    if next_def == -1:
        # If no more methods, replace until end? No, let's be more precise.
        next_def = len(content)

    replacement = """    def register_incoming_damage(self, amount=0.0, damage_type="physical"):
        \"\"\"Legacy support wrapper\"\"\"
        self.take_damage(amount, damage_type)

    def get_damage_vignette_state(self):
        return {
            "type": str(getattr(self, "_damage_vignette_type", "") or "").strip().lower(),
            "intensity": max(0.0, min(1.0, float(getattr(self, "_damage_vignette_intensity", 0.0) or 0.0))),
        }

    def _tick_damage_vignette_state(self, dt):
        try:
            decay = max(0.0, float(dt or 0.0)) * 1.85
        except Exception:
            decay = 0.0
        self._damage_vignette_intensity = max(
            0.0,
            float(getattr(self, "_damage_vignette_intensity", 0.0) or 0.0) - decay,
        )
        if self._damage_vignette_intensity <= 0.001:
            self._damage_vignette_intensity = 0.0
            self._damage_vignette_type = ""

    def _update_damage_feedback(self):
        \"\"\"Reactive fallback to catch damage not sent through take_damage()\"\"\"
        cs = getattr(self, "cs", None)
        if not cs or (not hasattr(cs, "health")):
            return
        try:
            current_hp = float(cs.health)
        except Exception:
            return
        prev_hp = getattr(self, "_last_hp_observed", None)
        self._last_hp_observed = current_hp
        if prev_hp is None:
            return
        delta = float(prev_hp) - current_hp
        if delta <= 0.35:
            return
        self.take_damage(delta, getattr(self, "_incoming_damage_type", "physical") or "physical")

"""
    content = content[:start_idx] + replacement + content[next_def:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Player Patched successfully")
