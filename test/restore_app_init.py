import os

path = 'src/app.py'
with open(path, 'rb') as f:
    lines = f.readlines()

# Identify the broken section
# Lines 305-309 are the method
# Lines 311-496 (approx) are the dangling init code
# We should move the dangling code back into __init__ (indented by 8 spaces)
# and move _force_shutdown to a better place.

# Let's find exactly where the dangling init code ends.
# It ends where the next def starts.
next_def_idx = -1
for i in range(311, len(lines)):
    if lines[i].startswith(b'    def '):
        next_def_idx = i
        break

if next_def_idx == -1:
    next_def_idx = len(lines)

shutdown_method = lines[304:310] # Including the empty line 304
dangling_code = lines[310:next_def_idx]

# Remove them from current position
del lines[304:next_def_idx]

# Re-insert dangling code into where it was (it's already indented correctly for __init__? Let's check)
# Original code at 311+ had 8 spaces? 
# View file output showed:
# 322:         self.data_mgr = DataManager()
# Yes, 8 spaces. So it IS indented for a method.
# But it was AFTER a 'def', so it was at class level.

# Re-insert dangling code back into __init__
for line in reversed(dangling_code):
    lines.insert(304, line)

# Find a good place for _force_shutdown (after __init__ ends or at the end of class)
# Let's just put it at the very end of the file for now.
lines.append(b'\r\n')
lines.extend(shutdown_method)

with open(path, 'wb') as f:
    f.writelines(lines)
print("app.py restored successfully.")
