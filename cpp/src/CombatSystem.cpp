#include "CombatSystem.h"
#include <cmath>
#include <algorithm>

CombatSystem::CombatSystem() {}

HitResult CombatSystem::startAttack(CharacterState& cs, AttackType type,
                                     std::vector<Enemy>& enemies) {
    HitResult result;
    if (_swing.active) return result;  // still swinging

    float cost = 0.f;
    switch (type) {
        case AttackType::Light:  cost = STAMINA_LIGHT;  break;
        case AttackType::Heavy:  cost = STAMINA_HEAVY;  break;
        case AttackType::Spin:   cost = STAMINA_SPIN;   break;
        case AttackType::Thrust: cost = STAMINA_THRUST; break;
        default: break;
    }
    if (cs.stamina < cost) return result;
    cs.stamina -= cost;

    _combo = advanceCombo(type);

    // Configure swing
    _swing.type     = type;
    _swing.origin   = cs.position;
    _swing.dir      = cs.facingDir;
    _swing.active   = true;
    _swing.elapsed  = 0.f;

    switch (type) {
        case AttackType::Light:
            _swing.reach    = 2.0f;
            _swing.arc      = 70.f;
            _swing.damage   = 18.f * comboMultiplier();
            _swing.duration = 0.3f;
            break;
        case AttackType::Heavy:
            _swing.reach    = 2.6f;
            _swing.arc      = 100.f;
            _swing.damage   = 42.f * comboMultiplier();
            _swing.duration = 0.55f;
            break;
        case AttackType::Thrust:
            _swing.reach    = 3.2f;
            _swing.arc      = 20.f;
            _swing.damage   = 30.f * comboMultiplier();
            _swing.duration = 0.35f;
            break;
        case AttackType::Spin:
            _swing.reach    = 2.4f;
            _swing.arc      = 360.f;
            _swing.damage   = 28.f;
            _swing.duration = 0.6f;
            break;
        default: break;
    }

    // Activate parry window for counter-attack boost
    _parryWindow = 0.15f;

    // Immediate hit detection for the active phase
    for (auto& e : enemies) {
        if (!e.alive) continue;
        if (isSwordHit(_swing, e)) {
            float dmg = calcDamage(_swing, e);
            e.health -= dmg;
            if (e.health <= 0.f) e.alive = false;

            result.hit      = true;
            result.damage  += dmg;
            result.staggered = type == AttackType::Heavy || type == AttackType::Spin;
            result.knockback = cs.facingDir * 3.f;
            result.effect   = "blood";
        }
    }

    return result;
}

void CombatSystem::update(float dt, CharacterState& cs, std::vector<Enemy>& /*enemies*/) {
    if (_swing.active) {
        _swing.elapsed += dt;
        if (_swing.elapsed >= _swing.duration) {
            _swing.active = false;
        }
    }

    if (_parryWindow > 0.f) _parryWindow -= dt;

    // Combo timeout
    _comboTime += dt;
    if (_comboTime > 1.8f) {
        _combo     = ComboStep::None;
        _comboTime = 0.f;
    }

    // Stamina regen
    if (!_swing.active) {
        cs.stamina = std::min(cs.maxStamina, cs.stamina + STAMINA_REGEN * dt);
    }
}

bool CombatSystem::tryParry(CharacterState& cs) {
    if (_parryWindow > 0.f) {
        cs.stamina = std::min(cs.maxStamina, cs.stamina + 20.f);
        return true;
    }
    return false;
}

float CombatSystem::applyBlock(CharacterState& cs, float incomingDamage) {
    float reduction = 0.65f;
    float stamCost  = incomingDamage * 0.3f;
    cs.stamina -= stamCost;
    if (cs.stamina < 0.f) {
        cs.stamina = 0.f;
        return incomingDamage;  // guard broken
    }
    return incomingDamage * (1.f - reduction);
}

bool CombatSystem::isSwordHit(const SwordSwing& sw, const Enemy& e) const {
    Vec3 toEnemy = e.pos - sw.origin;
    float dist   = toEnemy.len();
    if (dist > sw.reach) return false;

    if (sw.arc >= 360.f) return true;

    // Check angle
    Vec3  te2d    = {toEnemy.x, toEnemy.y, 0.f};
    Vec3  fd2d    = {sw.dir.x,  sw.dir.y,  0.f};
    float len2d   = te2d.len();
    if (len2d < 0.01f) return true;

    float cosA = fd2d.normalized().dot(te2d.normalized());
    float halfArc = (sw.arc * 0.5f) * (3.14159f / 180.f);
    return cosA >= std::cos(halfArc);
}

float CombatSystem::calcDamage(const SwordSwing& sw, const Enemy& e) const {
    float dmg = sw.damage;
    if (e.blocking) dmg *= 0.2f;
    dmg -= e.armor * 0.5f;
    return std::max(1.f, dmg);
}

ComboStep CombatSystem::advanceCombo(AttackType t) {
    _comboTime = 0.f;
    bool isLight = (t == AttackType::Light);
    switch (_combo) {
        case ComboStep::None: return isLight ? ComboStep::A  : ComboStep::None;
        case ComboStep::A:    return isLight ? ComboStep::AA : ComboStep::AB;
        case ComboStep::AA:   return isLight ? ComboStep::AAA: ComboStep::None;
        default:              return ComboStep::None;
    }
}

float CombatSystem::comboMultiplier() const {
    switch (_combo) {
        case ComboStep::A:   return 1.0f;
        case ComboStep::AA:  return 1.2f;
        case ComboStep::AAA: return 1.5f;
        case ComboStep::AB:  return 1.3f;
        default:             return 1.0f;
    }
}
