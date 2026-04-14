"""
WeatherManager - Controls global environmental states (Rain, Storm, Snow, Clear).
Coordinates VFX, Audio, and Lighting for immersive atmosphere.
"""
import random
import math
from panda3d.core import Vec4, Vec3
from utils.logger import logger

class WeatherState:
    CLEAR = "clear"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    CURSED = "cursed" # Krimora-specific reddish hue

class WeatherManager:
    def __init__(self, app):
        self.app = app
        self.current_state = WeatherState.CLEAR
        self.target_state = WeatherState.CLEAR
        self.transition_accum = 1.0
        self.transition_duration = 5.0
        self.blend = 0.0 # New blend for state transitions
        
        self.vfx = getattr(app, "vfx", None)
        self.active_weather_effects = []
        
        # Audio & Lighting refs (placeholders for now)
        self.ambient_sound = None
        self.timer = 0.0
        self.location_profile = "default"
        self.cursed_blend = 0.0 # 0.0 to 1.0 reddish hue blend
        
        app.taskMgr.add(self.update, "weather-update")
        logger.info("[WeatherManager] Initialized in Clear state.")

    def set_state(self, state, duration=5.0):
        if state == self.current_state:
            return
        logger.info(f"[WeatherManager] Transitioning from {self.current_state} to {state}")
        self.target_state = state
        self.transition_accum = 0.0
        self.transition_duration = max(0.1, float(duration))
        self.blend = 0.0 # Reset blend on new state transition
        
        # Trigger VFX changes immediately or start fading
        self._sync_vfx()

    def _sync_vfx(self):
        if not self.vfx:
            return
            
        # Cleanup old effects if needed (or fade them)
        for fx in self.active_weather_effects:
            if hasattr(fx, "cleanup"):
                fx.cleanup()
        self.active_weather_effects = []
        
        if self.target_state == WeatherState.RAIN:
            fx = self.vfx.spawn_rain_vfx(self.app.render)
            self.active_weather_effects.append(fx)
        elif self.target_state == WeatherState.STORM:
            fx = self.vfx.spawn_rain_vfx(self.app.render, heavy=True)
            self.active_weather_effects.append(fx)
        elif self.target_state == WeatherState.SNOW:
            fx = self.vfx.spawn_snow_vfx(self.app.render)
            self.active_weather_effects.append(fx)

    def update(self, task):
        """Update transitions and storm events."""
        dt = self.app.clock.getDt()
        
        # Handle state transition (lerp lighting/fog)
        if self.target_state != self.current_state:
            self.blend += dt / self.transition_duration
            if self.blend >= 1.0:
                self.blend = 1.0
                self.current_state = self.target_state
        
        # Handle location profiles (Atmosphere)
        player = getattr(self.app, "player", None)
        if player and player.actor:
            pos = player.actor.getPos()
            # Kremor logic (near 76, 12)
            dist_to_kremor = (Vec3(pos.x, pos.y, 0) - Vec3(76, 12, 0)).length()
            if dist_to_kremor < 60.0:
                self.cursed_blend = min(1.0, (self.cursed_blend if not (math.isnan(self.cursed_blend) or math.isinf(self.cursed_blend)) else 0.0) + dt / 3.0)
            else:
                self.cursed_blend = max(0.0, (self.cursed_blend if not (math.isnan(self.cursed_blend) or math.isinf(self.cursed_blend)) else 0.0) - dt / 3.0)
            
            if math.isnan(self.cursed_blend) or math.isinf(self.cursed_blend):
                self.cursed_blend = 0.0

        # Sync with HUD for post-fx (reddish hue)
        hud = getattr(self.app, "hud", None)
        if hud and hasattr(hud, "update_cursed_effect"):
            hud.update_cursed_effect(self.cursed_blend)

        # Update persistent weather VFX position
        if self.app.player and self.app.player.actor:
            ppos = self.app.player.actor.getPos(self.app.render)
            # Safety: skip if position is invalid (prevents TransformState has_mat assertion errors)
            if any(math.isnan(v) or math.isinf(v) for v in (ppos.x, ppos.y, ppos.z)):
                return task.cont
                
            for fx in self.active_weather_effects:
                if hasattr(fx, "setPos"):
                    fx.setPos(ppos.x, ppos.y, ppos.z + 15.0)

        # Storm Logic (Lightning)
        if self.current_state == WeatherState.STORM:
            self.timer -= dt
            if self.timer <= 0:
                self._trigger_lightning()
                self.timer = random.uniform(4.0, 12.0)

        self._apply_environmental_lerp()
        return task.cont

    def _apply_environmental_lerp(self):
        """Adjust global fog and potentially lighting based on weather blends."""
        if not self.app.render:
            return
            
        render = self.app.render
        
        # Adjust Fog based on cursed_blend
        if self.cursed_blend > 0.01:
            from panda3d.core import Fog
            existing_fog = render.getFog()
            if not existing_fog:
                existing_fog = Fog("cursed_fog")
                render.setFog(existing_fog)
                
            # Lerp from standard blue-ish fog to dark-red cursed fog
            # Standard: (0.45, 0.62, 0.85)
            # Cursed: (0.18, 0.02, 0.01) - very dark red
            
            b = self.cursed_blend
            r = 0.45 * (1.0 - b) + 0.18 * b
            g = 0.62 * (1.0 - b) + 0.02 * b
            blue = 0.85 * (1.0 - b) + 0.01 * b
            
            existing_fog.setColor(r, g, blue)
            # Higher density in cursed zone
            density = 0.008 * (1.0 - b) + 0.024 * b
            existing_fog.setExpDensity(density)
            
        # Potentially adjust global light color too
        # ...

    def _trigger_lightning(self):
        logger.debug("[WeatherManager] Lightning strike!")
        # 1. VFX: Screen flash (white background for a frame)
        # 2. Audio: Thunder sound
        if hasattr(self.app, "hud"):
            self.app.hud.trigger_screen_flash(color=Vec4(1,1,1,0.5), duration=0.15)
        
        # Random delay for thunder
        delay = random.uniform(0.2, 1.0)
        # self.app.taskMgr.doMethodLater(delay, self._play_thunder, "thunder-sound")
