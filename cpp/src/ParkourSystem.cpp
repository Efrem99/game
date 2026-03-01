#include "ParkourSystem.h"
#include <cmath>
#include <algorithm>

ParkourSystem::ParkourSystem() {}

void ParkourSystem::update(CharacterState& cs, ParkourState& ps,
                            PhysicsEngine& phys, float dt,
                            bool jumpHeld, bool moveHeld, const Vec3& moveDir) {
    switch (ps.action) {
        case ParkourAction::WallRun:  tickWallRun(cs, ps, phys, dt, jumpHeld); break;
        case ParkourAction::LedgeGrab:
        case ParkourAction::LedgeClimb: tickLedge(cs, ps, dt, jumpHeld); break;
        case ParkourAction::Roll:     tickRoll(cs, ps, dt);    break;
        case ParkourAction::AirDash:  tickAirDash(cs, ps, dt); break;
        default: break;
    }
}

bool ParkourSystem::tryWallRun(CharacterState& cs, ParkourState& ps, PhysicsEngine& phys) {
    if (cs.grounded || cs.inWater) return false;
    if (ps.action == ParkourAction::WallRun) return false;

    // Raycast sideways to detect a wallrun surface
    Vec3 right = cs.facingDir.cross({0,0,1}).normalized();

    Vec3 hitPos, hitNorm;
    bool hitL = phys.raycast(cs.position, {-right.x,-right.y,0}, _wallDetectRadius, hitPos, hitNorm);
    bool hitR = phys.raycast(cs.position, { right.x, right.y,0}, _wallDetectRadius, hitPos, hitNorm);

    if (!hitL && !hitR) return false;

    ps.action     = ParkourAction::WallRun;
    ps.wallNormal = hitNorm;
    ps.timer      = 0.f;
    ps.duration   = WALL_RUN_MAXTIME;
    cs.onWall     = true;
    cs.velocity.z = 0.f;
    return true;
}

bool ParkourSystem::tryVault(CharacterState& cs, ParkourState& ps, PhysicsEngine& phys) {
    Vec3 hitPos, hitNorm;
    Vec3 fwd = cs.facingDir;
    bool hit = phys.raycast(cs.position + Vec3{0,0,0.8f}, fwd, _vaultDetectDist, hitPos, hitNorm);
    if (!hit) return false;

    ps.action   = ParkourAction::Vault;
    ps.timer    = 0.f;
    ps.duration = 0.45f;

    // Push over the obstacle
    cs.velocity = fwd * VAULT_SPEED;
    cs.velocity.z = 5.5f;
    cs.grounded = false;
    return true;
}

bool ParkourSystem::tryLedgeGrab(CharacterState& cs, ParkourState& ps, PhysicsEngine& phys) {
    if (cs.velocity.z >= 0.f) return false;  // only grabbing while falling

    Vec3 hitPos, hitNorm;
    bool hit = phys.raycast(
        cs.position + Vec3{0,0,LEDGE_REACH},
        cs.facingDir,
        0.9f,
        hitPos, hitNorm
    );
    if (!hit) return false;

    ps.action   = ParkourAction::LedgeGrab;
    ps.ledgePos = hitPos;
    ps.timer    = 0.f;
    ps.duration = 10.f;  // hold until jump or climb

    cs.velocity   = {0,0,0};
    cs.position.z = hitPos.z - LEDGE_REACH;
    cs.grounded   = false;
    return true;
}

bool ParkourSystem::tryRoll(CharacterState& cs, ParkourState& ps) {
    if (!cs.grounded) return false;
    if (cs.stamina < 15.f) return false;
    cs.stamina -= 15.f;

    ps.action   = ParkourAction::Roll;
    ps.timer    = 0.f;
    ps.duration = ROLL_DUR;

    cs.velocity.x = cs.facingDir.x * ROLL_SPEED;
    cs.velocity.y = cs.facingDir.y * ROLL_SPEED;
    return true;
}

bool ParkourSystem::tryAirDash(CharacterState& cs, ParkourState& ps, const Vec3& dir) {
    if (!ps.canAirDash || ps.airDashes >= ps.maxAirDashes) return false;
    if (cs.grounded || cs.inWater) return false;
    if (cs.stamina < 20.f) return false;
    cs.stamina -= 20.f;

    ps.action   = ParkourAction::AirDash;
    ps.timer    = 0.f;
    ps.duration = AIR_DASH_DUR;
    ps.airDashes++;

    Vec3 d = dir.normalized();
    cs.velocity = d * AIR_DASH_SPEED;
    return true;
}

void ParkourSystem::doWallJump(CharacterState& cs, ParkourState& ps) {
    if (ps.action != ParkourAction::WallRun && !cs.onWall) return;
    Vec3 jumpDir = ps.wallNormal * 0.7f;
    jumpDir.z = 1.0f;
    cs.velocity = jumpDir.normalized() * 11.f;
    ps.action   = ParkourAction::None;
    cs.onWall   = false;
    ps.airDashes = 0;  // reset air dashes after wall jump
}

// ─── tick helpers ────────────────────────────────

void ParkourSystem::tickWallRun(CharacterState& cs, ParkourState& ps,
                                  PhysicsEngine& phys, float dt, bool jumpHeld) {
    ps.timer += dt;
    if (ps.timer > ps.duration || cs.grounded) {
        ps.action = ParkourAction::None;
        cs.onWall = false;
        return;
    }

    // Reduced gravity while wall running
    cs.velocity.z -= WALL_GRAVITY * dt;

    // Run along wall
    Vec3 along = ps.wallNormal.cross({0,0,1}).normalized();
    cs.velocity.x = along.x * WALL_RUN_SPEED;
    cs.velocity.y = along.y * WALL_RUN_SPEED;

    if (!jumpHeld) ps.action = ParkourAction::None;
}

void ParkourSystem::tickLedge(CharacterState& cs, ParkourState& ps, float dt, bool jumpHeld) {
    cs.velocity = {0,0,0};  // hang

    ps.timer += dt;
    if (!jumpHeld) return;  // wait for jump

    // Climb up
    ps.action = ParkourAction::LedgeClimb;
    cs.velocity = {cs.facingDir.x * 3.f, cs.facingDir.y * 3.f, 5.f};
    ps.timer = ps.duration;  // done
    ps.action = ParkourAction::None;
    cs.grounded = false;
}

void ParkourSystem::tickRoll(CharacterState& cs, ParkourState& ps, float dt) {
    ps.timer += dt;
    if (ps.timer >= ps.duration) {
        ps.action = ParkourAction::None;
        // Decelerate
        cs.velocity.x *= 0.3f;
        cs.velocity.y *= 0.3f;
    }
}

void ParkourSystem::tickAirDash(CharacterState& cs, ParkourState& ps, float dt) {
    ps.timer += dt;
    if (ps.timer >= ps.duration) {
        ps.action = ParkourAction::None;
        cs.velocity.x *= 0.4f;
        cs.velocity.y *= 0.4f;
    }
}

std::string ParkourSystem::getAnimState(const ParkourState& ps) const {
    switch (ps.action) {
        case ParkourAction::WallRun:    return "wall_run";
        case ParkourAction::Vault:      return "vault";
        case ParkourAction::LedgeGrab:  return "ledge_hang";
        case ParkourAction::LedgeClimb: return "ledge_climb";
        case ParkourAction::Roll:       return "roll";
        case ParkourAction::AirDash:    return "air_dash";
        default:                        return "none";
    }
}

bool ParkourSystem::isInParkour(const ParkourState& ps) const {
    return ps.action != ParkourAction::None;
}
