#pragma once
#include "PhysicsEngine.h"
#include <vector>
#include <functional>
#include <string>

enum class AttackType { Light, Heavy, Thrust, Spin, Parry };
enum class ComboStep  { None, A, AA, AAA, AB, ABA };

struct HitResult {
    bool  hit          = false;
    float damage       = 0.f;
    Vec3  knockback    {};
    bool  staggered    = false;
    std::string effect;  // "blood", "spark", "magic_hit"
};

struct SwordSwing {
    AttackType type    = AttackType::Light;
    Vec3       origin  {};
    Vec3       dir     {};
    float      reach   = 2.2f;
    float      arc     = 90.f;   // degrees swept
    float      damage  = 20.f;
    float      duration= 0.35f;
    float      elapsed = 0.f;
    bool       active  = false;
};

class CombatSystem {
public:
    CombatSystem();

    // Returns HitResult; updates stamina
    HitResult startAttack(CharacterState& cs, AttackType type,
                           std::vector<Enemy>& enemies);

    // Call every frame to advance active swing
    void update(float dt, CharacterState& cs, std::vector<Enemy>& enemies);

    // Parry window check
    bool tryParry(CharacterState& cs);

    // Block (reduces damage)
    float applyBlock(CharacterState& cs, float incomingDamage);

    // Combo state
    ComboStep getCurrentCombo() const { return _combo; }
    bool      isAttacking()     const { return _swing.active; }

    // Stamina cost per attack type
    static constexpr float STAMINA_LIGHT  = 15.f;
    static constexpr float STAMINA_HEAVY  = 30.f;
    static constexpr float STAMINA_SPIN   = 45.f;
    static constexpr float STAMINA_THRUST = 20.f;
    static constexpr float STAMINA_REGEN  = 18.f;

private:
    SwordSwing _swing;
    ComboStep  _combo     = ComboStep::None;
    float      _comboTime = 0.f;
    float      _parryWindow = 0.f;
    bool       _parryActive = false;

    bool    isSwordHit(const SwordSwing& sw, const Enemy& e) const;
    float   calcDamage(const SwordSwing& sw, const Enemy& e) const;
    ComboStep advanceCombo(AttackType t);
    float   comboMultiplier() const;
};
