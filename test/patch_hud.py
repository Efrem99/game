
import os

path = r'C:/xampp/htdocs/king-wizard/src/ui/hud_overlay.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add _create_respawn_notification call in __init__
init_target = 'self._create_npc_scene_debug()'
init_replacement = 'self._create_npc_scene_debug()\n        self._create_respawn_notification()'
content = content.replace(init_target, init_replacement)

# 2. Add methods after _create_damage_feed
feed_end = 'place_ui_on_top(self.damage_text, 84)'
methods = """
    def push_damage_event(self, amount, damage_type):
        \"\"\"Called when player takes damage. Triggers visual effects but no floating numbers.\"\"\"
        pass

    def notify_respawn(self, duration=4.0):
        self._respawn_active = True
        self._respawn_timer = float(duration)
        if hasattr(self, "respawn_root"):
            self.respawn_root.show()

    def _create_respawn_notification(self):
        self._respawn_active = False
        self._respawn_timer = 0.0
        self.respawn_root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.root,
        )
        self.respawn_bg = DirectFrame(
            frameColor=(0.05, 0.01, 0.01, 0.0),
            frameSize=(-2, 2, -1, 1),
            parent=self.respawn_root,
        )
        self.respawn_title = OnscreenText(
            text=self.app.data_mgr.t("hud.fainted", "YOU HAVE FAINTED"),
            pos=(0.0, 0.12),
            scale=0.10,
            fg=(0.92, 0.24, 0.24, 0.0),
            shadow=(0, 0, 0, 0.0),
            align=TextNode.ACenter,
            parent=self.respawn_root,
            mayChange=True,
            font=title_font(self.app),
        )
        self.respawn_hint = OnscreenText(
            text=self.app.data_mgr.t("hud.respawn_tip", "Respawn available soon..."),
            pos=(0.0, -0.05),
            scale=0.035,
            fg=(0.85, 0.85, 0.88, 0.0),
            shadow=(0, 0, 0, 0.0),
            align=TextNode.ACenter,
            parent=self.respawn_root,
            mayChange=True,
            font=body_font(self.app),
        )
        self.respawn_timer_text = OnscreenText(
            text="",
            pos=(0.0, -0.15),
            scale=0.05,
            fg=(0.95, 0.90, 0.60, 0.0),
            shadow=(0, 0, 0, 0.0),
            align=TextNode.ACenter,
            parent=self.respawn_root,
            mayChange=True,
            font=title_font(self.app),
        )
        for node in (self.respawn_bg, self.respawn_title, self.respawn_hint, self.respawn_timer_text):
            place_ui_on_top(node, 95)
        self.respawn_root.hide()
"""
if feed_end in content:
    content = content.replace(feed_end, feed_end + methods)

# 3. Update update method logic (targeted replacement of the beginning of the method)
import re
update_pattern = r'def update\(\s+self,\s+dt,\s+char_state,'
update_replacement = r'''def update(
        self,
        dt,
        char_state,'''

# Since update has a lot of args, I'll just find the line after 'dt = max(0.0, float(dt or 0.0))'
dt_line = 'dt = max(0.0, float(dt or 0.0))'
respawn_logic = """
        if getattr(self, "_respawn_active", False):
            self._respawn_timer = max(0.0, self._respawn_timer - dt)
            alpha = min(1.0, (4.0 - self._respawn_timer) * 1.5) if self._respawn_timer > 0 else 1.0
            if self._respawn_timer <= 0:
                alpha = 1.0
                hint = self.app.data_mgr.t("hud.respawn_ready", "Press JUMP to respawn")
                self.respawn_hint.setText(hint)
            
            self.respawn_bg["frameColor"] = (0.05, 0.01, 0.01, alpha * 0.75)
            self.respawn_title.setFg((0.92, 0.24, 0.24, alpha))
            self.respawn_title.setShadow((0, 0, 0, alpha * 0.85))
            self.respawn_hint.setFg((0.85, 0.85, 0.88, alpha))
            self.respawn_hint.setShadow((0, 0, 0, alpha * 0.75))
            
            if self._respawn_timer > 0:
                self.respawn_timer_text.setText(f"{int(math.ceil(self._respawn_timer))}s")
                self.respawn_timer_text.setFg((0.95, 0.90, 0.60, alpha))
            else:
                self.respawn_timer_text.setText("")
        elif hasattr(self, "respawn_root"):
            self.respawn_root.hide()
"""

if dt_line in content:
    # Find the first occurrence after index 2000 (roughly where update is)
    idx = content.find(dt_line, 80000) # file size is 88k
    if idx != -1:
        insert_pos = idx + len(dt_line)
        content = content[:insert_pos] + respawn_logic + content[insert_pos:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("HUD Patched successfully")
