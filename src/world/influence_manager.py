"""World influence system for reactive static layers (bending foliage, etc.)."""

from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import PTA_LVecBase4f, LVecBase4f
import math

class WorldInfluence:
    def __init__(self, fx_type, pos, radius, strength, duration):
        self.fx_type = fx_type # "fire", "ice", "force", "wind"
        self.pos = pos
        self.radius = radius
        self.strength = strength
        self.max_duration = duration
        self.timer = duration

class InfluenceManager:
    MAX_INFLUENCES = 16

    def __init__(self, render):
        self.render = render
        self.influences = []

        self.pta_pos = PTA_LVecBase4f()
        self.pta_param = PTA_LVecBase4f()
        for _ in range(self.MAX_INFLUENCES):
            self.pta_pos.push_back(LVecBase4f(0, 0, 0, 0))
            self.pta_param.push_back(LVecBase4f(0, 0, 0, 0))

        self.render.set_shader_input("inf_pos", self.pta_pos)
        self.render.set_shader_input("inf_param", self.pta_param)
        self.render.set_shader_input("inf_count", 0)
        self.render.set_shader_input("bend_weight", 0.0) # Global offset, overridden by foliage

    def add_influence(self, fx_type, pos, radius, strength, duration):
        infl = WorldInfluence(fx_type, pos, radius, strength, duration)
        self.influences.append(infl)
        if len(self.influences) > self.MAX_INFLUENCES:
            self.influences.pop(0)

    def update(self, dt):
        dt = float(dt)
        for i in range(len(self.influences) - 1, -1, -1):
            infl = self.influences[i]
            infl.timer -= dt
            if infl.timer <= 0:
                self.influences.pop(i)

        count = min(len(self.influences), self.MAX_INFLUENCES)
        for i in range(self.MAX_INFLUENCES):
            if i < count:
                infl = self.influences[i]
                life_pct = max(0.0, infl.timer / max(0.001, infl.max_duration))
                current_strength = infl.strength * math.pow(life_pct, 0.5)

                type_id = 0.0
                if infl.fx_type == "fire": type_id = 1.0
                elif infl.fx_type == "ice": type_id = 2.0
                elif infl.fx_type == "force": type_id = 3.0

                self.pta_pos[i] = LVecBase4f(infl.pos.x, infl.pos.y, infl.pos.z, infl.radius)
                self.pta_param[i] = LVecBase4f(current_strength, type_id, infl.timer, 0.0)
            else:
                self.pta_pos[i] = LVecBase4f(0, 0, 0, 0)
                self.pta_param[i] = LVecBase4f(0, 0, 0, 0)

        self.render.set_shader_input("inf_count", count)
