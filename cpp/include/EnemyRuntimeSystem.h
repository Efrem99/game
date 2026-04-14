#pragma once

#include "PhysicsEngine.h"

#include <string>
#include <vector>

struct EnemyRuntimeContext {
    float dt = 0.0f;
    float gameTime = 0.0f;
    Vec3 playerPos;
};

struct EnemyRuntimeUnit {
    int id = 0;
    std::string kind;
    bool alive = true;

    Vec3 actorPos;
    float currentHeading = 0.0f;

    float runSpeed = 4.0f;
    float attackRange = 2.5f;
    float aggroRange = 18.0f;
    float disengageHold = 4.0f;
    float engagedUntil = 0.0f;
    bool isEngaged = false;

    std::string state;
    float stateLock = 0.0f;
    float attackCooldown = 0.0f;
    float phaseSpeedMul = 1.0f;

    float groundZ = 0.0f;
    float groundOffset = 1.2f;
    float hoverHeight = 1.2f;

    float desiredHeading = 0.0f;
    std::string desiredState = "idle";
    float targetDistance = 0.0f;
    bool moving = false;
};

class EnemyRuntimeSystem {
public:
    std::vector<EnemyRuntimeUnit> updateUnits(
        const std::vector<EnemyRuntimeUnit>& units,
        const EnemyRuntimeContext& context
    ) const;

private:
    static float clampFinite(float value, float fallback);
    static bool isHoveringKind(const std::string& kind);
};
