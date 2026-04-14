#include "EnemyRuntimeSystem.h"

#include <algorithm>
#include <cmath>
#include <cctype>

namespace {
constexpr float kMoveThreshold = 0.18f;
constexpr float kHeadingRadToDeg = 57.29577951308232f;
constexpr float kTurnSpeedDegPerSec = 130.0f;

std::string toLower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

bool isFiniteVec3(const Vec3& value) {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

Vec3 sanitizeVec3(const Vec3& value, const Vec3& fallback) {
    return isFiniteVec3(value) ? value : fallback;
}

float normalizeDegrees(float value, float fallback = 0.0f) {
    if (!std::isfinite(value)) {
        return fallback;
    }
    float normalized = std::fmod(value + 180.0f, 360.0f);
    if (normalized < 0.0f) {
        normalized += 360.0f;
    }
    return normalized - 180.0f;
}
} // namespace

float EnemyRuntimeSystem::clampFinite(float value, float fallback) {
    return std::isfinite(value) ? value : fallback;
}

bool EnemyRuntimeSystem::isHoveringKind(const std::string& kind) {
    const std::string token = toLower(kind);
    return token == "fire_elemental" || token == "shadow";
}

std::vector<EnemyRuntimeUnit> EnemyRuntimeSystem::updateUnits(
    const std::vector<EnemyRuntimeUnit>& units,
    const EnemyRuntimeContext& context
) const {
    std::vector<EnemyRuntimeUnit> result = units;
    const float dt = std::max(0.0f, clampFinite(context.dt, 0.0f));
    const float gameTime = std::max(0.0f, clampFinite(context.gameTime, 0.0f));
    const Vec3 safePlayerPos = sanitizeVec3(context.playerPos, Vec3{});

    for (auto& unit : result) {
        const Vec3 originalPos = sanitizeVec3(unit.actorPos, Vec3{});
        unit.actorPos = originalPos;
        unit.moving = false;
        unit.currentHeading = normalizeDegrees(clampFinite(unit.currentHeading, 0.0f), 0.0f);
        unit.desiredHeading = unit.currentHeading;
        unit.desiredState = unit.state.empty() ? "idle" : unit.state;
        unit.engagedUntil = clampFinite(unit.engagedUntil, 0.0f);

        const float baseGroundZ = clampFinite(unit.groundZ, unit.actorPos.z);
        const float groundOffset = std::max(0.0f, clampFinite(unit.groundOffset, 1.2f));
        const float hoverHeight = std::max(0.0f, clampFinite(unit.hoverHeight, 1.2f));
        if (isHoveringKind(unit.kind)) {
            unit.actorPos.z = baseGroundZ + groundOffset + hoverHeight + (std::sin(gameTime * 2.4f) * 0.2f);
        } else {
            unit.actorPos.z = baseGroundZ + groundOffset;
        }
        if (!isFiniteVec3(unit.actorPos)) {
            unit.actorPos = originalPos;
        }

        if (!unit.alive) {
            unit.desiredState = "dead";
            unit.isEngaged = false;
            unit.targetDistance = 0.0f;
            continue;
        }

        Vec3 toPlayer = safePlayerPos - unit.actorPos;
        if (!isFiniteVec3(toPlayer)) {
            toPlayer = Vec3{};
        }
        toPlayer.z = 0.0f;
        const float distance = clampFinite(toPlayer.len(), 0.0f);
        unit.targetDistance = distance;

        const float aggroRange = std::max(0.0f, clampFinite(unit.aggroRange, 18.0f));
        const float disengageHold = std::max(0.0f, clampFinite(unit.disengageHold, 4.0f));
        if (distance <= aggroRange) {
            unit.engagedUntil = std::max(unit.engagedUntil, gameTime + disengageHold);
        }
        unit.isEngaged = gameTime < unit.engagedUntil;

        if (!unit.isEngaged) {
            unit.desiredState = "idle";
            continue;
        }

        if (distance > 1e-6f) {
            const Vec3 dir = toPlayer.normalized();
            const float desiredHeading = std::atan2(dir.x, dir.y) * kHeadingRadToDeg;
            const float currentHeading = normalizeDegrees(clampFinite(unit.currentHeading, desiredHeading), desiredHeading);
            float delta = std::fmod((desiredHeading - currentHeading + 180.0f), 360.0f);
            if (delta < 0.0f) {
                delta += 360.0f;
            }
            delta -= 180.0f;
            const float maxTurn = kTurnSpeedDegPerSec * dt;
            unit.desiredHeading = normalizeDegrees(currentHeading + std::max(-maxTurn, std::min(maxTurn, delta)), currentHeading);
        }

        const float attackRange = std::max(0.0f, clampFinite(unit.attackRange, 2.5f));
        const bool attackReady = clampFinite(unit.stateLock, 0.0f) <= 0.0f
            && clampFinite(unit.attackCooldown, 0.0f) <= 0.0f;

        if (attackReady && distance <= attackRange) {
            unit.desiredState = "telegraph";
            continue;
        }

        if (distance > kMoveThreshold) {
            Vec3 dir = toPlayer.normalized();
            const float runSpeed = std::max(0.1f, clampFinite(unit.runSpeed, 4.0f));
            const float phaseSpeedMul = std::max(0.2f, clampFinite(unit.phaseSpeedMul, 1.0f));
            const float maxStep = runSpeed * phaseSpeedMul * dt;
            const float step = std::min(distance, maxStep);
            unit.actorPos += dir * step;
            if (isHoveringKind(unit.kind)) {
                unit.actorPos.z = baseGroundZ + groundOffset + hoverHeight + (std::sin(gameTime * 2.4f) * 0.2f);
            } else {
                unit.actorPos.z = baseGroundZ + groundOffset;
            }
            if (!isFiniteVec3(unit.actorPos)) {
                unit.actorPos = originalPos;
            }
            unit.moving = true;
            unit.desiredState = "chase";
            continue;
        }

        unit.desiredState = "idle";
    }

    return result;
}
