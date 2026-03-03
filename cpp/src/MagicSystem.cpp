#include "MagicSystem.h"
#include <cmath>
#include <algorithm>

MagicSystem::MagicSystem() {
    _cooldowns.resize(11, 0.f);

    _spellDefs[SpellType::Fireball] = {45.0f, 18.0f, 0.4f, 4.0f, 0.0f};
    _spellDefs[SpellType::LightningBolt] = {60.0f, 0.0f, 1.0f, 0.0f, 0.0f};
    _spellDefs[SpellType::ChainLightning] = {70.0f, 0.0f, 1.0f, 0.0f, 0.0f};
    _spellDefs[SpellType::IceShards] = {18.0f, 22.0f, 0.2f, 2.0f, 0.0f};
    _spellDefs[SpellType::ForceWave] = {25.0f, 12.0f, 6.0f, 0.0f, 0.0f};
    _spellDefs[SpellType::HealingAura] = {50.0f, 0.0f, 2.0f, 0.0f, 0.0f};
    _spellDefs[SpellType::PhaseStep] = {0.0f, 8.0f, 0.0f, 0.0f, 0.0f};
    _spellDefs[SpellType::MeteorStrike] = {120.0f, 35.0f, 1.5f, 3.0f, 0.0f};
    _spellDefs[SpellType::ArcaneMissile] = {30.0f, 15.0f, 0.3f, 5.0f, 0.0f};
    _spellDefs[SpellType::Blizzard] = {15.0f, 0.0f, 8.0f, 8.0f, 1.0f};
    _spellDefs[SpellType::BlackHole] = {10.0f, 0.0f, 12.0f, 5.0f, 0.5f};
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
        case SpellType::ArcaneMissile:cost= MANA_ARCANE;    break;
        case SpellType::ChainLightning:cost=MANA_CHAIN;     break;
        case SpellType::Blizzard:    cost = MANA_BLIZZARD;  break;
        case SpellType::BlackHole:   cost = MANA_BLACKHOLE; break;
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
        case SpellType::ArcaneMissile:fx = castArcaneMissile(cs, targetDir, enemies); break;
        case SpellType::ChainLightning:fx= castChainLightning(cs, targetDir, enemies); break;
        case SpellType::Blizzard:     fx = castBlizzard(cs, targetDir * 15.f + cs.position); break;
        case SpellType::BlackHole:    fx = castBlackHole(cs, targetDir * 15.f + cs.position); break;
    }

    // Cooldowns (seconds)
    float cds[] = {1.5f, 3.f, 1.8f, 2.f, 4.f, 2.5f, 8.f, 5.f, 6.f, 10.f, 12.f};
    if (idx < 11) _cooldowns[idx] = cds[idx];

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
                // Determine damage type
                DamageType dt_type = DamageType::Physical;
                if (p.type == SpellType::Fireball || p.type == SpellType::MeteorStrike) dt_type = DamageType::Fire;
                else if (p.type == SpellType::IceShards || p.type == SpellType::Blizzard) dt_type = DamageType::Ice;
                else if (p.type == SpellType::LightningBolt || p.type == SpellType::ChainLightning) dt_type = DamageType::Lightning;
                else if (p.type == SpellType::ArcaneMissile || p.type == SpellType::BlackHole || p.type == SpellType::ForceWave) dt_type = DamageType::Arcane;

                DamagePacket pkt{dt_type, p.damage, 0, false};
                applyDamage(e, pkt);

                // Apply specific status based on projectile
                if (p.type == SpellType::Fireball) {
                    applyStatus(e, StatusType::Burn, 3.0f, 6.0f, 1.0f, 0); // Example burn
                }

                SpellEffect fx;
                fx.type   = p.type;
                fx.pos    = p.pos;
                fx.radius = p.radius;
                fx.damage = p.damage;
                onHit(fx);

                // AoE
                if (p.type == SpellType::Fireball || p.type == SpellType::MeteorStrike)
                    damageEnemiesInRadius(p.pos, p.radius * 2.f, p.damage * 0.5f, dt_type, enemies);

                p.alive = false;
                break;
            }
        }
    }

    // Cleanup
    _projectiles.erase(std::remove_if(_projectiles.begin(), _projectiles.end(),
        [](const SpellProjectile& p){ return !p.alive; }), _projectiles.end());

    // Update Statuses for all enemies
    for (auto& e : enemies) {
        if (!e.alive) continue;
        updateStatuses(dt, e, onHit);
    }
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
    const auto& cfg = _spellDefs[SpellType::LightningBolt];

    Vec3 start = cs.position + Vec3{0, 0, 1.0f};
    Vec3 end = start + dir * 40.0f;

    for (auto& enemy : enemies) {
        if (!enemy.alive) continue;

        Vec3 toEnemy = enemy.pos - start;
        float projection = toEnemy.dot(dir);

        if (projection > 0 && projection < 40.0f) {
            Vec3 closestPoint = start + dir * projection;
            float dist = (closestPoint - enemy.pos).len();

            if (dist < 2.0f /* enemy radius approx */ + 1.0f) {
                DamagePacket pkt{DamageType::Lightning, cfg.damage, 0, false};
                applyDamage(enemy, pkt);
            }
        }
    }

    SpellEffect fx;
    fx.type = SpellType::LightningBolt;
    fx.pos = start;
    fx.destination = end;
    fx.normal = Vec3{0,0,1};
    fx.scale = 1.0f;
    fx.particleTag = "lightning_beam";
    fx.soundTag = "thunder_sfx";
    return fx;
}

SpellEffect MagicSystem::castIceShards(CharacterState& cs, const Vec3& dir) {
    cs.mana -= MANA_ICE;
    const auto& cfg = _spellDefs[SpellType::IceShards];

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
        p.vel    = shotDir * cfg.speed;
        p.color  = {0.5f, 0.8f, 1.f};
        p.damage = cfg.damage;
        p.radius = cfg.radius;
        p.lifetime = cfg.life;
        _projectiles.push_back(p);
    }
    return { SpellType::IceShards, cs.position, {}, {}, 1.0f, 0.f, 0.f, "ice_launch", "ice_sfx" };
}

SpellEffect MagicSystem::castForceWave(CharacterState& cs, const Vec3& dir,
                                        std::vector<Enemy>& enemies) {
    cs.mana -= MANA_FORCE;
    const auto& cfg = _spellDefs[SpellType::ForceWave];
    Vec3 knock = dir.normalized() * 12.f;
    knock.z = 4.f;
    damageEnemiesInRadius(cs.position, cfg.radius, cfg.damage, DamageType::Physical, enemies, knock);
    return { SpellType::ForceWave, cs.position, {}, {}, 1.0f, cfg.radius, cfg.damage, "force_wave", "force_sfx" };
}

SpellEffect MagicSystem::castHeal(CharacterState& cs) {
    cs.mana   -= MANA_HEAL;
    const auto& cfg = _spellDefs[SpellType::HealingAura];
    cs.health  = std::min(cs.maxHealth, cs.health + cfg.damage);
    return { SpellType::HealingAura, cs.position, {}, {}, 1.0f, cfg.radius, 0.f, "heal_aura", "heal_sfx" };
}

SpellEffect MagicSystem::castPhaseStep(CharacterState& cs, const Vec3& dir) {
    cs.mana -= MANA_PHASE;
    const auto& cfg = _spellDefs[SpellType::PhaseStep];
    cs.position += dir.normalized() * cfg.speed;
    cs.velocity  = {0,0,0};
    return { SpellType::PhaseStep, cs.position, {}, {}, 1.0f, 0.f, 0.f, "phase_trail", "phase_sfx" };
}

SpellEffect MagicSystem::castMeteor(CharacterState& cs, const Vec3& targetPos,
                                     std::vector<Enemy>& enemies) {
    cs.mana -= MANA_METEOR;
    const auto& cfg = _spellDefs[SpellType::MeteorStrike];
    // Spawn high-speed projectile from sky
    SpellProjectile p;
    p.id   = _nextId++;
    p.type = SpellType::MeteorStrike;
    p.pos  = {targetPos.x, targetPos.y, 30.f};
    Vec3 toTarget = targetPos - p.pos;
    p.vel    = toTarget.normalized() * cfg.speed;
    p.color  = {1.f, 0.3f, 0.f};
    p.damage = cfg.damage;
    p.radius = cfg.radius;
    p.lifetime = cfg.life;
    _projectiles.push_back(p);
    return { SpellType::MeteorStrike, p.pos, {}, {}, 1.0f, cfg.radius, cfg.damage, "meteor_tail", "meteor_sfx" };
}

SpellEffect MagicSystem::castChainLightning(CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies) {
    cs.mana -= MANA_CHAIN;
    const auto& cfg = _spellDefs[SpellType::ChainLightning];

    int currentTargetId = findClosestEnemy(cs.position, 20.0f, enemies);
    if (currentTargetId == -1) return {};

    Vec3 currentPos = cs.position + Vec3{0, 0, 1.0f};
    float damage = cfg.damage;

    std::vector<Vec3> points;
    points.push_back(currentPos);

    for (int bounce = 0; bounce < 4; ++bounce) {
        auto it = std::find_if(enemies.begin(), enemies.end(),
                               [currentTargetId](const Enemy& e) {
                                   return e.id == currentTargetId;
                               });

        if (it == enemies.end() || !it->alive) break;

        DamagePacket pkt{DamageType::Lightning, damage, 0, false};
        applyDamage(*it, pkt);

        points.push_back(it->pos);

        damage *= 0.75f; // reduced damage per bounce

        currentPos = it->pos;
        currentTargetId = findClosestEnemy(currentPos, 15.0f, enemies, currentTargetId);

        if (currentTargetId == -1) break;
    }

    if(points.size() > 1) {
       return { SpellType::ChainLightning, points[0], points[1], Vec3{0,0,1}, 1.0f, 0.f, cfg.damage, "chain_segment", "thunder_sfx" };
    }
    return {};
}

SpellEffect MagicSystem::castArcaneMissile(CharacterState& cs, const Vec3& dir, std::vector<Enemy>& enemies) {
    cs.mana -= MANA_ARCANE;
    const auto& cfg = _spellDefs[SpellType::ArcaneMissile];

    SpellProjectile p;
    p.id   = _nextId++;
    p.type = SpellType::ArcaneMissile;
    p.pos  = cs.position + Vec3{0,0,1.5f};
    p.vel  = dir.normalized() * cfg.speed;
    p.color  = {0.8f, 0.1f, 0.8f};
    p.damage = cfg.damage;
    p.radius = cfg.radius;
    p.lifetime = cfg.life;
    p.targetId = findClosestEnemy(p.pos, 30.0f, enemies);
    _projectiles.push_back(p);

    return { SpellType::ArcaneMissile, p.pos, {}, {}, 1.0f, cfg.radius, cfg.damage, "arcane_launch", "arcane_sfx" };
}

SpellEffect MagicSystem::castBlizzard(CharacterState& cs, const Vec3& targetPos) {
    cs.mana -= MANA_BLIZZARD;
    const auto& cfg = _spellDefs[SpellType::Blizzard];

    SpellProjectile p; // Actually a persistent zone
    p.id   = _nextId++;
    p.type = SpellType::Blizzard;
    p.pos  = targetPos;
    p.vel  = {0,0,0};
    p.color  = {0.3f, 0.8f, 1.0f};
    p.damage = cfg.damage;
    p.radius = cfg.radius;
    p.lifetime = cfg.life;
    p.tickRate = cfg.tickRate;
    _projectiles.push_back(p);

    return { SpellType::Blizzard, targetPos, {}, {}, 1.0f, cfg.radius, cfg.damage, "blizzard_zone", "blizzard_sfx" };
}

SpellEffect MagicSystem::castBlackHole(CharacterState& cs, const Vec3& targetPos) {
    cs.mana -= MANA_BLACKHOLE;
    const auto& cfg = _spellDefs[SpellType::BlackHole];

    SpellProjectile p;
    p.id   = _nextId++;
    p.type = SpellType::BlackHole;
    p.pos  = targetPos;
    p.vel  = {0,0,0};
    p.color  = {0.1f, 0.0f, 0.3f};
    p.damage = cfg.damage;
    p.radius = cfg.radius;
    p.lifetime = cfg.life;
    p.tickRate = cfg.tickRate; // 0.5f in standard defs
    p.pullForce = 8.0f;        // Custom property mapped here
    _projectiles.push_back(p);

    return { SpellType::BlackHole, targetPos, {}, {}, 1.0f, cfg.radius, cfg.damage, "blackhole_zone", "blackhole_sfx" };
}

void MagicSystem::damageEnemiesInRadius(const Vec3& center, float radius,
                                         float dmg, DamageType damageType, std::vector<Enemy>& enemies,
                                         Vec3 knockback) {
    for (auto& e : enemies) {
        if (!e.alive) continue;
        Vec3 diff = e.pos - center;
        if (diff.len() <= radius) {
            DamagePacket pkt{damageType, dmg, 0, false};
            applyDamage(e, pkt);
            e.vel += knockback;
        }
    }
}

int MagicSystem::findClosestEnemy(const Vec3& pos, float maxRadius, const std::vector<Enemy>& enemies, int ignoreId) {
    int bestId = -1;
    float bestDistSq = maxRadius * maxRadius;
    for (const auto& e : enemies) {
        if (!e.alive || e.id == ignoreId) continue;
        Vec3 d = e.pos - pos;
        float dSq = d.dot(d);
        if (dSq < bestDistSq) {
            bestDistSq = dSq;
            bestId = e.id;
        }
    }
    return bestId;
}

float MagicSystem::applyDamage(Enemy& e, const DamagePacket& dmg) {
    float resistVal = 0.f;
    bool immune = false;

    switch (dmg.type) {
        case DamageType::Fire:
            resistVal = e.resist.fire; immune = e.resist.immuneFire; break;
        case DamageType::Ice:
            resistVal = e.resist.ice; immune = e.resist.immuneIce; break;
        case DamageType::Lightning:
            resistVal = e.resist.lightning; immune = e.resist.immuneLightning; break;
        case DamageType::Arcane:
            resistVal = e.resist.arcane; immune = e.resist.immuneArcane; break;
        case DamageType::Physical:
            // Could add armor application here
            break;
    }

    if (immune) return 0.f;

    resistVal = std::clamp(resistVal, 0.f, 1.f);
    float finalDmg = dmg.amount * (1.f - resistVal);

    // Simplistic armor calculation
    if (dmg.type == DamageType::Physical) {
        finalDmg = std::max(1.0f, finalDmg - e.armor);
    }

    e.health -= finalDmg;
    if (e.health <= 0.f) e.alive = false;

    return finalDmg;
}

void MagicSystem::applyStatus(Enemy& e, StatusType type, float duration, float magnitude, float tickRate, int casterId) {
    for (auto& st : e.statuses) {
        if (st.type == type) {
            st.remaining = std::max(st.remaining, duration);
            st.magnitude = std::max(st.magnitude, magnitude);
            return;
        }
    }
    e.statuses.push_back({type, duration, tickRate, 0.f, magnitude, casterId});
}

void MagicSystem::updateStatuses(float dt, Enemy& e, std::function<void(const SpellEffect&)> onHit) {
    for (auto& st : e.statuses) {
        st.remaining -= dt;
        if (st.remaining <= 0.f) continue;

        if (st.tickRate > 0.f) {
            st.tickTimer += dt;
            if (st.tickTimer >= st.tickRate) {
                st.tickTimer -= st.tickRate;

                switch (st.type) {
                    case StatusType::Burn:
                        applyDamage(e, {DamageType::Fire, st.magnitude, st.sourceCasterId, true});
                        if (onHit) {
                            SpellEffect fx;
                            fx.type = SpellType::Fireball;
                            fx.pos = e.pos;
                            fx.particleTag = "burn_tick";
                            onHit(fx);
                        }
                        break;
                    case StatusType::Shock:
                        applyDamage(e, {DamageType::Lightning, st.magnitude, st.sourceCasterId, true});
                        if (onHit) {
                            SpellEffect fx;
                            fx.type = SpellType::LightningBolt;
                            fx.pos = e.pos;
                            fx.particleTag = "shock_tick";
                            onHit(fx);
                        }
                        break;
                    // Other statuses...
                    default: break;
                }
            }
        }
    }

    // Clean up expired statuses
    e.statuses.erase(std::remove_if(e.statuses.begin(), e.statuses.end(),
        [](const StatusInstance& s){ return s.remaining <= 0.f; }), e.statuses.end());
}
