#pragma once

#include "PhysicsEngine.h"

#include <string>
#include <vector>

struct NpcRuntimeContext {
    float dt = 0.0f;
    std::string weather;
    std::string phase;
    bool isNight = false;
    float visibility = 1.0f;
};

struct NpcRuntimeUnit {
    int id = 0;

    Vec3 home;
    Vec3 target;
    Vec3 actorPos;

    float baseWalkSpeed = 1.5f;
    float walkSpeed = 1.5f;
    float baseWanderRadius = 3.0f;
    float wanderRadius = 3.0f;
    float baseIdleMin = 1.5f;
    float baseIdleMax = 4.2f;
    float idleMin = 1.5f;
    float idleMax = 4.2f;
    float idleTimer = 1.0f;

    float suspicion = 0.0f;
    bool alerted = false;
    bool detectedPlayer = false;

    std::string role;
    std::string activity;
    std::string anim;

    float actionRoll = 1.0f;
    float targetAngle = 0.0f;
    float targetDistance01 = 0.0f;
    float idleReset01 = 0.5f;

    float desiredHeading = 0.0f;
    float desiredPlayRate = 1.0f;
    std::string desiredAnim = "idle";
    bool moving = false;
    bool targetChanged = false;
};

class NpcRuntimeSystem {
public:
    std::vector<NpcRuntimeUnit> updateUnits(
        const std::vector<NpcRuntimeUnit>& units,
        const NpcRuntimeContext& context
    ) const;

private:
    struct MotionModifiers {
        float speedScale = 1.0f;
        float idleScale = 1.0f;
        float wanderScale = 1.0f;
        bool forceHome = false;
    };

    static MotionModifiers computeMotionModifiers(
        const NpcRuntimeUnit& unit,
        const NpcRuntimeContext& context
    );
    static bool isGuardRole(const std::string& role);
    static void pickNextTarget(NpcRuntimeUnit& unit);
    static float clamp01(float value);
    static float clampFinite(float value, float fallback);
    static float remapIdleReset(const NpcRuntimeUnit& unit);
};
