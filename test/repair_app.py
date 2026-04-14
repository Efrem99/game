
import os

target = r"C:/xampp/htdocs/king-wizard/src/app.py"
with open(target, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip_until = None

# We want to find _heartbeat and replace it entirely with a clean version.
heartbeat_start = -1
for i, line in enumerate(lines):
    if "def _heartbeat(self, task):" in line:
        heartbeat_start = i
        break

if heartbeat_start != -1:
    # Keep everything BEFORE _heartbeat
    new_lines = lines[:heartbeat_start]
    
    # Add a CLEAN _heartbeat
    new_lines.append("    def _heartbeat(self, task):\n")
    new_lines.append("        if task.frame < 10:\n")
    new_lines.append('            logger.debug(f"Heartbeat - Frame {task.frame} processed.")\n')
    new_lines.append("        elif task.frame == 10:\n")
    new_lines.append('            logger.info("Main loop confirmed healthy (10 frames processed).")\n')
    new_lines.append("        else:\n")
    new_lines.append("            now = globalClock.getRealTime()\n")
    new_lines.append("            if (now - self._last_diag_log_time) >= self._diag_log_interval_sec:\n")
    new_lines.append("                self._last_diag_log_time = now\n")
    new_lines.append("                cam = self.camera.getPos()\n")
    new_lines.append('                plyr = self.player.actor.getPos() if self.player else "None"\n')
    new_lines.append('                load_level = int(getattr(self, "_runtime_load_level", 0))\n')
    new_lines.append('                perf_mgr = getattr(self, "adaptive_perf_mgr", None)\n')
    new_lines.append("                perf_fps = perf_mgr.get_fps() if perf_mgr else 0.0\n")
    new_lines.append('                adaptive_mode = str(getattr(self, "_adaptive_mode", "balanced") or "balanced")\n')
    new_lines.append('                if perf_mgr and hasattr(perf_mgr, "debug_snapshot"):\n')
    new_lines.append("                    try:\n")
    new_lines.append("                        snap = perf_mgr.debug_snapshot() or {}\n")
    new_lines.append('                        load_level = int(snap.get("level", load_level))\n')
    new_lines.append('                        perf_fps = float(snap.get("average_fps", 0.0) or 0.0)\n')
    new_lines.append('                        adaptive_mode = str(snap.get("mode", adaptive_mode) or adaptive_mode)\n')
    new_lines.append("                    except Exception:\n")
    new_lines.append("                        perf_fps = 0.0\n")
    new_lines.append("                logger.info(\n")
    new_lines.append('                    f"[Diagnostics] FPS: {globalClock.getAverageFrameRate():.1f} | "\n')
    new_lines.append('                    f"Adaptive: {adaptive_mode}/L{load_level} ({perf_fps:.1f}) | "\n')
    new_lines.append('                    f"Cam: {cam} | Player: {plyr} | Particles: {self._last_particle_count}"\n')
    new_lines.append("                )\n")
    new_lines.append("        return Task.cont\n\n")
    
    # Add a CLEAN _scan_for_nan
    new_lines.append("    def _scan_for_nan(self, node_path):\n")
    new_lines.append('        """Recursively scan for NaN transforms and log offending nodes."""\n')
    new_lines.append("        count = 0\n")
    new_lines.append("        if not node_path or node_path.isEmpty():\n")
    new_lines.append("            return count\n")
    new_lines.append("        count += 1\n")
    new_lines.append("        ts = node_path.getTransform()\n")
    new_lines.append("        if ts.isInvalid():\n")
    new_lines.append('             logger.error(f"[Audit] INVALID TRANSFORM detected on: {node_path}")\n')
    new_lines.append("        pos = node_path.getPos()\n")
    new_lines.append("        import math\n")
    new_lines.append("        if any(math.isnan(float(c)) for c in [pos.x, pos.y, pos.z]):\n")
    new_lines.append('             logger.error(f"[Audit] NaN POSITION detected on: {node_path} -> {pos}")\n')
    new_lines.append("             node_path.setPos(0, 0, 0)\n")
    new_lines.append("        scale = node_path.getScale()\n")
    new_lines.append("        if any(math.isnan(float(c)) for c in [scale.x, scale.y, scale.z]):\n")
    new_lines.append('             logger.error(f"[Audit] NaN SCALE detected on: {node_path} -> {scale}")\n')
    new_lines.append("             node_path.setScale(1, 1, 1)\n")
    new_lines.append("        for child in node_path.getChildren():\n")
    new_lines.append("            count += self._scan_for_nan(child)\n")
    new_lines.append("        return count\n\n")

    # Now find where to resume after the mess.
    # The mess likely ends before _upload_particles.
    resume_index = -1
    for i in range(heartbeat_start, len(lines)):
        if "def _upload_particles(self):" in lines[i]:
            resume_index = i
            break
    
    if resume_index != -1:
        new_lines.extend(lines[resume_index:])
    
    with open(target, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Repair of app.py completed.")
else:
    print("Could not find _heartbeat in app.py")
