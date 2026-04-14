#include "PhysicsEngine.h"
#include <algorithm>
#include <cmath>

PhysicsEngine::PhysicsEngine() {}

void PhysicsEngine::addPlatform(const Platform &p) { _platforms.push_back(p); }
void PhysicsEngine::clearPlatforms() { _platforms.clear(); }

void PhysicsEngine::applyImpulse(CharacterState &cs, const Vec3 &impulse)
{
    cs.velocity += impulse;
}

void PhysicsEngine::applyJump(CharacterState &cs, float force)
{
    if (!cs.grounded && !cs.inWater)
        return;
    cs.velocity.z = force;
    cs.grounded = false;
}

void PhysicsEngine::applyWallJump(CharacterState &cs, const Vec3 &wallNormal, float force)
{
    Vec3 jump = wallNormal * (force * 0.7f);
    jump.z = force * 0.9f;
    cs.velocity = jump;
    cs.grounded = false;
    cs.onWall = false;
}

// ─────────────────────────────────────────────────────
void PhysicsEngine::step(CharacterState &cs, float dt)
{
    bool wasInWater = cs.inWater;

    // Water check
    resolveWater(cs);

    // Gravity
    if (!cs.grounded && !cs.inWater)
    {
        cs.velocity.z -= GRAVITY * dt;
        // Terminal velocity
        if (cs.velocity.z < -TERM_VEL)
            cs.velocity.z = -TERM_VEL;
    }

    // Water physics
    if (cs.inWater)
    {
        // Buoyancy when partially submerged
        float buoy = (1.f - cs.waterDepth) * WATER_BUOY;
        cs.velocity.z += (buoy - GRAVITY) * dt;
        // Drag
        cs.velocity.x *= std::pow(WATER_DRAG, dt * 60.f);
        cs.velocity.y *= std::pow(WATER_DRAG, dt * 60.f);
        cs.velocity.z *= std::pow(0.9f, dt * 60.f);
    }

    // Drag in air
    applyDrag(cs, dt);

    // Integrate position
    cs.position += cs.velocity * dt;

    // Ground resolution
    resolveGround(cs);

    // Boundary
    clampToBoundary(cs);

    // Stamina regen
    cs.stamina = std::min(cs.maxStamina, cs.stamina + 18.f * dt);
    cs.mana = std::min(cs.maxMana, cs.mana + 8.f * dt);

    // Combo timeout
    if (cs.comboTimer > 0.f)
    {
        cs.comboTimer -= dt;
        if (cs.comboTimer <= 0.f)
            cs.comboCount = 0;
    }
}

bool PhysicsEngine::resolveGround(CharacterState &cs)
{
    const float CHAR_HALF_H = 1.0f;

    // Check main ground plane
    if (cs.position.z < 0.1f && !cs.inWater)
    {
        cs.position.z = 0.1f;
        if (cs.velocity.z < 0)
            cs.velocity.z = 0.f;
        cs.grounded = true;
        return true;
    }

    // Check platforms
    for (auto &p : _platforms)
    {
        if (p.isWater)
            continue;
        AABB charBox;
        charBox.min = {cs.position.x - 0.4f, cs.position.y - 0.4f, cs.position.z};
        charBox.max = {cs.position.x + 0.4f, cs.position.y + 0.4f, cs.position.z + CHAR_HALF_H * 2};

        if (p.aabb.intersects(charBox) && cs.velocity.z <= 0.f)
        {
            // Only resolve on top surface
            if (cs.position.z >= p.aabb.max.z - 0.2f)
            {
                cs.position.z = p.aabb.max.z;
                cs.velocity.z = 0.f;
                cs.grounded = true;
                return true;
            }
        }
    }

    // If nothing under character
    if (cs.position.z > 0.05f)
        cs.grounded = false;
    return false;
}

bool PhysicsEngine::resolveWater(CharacterState &cs)
{
    const float WATER_SURFACE = 0.f;
    const float SWIM_DEPTH = 1.5f;

    // Very simple: water is at z <= 0 in "water zones"
    // Python marks water zones via addPlatform with isWater=true
    bool inWaterZone = false;
    for (auto &p : _platforms)
    {
        if (!p.isWater)
            continue;
        if (cs.position.x >= p.aabb.min.x && cs.position.x <= p.aabb.max.x &&
            cs.position.y >= p.aabb.min.y && cs.position.y <= p.aabb.max.y &&
            cs.position.z <= p.aabb.max.z + 0.2f)
        {
            inWaterZone = true;
            float surface = p.aabb.max.z;
            float depth = surface - cs.position.z;
            cs.waterDepth = std::clamp(depth / SWIM_DEPTH, 0.f, 1.f);
            cs.inWater = cs.position.z < surface;
            if (cs.inWater)
                cs.grounded = false;
            return cs.inWater;
        }
    }
    cs.inWater = false;
    cs.waterDepth = 0.f;
    return false;
}

void PhysicsEngine::applyDrag(CharacterState &cs, float dt)
{
    float drag = cs.grounded ? 0.f : 0.02f;
    float xz = 1.f - drag;
    cs.velocity.x *= xz;
    cs.velocity.y *= xz;
}

void PhysicsEngine::clampToBoundary(CharacterState &cs)
{
    const float BOUND = 48.f;
    cs.position.x = std::clamp(cs.position.x, -BOUND, BOUND);
    cs.position.y = std::clamp(cs.position.y, -BOUND, BOUND);
    cs.position.z = std::max(cs.position.z, -5.f); // ocean floor
}

bool PhysicsEngine::isInWater(const Vec3 &pos) const
{
    for (auto &p : _platforms)
    {
        if (!p.isWater)
            continue;
        if (pos.x >= p.aabb.min.x && pos.x <= p.aabb.max.x &&
            pos.y >= p.aabb.min.y && pos.y <= p.aabb.max.y &&
            pos.z <= p.aabb.max.z)
            return true;
    }
    return false;
}

bool PhysicsEngine::raycast(const Vec3 &origin, const Vec3 &dir,
                            float maxDist, Vec3 &hitPos, Vec3 &hitNorm) const
{
    const int STEPS = 60;
    float step = maxDist / STEPS;
    Vec3 p = origin;
    Vec3 d = dir.normalized();

    for (int i = 0; i < STEPS; i++)
    {
        p += d * step;

        // Ground plane
        if (p.z <= 0.f)
        {
            hitPos = {p.x, p.y, 0.f};
            hitNorm = {0, 0, 1};
            return true;
        }

        // Platforms
        for (auto &pl : _platforms)
        {
            if (pl.isWater)
                continue;
            if (pl.aabb.containsPoint(p))
            {
                hitPos = p;
                hitNorm = pl.normal;
                return true;
            }
        }
    }
    return false;
}

int PhysicsEngine::addRigidBody(const RigidBody &rb)
{
    _rigidBodies.push_back(rb);
    _rbAlive.push_back(true);
    return int(_rigidBodies.size()) - 1;
}

void PhysicsEngine::stepRigidBodies(float dt)
{
    for (size_t i = 0; i < _rigidBodies.size(); i++)
    {
        if (!_rbAlive[i])
            continue;
        auto &rb = _rigidBodies[i];
        if (rb.isStatic)
            continue;
        rb.vel.z -= GRAVITY * dt;
        rb.pos += rb.vel * dt;
        if (rb.pos.z <= 0.f)
        {
            rb.pos.z = 0.f;
            rb.vel.z *= -rb.restitution;
            rb.vel.x *= 0.8f;
            rb.vel.y *= 0.8f;
        }
    }
}

Vec3 PhysicsEngine::getRigidBodyPos(int id) const
{
    if (id >= 0 && id < (int)_rigidBodies.size() && _rbAlive[id])
        return _rigidBodies[id].pos;
    return {};
}

void PhysicsEngine::removeRigidBody(int id)
{
    if (id >= 0 && id < (int)_rbAlive.size())
        _rbAlive[id] = false;
}
