import os

path = 'src/app.py'
with open(path, 'rb') as f:
    lines = f.readlines()

# Line 208 (index 207) - Register userExit
target_line = b'        write_startup_breadcrumb(self.project_root, "window_setup_complete")\r\n'
if target_line in lines[207]:
    lines.insert(208, b'\r\n')
    lines.insert(209, b'        # Shutdown Handling\r\n')
    lines.insert(210, b'        self.userExit = self._force_shutdown\r\n')

# Line 300 (index 299 originally, now shifted by 3)
# Target: self.render.setLight(self._dlnp)
# New index: 299 + 3 = 302
target_light = b'        self.render.setLight(self._dlnp)\r\n'
found_index = -1
for i, line in enumerate(lines):
    if target_light in line and i > 250:
        found_index = i
        break

if found_index != -1:
    lines.insert(found_index + 1, b'\r\n')
    lines.insert(found_index + 2, b'    def _force_shutdown(self):\r\n')
    lines.insert(found_index + 3, b'        """Robust shutdown call to ensure process dies immediately."""\r\n')
    lines.insert(found_index + 4, b'        logger.info("[App] Shutdown requested. Forcing process termination...")\r\n')
    lines.insert(found_index + 5, b'        import os\r\n')
    lines.insert(found_index + 6, b'        os._exit(0)\r\n')

with open(path, 'wb') as f:
    f.writelines(lines)
print("app.py patched successfully.")
