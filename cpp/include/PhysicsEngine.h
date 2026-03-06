#pragma once
#include <array>
#include <vector>
#include <cmath>
#include <algorithm>

// ───────────────────────────────────────────────
// Simple 3-vector (avoids pulling in Panda headers here)
// ───────────────────────────────────────────────
struct Vec3 {
    float x = 0, y = 0, z = 0;
    Vec3() = default;
    Vec3(float x, float y, float z) : x(x), y(y), z(z) {}
    Vec3 operator+(const Vec3& o) const { return {x+o.x, y+o.y, z+o.z}; }
    Vec3 operator-(const Vec3& o) const { return {x-o.x, y-o.y, z-o.z}; }
    Vec3 operator*(float s) const { return {x*s, y*s, z*s}; }
    Vec3& operator+=(const Vec3& o) { x+=o.x; y+=o.y; z+=o.z; return *this; }
    float dot(const Vec3& o) const { return x*o.x + y*o.y + z*o.z; }
    float lenSq() const { return dot(*this); }
    float len()   const { return std::sqrt(lenSq()); }
    Vec3  normalized() const { float l = len(); return l > 1e-6f ? (*this)*(1.f/l) : Vec3{}; }
    Vec3  cross(const Vec3& o) const {
        return { y*o.z - z*o.y, z*o.x - x*o.z, x*o.y - y*o.x };
    }
};

// ───────────────────────────────────────────────
// Axis-aligned bounding box
// ───────────────────────────────────────────────
struct AABB {
    Vec3 min, max;
    bool intersects(const AABB& o) const {
        return min.x <= o.max.x && max.x >= o.min.x &&
               min.y <= o.max.y && max.y >= o.min.y &&
               min.z <= o.max.z && max.z >= o.min.z;
    }
    bool containsPoint(const Vec3& p) const {
        return p.x >= min.x && p.x <= max.x &&
               p.y >= min.y && p.y <= max.y &&
               p.z >= min.z && p.z <= max.z;
    }
};

// ───────────────────────────────────────────────
// Character state  (shared between C++ systems)
// ───────────────────────────────────────────────
struct CharacterState {
    Vec3  position    {0, 0, 0};
    Vec3  velocity    {0, 0, 0};
    Vec3  facingDir   {0, 1, 0};
    float health      = 100.f;
    float maxHealth   = 100.f;
    float stamina     = 100.f;
    float maxStamina  = 100.f;
    float mana        = 100.f;
    float maxMana     = 100.f;
    bool  grounded    = true;
    bool  inWater     = false;
    bool  onWall      = false;
    float waterDepth  = 0.f;    // 0 = out, 1 = fully submerged
    float yaw         = 0.f;    // degrees
    int   comboCount  = 0;
    float comboTimer  = 0.f;
};

// ───────────────────────────────────────────────
// Status Effects and Damage Types
// ───────────────────────────────────────────────
enum class StatusType { Burn, Freeze, Shock, Slow, Weaken, Stun };

struct StatusInstance {
    StatusType type;
    float remaining = 0.f;
    float tickRate  = 1.f;
    float tickTimer = 0.f;
    float magnitude = 0.f;
    int sourceCasterId = 0;
};

enum class DamageType { Physical, Fire, Ice, Lightning, Arcane };

struct ResistProfile {
    float fire      = 0.f;
    float ice       = 0.f;
    float lightning = 0.f;
    float arcane    = 0.f;

    bool immuneFire      = false;
    bool immuneIce       = false;
    bool immuneLightning = false;
    bool immuneArcane    = false;
};

// ───────────────────────────────────────────────
// Rigid body (simple verlet integration)
// ───────────────────────────────────────────────
struct RigidBody {
    Vec3  pos        {};
    Vec3  vel        {};
    Vec3  acc        {};
    float mass       = 1.f;
    float restitution= 0.4f;
    bool  isStatic   = false;
    AABB  bounds     {};
};

// ───────────────────────────────────────────────
// Platform / collidable surface
// ───────────────────────────────────────────────
struct Platform {
    AABB  aabb;
    bool  isWater   = false;
    bool  isWallRun = false;  // can be wall-run
    Vec3  normal    {0, 0, 1};
};

struct Enemy {
    int   id;
    Vec3  pos;
    Vec3  vel;
    float health   = 80.f;
    float armor    = 0.f;
    bool  blocking = false;
    bool  alive    = true;

    // Status and Resistances
    std::vector<StatusInstance> statuses;
    ResistProfile resist;
};

// ───────────────────────────────────────────────
// PhysicsEngine
// ───────────────────────────────────────────────
class PhysicsEngine {
public:
    static constexpr float GRAVITY      = 24.0f;
    static constexpr float WATER_DRAG   = 0.85f;
    static constexpr float WATER_BUOY   = 12.0f;
    static constexpr float TERM_VEL     = 30.0f;
    static constexpr float WATER_LEVEL  = 0.0f;   // y=0 is water surface (in water areas)

    PhysicsEngine();

    // Main tick – called every frame from Python
    void step(CharacterState& cs, float dt);

    // Platform management
    void addPlatform(const Platform& p);
    void clearPlatforms();

    // Impulses (called by Combat/Magic/Parkour)
    void applyImpulse(CharacterState& cs, const Vec3& impulse);
    void applyJump(CharacterState& cs, float force);
    void applyWallJump(CharacterState& cs, const Vec3& wallNormal, float force);

    // Queries
    bool         raycast(const Vec3& origin, const Vec3& dir, float maxDist, Vec3& hitPos, Vec3& hitNorm) const;
    bool         isInWater(const Vec3& pos) const;
    const Vec3&  getGravity() const { return _gravity; }

    // Rigid bodies (projectiles, debris)
    int   addRigidBody(const RigidBody& rb);
    void  stepRigidBodies(float dt);
    Vec3  getRigidBodyPos(int id) const;
    void  removeRigidBody(int id);

private:
    Vec3                 _gravity   {0, 0, -GRAVITY};
    std::vector<Platform>  _platforms;
    std::vector<RigidBody> _rigidBodies;
    std::vector<bool>      _rbAlive;

    bool  resolveGround(CharacterState& cs);
    bool  resolveWater(CharacterState& cs);
    void  applyDrag(CharacterState& cs, float dt);
    void  clampToBoundary(CharacterState& cs);
};
