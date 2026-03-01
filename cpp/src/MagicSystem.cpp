#include "MagicSystem.h"
#include <cmath>
#include <algorithm>

MagicSystem::MagicSystem() {
    _cooldowns.resize(8, 0.f);
}

float MagicSystem::getCooldown(SpellType t) const {
    int idx = static_cast<int>(t);
    return idx < (int)_cooldowns.size() ? _cooldowns[idx] : 0.f;
}

bool MagicSystem::canCast(const CharacterState& cs, SpellType t) const {
    if (getCooldown(t) > 0.f) return false;
    float cost = 0.f;
    switch (t) {
        case SpellType::Fireball:    cost = MANA_FIREBALL;  break;
        case SpellType::LightningBolt:cost = MANA_LIGHTNING; break;
        case SpellType::IceShards:   cost = MANA_ICE;       break;
        case SpellType::ForceWave:   cost = MANA_FORCE;     break;
        case SpellType::HealingAura: cost = MANA_HEAL;      break;
        case SpellType::PhaseStep:   cost = MANA_PHASE;     break;
        case SpellType::MeteorStrike:cost = MANA_METEOR;    break;
    }
    return cs.mana >= cost;
}

SpellEffect MagicSystem::castSpell(CharacterState& cs, SpellType type,
                                    const Vec3& targetDir, std::vector<Enemy>& enemies) {
    if (!canCast(cs, type)) return {};

    SpellEffect fx;
    fx.type = type;
    int idx = static_cast<int>(type);

    switch (type) {
        case SpellType::Fireball:     fx = castFireball(cs, targetDir);         break;
        case SpellType::LightningBolt:fx = castLightning(cs, targetDir, enemies); break;
        case SpellType::IceShards:    fx = castIceShards(cs, targetDir);        break;
        case SpellType::ForceWave:    fx = castForceWave(cs, targetDir, enemies);break;
        case SpellType::HealingAura:  fx = castHeal(cs);                        break;
        case SpellType::PhaseStep:    fx = castPhaseStep(cs, targetDir);        break;
        case SpellType::MeteorStrike: fx = castMeteor(cs, targetDir * 15.f + cs.position, enemies); break;
    }

    // Cooldowns (seconds)
    float cds[] = {1.5f, 3.f, 1.8f, 2.f, 4.f, 2.5f, 8.f};
    if (idx < 7) _cooldowns[idx] = cds[idx];

    return fx;
}

void MagicSystem::update(float dt, std::vector<Enemy>& enemies,
                          std::function<void(const SpellEffect&)> onHit) {
    // Cooldowns
    for (auto& cd : _cooldowns)
        if (cd > 0.f) cd -= dt;

    // Projectiles
    for (auto& p : _projectiles) {
        if (!p.alive) continue;
        p.elapsed += dt;
        if (p.elapsed >= p.lifetime) { p.alive = false; continue; }

        p.pos += p.vel * dt;

        // Gravity for some types
        if (p.type == SpellType::IceShards)
            p.vel.z -= 9.8f * dt;

        // Hit detection
        for (auto& e : enemies) {
            if (!e.alive) continue;
            Vec3 diff = e.pos - p.pos;
            if (diff.len() < p.radius + 0.5f) {
                e.health -= p.damage;
                if (e.health <= 0.f) e.alive = false;

                SpellEffect fx;
                fx.type   = p.type;
                fx.pos    = p.pos;
                fx.radius = p.radius;
                fx.damage = p.damage;
                onHit(fx);

                // AoE
                if (p.type == SpellType::Fireball || p.type == SpellType::MeteorStrike)
                    damageEnemiesInRadius(p.pos, p.radius * 2.f, p.damage * 0.5f, enemies);

                p.alive = false;
                break;
            }
        }
    }

    // Cleanup
    _projectiles.erase(std::remove_if(_projectiles.begin(), _projectiles.end(),
        [](const SpellProjectile& p){ return !p.alive; }), _projectiles.end());
}

// ─── Spell implementations ────────────────────────

SpellEffect MagicSystem::castFireball(CharacterState& cs, const Vec3& dir) {
    cs.mana -= MANA_FIREBALL;
    SpellProjectile p;
    p.id = _nextId++;
    p.type = SpellType::Fireball;
    p.pos  = cs.position + Vec3{0,0,1.5f};
    p.vel  = dir.normalized() * 18.f;
    p.color= {1.f, 0.4f, 0.1f};
    p.damage  = 45.f;
    p.radius  = 0.4f;
    p.lifetime= 4.f;
    _projectiles.push_back(p);
    return { SpellType::Fireball, p.pos, 0.3f, 0.f, "fireball_launch", "fireball_sfx" };
}

SpellEffect MagicSystem::castLightning(CharacterState& cs, const Vec3& dir,
                                        std::vector<Enemy>& enemies) {
    cs.mana -= MANA_LIGHTNING;
    // Instant chain lightning
    SpellEffect fx;
    fx.type = SpellType::LightningBolt;
    fx.pos  = cs.position;
    fx.particleTag = "lightning";
    fx.soundTag    = "thunder_sfx";

    // Find nearest enemy in front
    float bestDist = 20.f;
    Enemy* target  = nullptr;
    for (auto& e : enemies) {
        if (!e.alive) continue;
        Vec3 toE = e.pos - cs.position;
        if (toE.dot(dir) < 0.f) continue;
        float d = toE.len();
        if (d < bestDist) { bestDist = d; target = &e; }
    }

    if (target) {
        // Primary hit
        target->health -= 60.f;
        if (target->health <= 0.f) target->alive = false;
        fx.damage = 60.f;

        // Chain to 2 nearby
        int chains = 0;
        for (auto& e2 : enemies) {
            if (!e2.alive || &e2 == target) continue;
            if ((e2.pos - target->pos).len() < 5.f && chains < 2) {
                e2.health -= 30.f;
                if (e2.health <= 0.f) e2.alive = false;
                chains++;
            }
        }
    }
    return fx;
}

SpellEffect MagicSystem::castIceShards(CharacterState& cs, const Vec3& dir) {
    cs.mana -= MANA_ICE;
    // 5 shards in a spread
    for (int i = 0; i < 5; i++) {
        float angle = (-2.f + float(i)) * 12.f * (3.14159f / 180.f);
        Vec3 d = dir.normalized();
        Vec3 side = d.cross({0,0,1}).normalized() * std::sin(angle) * d.len();
        Vec3 shotDir = (d + side).normalized();

        SpellProjectile p;
        p.id = _nextId++;
        p.type   = SpellType::IceShards;
        p.pos    = cs.position + Vec3{0,0,1.2f};
        p.vel    = shotDir * 22.f;
        p.color  = {0.5f, 0.8f, 1.f};
        p.damage = 18.f;
        p.radius = 0.2f;
        p.lifetime = 2.f;
        _projectiles.push_back(p);
    }
    return { SpellType::IceShards, cs.position, 0.f, 0.f, "ice_launch", "ice_sfx" };
}

SpellEffect MagicSystem::castForceWave(CharacterState& cs, const Vec3& dir,
                                        std::vector<Enemy>& enemies) {
    cs.mana -= MANA_FORCE;
    Vec3 knock = dir.normalized() * 12.f;
    knock.z = 4.f;
    damageEnemiesInRadius(cs.position, 6.f, 25.f, enemies, knock);
    return { SpellType::ForceWave, cs.position, 6.f, 25.f, "force_wave", "force_sfx" };
}

SpellEffect MagicSystem::castHeal(CharacterState& cs) {
    cs.mana   -= MANA_HEAL;
    cs.health  = std::min(cs.maxHealth, cs.health + 50.f);
    return { SpellType::HealingAura, cs.position, 2.f, 0.f, "heal_aura", "heal_sfx" };
}

SpellEffect MagicSystem::castPhaseStep(CharacterState& cs, const Vec3& dir) {
    cs.mana -= MANA_PHASE;
    cs.position += dir.normalized() * 8.f;
    cs.velocity  = {0,0,0};
    return { SpellType::PhaseStep, cs.position, 0.f, 0.f, "phase_trail", "phase_sfx" };
}

SpellEffect MagicSystem::castMeteor(CharacterState& cs, const Vec3& targetPos,
                                     std::vector<Enemy>& enemies) {
    cs.mana -= MANA_METEOR;
    // Spawn high-speed projectile from sky
    SpellProjectile p;
    p.id   = _nextId++;
    p.type = SpellType::MeteorStrike;
    p.pos  = {targetPos.x, targetPos.y, 30.f};
    Vec3 toTarget = targetPos - p.pos;
    p.vel    = toTarget.normalized() * 35.f;
    p.color  = {1.f, 0.3f, 0.f};
    p.damage = 120.f;
    p.radius = 1.5f;
    p.lifetime = 3.f;
    _projectiles.push_back(p);
    return { SpellType::MeteorStrike, p.pos, 1.5f, 120.f, "meteor_tail", "meteor_sfx" };
}

void MagicSystem::damageEnemiesInRadius(const Vec3& center, float radius,
                                         float dmg, std::vector<Enemy>& enemies,
                                         Vec3 knockback) {
    for (auto& e : enemies) {
        if (!e.alive) continue;
        Vec3 diff = e.pos - center;
        if (diff.len() <= radius) {
            e.health -= dmg;
            e.vel    += knockback;
            if (e.health <= 0.f) e.alive = false;
        }
    }
}
