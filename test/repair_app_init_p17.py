import os

path = 'src/app.py'
with open(path, 'rb') as f:
    content = f.read()

# We need to find the spot after fog.setColor and before self._cutscene_triggers_enabled
# Note: The file might have CRLF or LF.

target_start = b'                fog.setColor(0.45, 0.62, 0.85)'
target_end = b'            self._cutscene_triggers_enabled = False'

if target_start in content and target_end in content:
    start_idx = content.find(target_start) + len(target_start)
    end_idx = content.find(target_end)
    
    # Check what's between them. View file showed line 3838 was directly self._cutscene_triggers_enabled.
    # We want to replace everything from just after target_start to target_end with our full block.
    
    new_block = b'''
                fog.setExpDensity(0.008)
                self.render.setFog(fog)

        if not hasattr(self, 'player') or self.player is None:
            self.player = Player(
                self, self.render, self.loader,
                self.char_state, self.phys,
                self.combat, self.parkour,
                self.magic, self.particles,
                self.parkour_state
            )
            # Spawn slightly away from (0,0,0) so we don't start inside the pillar
            if "sharuan" in str(self.world.__class__).lower():
                # Moving closer to sandbox NPCs (Adalin is at 10,45, Sentry Marcus at 18,48, Martha at 15,52)
                self.player.actor.setPos(15.0, 40.0, 5.0)
        self._video_bot_refresh_bindings()

        self.enemy_proxies = []
        force_enemy_runtime = bool(getattr(self, "_video_bot_force_aggro_mobs", False))
        lightweight_test_runtime = self._is_lightweight_test_runtime()
        if lightweight_test_runtime:
            logger.info(
                "[Perf] Python-only runtime test: skipping NPC/enemy spawns and cinematic triggers for stability."
            )
            self.boss_manager = None
            self.dragon_boss = None
'''
    # Careful with indentation. target_end has 12 spaces in the view_file.
    # The new_block needs to align.
    
    repaired_content = content[:start_idx] + new_block + content[end_idx:]
    
    with open(path, 'wb') as f:
        f.write(repaired_content)
    print("app.py repaired successfully with robust python script.")
else:
    print(f"Failed to find targets. target_start in content: {target_start in content}, target_end in content: {target_end in content}")
