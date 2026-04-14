
import os

path = r'C:/xampp/htdocs/king-wizard/src/app.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
import_line = "from ui.credits_sequence import CreditsSequence"
if import_line not in content:
    content = content.replace("from ui.hud_overlay import HUDOverlay", "from ui.hud_overlay import HUDOverlay\n" + import_line)

# 2. Add initialization in __init__
init_target = "self.hud = HUDOverlay(self)"
init_replacement = "self.hud = HUDOverlay(self)\n        self.credits = CreditsSequence(self)"
if init_target in content:
    content = content.replace(init_target, init_replacement)

# 3. Add update call
update_target = "self.hud.update("
update_replacement = "self.credits.update(dt)\n        self.hud.update("
if update_target in content:
    content = content.replace(update_target, update_replacement)

# 4. Add trigger (we can repurpose a console command or key)
# Let's add it to the input handling section.
# I'll search for 'if self.mouseWatcherNode.isButtonDown(MouseButton.one()):'
trigger_logic = """
        # Debug Credits Trigger (Ctrl+Alt+C) for sandbox
        if self.mouseWatcherNode.isButtonDown("c") and self.mouseWatcherNode.isButtonDown("control") and self.mouseWatcherNode.isButtonDown("alt"):
            if hasattr(self, "credits") and not self.credits._is_active:
                self.credits.start()
"""
input_target = 'if self.mouseWatcherNode.isButtonDown(MouseButton.one()):'
if input_target in content:
    content = content.replace(input_target, trigger_logic + "        " + input_target)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("App Patched successfully with Credits Sequence")
