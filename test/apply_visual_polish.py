
import os
import re

file_path = "src/entities/player.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Redesign Bow
bow_old = r'if token == "bow":\s+grip = self\._make_box\(parent, "bow_grip", 0\.05, 0\.07, 0\.52, \(0\.34, 0\.22, 0\.12, 1\.0\)\)\s+limb_top = self\._make_box\(parent, "bow_limb_top", 0\.05, 0\.03, 0\.52, \(0\.48, 0\.34, 0\.18, 1\.0\)\)\s+limb_bottom = self\._make_box\(parent, "bow_limb_bottom", 0\.05, 0\.03, 0\.52, \(0\.48, 0\.34, 0\.18, 1\.0\)\)\s+string = self\._make_box\(parent, "bow_string", 0\.01, 0\.01, 0\.96, \(0\.86, 0\.84, 0\.76, 0\.95\)\)\s+rest = self\._make_box\(parent, "bow_arrow_rest", 0\.12, 0\.02, 0\.04, \(0\.70, 0\.58, 0\.42, 1\.0\)\)\s+grip\.setPos\(0\.0, 0\.0, 0\.26\)\s+limb_top\.setPos\(0\.0, 0\.07, 0\.54\)\s+limb_bottom\.setPos\(0\.0, -0\.07, 0\.02\)\s+string\.setPos\(0\.0, 0\.0, 0\.48\)\s+rest\.setPos\(0\.05, 0\.0, 0\.26\)\s+return'

bow_new = '''if token == "bow":
            # Premium Curved Bow: Segmented geometry
            grip = self._make_box(parent, "bow_grip", 0.04, 0.08, 0.15, (0.34, 0.22, 0.12, 1.0))
            grip.setPos(0.0, 0.0, 0.25)
            # Limbs
            for side in [1, -1]:
                for i in range(1, 5):
                    thickness = 0.04 - (i * 0.005)
                    limb = self._make_box(parent, f"bow_limb_{side}_{i}", 0.03, thickness, 0.18, (0.45, 0.32, 0.18, 1.0))
                    limb.setPos(0.0, (i*i)*0.015, 0.25 + (side * (i * 0.14)))
                    limb.setP(side * (i * 12))
            # String with tension
            string = self._make_box(parent, "bow_string", 0.008, 0.008, 1.15, (0.9, 0.9, 0.85, 0.8))
            string.setPos(0.0, -0.05, 0.25)
            # Glow rest
            rest = self._make_box(parent, "bow_arrow_rest", 0.08, 0.03, 0.03, (0.2, 0.6, 1.0, 0.9))
            rest.setPos(0.02, 0.0, 0.25)
            rest.setLightOff(1)
            return'''

content = re.sub(bow_old, bow_new, content)

# 2. Add Parkour VFX triggers
# Update _update_parkour_ik to include wind effects?
ik_old = r'if alpha <= 0\.001:\s+for node in controls\.values\(\):\s+_apply\(node, \(0\.0, 0\.0, 0\.0\)\)\s+return'
ik_new = '''if alpha <= 0.001:
            for node in controls.values():
                _apply(node, (0.0, 0.0, 0.0))
            if hasattr(self, "_parkour_wind_vfx") and self._parkour_wind_vfx:
                self._parkour_wind_vfx.cleanup()
                self._parkour_wind_vfx = None
            return'''

content = re.sub(ik_old, ik_new, content)

# Update wallrun logic to spawn wind
wallrun_old = r'if family == "wallrun" or state == "wallrun":\s+sway = math\.sin\(t \* 8\.6\)'
wallrun_new = '''if family == "wallrun" or state == "wallrun":
            # Spawn wind streaks during wallrun
            if not getattr(self, "_parkour_wind_vfx", None):
                if hasattr(self.app, "magic_vfx"):
                    self._parkour_wind_vfx = self.app.magic_vfx.spawn_parkour_wind_vfx(self.actor)
            sway = math.sin(t * 8.6)'''

content = re.sub(wallrun_old, wallrun_new, content)

# Landing dust
land_old = r'context = \{\s+"speed":               speed,'
land_new = '''# Trigger landing dust if just landed
        if on_ground and not getattr(self, "_was_grounded", True):
            impact = float(getattr(self, "_last_landing_impact_speed", 0.0) or 0.0)
            if impact > 2.0 and hasattr(self.app, "magic_vfx"):
                self.app.magic_vfx.spawn_landing_dust_vfx(self.actor.getPos())

        context = {
            "speed":               speed,'''

content = re.sub(land_old, land_new, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Visual Polish applied successfully.")
