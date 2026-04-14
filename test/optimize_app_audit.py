
import os

target = r"C:/xampp/htdocs/king-wizard/src/app.py"
with open(target, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the heavy audit in update()
old_audit = """        # Emergency Scene Audit before render
        if bool(getattr(self, "_active_scene_audit", True)):
            self._scan_for_nan(self.render)"""

new_audit = """        # Optimized Scene Audit before render (only once every 5 frames in PLAYING state)
        if bool(getattr(self, "_active_scene_audit", True)) and getattr(self, "state", "") == "PLAYING":
            if int(globalClock.getFrameCount()) % 5 == 0:
                self._scan_for_nan(self.render)"""

content = content.replace(old_audit, new_audit)

with open(target, "w", encoding="utf-8") as f:
    f.write(content)

print("Optimization of app.py completed.")
