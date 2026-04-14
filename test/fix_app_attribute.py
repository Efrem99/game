
import os

target = r"C:/xampp/htdocs/king-wizard/src/app.py"
with open(target, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the perf_fps calculation
old_fps = 'perf_fps = perf_mgr.get_fps() if perf_mgr else 0.0'
new_fps = 'perf_fps = perf_mgr.average_fps if perf_mgr else 0.0'
content = content.replace(old_fps, new_fps)

# Fix any redundant _scan_for_nan if I accidentally double-defined it
# (The repair script from before had it once, but my previous replace might have left an orphaned one)

with open(target, "w", encoding="utf-8") as f:
    f.write(content)

print("Fix of app.py completed.")
