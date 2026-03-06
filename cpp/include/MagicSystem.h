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
    ArcaneMissile,
    ChainLightning,
    Blizzard,
    BlackHole
};

struct SpellProjectile {
    int       id;
    int       targetId = -1; // for homing
    SpellType type;
    Vec3      pos;
    Vec3      vel;
    Vec3      color;   // for particle system
    float     damage;
    float     radius;
    float     lifetime;
    float     elapsed  = 0.f;
    float     tickRate = 1.0f;
    float     tickTimer= 0.0f;
    float     pullForce = 0.0f;
    bool      alive    = true;
};

struct SpellEffect {
    SpellType   type;
    Vec3        pos;      // origin
    Vec3        destination;
    Vec3        normal;
    float       scale;
    float       radius;
    float       damage;
    std::string particleTag;
    std::string soundTag;
};

struct DamagePacket {
    DamageType type;
    float amount;
    int sourceCasterId = 0;
    bool isDot = false;
};

struct SpellConfig {
    float damage;
    float speed;
    float radius;
    float life;
    float tickRate;
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
    static constexpr float MANA_BLIZZARD    = 50.f;
    static constexpr float MANA_BLACKHOLE   = 60.f;
    static constexpr float MANA_ARCANE      = 30.f;
    static constexpr float MANA_CHAIN       = 45.f;
    static constexpr float MANA_REGEN       = 8.f;   // per second

private:
    std::vector<SpellProjectile> _projectiles;
    int  _nextId = 0;
    std::vector<float> _cooldowns;  // indexed by SpellType
    std::unordered_map<SpellType, SpellConfig> _spellDefs;

    SpellEffect castFireball    (CharacterState& cs, const Vec3& dir);
    SpellEffect castLightning   (CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies);
    SpellEffect castChainLightning(CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies);
    SpellEffect castIceShards   (CharacterState& cs, const Vec3& dir);
    SpellEffect castForceWave   (CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies);
    SpellEffect castHeal        (CharacterState& cs);
    SpellEffect castPhaseStep   (CharacterState& cs, const Vec3& dir);
    SpellEffect castMeteor      (CharacterState& cs, const Vec3& targetPos, std::vector<Enemy>& enemies);
    SpellEffect castArcaneMissile(CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies);
    SpellEffect castBlizzard    (CharacterState& cs, const Vec3& targetPos);
    SpellEffect castBlackHole   (CharacterState& cs, const Vec3& targetPos);

    void damageEnemiesInRadius(const Vec3& center, float radius,
                                float dmg, DamageType damageType, std::vector<Enemy>& enemies,
                                Vec3 knockback = {});

    int findClosestEnemy(const Vec3& pos, float maxRadius, const std::vector<Enemy>& enemies, int ignoreId = -1);
    float applyDamage(Enemy& e, const DamagePacket& dmg);
    void applyStatus(Enemy& e, StatusType type, float duration, float magnitude, float tickRate, int casterId);
    void updateStatuses(float dt, Enemy& e, std::function<void(const SpellEffect&)> onHit);
};
