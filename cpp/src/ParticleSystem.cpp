#include "ParticleSystem.h"
#include <cmath>
#include <algorithm>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

ParticleSystem::ParticleSystem() : _rng(std::random_device{}()) {}

float ParticleSystem::randF(float lo, float hi) {
    std::uniform_real_distribution<float> d(lo, hi);
    return d(_rng);
}

Vec3 ParticleSystem::lerp3(const Vec3& a, const Vec3& b, float t) {
    return { a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t, a.z+(b.z-a.z)*t };
}

Vec3 ParticleSystem::randomInCone(const Vec3& dir, float spreadDeg) {
    float angle  = spreadDeg * (float(M_PI) / 180.f) * randF(0.f, 1.f);
    float azimuth= randF(0.f, float(M_PI) * 2.f);
    Vec3 perp;
    if (std::fabs(dir.x) < 0.9f) perp = dir.cross({1,0,0}).normalized();
    else                          perp = dir.cross({0,1,0}).normalized();
    Vec3 perp2 = dir.cross(perp).normalized();
    return (dir.normalized() + perp*(std::sin(angle)*std::cos(azimuth))
                             + perp2*(std::sin(angle)*std::sin(azimuth))).normalized();
}

int ParticleSystem::spawnEmitter(const ParticleEmitter& spec) {
    ParticleEmitter e = spec;
    e.id = _nextId++;
    e.alive = true;
    _emitters.push_back(e);
    return e.id;
}

void ParticleSystem::killEmitter(int id) {
    for (auto& e : _emitters) if (e.id == id) e.alive = false;
}

void ParticleSystem::setEmitterPos(int id, const Vec3& pos) {
    for (auto& e : _emitters) if (e.id == id) e.pos = pos;
}

void ParticleSystem::burst(const Vec3& pos, const Vec3& dir,
                            const std::string& tag, int count) {
    ParticleEmitter e;
    e.tag = tag; e.pos = pos; e.dir = dir;
    e.rate = 0; e.duration = 0.01f;
    int id = spawnEmitter(e);
    // Emit count immediately
    auto& em = _emitters.back();
    for (int i = 0; i < count; i++) {
        Particle p;
        p.pos  = pos;
        p.vel  = randomInCone(dir, em.spread) * randF(em.speed * 0.5f, em.speed * 1.5f);
        p.color= lerp3(em.colorA, em.colorB, randF(0.f,1.f));
        p.alpha= 1.f;
        p.size = em.size + randF(-em.sizeVar, em.sizeVar);
        p.lifetime = em.lifetime + randF(-em.lifetimeVar, em.lifetimeVar);
        p.affectedByGravity = em.useGravity;
        _particles.push_back(p);
    }
}

void ParticleSystem::update(float dt) {
    // Emitters → spawn
    for (auto& e : _emitters) {
        if (!e.alive) continue;
        if (e.duration >= 0.f) {
            e.elapsed += dt;
            if (e.elapsed > e.duration) { e.alive = false; continue; }
        }
        if (e.rate <= 0) continue;
        e.emitAccum += e.rate * dt;
        while (e.emitAccum >= 1.f) {
            e.emitAccum -= 1.f;
            Particle p;
            p.pos   = e.pos;
            p.vel   = randomInCone(e.dir, e.spread)
                    * randF(e.speed - e.speedVar, e.speed + e.speedVar);
            p.color = lerp3(e.colorA, e.colorB, randF(0.f, 1.f));
            p.alpha = 1.f;
            p.size  = e.size + randF(-e.sizeVar, e.sizeVar);
            p.lifetime = e.lifetime + randF(-e.lifetimeVar, e.lifetimeVar);
            p.affectedByGravity = e.useGravity;
            _particles.push_back(p);
        }
    }

    // Particle tick
    for (auto& p : _particles) {
        if (!p.alive) continue;
        p.elapsed += dt;
        if (p.elapsed >= p.lifetime) { p.alive = false; continue; }
        if (p.affectedByGravity) p.vel.z -= 9.8f * dt;
        p.pos += p.vel * dt;
        float life = 1.f - p.elapsed / p.lifetime;
        p.alpha = life;
        p.size *= (1.f + dt * 0.5f);  // expand slowly
    }

    // Cleanup
    _particles.erase(std::remove_if(_particles.begin(), _particles.end(),
        [](const Particle& p){ return !p.alive; }), _particles.end());
    _emitters.erase(std::remove_if(_emitters.begin(), _emitters.end(),
        [](const ParticleEmitter& e){ return !e.alive; }), _emitters.end());
}

std::vector<ParticleVertex> ParticleSystem::buildVertexBuffer() const {
    std::vector<ParticleVertex> buf;
    buf.reserve(_particles.size());
    for (auto& p : _particles) {
        if (!p.alive) continue;
        buf.push_back({p.pos.x, p.pos.y, p.pos.z,
                       p.color.x, p.color.y, p.color.z, p.alpha, p.size});
    }
    return buf;
}

int ParticleSystem::aliveCount() const { return int(_particles.size()); }

// ─── Presets ─────────────────────────────────────────────

int ParticleSystem::spawnBloodSplat(const Vec3& pos, const Vec3& normal) {
    ParticleEmitter e;
    e.pos = pos; e.dir = normal; e.tag = "blood";
    e.colorA = {0.8f,0.0f,0.0f}; e.colorB = {0.5f,0.0f,0.0f};
    e.speed = 4.f; e.speedVar = 2.f; e.spread = 60.f;
    e.size = 0.06f; e.lifetime = 0.6f; e.duration = 0.05f;
    e.rate = 0; e.useGravity = true;
    return spawnEmitter(e);
}

int ParticleSystem::spawnFireball(const Vec3& pos) {
    ParticleEmitter e;
    e.pos = pos; e.dir = {0,0,1}; e.tag = "fire";
    e.colorA = {1.f,0.5f,0.1f}; e.colorB = {1.f,0.15f,0.f};
    e.speed = 1.5f; e.spread = 90.f; e.size = 0.15f;
    e.lifetime = 0.5f; e.duration = -1.f; e.rate = 50;
    return spawnEmitter(e);
}

int ParticleSystem::spawnLightningArc(const Vec3& from, const Vec3& to) {
    ParticleEmitter e;
    e.pos = from;
    Vec3 d = {to.x-from.x, to.y-from.y, to.z-from.z};
    e.dir = d; e.tag = "lightning";
    e.colorA = {0.6f,0.8f,1.f}; e.colorB = {1.f,1.f,1.f};
    e.speed = d.len() * 2.f; e.spread = 15.f;
    e.size = 0.04f; e.lifetime = 0.2f;
    e.duration = 0.15f; e.rate = 200;
    return spawnEmitter(e);
}

int ParticleSystem::spawnIceShard(const Vec3& pos, const Vec3& dir) {
    ParticleEmitter e;
    e.pos = pos; e.dir = dir; e.tag = "ice";
    e.colorA = {0.6f,0.9f,1.f}; e.colorB = {0.9f,1.f,1.f};
    e.speed = 3.f; e.spread = 20.f; e.size = 0.08f;
    e.lifetime = 0.4f; e.duration = 0.1f; e.rate = 80;
    return spawnEmitter(e);
}

int ParticleSystem::spawnHealAura(const Vec3& pos) {
    ParticleEmitter e;
    e.pos = pos; e.dir = {0,0,1}; e.tag = "heal";
    e.colorA = {0.2f,1.f,0.4f}; e.colorB = {0.1f,0.8f,0.8f};
    e.speed = 1.f; e.spread = 180.f; e.size = 0.1f;
    e.lifetime = 1.2f; e.duration = 0.8f; e.rate = 40;
    return spawnEmitter(e);
}

int ParticleSystem::spawnSwordTrail(const Vec3& pos, const Vec3& dir) {
    ParticleEmitter e;
    e.pos = pos; e.dir = dir; e.tag = "sword_trail";
    e.colorA = {1.f,0.3f,1.f}; e.colorB = {0.8f,0.1f,0.9f};
    e.speed = 0.5f; e.spread = 10.f; e.size = 0.07f;
    e.lifetime = 0.25f; e.duration = -1.f; e.rate = 60;
    return spawnEmitter(e);
}

int ParticleSystem::spawnWaterSplash(const Vec3& pos) {
    ParticleEmitter e;
    e.pos = pos; e.dir = {0,0,1}; e.tag = "water";
    e.colorA = {0.5f,0.7f,1.f}; e.colorB = {0.8f,0.9f,1.f};
    e.speed = 5.f; e.speedVar = 2.f; e.spread = 70.f;
    e.size = 0.12f; e.lifetime = 0.8f;
    e.duration = 0.05f; e.rate = 0; e.useGravity = true;
    int id = spawnEmitter(e);
    burst(pos, {0,0,1}, "water", 30);
    return id;
}

int ParticleSystem::spawnMagicOrb(const Vec3& pos, const Vec3& color) {
    ParticleEmitter e;
    e.pos = pos; e.dir = {0,0,1}; e.tag = "orb";
    e.colorA = color; e.colorB = {1.f,1.f,1.f};
    e.speed = 0.8f; e.spread = 360.f; e.size = 0.1f;
    e.lifetime = 0.6f; e.duration = -1.f; e.rate = 30;
    return spawnEmitter(e);
}

int ParticleSystem::spawnDust(const Vec3& pos) {
    ParticleEmitter e;
    e.pos = pos; e.dir = {0,0,1}; e.tag = "dust";
    e.colorA = {0.8f,0.7f,0.5f}; e.colorB = {0.6f,0.5f,0.4f};
    e.speed = 1.5f; e.spread = 80.f; e.size = 0.15f;
    e.lifetime = 0.7f; e.duration = 0.1f; e.rate = 0;
    burst(pos, {0,0,1}, "dust", 15);
    return spawnEmitter(e);
}

int ParticleSystem::spawnMeteorTail(const Vec3& pos) {
    ParticleEmitter e;
    e.pos = pos; e.dir = {0,0,1}; e.tag = "meteor";
    e.colorA = {1.f,0.6f,0.1f}; e.colorB = {1.f,0.2f,0.f};
    e.speed = 2.f; e.spread = 25.f; e.size = 0.2f;
    e.lifetime = 0.4f; e.duration = -1.f; e.rate = 80;
    return spawnEmitter(e);
}
