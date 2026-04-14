
import os
import re

def patch_file(path, replacements):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f"Patched {os.path.basename(path)}")
        else:
            print(f"FAILED to find target in {os.path.basename(path)}")
            # Try a slightly more flexible match if direct fails
            # (only if it's a small enough block)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# 1. BOSS MANAGER
bm_path = r"C:/xampp/htdocs/king-wizard/src/entities/boss_manager.py"
bm_reps = [
    (
        "def _update_stealth(self, dt, player_pos):",
        "def _update_stealth(self, dt, player_pos, stealth_state=None):"
    ),
    (
        "self._update_stealth(dt, player_pos)",
        "self._update_stealth(dt, player_pos, stealth_state)"
    ),
    (
        "def update(self, dt, player_pos):",
        "def update(self, dt, player_pos, stealth_state=None):"
    ),
    (
        "unit.update(dt, player_pos)",
        "unit.update(dt, player_pos, stealth_state)"
    )
]

# 2. DRAGON BOSS
db_path = r"C:/xampp/htdocs/king-wizard/src/entities/dragon_boss.py"
db_reps = [
    (
        "def _update_stealth(self, dt, player_pos):",
        "def _update_stealth(self, dt, player_pos, stealth_state=None):"
    ),
    (
        "self._update_stealth(dt, player_pos)",
        "self._update_stealth(dt, player_pos, stealth_state)"
    ),
    (
        "def update(self, dt, player_pos):",
        "def update(self, dt, player_pos, stealth_state=None):"
    ),
    (
        "self._tick_state_machine(dt, player_pos)",
        "self._tick_state_machine(dt, player_pos, stealth_state)"
    ),
    (
        "def _tick_state_machine(self, dt, player_pos):",
        "def _tick_state_machine(self, dt, player_pos, stealth_state=None):"
    )
]

# 3. PLAYER COMBAT MIXIN (Sneak Attack)
pcm_path = r"C:/xampp/htdocs/king-wizard/src/entities/player_combat_mixin.py"
pcm_reps = [
    (
        "mul = 1.0 - (0.45 * t)",
        "mul = 1.0 - (0.45 * t)\n        # Sneak Attack Multiplier\n        ss = getattr(self, '_stealth_state_cache', {})\n        if ss.get('state') == 'hidden':\n            mul *= 2.5"
    )
]

if os.path.exists(bm_path): patch_file(bm_path, bm_reps)
if os.path.exists(db_path): patch_file(db_path, db_reps)
if os.path.exists(pcm_path): patch_file(pcm_path, pcm_reps)
