#include "NpcRuntimeSystem.h"

#include <algorithm>
#include <cmath>
#include <cctype>

namespace {
constexpr float kMoveThreshold = 0.18f;
constexpr float kPi = 3.14159265358979323846f;

std::string toLower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}
} // namespace

float NpcRuntimeSystem::clamp01(float value) {
    if (!std::isfinite(value)) {
        return 0.0f;
    }
    return std::max(0.0f, std::min(1.0f, value));
}

float NpcRuntimeSystem::clampFinite(float value, float fallback) {
    return std::isfinite(value) ? value : fallback;
}

bool NpcRuntimeSystem::isGuardRole(const std::string& role) {
    const std::string token = toLower(role);
    return token.find("guard") != std::string::npos
        || token.find("patrol") != std::string::npos
        || token.find("watch") != std::string::npos
        || token.find("captain") != std::string::npos
        || token.find("knight") != std::string::npos
        || token.find("soldier") != std::string::npos;
}

NpcRuntimeSystem::MotionModifiers NpcRuntimeSystem::computeMotionModifiers(
    const NpcRuntimeUnit& unit,
    const NpcRuntimeContext& context
) {
    const bool guard = isGuardRole(unit.role);
    const std::string weather = toLower(context.weather);
    const std::string phase = toLower(context.phase);
    const std::string activity = toLower(unit.activity);

    MotionModifiers modifiers{};
    modifiers.speedScale = 1.0f;
    modifiers.idleScale = 1.0f;
    modifiers.wanderScale = 1.0f;
    modifiers.forceHome = false;

    if (weather == "rainy" || weather == "stormy") {
        if (guard) {
            modifiers.speedScale *= 0.95f;
            modifiers.wanderScale *= 1.15f;
            modifiers.idleScale *= 0.85f;
        } else {
            modifiers.speedScale *= 0.58f;
            modifiers.wanderScale *= 0.42f;
            modifiers.idleScale *= 1.65f;
            modifiers.forceHome = true;
        }
    } else if (weather == "overcast" && !guard) {
        modifiers.speedScale *= 0.90f;
        modifiers.wanderScale *= 0.84f;
        modifiers.idleScale *= 1.15f;
    }

    if (context.isNight || phase == "night" || phase == "midnight") {
        if (guard) {
            modifiers.speedScale *= 1.12f;
            modifiers.wanderScale *= 1.28f;
            modifiers.idleScale *= 0.80f;
        } else {
            modifiers.speedScale *= 0.62f;
            modifiers.wanderScale *= 0.36f;
            modifiers.idleScale *= 1.35f;
            modifiers.forceHome = true;
        }
    } else if ((phase == "dawn" || phase == "dusk") && !guard) {
        modifiers.speedScale *= 0.90f;
        modifiers.idleScale *= 1.12f;
    }

    if (clampFinite(context.visibility, 1.0f) < 0.45f && !guard) {
        modifiers.speedScale *= 0.84f;
        modifiers.idleScale *= 1.24f;
    }

    const float suspicion = std::max(0.0f, clampFinite(unit.suspicion, 0.0f));
    if (unit.alerted) {
        if (guard) {
            modifiers.speedScale *= 1.22f;
            modifiers.wanderScale *= 1.34f;
            modifiers.idleScale *= 0.72f;
        } else {
            modifiers.speedScale *= 1.08f;
            modifiers.wanderScale *= 0.48f;
            modifiers.idleScale *= 1.15f;
        }
    } else if (suspicion >= 0.35f && guard) {
        modifiers.speedScale *= 1.08f;
        modifiers.wanderScale *= 1.12f;
        modifiers.idleScale *= 0.90f;
    }

    if (activity == "patrol" || activity == "inspect" || activity == "escort") {
        modifiers.speedScale *= 1.14f;
        modifiers.wanderScale *= 1.28f;
        modifiers.idleScale *= 0.82f;
    } else if (activity == "work" || activity == "repair" || activity == "haul") {
        modifiers.speedScale *= 0.90f;
        modifiers.wanderScale *= 1.05f;
        modifiers.idleScale *= 0.92f;
    } else if (activity == "talk" || activity == "rest") {
        modifiers.speedScale *= 0.74f;
        modifiers.wanderScale *= 0.62f;
        modifiers.idleScale *= 1.22f;
    } else if (activity == "shelter" || activity == "panic") {
        modifiers.speedScale *= 0.65f;
        modifiers.wanderScale *= 0.30f;
        modifiers.idleScale *= 1.35f;
        modifiers.forceHome = true;
    }

    modifiers.speedScale = std::max(0.30f, std::min(1.80f, modifiers.speedScale));
    modifiers.idleScale = std::max(0.60f, std::min(2.50f, modifiers.idleScale));
    modifiers.wanderScale = std::max(0.20f, std::min(2.20f, modifiers.wanderScale));
    return modifiers;
}

void NpcRuntimeSystem::pickNextTarget(NpcRuntimeUnit& unit) {
    const float radius = std::max(0.0f, clampFinite(unit.wanderRadius, 0.0f));
    if (radius <= 0.01f) {
        unit.target = unit.home;
        unit.targetChanged = true;
        return;
    }

    const float angle = clampFinite(unit.targetAngle, 0.0f);
    const float distance01 = clamp01(unit.targetDistance01);
    const float minDist = std::min(0.30f, radius);
    const float distance = minDist + (distance01 * (radius - minDist));

    unit.target = Vec3(
        unit.home.x + std::cos(angle) * distance,
        unit.home.y + std::sin(angle) * distance,
        unit.home.z
    );
    unit.targetChanged = true;
}

float NpcRuntimeSystem::remapIdleReset(const NpcRuntimeUnit& unit) {
    const float minIdle = std::max(0.1f, clampFinite(unit.idleMin, 1.5f));
    const float maxIdle = std::max(minIdle, clampFinite(unit.idleMax, minIdle));
    return minIdle + ((maxIdle - minIdle) * clamp01(unit.idleReset01));
}

std::vector<NpcRuntimeUnit> NpcRuntimeSystem::updateUnits(
    const std::vector<NpcRuntimeUnit>& units,
    const NpcRuntimeContext& context
) const {
    std::vector<NpcRuntimeUnit> result = units;
    const float dt = std::max(0.0f, clampFinite(context.dt, 0.0f));

    for (auto& unit : result) {
        unit.targetChanged = false;
        unit.moving = false;
        unit.desiredHeading = 0.0f;
        unit.desiredPlayRate = 1.0f;
        unit.desiredAnim = "idle";

        const MotionModifiers modifiers = computeMotionModifiers(unit, context);

        const float baseSpeed = std::max(0.2f, clampFinite(unit.baseWalkSpeed, unit.walkSpeed));
        unit.walkSpeed = std::max(0.2f, baseSpeed * modifiers.speedScale);

        const float baseRadius = std::max(0.0f, clampFinite(unit.baseWanderRadius, unit.wanderRadius));
        unit.wanderRadius = std::max(0.0f, baseRadius * modifiers.wanderScale);

        const float baseIdleMin = std::max(0.1f, clampFinite(unit.baseIdleMin, unit.idleMin));
        const float baseIdleMax = std::max(baseIdleMin, clampFinite(unit.baseIdleMax, unit.idleMax));
        unit.idleMin = std::max(0.1f, baseIdleMin * modifiers.idleScale);
        unit.idleMax = std::max(unit.idleMin, baseIdleMax * modifiers.idleScale);

        const std::string activity = toLower(unit.activity);
        if (modifiers.forceHome) {
            unit.target = unit.home;
            unit.targetChanged = true;
        }

        if (activity == "talk" || activity == "rest" || activity == "shelter") {
            unit.target = unit.home;
            unit.targetChanged = true;
        } else {
            const float actionRoll = clamp01(unit.actionRoll);
            if ((activity == "work" || activity == "repair") && actionRoll < (dt * 0.12f)) {
                pickNextTarget(unit);
            } else if (
                activity == "patrol"
                || activity == "inspect"
                || activity == "escort"
                || activity == "haul"
            ) {
                if (actionRoll < (dt * 0.20f)) {
                    pickNextTarget(unit);
                }
            }
        }

        Vec3 toTarget = unit.target - unit.actorPos;
        toTarget.z = 0.0f;
        const float distance = toTarget.len();

        if (distance > kMoveThreshold) {
            const Vec3 direction = toTarget.normalized();
            const float step = std::min(distance, unit.walkSpeed * dt);
            unit.actorPos += direction * step;
            unit.desiredHeading = 180.0f - (std::atan2(direction.x, direction.y) * 180.0f / kPi);
            unit.desiredPlayRate = std::max(0.65f, std::min(1.35f, unit.walkSpeed / 1.5f));
            unit.desiredAnim = "walk";
            unit.moving = true;
            unit.idleTimer = remapIdleReset(unit);
            continue;
        }

        unit.idleTimer = clampFinite(unit.idleTimer, unit.idleMin) - dt;
        unit.desiredAnim = "idle";
        if (unit.idleTimer <= 0.0f) {
            pickNextTarget(unit);
            unit.idleTimer = remapIdleReset(unit);
        }
    }

    return result;
}
