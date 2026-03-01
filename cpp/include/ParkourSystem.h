#pragma once
#include "PhysicsEngine.h"
#include <string>

enum class ParkourAction {
    None,
    WallRun,
    WallJump,
    Vault,
    LedgeGrab,
    LedgeClimb,
    Roll,
    Slide,
    AirDash,
};

struct ParkourState {
    ParkourAction action    = ParkourAction::None;
    Vec3          wallNormal{};
    Vec3          ledgePos  {};
    float         timer     = 0.f;
    float         duration  = 0.f;
    int           airDashes = 0;
    int           maxAirDashes = 1;
    bool          canAirDash   = true;
};

class ParkourSystem {
public:
    ParkourSystem();

    // Called every frame – reads intent and updates state
    void update(CharacterState& cs, ParkourState& ps,
                PhysicsEngine& phys, float dt,
                bool jumpHeld, bool moveHeld, const Vec3& moveDir);

    // Trigger checks (called from Python on input events)
    bool tryWallRun   (CharacterState& cs, ParkourState& ps, PhysicsEngine& phys);
    bool tryVault     (CharacterState& cs, ParkourState& ps, PhysicsEngine& phys);
    bool tryLedgeGrab (CharacterState& cs, ParkourState& ps, PhysicsEngine& phys);
    bool tryRoll      (CharacterState& cs, ParkourState& ps);
    bool tryAirDash   (CharacterState& cs, ParkourState& ps, const Vec3& dir);
    void doWallJump   (CharacterState& cs, ParkourState& ps);

    // Info for animation layer
    std::string getAnimState(const ParkourState& ps) const;
    bool        isInParkour (const ParkourState& ps) const;

    // Tuning
    static constexpr float WALL_RUN_SPEED   = 8.5f;
    static constexpr float WALL_RUN_MAXTIME = 2.2f;
    static constexpr float WALL_GRAVITY     = 3.5f;
    static constexpr float VAULT_SPEED      = 6.0f;
    static constexpr float LEDGE_REACH      = 1.2f;
    static constexpr float ROLL_SPEED       = 7.5f;
    static constexpr float ROLL_DUR         = 0.5f;
    static constexpr float AIR_DASH_SPEED   = 14.f;
    static constexpr float AIR_DASH_DUR     = 0.25f;

private:
    void tickWallRun  (CharacterState& cs, ParkourState& ps, PhysicsEngine& phys, float dt, bool jumpHeld);
    void tickLedge    (CharacterState& cs, ParkourState& ps, float dt, bool jumpHeld);
    void tickRoll     (CharacterState& cs, ParkourState& ps, float dt);
    void tickAirDash  (CharacterState& cs, ParkourState& ps, float dt);

    float _wallDetectRadius = 0.6f;
    float _vaultDetectDist  = 1.2f;
};
