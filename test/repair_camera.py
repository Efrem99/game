
import os
import math

target = r"C:/xampp/htdocs/king-wizard/src/managers/camera_director.py"
with open(target, "r", encoding="utf-8") as f:
    content = f.read()

# 1. lerp3 replace
old_lerp = """def _lerp3(a, b, t):
    return LPoint3(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t,
    )"""

new_lerp = """def _lerp3(a, b, t):
    t = max(0.0, min(1.0, float(t)))
    try:
        ax, ay, az = float(a.x), float(a.y), float(a.z)
        bx, by, bz = float(b.x), float(b.y), float(b.z)
        if any(math.isnan(v) for v in (ax, ay, az, bx, by, bz)):
            return LPoint3(0, 0, 0)
        return LPoint3(
            ax + (bx - ax) * t,
            ay + (by - ay) * t,
            az + (bz - az) * t,
        )
    except Exception:
        return LPoint3(0, 0, 0)"""

content = content.replace(old_lerp, new_lerp)

# 2. player_center replace (approximate search)
old_pc = 'return Vec3(float(pos.x), float(pos.y), float(pos.z)), float(pos.z)'
new_pc = '''try:
            px, py, pz = float(pos.x), float(pos.y), float(pos.z)
            if math.isnan(px) or math.isnan(py) or math.isnan(pz):
                return LPoint3(0, 0, 0), 0.0
            return Vec3(px, py, pz), pz
        except Exception:
            return LPoint3(0, 0, 0), 0.0'''

# We need to be careful with indentation here.
# Line 271-272:
#         pos = player.actor.getPos()
#         return Vec3(float(pos.x), float(pos.y), float(pos.z)), float(pos.z)
content = content.replace('        return Vec3(float(pos.x), float(pos.y), float(pos.z)), float(pos.z)', '        ' + new_pc)

# 3. play_camera_shot info log replace
old_log = 'logger.info(f"[CameraDirector] Shot \'{name}\' \u2192 {duration:.2f}s")'
new_log = 'logger.info(f"[CameraDirector] Shot \'{name}\' \u2192 {duration:.2f}s params=[from={from_pos}, to={to_pos}, look={to_look}]")'
content = content.replace(old_log, new_log)

with open(target, "w", encoding="utf-8") as f:
    f.write(content)

print("Repair completed.")
