
import os

target = r"C:/xampp/htdocs/king-wizard/src/app.py"
with open(target, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip_scan = False

for line in lines:
    # 1. Remove the call to _scan_for_nan in update()
    if "# Optimized Scene Audit" in line:
        continue
    if 'bool(getattr(self, "_active_scene_audit", True)) and getattr(self, "state", "") == "PLAYING":' in line:
        continue
    if "if int(globalClock.getFrameCount()) % 5 == 0:" in line:
        continue
    if "self._scan_for_nan(self.render)" in line:
        continue
    
    # 2. Remove the _scan_for_nan method definition
    if "def _scan_for_nan(self, node_path):" in line:
        skip_scan = True
        continue
    
    if skip_scan:
        # Stop skipping if we hit the next method or end of current scope
        if line.startswith("    def "):
             skip_scan = False
             new_lines.append(line)
        continue
    
    new_lines.append(line)

with open(target, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Removal of Scene Audit from app.py completed.")
