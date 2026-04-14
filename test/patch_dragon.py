
import os

path = r'C:/xampp/htdocs/king-wizard/src/entities/dragon_boss.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update damage application to use new system
content = content.replace(
    'char_state.health = max(0.0, float(char_state.health) - damage)',
    'player.take_damage(damage, "fire", source=self)'
)

# 2. Add telegraph and AOE states to AI
ai_logic = """            if self._is_engaged and dist <= fire_range and self._fire_cooldown <= 0.0:
                # Add a telegraph phase before fire
                self._set_state("telegraph_fire", lock=1.0)
                self._fire_cooldown = self._ai_value("fire_cooldown", 5.8)
                self._fire_emit_accum = 0.0
                self._fire_tick_accum = 0.0
            elif self._is_engaged and dist <= 12.0 and self._fire_cooldown > 2.0 and self._rng.random() < 0.15:
                # AOE Tail Sweep if player is close
                self._set_state("telegraph_tail", lock=0.8)
            elif self._is_engaged and globalClock.getFrameTime() >= self._next_roar_time:
                self._set_state("roar", lock=1.15)
                self._next_roar_time = globalClock.getFrameTime() + self._rng.uniform(6.0, 9.0)
            elif self._is_engaged:
                self._set_state("patrol")
            else:
                self._set_state("idle")

        # Handle telegraph transitions
        if self._state == "telegraph_fire" and self._state_lock <= 0.001:
            self._set_state("fire_breath", lock=self._ai_value("fire_duration", 2.2))
        elif self._state == "telegraph_tail" and self._state_lock <= 0.001:
            self._set_state("tail_sweep", lock=1.2)
            self._apply_tail_sweep_aoe(player_pos)"""

ai_pattern = 'if self._is_engaged and dist <= fire_range and self._fire_cooldown <= 0.0:'
# Find the end of the if block
block_start = content.find(ai_pattern)
if block_start != -1:
    block_end = content.find('self._fire_cooldown = max(0.0, self._fire_cooldown - dt)', block_start)
    if block_end != -1:
        content = content[:block_start] + ai_logic + content[block_end-8:] # -8 to keep leading spaces of the next line

# 3. Add AOE application method and telegraph effects
update_fire = """if self._state == "fire_breath":
            self._fire_emit_accum += dt
            emit_rate = 0.02
            while self._fire_emit_accum >= emit_rate:
                self._fire_emit_accum -= emit_rate
                self._emit_fire_particle()

            now = globalClock.getFrameTime()
            if now - self._last_fire_sfx_time >= 0.32:
                audio = getattr(self.app, "audio", None)
                if audio:
                    try:
                        audio.play_sfx("dragon_fire", volume=0.92, rate=0.86)
                    except Exception:
                        pass
                self._last_fire_sfx_time = now

            self._apply_fire_damage(player_pos, dt)
        
        if self._state == "telegraph_fire":
            # Visual indicator for fire breath
            if self._rng.random() < 0.25:
                self._emit_fire_particle()

        self._tick_fire_particles(dt)

    def _apply_tail_sweep_aoe(self, player_pos):
        origin = self.root.getPos(self.render)
        dist = (player_pos - origin).length()
        radius = 12.0
        if dist <= radius:
            player = getattr(self.app, "player", None)
            if player:
                damage = int(self._stat("melee_damage", 35.0))
                player.take_damage(damage, "physical", source=self)
                # Blowback effect
                if hasattr(player, "cs") and hasattr(player.cs, "velocity"):
                    vec = player_pos - origin
                    vec.z = 0
                    vec.normalize()
                    try:
                        player.cs.velocity += vec * 15.0
                    except Exception:
                        pass
"""

update_target = 'if self._state == "fire_breath":'
u_start = content.rfind(update_target)
if u_start != -1:
    u_end = content.find('self._tick_fire_particles(dt)', u_start)
    if u_end != -1:
        content = content[:u_start] + update_fire + content[u_end + len('self._tick_fire_particles(dt)'):]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Dragon Patched successfully")
