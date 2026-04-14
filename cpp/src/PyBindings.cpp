#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "PhysicsEngine.h"
#include "CombatSystem.h"
#include "EnemyRuntimeSystem.h"
#include "ParkourSystem.h"
#include "MagicSystem.h"
#include "NpcRuntimeSystem.h"
#include "WaterSimulation.h"
#include "AnimationBlender.h"
#include "ParticleSystem.h"
#include "AttentionManager.h"

namespace py = pybind11;

PYBIND11_MODULE(game_core, m) {
    m.doc() = "XBot game – C++ core systems";

    // ─── Vec3 ────────────────────────────────────────
    py::class_<Vec3>(m, "Vec3")
        .def(py::init<>())
        .def(py::init<float,float,float>())
        .def_readwrite("x", &Vec3::x)
        .def_readwrite("y", &Vec3::y)
        .def_readwrite("z", &Vec3::z)
        .def("len",        &Vec3::len)
        .def("normalized", &Vec3::normalized)
        .def("dot",        &Vec3::dot)
        .def("cross",      &Vec3::cross)
        .def("__add__",    [](const Vec3& a, const Vec3& b){ return a+b; })
        .def("__sub__",    [](const Vec3& a, const Vec3& b){ return a-b; })
        .def("__mul__",    [](const Vec3& a, float s)      { return a*s; })
        .def("__repr__",   [](const Vec3& v){
            return "Vec3(" + std::to_string(v.x) + "," +
                   std::to_string(v.y) + "," + std::to_string(v.z) + ")"; });

    // ─── CharacterState ──────────────────────────────
    py::class_<CharacterState>(m, "CharacterState")
        .def(py::init<>())
        .def_readwrite("position",   &CharacterState::position)
        .def_readwrite("velocity",   &CharacterState::velocity)
        .def_readwrite("facingDir",  &CharacterState::facingDir)
        .def_readwrite("health",     &CharacterState::health)
        .def_readwrite("maxHealth",  &CharacterState::maxHealth)
        .def_readwrite("stamina",    &CharacterState::stamina)
        .def_readwrite("maxStamina", &CharacterState::maxStamina)
        .def_readwrite("mana",       &CharacterState::mana)
        .def_readwrite("maxMana",    &CharacterState::maxMana)
        .def_readwrite("grounded",   &CharacterState::grounded)
        .def_readwrite("inWater",    &CharacterState::inWater)
        .def_readwrite("onWall",     &CharacterState::onWall)
        .def_readwrite("waterDepth", &CharacterState::waterDepth)
        .def_readwrite("yaw",        &CharacterState::yaw)
        .def_readwrite("comboCount", &CharacterState::comboCount)
        .def_readwrite("comboTimer", &CharacterState::comboTimer);

    // ─── AABB ────────────────────────────────────────
    py::class_<AABB>(m, "AABB")
        .def(py::init<>())
        .def_readwrite("min", &AABB::min)
        .def_readwrite("max", &AABB::max);

    // ─── Platform ────────────────────────────────────
    py::class_<Platform>(m, "Platform")
        .def(py::init<>())
        .def_readwrite("aabb",      &Platform::aabb)
        .def_readwrite("isWater",   &Platform::isWater)
        .def_readwrite("isWallRun", &Platform::isWallRun)
        .def_readwrite("normal",    &Platform::normal);

    // ─── PhysicsEngine ───────────────────────────────
    py::class_<PhysicsEngine>(m, "PhysicsEngine")
        .def(py::init<>())
        .def("step",          &PhysicsEngine::step)
        .def("addPlatform",   &PhysicsEngine::addPlatform)
        .def("clearPlatforms",&PhysicsEngine::clearPlatforms)
        .def("applyImpulse",  &PhysicsEngine::applyImpulse)
        .def("applyJump",     &PhysicsEngine::applyJump)
        .def("applyWallJump", &PhysicsEngine::applyWallJump)
        .def("raycast",       [](PhysicsEngine& self, Vec3 o, Vec3 d, float dist){
            Vec3 hp{}, hn{};
            bool hit = self.raycast(o, d, dist, hp, hn);
            return py::make_tuple(hit, hp, hn);
        })
        .def("isInWater",     &PhysicsEngine::isInWater)
        .def("addRigidBody",  &PhysicsEngine::addRigidBody)
        .def("stepRigidBodies",&PhysicsEngine::stepRigidBodies)
        .def("getRigidBodyPos",&PhysicsEngine::getRigidBodyPos)
        .def("removeRigidBody",&PhysicsEngine::removeRigidBody);

    // ─── AttackType / ComboStep ──────────────────────
    py::enum_<AttackType>(m, "AttackType")
        .value("Light",  AttackType::Light)
        .value("Heavy",  AttackType::Heavy)
        .value("Thrust", AttackType::Thrust)
        .value("Spin",   AttackType::Spin)
        .value("Parry",  AttackType::Parry);

    // ─── HitResult ───────────────────────────────────
    py::class_<HitResult>(m, "HitResult")
        .def(py::init<>())
        .def_readwrite("hit",      &HitResult::hit)
        .def_readwrite("damage",   &HitResult::damage)
        .def_readwrite("knockback",&HitResult::knockback)
        .def_readwrite("staggered",&HitResult::staggered)
        .def_readwrite("effect",   &HitResult::effect);

    // ─── Status and Damage Types ─────────────────────
    py::enum_<StatusType>(m, "StatusType")
        .value("Burn",   StatusType::Burn)
        .value("Freeze", StatusType::Freeze)
        .value("Shock",  StatusType::Shock)
        .value("Slow",   StatusType::Slow)
        .value("Weaken", StatusType::Weaken)
        .value("Stun",   StatusType::Stun);

    py::enum_<DamageType>(m, "DamageType")
        .value("Physical", DamageType::Physical)
        .value("Fire",     DamageType::Fire)
        .value("Ice",      DamageType::Ice)
        .value("Lightning",DamageType::Lightning)
        .value("Arcane",   DamageType::Arcane);

    py::class_<StatusInstance>(m, "StatusInstance")
        .def(py::init<>())
        .def_readwrite("type",      &StatusInstance::type)
        .def_readwrite("remaining", &StatusInstance::remaining)
        .def_readwrite("tickRate",  &StatusInstance::tickRate)
        .def_readwrite("magnitude", &StatusInstance::magnitude);

    py::class_<ResistProfile>(m, "ResistProfile")
        .def(py::init<>())
        .def_readwrite("fire",      &ResistProfile::fire)
        .def_readwrite("ice",       &ResistProfile::ice)
        .def_readwrite("lightning", &ResistProfile::lightning)
        .def_readwrite("arcane",    &ResistProfile::arcane)
        .def_readwrite("immuneFire", &ResistProfile::immuneFire)
        .def_readwrite("immuneIce",  &ResistProfile::immuneIce)
        .def_readwrite("immuneLightning", &ResistProfile::immuneLightning)
        .def_readwrite("immuneArcane", &ResistProfile::immuneArcane);

    // ─── Enemy ───────────────────────────────────────
    py::class_<Enemy>(m, "Enemy")
        .def(py::init<>())
        .def_readwrite("id",      &Enemy::id)
        .def_readwrite("pos",     &Enemy::pos)
        .def_readwrite("vel",     &Enemy::vel)
        .def_readwrite("health",  &Enemy::health)
        .def_readwrite("armor",   &Enemy::armor)
        .def_readwrite("blocking",&Enemy::blocking)
        .def_readwrite("alive",   &Enemy::alive)
        .def_readwrite("statuses",&Enemy::statuses)
        .def_readwrite("resist",  &Enemy::resist);

    // ─── CombatSystem ────────────────────────────────
    py::class_<CombatSystem>(m, "CombatSystem")
        .def(py::init<>())
        .def("startAttack",  &CombatSystem::startAttack)
        .def("update",       &CombatSystem::update)
        .def("tryParry",     &CombatSystem::tryParry)
        .def("applyBlock",   &CombatSystem::applyBlock)
        .def("isAttacking",  &CombatSystem::isAttacking);

    // ─── ParkourAction ───────────────────────────────
    py::enum_<ParkourAction>(m, "ParkourAction")
        .value("None",       ParkourAction::None)
        .value("WallRun",    ParkourAction::WallRun)
        .value("WallJump",   ParkourAction::WallJump)
        .value("Vault",      ParkourAction::Vault)
        .value("LedgeGrab",  ParkourAction::LedgeGrab)
        .value("LedgeClimb", ParkourAction::LedgeClimb)
        .value("Roll",       ParkourAction::Roll)
        .value("Slide",      ParkourAction::Slide)
        .value("AirDash",    ParkourAction::AirDash);

    // ─── ParkourState ────────────────────────────────
    py::class_<ParkourState>(m, "ParkourState")
        .def(py::init<>())
        .def_readwrite("action",    &ParkourState::action)
        .def_readwrite("wallNormal",&ParkourState::wallNormal)
        .def_readwrite("ledgePos",  &ParkourState::ledgePos)
        .def_readwrite("timer",     &ParkourState::timer)
        .def_readwrite("airDashes", &ParkourState::airDashes)
        .def_readwrite("canAirDash",&ParkourState::canAirDash);

    // ─── ParkourSystem ───────────────────────────────
    py::class_<ParkourSystem>(m, "ParkourSystem")
        .def(py::init<>())
        .def("update",       &ParkourSystem::update)
        .def("tryWallRun",   &ParkourSystem::tryWallRun)
        .def("tryVault",     &ParkourSystem::tryVault)
        .def("tryLedgeGrab", &ParkourSystem::tryLedgeGrab)
        .def("tryRoll",      &ParkourSystem::tryRoll)
        .def("tryAirDash",   &ParkourSystem::tryAirDash)
        .def("doWallJump",   &ParkourSystem::doWallJump)
        .def("getAnimState", &ParkourSystem::getAnimState)
        .def("isInParkour",  &ParkourSystem::isInParkour);

    // ─── SpellType ───────────────────────────────────
    py::enum_<SpellType>(m, "SpellType")
        .value("Fireball",     SpellType::Fireball)
        .value("LightningBolt",SpellType::LightningBolt)
        .value("IceShards",    SpellType::IceShards)
        .value("ForceWave",    SpellType::ForceWave)
        .value("HealingAura",  SpellType::HealingAura)
        .value("PhaseStep",    SpellType::PhaseStep)
        .value("MeteorStrike", SpellType::MeteorStrike)
        .value("ArcaneMissile",SpellType::ArcaneMissile)
        .value("ChainLightning",SpellType::ChainLightning)
        .value("Blizzard",     SpellType::Blizzard)
        .value("BlackHole",    SpellType::BlackHole);

    // ─── SpellEffect ─────────────────────────────────
    py::class_<SpellEffect>(m, "SpellEffect")
        .def(py::init<>())
        .def_readwrite("type",        &SpellEffect::type)
        .def_readwrite("pos",         &SpellEffect::pos)
        .def_readwrite("destination", &SpellEffect::destination)
        .def_readwrite("normal",      &SpellEffect::normal)
        .def_readwrite("scale",       &SpellEffect::scale)
        .def_readwrite("radius",      &SpellEffect::radius)
        .def_readwrite("damage",      &SpellEffect::damage)
        .def_readwrite("particleTag", &SpellEffect::particleTag)
        .def_readwrite("soundTag",    &SpellEffect::soundTag);

    // ─── MagicSystem ─────────────────────────────────
    py::class_<MagicSystem>(m, "MagicSystem")
        .def(py::init<>())
        .def("castSpell",   &MagicSystem::castSpell)
        .def("update",      [](MagicSystem& self, float dt,
                                std::vector<Enemy>& enemies,
                                py::function onHit) {
            self.update(dt, enemies, [&](const SpellEffect& fx){ onHit(fx); });
        })
        .def("canCast",     &MagicSystem::canCast)
        .def("getCooldown", &MagicSystem::getCooldown);

    py::class_<EnemyRuntimeContext>(m, "EnemyRuntimeContext")
        .def(py::init<>())
        .def_readwrite("dt",         &EnemyRuntimeContext::dt)
        .def_readwrite("gameTime",   &EnemyRuntimeContext::gameTime)
        .def_readwrite("playerPos",  &EnemyRuntimeContext::playerPos);

    py::class_<EnemyRuntimeUnit>(m, "EnemyRuntimeUnit")
        .def(py::init<>())
        .def_readwrite("id",              &EnemyRuntimeUnit::id)
        .def_readwrite("kind",            &EnemyRuntimeUnit::kind)
        .def_readwrite("alive",           &EnemyRuntimeUnit::alive)
        .def_readwrite("actorPos",        &EnemyRuntimeUnit::actorPos)
        .def_readwrite("currentHeading",  &EnemyRuntimeUnit::currentHeading)
        .def_readwrite("runSpeed",        &EnemyRuntimeUnit::runSpeed)
        .def_readwrite("attackRange",     &EnemyRuntimeUnit::attackRange)
        .def_readwrite("aggroRange",      &EnemyRuntimeUnit::aggroRange)
        .def_readwrite("disengageHold",   &EnemyRuntimeUnit::disengageHold)
        .def_readwrite("engagedUntil",    &EnemyRuntimeUnit::engagedUntil)
        .def_readwrite("isEngaged",       &EnemyRuntimeUnit::isEngaged)
        .def_readwrite("state",           &EnemyRuntimeUnit::state)
        .def_readwrite("stateLock",       &EnemyRuntimeUnit::stateLock)
        .def_readwrite("attackCooldown",  &EnemyRuntimeUnit::attackCooldown)
        .def_readwrite("phaseSpeedMul",   &EnemyRuntimeUnit::phaseSpeedMul)
        .def_readwrite("groundZ",         &EnemyRuntimeUnit::groundZ)
        .def_readwrite("groundOffset",    &EnemyRuntimeUnit::groundOffset)
        .def_readwrite("hoverHeight",     &EnemyRuntimeUnit::hoverHeight)
        .def_readwrite("desiredHeading",  &EnemyRuntimeUnit::desiredHeading)
        .def_readwrite("desiredState",    &EnemyRuntimeUnit::desiredState)
        .def_readwrite("targetDistance",  &EnemyRuntimeUnit::targetDistance)
        .def_readwrite("moving",          &EnemyRuntimeUnit::moving);

    py::class_<EnemyRuntimeSystem>(m, "EnemyRuntimeSystem")
        .def(py::init<>())
        .def("updateUnits", &EnemyRuntimeSystem::updateUnits);

    // ─── WaterSimulation ─────────────────────────────
    py::class_<WaterSimulation>(m, "WaterSimulation")
        .def(py::init<int,float>(), py::arg("gridSize")=64, py::arg("worldSize")=40.f)
        .def("update",           &WaterSimulation::update)
        .def("getHeightAt",      &WaterSimulation::getHeightAt)
        .def("getNormalAt",      &WaterSimulation::getNormalAt)
        .def("applySwimForces",  &WaterSimulation::applySwimForces)
        .def("splash",           &WaterSimulation::splash)
        .def("getVertexBuffer",  &WaterSimulation::getVertexBuffer)
        .def("getIndexBuffer",   &WaterSimulation::getIndexBuffer)
        .def("gridSize",         &WaterSimulation::gridSize)
        .def("vertCount",        &WaterSimulation::vertCount)
        .def("indexCount",       &WaterSimulation::indexCount);

    // ─── AnimLayer ───────────────────────────────────
    py::class_<AnimLayer>(m, "AnimLayer")
        .def_readwrite("name",   &AnimLayer::name)
        .def_readwrite("weight", &AnimLayer::weight)
        .def_readwrite("speed",  &AnimLayer::speed);

    // ─── AnimationBlender ────────────────────────────
    py::class_<AnimationBlender>(m, "AnimationBlender")
        .def(py::init<>())
        .def("update",          &AnimationBlender::update)
        .def("getLayers",       &AnimationBlender::getLayers)
        .def("consumeFootstep", &AnimationBlender::consumeFootstep);

    py::class_<NpcRuntimeContext>(m, "NpcRuntimeContext")
        .def(py::init<>())
        .def_readwrite("dt",         &NpcRuntimeContext::dt)
        .def_readwrite("weather",    &NpcRuntimeContext::weather)
        .def_readwrite("phase",      &NpcRuntimeContext::phase)
        .def_readwrite("isNight",    &NpcRuntimeContext::isNight)
        .def_readwrite("visibility", &NpcRuntimeContext::visibility);

    py::class_<NpcRuntimeUnit>(m, "NpcRuntimeUnit")
        .def(py::init<>())
        .def_readwrite("id",                &NpcRuntimeUnit::id)
        .def_readwrite("home",              &NpcRuntimeUnit::home)
        .def_readwrite("target",            &NpcRuntimeUnit::target)
        .def_readwrite("actorPos",          &NpcRuntimeUnit::actorPos)
        .def_readwrite("baseWalkSpeed",     &NpcRuntimeUnit::baseWalkSpeed)
        .def_readwrite("walkSpeed",         &NpcRuntimeUnit::walkSpeed)
        .def_readwrite("baseWanderRadius",  &NpcRuntimeUnit::baseWanderRadius)
        .def_readwrite("wanderRadius",      &NpcRuntimeUnit::wanderRadius)
        .def_readwrite("baseIdleMin",       &NpcRuntimeUnit::baseIdleMin)
        .def_readwrite("baseIdleMax",       &NpcRuntimeUnit::baseIdleMax)
        .def_readwrite("idleMin",           &NpcRuntimeUnit::idleMin)
        .def_readwrite("idleMax",           &NpcRuntimeUnit::idleMax)
        .def_readwrite("idleTimer",         &NpcRuntimeUnit::idleTimer)
        .def_readwrite("suspicion",         &NpcRuntimeUnit::suspicion)
        .def_readwrite("alerted",           &NpcRuntimeUnit::alerted)
        .def_readwrite("detectedPlayer",    &NpcRuntimeUnit::detectedPlayer)
        .def_readwrite("role",              &NpcRuntimeUnit::role)
        .def_readwrite("activity",          &NpcRuntimeUnit::activity)
        .def_readwrite("anim",              &NpcRuntimeUnit::anim)
        .def_readwrite("actionRoll",        &NpcRuntimeUnit::actionRoll)
        .def_readwrite("targetAngle",       &NpcRuntimeUnit::targetAngle)
        .def_readwrite("targetDistance01",  &NpcRuntimeUnit::targetDistance01)
        .def_readwrite("idleReset01",       &NpcRuntimeUnit::idleReset01)
        .def_readwrite("desiredHeading",    &NpcRuntimeUnit::desiredHeading)
        .def_readwrite("desiredPlayRate",   &NpcRuntimeUnit::desiredPlayRate)
        .def_readwrite("desiredAnim",       &NpcRuntimeUnit::desiredAnim)
        .def_readwrite("moving",            &NpcRuntimeUnit::moving)
        .def_readwrite("targetChanged",     &NpcRuntimeUnit::targetChanged);

    py::class_<NpcRuntimeSystem>(m, "NpcRuntimeSystem")
        .def(py::init<>())
        .def("updateUnits", &NpcRuntimeSystem::updateUnits);

    // ─── ParticleVertex ──────────────────────────────
    py::class_<ParticleVertex>(m, "ParticleVertex")
        .def_readwrite("x", &ParticleVertex::x)
        .def_readwrite("y", &ParticleVertex::y)
        .def_readwrite("z", &ParticleVertex::z)
        .def_readwrite("r", &ParticleVertex::r)
        .def_readwrite("g", &ParticleVertex::g)
        .def_readwrite("b", &ParticleVertex::b)
        .def_readwrite("a", &ParticleVertex::a)
        .def_readwrite("size", &ParticleVertex::size);

    // ─── ParticleSystem ──────────────────────────────
    py::class_<ParticleSystem>(m, "ParticleSystem")
        .def(py::init<>())
        .def("update",             &ParticleSystem::update)
        .def("buildVertexBuffer",  &ParticleSystem::buildVertexBuffer)
        .def("aliveCount",         &ParticleSystem::aliveCount)
        .def("burst",              &ParticleSystem::burst)
        .def("killEmitter",        &ParticleSystem::killEmitter)
        .def("setEmitterPos",      &ParticleSystem::setEmitterPos)
        .def("spawnBloodSplat",    &ParticleSystem::spawnBloodSplat)
        .def("spawnFireball",      &ParticleSystem::spawnFireball)
        .def("spawnLightningArc",  &ParticleSystem::spawnLightningArc)
        .def("spawnIceShard",      &ParticleSystem::spawnIceShard)
        .def("spawnHealAura",      &ParticleSystem::spawnHealAura)
        .def("spawnSwordTrail",    &ParticleSystem::spawnSwordTrail)
        .def("spawnWaterSplash",   &ParticleSystem::spawnWaterSplash)
        .def("spawnMagicOrb",      &ParticleSystem::spawnMagicOrb)
        .def("spawnDust",          &ParticleSystem::spawnDust)
        .def("spawnMeteorTail",    &ParticleSystem::spawnMeteorTail);

    // ─── SimTier ──────────────────────────────────────
    py::enum_<SimTier>(m, "SimTier")
        .value("Hero",       SimTier::Hero)
        .value("Active",     SimTier::Active)
        .value("Simplified", SimTier::Simplified)
        .value("Frozen",     SimTier::Frozen);

    // ─── ATT_* flag constants ─────────────────────────
    m.attr("ATT_IN_COMBAT") = ATT_IN_COMBAT;
    m.attr("ATT_RECENT")    = ATT_RECENT;
    m.attr("ATT_QUEST")     = ATT_QUEST;
    m.attr("ATT_IN_AOE")    = ATT_IN_AOE;
    m.attr("ATT_TARGETED")  = ATT_TARGETED;
    m.attr("ATT_HOMING")    = ATT_HOMING;

    // ─── AttentionObject ─────────────────────────────
    py::class_<AttentionObject>(m, "AttentionObject")
        .def(py::init<>())
        .def_readwrite("id",              &AttentionObject::id)
        .def_readwrite("pos",             &AttentionObject::pos)
        .def_readwrite("radius",          &AttentionObject::radius)
        .def_readwrite("flags",           &AttentionObject::flags)
        .def_readwrite("currentTier",     &AttentionObject::currentTier)
        .def_readwrite("lastChangeTime",  &AttentionObject::lastChangeTime)
        .def_readwrite("priorityScore",   &AttentionObject::priorityScore);

    // ─── TierBudget ──────────────────────────────────
    py::class_<TierBudget>(m, "TierBudget")
        .def(py::init<>())
        .def_readwrite("maxHero",       &TierBudget::maxHero)
        .def_readwrite("maxActive",     &TierBudget::maxActive)
        .def_readwrite("maxSimplified", &TierBudget::maxSimplified);

    // ─── AttentionManager ────────────────────────────
    py::class_<AttentionManager>(m, "AttentionManager")
        .def(py::init<float, float, float>(),
             py::arg("maxDist")    = 120.f,
             py::arg("dotMin")     = 0.20f,
             py::arg("hysteresis") = 0.45f)
        .def("setObjects",      &AttentionManager::setObjects)
        .def("update",          &AttentionManager::update)
        .def("getTierChanges",  &AttentionManager::getTierChanges)
        .def("getPrewarmIds",   &AttentionManager::getPrewarmIds)
        .def("getObjects",      &AttentionManager::getObjects)
        .def("setFlags",        &AttentionManager::setFlags)
        .def("clearFlags",      &AttentionManager::clearFlags);
}
