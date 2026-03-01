#pragma once
#include "PhysicsEngine.h"
#include <vector>
#include <string>
#include <functional>

enum class SpellType {
    Fireball,
    LightningBolt,
    IceShards,
    ForceWave,
    HealingAura,
    PhaseStep,      // teleport-dash
    MeteorStrike,
};

struct SpellProjectile {
    int       id;
    SpellType type;
    Vec3      pos;
    Vec3      vel;
    Vec3      color;   // for particle system
    float     damage;
    float     radius;
    float     lifetime;
    float     elapsed  = 0.f;
    bool      alive    = true;
};

struct SpellEffect {
    SpellType   type;
    Vec3        pos;
    float       radius;
    float       damage;
    std::string particleTag;
    std::string soundTag;
};

class MagicSystem {
public:
    MagicSystem();

    // Cast – returns SpellEffect (for Python to dispatch visuals/sound)
    // Returns empty effect if mana insufficient or cooldown active
    SpellEffect castSpell(CharacterState& cs, SpellType type,
                          const Vec3& targetDir,
                          std::vector<Enemy>& enemies);

    // Projectile sim tick
    void update(float dt, std::vector<Enemy>& enemies,
                std::function<void(const SpellEffect&)> onHit);

    // Queries
    const std::vector<SpellProjectile>& getProjectiles() const { return _projectiles; }
    float getCooldown(SpellType t) const;
    bool  canCast(const CharacterState& cs, SpellType t) const;

    // Mana costs
    static constexpr float MANA_FIREBALL    = 20.f;
    static constexpr float MANA_LIGHTNING   = 35.f;
    static constexpr float MANA_ICE         = 25.f;
    static constexpr float MANA_FORCE       = 30.f;
    static constexpr float MANA_HEAL        = 40.f;
    static constexpr float MANA_PHASE       = 45.f;
    static constexpr float MANA_METEOR      = 80.f;
    static constexpr float MANA_REGEN       = 8.f;   // per second

private:
    std::vector<SpellProjectile> _projectiles;
    int  _nextId = 0;
    std::vector<float> _cooldowns;  // indexed by SpellType

    SpellEffect castFireball    (CharacterState& cs, const Vec3& dir);
    SpellEffect castLightning   (CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies);
    SpellEffect castIceShards   (CharacterState& cs, const Vec3& dir);
    SpellEffect castForceWave   (CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies);
    SpellEffect castHeal        (CharacterState& cs);
    SpellEffect castPhaseStep   (CharacterState& cs, const Vec3& dir);
    SpellEffect castMeteor      (CharacterState& cs, const Vec3& targetPos, std::vector<Enemy>& enemies);

    void damageEnemiesInRadius(const Vec3& center, float radius,
                                float dmg, std::vector<Enemy>& enemies,
                                Vec3 knockback = {});
};
