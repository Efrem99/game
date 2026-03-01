#pragma once
#include "PhysicsEngine.h"
#include <vector>
#include <string>
#include <random>

struct Particle {
    Vec3  pos;
    Vec3  vel;
    Vec3  color;      // RGB
    float alpha;
    float size;
    float lifetime;
    float elapsed  = 0.f;
    bool  alive    = true;
    bool  affectedByGravity = false;
};

struct ParticleEmitter {
    int         id;
    std::string tag;
    Vec3        pos;
    Vec3        dir;
    Vec3        colorA {1,1,1};
    Vec3        colorB {1,0.3f,0};
    float       spread      = 30.f;   // degrees cone
    float       speed       = 3.f;
    float       speedVar    = 1.f;
    float       size        = 0.1f;
    float       sizeVar     = 0.05f;
    float       lifetime    = 0.8f;
    float       lifetimeVar = 0.3f;
    int         rate        = 30;     // particles / second
    float       duration    = -1.f;   // -1 = forever
    float       elapsed     = 0.f;
    float       emitAccum   = 0.f;
    bool        alive       = true;
    bool        useGravity  = false;
};

// Flat struct for GPU upload (Python -> Panda3D GeomNode)
struct ParticleVertex {
    float x, y, z;
    float r, g, b, a;
    float size;
};

class ParticleSystem {
public:
    ParticleSystem();

    // Emitter management
    int  spawnEmitter(const ParticleEmitter& spec);
    void killEmitter(int id);
    void setEmitterPos(int id, const Vec3& pos);
    void burst(const Vec3& pos, const Vec3& dir, const std::string& tag, int count = 40);

    // Simulate
    void update(float dt);

    // Get flat GPU-ready buffer; Python uploads to a point-cloud GeomNode
    std::vector<ParticleVertex> buildVertexBuffer() const;
    int aliveCount() const;

    // Pre-defined effect presets
    int spawnBloodSplat    (const Vec3& pos, const Vec3& normal);
    int spawnFireball      (const Vec3& pos);
    int spawnLightningArc  (const Vec3& from, const Vec3& to);
    int spawnIceShard      (const Vec3& pos, const Vec3& dir);
    int spawnHealAura      (const Vec3& pos);
    int spawnSwordTrail    (const Vec3& pos, const Vec3& dir);
    int spawnWaterSplash   (const Vec3& pos);
    int spawnMagicOrb      (const Vec3& pos, const Vec3& color);
    int spawnDust          (const Vec3& pos);
    int spawnMeteorTail    (const Vec3& pos);

private:
    std::vector<Particle>       _particles;
    std::vector<ParticleEmitter>_emitters;
    int _nextId = 0;
    std::mt19937 _rng;

    Vec3  randomInCone(const Vec3& dir, float spreadDeg);
    float randF(float lo, float hi);
    Vec3  lerp3(const Vec3& a, const Vec3& b, float t);
};
