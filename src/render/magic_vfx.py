"""Advanced Magic VFX system using Panda3D ParticleEffects."""

import math

from panda3d.core import (
    CardMaker,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    TransparencyAttrib,
    Vec3,
    Vec4,
)
from direct.particles.ParticleEffect import ParticleEffect
from direct.particles.ForceGroup import ForceGroup
from utils.logger import logger
from render.fx_policy import make_soft_disc_texture

class MagicVFXSystem:
    def __init__(self, app):
        self.app = app
        self.render = app.render
        self.active_effects = []
        
    def spawn_nova_vfx(self, pos, color=Vec4(0.4, 0.6, 1.0, 1.0)):
        """Spawns an expanding arcane nova effect using procedural particles."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/nova.ptf")
        except:
            # Procedural Sparkle Burst
            from panda3d.physics import LinearVectorForce
            from direct.particles.Particles import Particles
            from direct.particles.ParticleEmitterStack import ParticleEmitterStack
            
            ps = Particles()
            ps.setFactory("PointParticleFactory")
            ps.setRenderer("LineParticleRenderer")
            ps.setEmitter("SphereVolumeEmitter")
            
            ps.factory.setLifespanBase(0.4)
            ps.factory.setLifespanVariation(0.1)
            
            ps.renderer.setHeadColor(color)
            ps.renderer.setTailColor(Vec4(color[0]*0.5, color[1]*0.5, color[2]*0.5, 0))
            ps.renderer.setLineScaleFactor(2.0)
            
            ps.emitter.setRadius(0.5)
            ps.emitter.setAmplitude(12.0)
            ps.emitter.setAmplitudeSpread(4.0)
            
            p.addParticles(ps)
            
        p.setPos(pos)
        p.reparentTo(self.render)
        p.start(self.render)
        self.active_effects.append(p)
        self.app.taskMgr.doMethodLater(
            0.8,
            self._build_cleanup_task_callback(p.cleanup, None),
            "cleanup-nova",
        )
        
    def spawn_meteor_vfx(self, pos):
        """Spawns a fiery impact effect."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/meteor_impact.ptf")
        except:
            logger.debug("meteor_impact.ptf not found")
            pass
            
        p.setPos(pos)
        p.reparentTo(self.render)
        p.start(self.render)
        self.active_effects.append(p)
        self.app.taskMgr.doMethodLater(
            2.5,
            self._build_cleanup_task_callback(p.cleanup, None),
            "cleanup-meteor",
        )

    def spawn_ward_vfx(self, pos):
        """Spawns a protective golden aura with procedural starburst."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/ward.ptf")
        except:
            from direct.particles.Particles import Particles
            ps = Particles()
            ps.setFactory("PointParticleFactory")
            ps.setRenderer("SparkleParticleRenderer")
            ps.setEmitter("DiscEmitter")
            
            ps.factory.setLifespanBase(1.2)
            ps.renderer.setCenterColor(Vec4(1.0, 0.9, 0.4, 1.0))
            ps.renderer.setEdgeColor(Vec4(1.0, 0.8, 0.2, 0))
            ps.renderer.setBirthScale(0.08)
            ps.renderer.setDeathScale(0.02)
            
            ps.emitter.setRadius(2.5)
            ps.emitter.setAmplitude(1.5)
            p.addParticles(ps)
            
        p.setPos(pos)
        p.reparentTo(self.render)
        p.start(self.render)
        self.active_effects.append(p)
        self.app.taskMgr.doMethodLater(
            2.0,
            self._build_cleanup_task_callback(p.cleanup, None),
            "cleanup-ward",
        )

    def spawn_spell_telegraph_vfx(self, pos, radius=4.0, color=None, duration=0.85):
        """Spawn a high-fidelity layered arcane telegraph with particle sparkles."""
        tint = color if isinstance(color, (list, tuple)) and len(color) >= 3 else (0.42, 0.72, 1.0, 0.32)
        alpha = float(tint[3] if len(tint) > 3 else 0.32)
        
        root = self.render.attachNewNode("telegraph_root")
        root.setPos(pos)
        root.setTransparency(TransparencyAttrib.MAlpha)
        root.setDepthWrite(False)
        root.setBin("transparent", 30)

        # Layer 1: Soft Base Disc
        cm_base = CardMaker("telegraph_base")
        cm_base.setFrame(-1.0, 1.0, -1.0, 1.0)
        base = root.attachNewNode(cm_base.generate())
        base.setP(-90)
        base.setScale(max(0.35, float(radius)))
        base.setColorScale(float(tint[0]), float(tint[1]), float(tint[2]), alpha * 0.6)
        
        # Layer 2: Arcane Ring (Rotating)
        cm_ring = CardMaker("telegraph_ring")
        cm_ring.setFrame(-1.0, 1.0, -1.0, 1.0)
        ring = root.attachNewNode(cm_ring.generate())
        ring.setP(-90)
        ring.setScale(max(0.35, float(radius)) * 1.1)
        ring.setColorScale(float(tint[0]) * 1.2, float(tint[1]) * 1.2, float(tint[2]) * 1.2, alpha)

        try:
            tex_base = make_soft_disc_texture("telegraph_base", size=192, warm=float(tint[0]) > float(tint[2]))
            if tex_base:
                base.setTexture(tex_base, 1)
            tex_ring = make_soft_disc_texture("telegraph_ring", size=128, warm=float(tint[0]) > float(tint[2]))
            if tex_ring:
                ring.setTexture(tex_ring, 1)
        except Exception:
            pass

        # Layer 3: Procedural Sparkle Particles
        p = ParticleEffect()
        from direct.particles.Particles import Particles
        ps = Particles()
        ps.setFactory("PointParticleFactory")
        ps.setRenderer("SparkleParticleRenderer")
        ps.setEmitter("BoxEmitter")
        
        ps.factory.setLifespanBase(0.8)
        ps.renderer.setCenterColor(Vec4(float(tint[0]), float(tint[1]), float(tint[2]), 1.0))
        ps.renderer.setEdgeColor(Vec4(float(tint[0])*0.5, float(tint[1])*0.5, float(tint[2])*0.5, 0))
        ps.renderer.setBirthScale(0.05)
        ps.renderer.setDeathScale(0.01)
        
        # Emitter covers the radius
        sz = max(0.35, float(radius))
        ps.emitter.setMinBound(Vec3(-sz, -sz, 0))
        ps.emitter.setMaxBound(Vec3(sz, sz, 0.5))
        ps.emitter.setAmplitude(1.0)
        p.addParticles(ps)
        
        p.reparentTo(root)
        p.start(root)

        # Animation: Rotation & Pulsing
        def _animate_telegraph(task):
            dt = self.app.clock.getDt()
            if root.isEmpty():
                done = getattr(task, "done", None)
                return done() if callable(done) else done
            ring.setH(ring.getH() + 180.0 * dt)
            s = 1.0 + math.sin(task.time * 6.0) * 0.05
            root.setScale(s)
            return task.cont

        self.app.taskMgr.add(_animate_telegraph, f"anim-telegraph-{id(root)}")
        self.active_effects.append(root)
        ttl = max(0.2, min(4.5, float(duration or 0.85)))
        self.app.taskMgr.doMethodLater(
            ttl,
            self._build_cleanup_task_callback(p.cleanup, root),
            f"cleanup-telegraph-{id(root)}",
        )
        return root

    def spawn_spell_phase_vfx(self, pos, phase="", color=None, radius=1.0, duration=0.12):
        """Spawn a phase marker with a particle pop (prepare/release/impact)."""
        token = str(phase or "").strip().lower()
        tint = color if isinstance(color, (list, tuple)) and len(color) >= 3 else (0.72, 0.86, 1.0, 0.42)
        alpha = float(tint[3] if len(tint) > 3 else 0.42)
        
        node = self.render.attachNewNode(f"spell_phase_{token}")
        node.setPos(pos)
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setBin("transparent", 31)

        # Particle Burst
        p = ParticleEffect()
        from direct.particles.Particles import Particles
        ps = Particles()
        ps.setFactory("PointParticleFactory")
        ps.setRenderer("LineParticleRenderer")
        ps.setEmitter("SphereVolumeEmitter")
        
        ps.factory.setLifespanBase(0.2)
        ps.renderer.setHeadColor(Vec4(float(tint[0]), float(tint[1]), float(tint[2]), alpha))
        ps.renderer.setTailColor(Vec4(float(tint[0])*0.5, float(tint[1])*0.5, float(tint[2])*0.5, 0))
        ps.renderer.setLineScaleFactor(1.5)
        
        ps.emitter.setRadius(0.2)
        ps.emitter.setAmplitude(6.0)
        p.addParticles(ps)
        
        p.reparentTo(node)
        p.start(node)

        self.active_effects.append(node)
        ttl = max(0.08, min(1.2, float(duration or 0.12)))
        self.app.taskMgr.doMethodLater(
            ttl,
            self._build_cleanup_task_callback(p.cleanup, node),
            f"cleanup-spell-phase-{token}-{id(node)}",
        )
        return node

    def spawn_portal_vfx(self, pos, color=Vec4(0.2, 0.4, 1.0, 0.8)):
        """Spawns an ethereal portal rift effect."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/portal_rift.ptf")
        except:
            logger.debug("portal_rift.ptf not found")
            pass
            
        p.setPos(pos)
        p.reparentTo(self.render)
        p.start(self.render)
        self.active_effects.append(p)
        # Portals are usually persistent, but here we just spawn the burst/loop
        return p

    def spawn_shadow_aura_vfx(self, parent_node):
        """Spawns a persistent shadowy aura attached to a node."""
        p = ParticleEffect()
        try:
            # We'll try to load a shadowy config, fallback to default if missing
            p.loadConfig("assets/particles/shadow_aura.ptf")
        except:
            logger.debug("shadow_aura.ptf not found")
            # In a real environment we'd create it procedurally if needed
            pass
            
        p.reparentTo(parent_node)
        p.start(parent_node)
        self.active_effects.append(p)
        return p

    def spawn_parkour_wind_vfx(self, parent_node):
        """Spawns ethereal wind streaks for high-speed parkour."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/wind_streaks.ptf")
        except:
            logger.debug("wind_streaks.ptf not found")
            pass
        p.reparentTo(parent_node)
        p.start(parent_node)
        self.active_effects.append(p)
        return p

    def spawn_flight_vfx(self, parent_node):
        """Spawns ethereal flight trails (wind/magic) attached to the player."""
        p = ParticleEffect()
        try:
            # Try to load a specialized flight config
            p.loadConfig("assets/particles/flight_trail.ptf")
        except:
            # Procedural fallback: Ethereal streaks
            from direct.particles.Particles import Particles
            ps = Particles()
            ps.setFactory("PointParticleFactory")
            ps.setRenderer("LineParticleRenderer")
            ps.setEmitter("BoxEmitter")
            
            ps.factory.setLifespanBase(0.4)
            ps.renderer.setHeadColor(Vec4(0.4, 0.8, 1.0, 0.5))
            ps.renderer.setTailColor(Vec4(0.2, 0.4, 0.8, 0))
            ps.renderer.setLineScaleFactor(2.0)
            
            ps.emitter.setMinBound(Vec3(-0.5, -0.5, 0))
            ps.emitter.setMaxBound(Vec3(0.5, 0.5, 1.0))
            ps.emitter.setAmplitude(2.0)
            
            p.addParticles(ps)
            
        p.reparentTo(parent_node)
        p.start(parent_node)
        self.active_effects.append(p)
        return p

    def spawn_landing_dust_vfx(self, pos):
        """Spawns a subtle dust puff on landing."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/landing_dust.ptf")
        except:
            pass
        p.setPos(pos)
        p.reparentTo(self.render)
        p.start(self.render)
        self.active_effects.append(p)
        self.app.taskMgr.doMethodLater(1.0, p.cleanup, f"cleanup-dust-{id(p)}")
        return p

    def spawn_rain_vfx(self, parent_node, heavy=False):
        """Spawns falling rain particles around the player."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/rain_fall.ptf")
        except:
            from direct.particles.Particles import Particles
            ps = Particles()
            ps.setFactory("PointParticleFactory")
            ps.setRenderer("LineParticleRenderer")
            ps.setEmitter("BoxEmitter")
            
            ps.factory.setLifespanBase(1.5)
            ps.renderer.setHeadColor(Vec4(0.7, 0.8, 1.0, 0.4))
            ps.renderer.setTailColor(Vec4(0.4, 0.6, 1.0, 0))
            ps.renderer.setLineScaleFactor(4.0 if heavy else 2.5)
            
            ps.emitter.setMinBound(Vec3(-20, -20, 0))
            ps.emitter.setMaxBound(Vec3(20, 20, 15))
            ps.emitter.setAmplitude(18.0 if heavy else 12.0)
            
            p.addParticles(ps)
            
        p.reparentTo(parent_node)
        p.start(parent_node)
        self.active_effects.append(p)
        return p

    def spawn_snow_vfx(self, parent_node):
        """Spawns falling snowflake particles (slow drifting soft discs)."""
        p = ParticleEffect()
        try:
            p.loadConfig("assets/particles/snow_fall.ptf")
        except:
            from direct.particles.Particles import Particles
            ps = Particles()
            ps.setFactory("PointParticleFactory")
            ps.setRenderer("SparkleParticleRenderer")
            ps.setEmitter("BoxEmitter")
            
            ps.factory.setLifespanBase(4.0)
            ps.renderer.setCenterColor(Vec4(1, 1, 1, 0.8))
            ps.renderer.setEdgeColor(Vec4(0.8, 0.9, 1.0, 0))
            ps.renderer.setBirthScale(0.12)
            ps.renderer.setDeathScale(0.04)
            
            ps.emitter.setMinBound(Vec3(-22, -22, 0))
            ps.emitter.setMaxBound(Vec3(22, 22, 20))
            ps.emitter.setAmplitude(1.2)
            ps.emitter.setAmplitudeSpread(0.8)
            
            p.addParticles(ps)
            
        p.reparentTo(parent_node)
        p.start(parent_node)
        self.active_effects.append(p)
        return p

    def spawn_sword_trail(self, color=Vec4(0.8, 0.9, 1.0, 0.5), length=8):
        """Spawns a procedural sword trail root."""
        root = self.render.attachNewNode("sword_trail_root")
        root.setTransparency(TransparencyAttrib.MAlpha)
        root.setDepthWrite(False)
        root.setBin("transparent", 40)
        
        # We'll use a local list of segments to update
        trail_data = {
            "root": root,
            "segments": [],
            "max_segments": length,
            "color": color,
            "last_pos": None,
            "last_pos_base": None,
        }
        self.active_effects.append(root)
        return trail_data

    def update_sword_trail(self, trail_data, tip_pos, base_pos, dt):
        """Updates the procedural sword trail with new segments."""
        if not trail_data or trail_data["root"].isEmpty():
            return

        trail_data.setdefault("last_pos_base", None)
        root = trail_data["root"]
        color = trail_data["color"]
        
        # Only add segment if moved significantly
        if trail_data["last_pos"] and (tip_pos - trail_data["last_pos"]).length() < 0.05:
            # Still update existing segments' alpha
            pass
        else:
            # Create a triangle strip for the trail segment
            cm = CardMaker("trail_seg")
            # We'll build a custom mesh for better look, but CardMaker is easier for now
            # Actually, let's just use a simple oriented quad between prev and current
            if trail_data.get("last_pos_base") is not None:
                # Build a quad using 4 points: prev_base, prev_tip, curr_tip, curr_base
                vdata = GeomVertexData("trail", GeomVertexFormat.getV3cp(), Geom.UHDynamic)
                vertex = GeomVertexWriter(vdata, "vertex")
                color_writer = GeomVertexWriter(vdata, "color")
                
                p1 = trail_data["last_pos_base"]
                p2 = trail_data["last_pos"]
                p3 = tip_pos
                p4 = base_pos
                
                vertex.addData3(p1)
                vertex.addData3(p2)
                vertex.addData3(p3)
                vertex.addData3(p4)
                
                for _ in range(4):
                    color_writer.addData4(color)
                    
                tris = GeomTriangles(Geom.UHDynamic)
                tris.addVertices(0, 1, 2)
                tris.addVertices(0, 2, 3)
                
                geom = Geom(vdata)
                geom.addPrimitive(tris)
                
                node = GeomNode("trail_segment")
                node.addGeom(geom)
                
                seg_np = root.attachNewNode(node)
                trail_data["segments"].insert(0, seg_np)
                
            trail_data["last_pos"] = Vec3(tip_pos)
            trail_data["last_pos_base"] = Vec3(base_pos)

        # Decay segments
        to_remove = []
        for i, seg in enumerate(trail_data["segments"]):
            alpha = 1.0 - (i / trail_data["max_segments"])
            if alpha <= 0:
                to_remove.append(seg)
            else:
                seg.setColorScale(1, 1, 1, alpha)
                
        for seg in to_remove:
            seg.removeNode()
            trail_data["segments"].remove(seg)
            
        if len(trail_data["segments"]) > trail_data["max_segments"]:
            old = trail_data["segments"].pop()
            old.removeNode()

    def spawn_hand_burst_vfx(self, hand_node, color=Vec4(0.4, 0.7, 1.0, 0.8)):
        """Spawns a quick energy burst at the casting hand."""
        if not hand_node:
            return
            
        root = hand_node.attachNewNode("hand_burst")
        root.setTransparency(TransparencyAttrib.MAlpha)
        root.setLightOff(1)
        root.setShaderOff(1)
        
        # Create a simple glowing sphere or burst
        for i in range(3):
            cm = CardMaker(f"burst_{i}")
            cm.setFrame(-0.2, 0.2, -0.2, 0.2)
            card = root.attachNewNode(cm.generate())
            card.setBillboardPointEye()
            card.setPos(0, 0, 0)
            card.setColor(color)
            card.setBin("transparent", 50)
            
            # Animating scale and alpha
            t = 0.2 + (i * 0.1)
            card.setScale(0.1)
            card.scaleInterval(t, 2.5 + i, startScale=0.1).start()
            card.colorInterval(t, Vec4(color.x, color.y, color.z, 0), startColor=color).start()
            
        # Cleanup
        self.app.taskMgr.doMethodLater(
            0.5,
            self._build_cleanup_task_callback(None, root),
            f"cleanup-hand-burst-{id(root)}",
        )

    def update(self, dt):
        # Cleanup inactive effects if needed
        self.active_effects = [e for e in self.active_effects if not e.isEmpty()]

    def _cleanup_node(self, node, task=None):
        try:
            if node and not node.isEmpty():
                node.removeNode()
        except Exception:
            pass
        if task is None:
            return None
        done = getattr(task, "done", None)
        return done() if callable(done) else done

    def _build_cleanup_task_callback(self, cleanup_fn, node):
        def _callback(task):
            try:
                if callable(cleanup_fn):
                    cleanup_fn()
            except Exception:
                pass
            return self._cleanup_node(node, task)

        return _callback
