#include "AttentionManager.h"
#include <algorithm>
#include <cmath>

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────
namespace {
inline float clamp01(float x) { return x < 0.f ? 0.f : (x > 1.f ? 1.f : x); }

// Forced minimum tier from flags (independent of scoring)
SimTier forcedMinTier(uint32_t flags) {
    if (flags & (ATT_IN_COMBAT | ATT_TARGETED | ATT_HOMING))
        return SimTier::Active;
    if (flags & (ATT_QUEST | ATT_IN_AOE | ATT_RECENT))
        return SimTier::Active;
    return SimTier::Frozen; // no forced minimum
}
} // anonymous namespace

// ─────────────────────────────────────────────────────────────────────────
// Constructor
// ─────────────────────────────────────────────────────────────────────────
AttentionManager::AttentionManager(float maxDist, float dotMin, float hysteresis)
    : _maxDist(maxDist), _dotMin(dotMin), _hysteresis(hysteresis)
{}

// ─────────────────────────────────────────────────────────────────────────
// setObjects
// ─────────────────────────────────────────────────────────────────────────
void AttentionManager::setObjects(std::vector<AttentionObject> objects) {
    _objects = std::move(objects);
}

// ─────────────────────────────────────────────────────────────────────────
// setFlags / clearFlags
// ─────────────────────────────────────────────────────────────────────────
void AttentionManager::setFlags(int id, uint32_t flags) {
    for (auto& o : _objects) {
        if (o.id == id) { o.flags |= flags; return; }
    }
}
void AttentionManager::clearFlags(int id, uint32_t flags) {
    for (auto& o : _objects) {
        if (o.id == id) { o.flags &= ~flags; return; }
    }
}

// ─────────────────────────────────────────────────────────────────────────
// computePriority
// Score range: roughly 0..1 (plus flag boosts can push above 1)
// ─────────────────────────────────────────────────────────────────────────
float AttentionManager::computePriority(const AttentionObject& o,
                                        Vec3 camPos, Vec3 camFwd,
                                        float turnSpeed01) const
{
    Vec3 toObj = { o.pos.x - camPos.x,
                   o.pos.y - camPos.y,
                   o.pos.z - camPos.z };

    float dist = toObj.len();
    if (dist > _maxDist) return 0.f;

    float distScore = clamp01(1.f - (dist / _maxDist));

    // Angle score: 1 = centre, 0 = at _dotMin, negative = behind
    float dot = (dist > 1e-4f) ? camFwd.dot(toObj.normalized()) : 1.f;
    float angleScore = clamp01((dot - _dotMin) / (1.f - _dotMin));

    // Predictive boost: if camera is rotating quickly toward the object,
    // pre-elevate it even before it enters the frustum centre.
    float edgeFactor = 1.f - angleScore;          // high when object is on periphery
    float predictBoost = clamp01(turnSpeed01) * edgeFactor * 0.15f;

    float base = distScore * 0.55f + angleScore * 0.35f + predictBoost;

    // Flag boosts
    float flagBoost = 0.f;
    if (o.flags & ATT_IN_COMBAT) flagBoost += 0.35f;
    if (o.flags & ATT_TARGETED)  flagBoost += 0.50f;
    if (o.flags & ATT_HOMING)    flagBoost += 0.40f;
    if (o.flags & ATT_IN_AOE)    flagBoost += 0.30f;
    if (o.flags & ATT_RECENT)    flagBoost += 0.25f;
    if (o.flags & ATT_QUEST)     flagBoost += 0.40f;

    return base + flagBoost;
}

// ─────────────────────────────────────────────────────────────────────────
// priorityToTier  (respects budgets and forced minimums)
// ─────────────────────────────────────────────────────────────────────────
SimTier AttentionManager::priorityToTier(float priority, uint32_t flags,
                                          int& heroUsed, int& activeUsed, int& simUsed,
                                          const TierBudget& budget) const
{
    SimTier forced = forcedMinTier(flags);

    auto tryAssign = [&](SimTier desired) -> SimTier {
        // enforce budget
        if (desired == SimTier::Hero) {
            if (heroUsed < budget.maxHero) { ++heroUsed; return SimTier::Hero; }
            desired = SimTier::Active;
        }
        if (desired == SimTier::Active) {
            if (activeUsed < budget.maxActive) { ++activeUsed; return SimTier::Active; }
            desired = SimTier::Simplified;
        }
        if (desired == SimTier::Simplified) {
            if (simUsed < budget.maxSimplified) { ++simUsed; return SimTier::Simplified; }
        }
        return SimTier::Frozen;
    };

    SimTier scoredTier;
    if      (priority >= 0.75f) scoredTier = SimTier::Hero;
    else if (priority >= 0.40f) scoredTier = SimTier::Active;
    else if (priority >= 0.15f) scoredTier = SimTier::Simplified;
    else                        scoredTier = SimTier::Frozen;

    // Pick the higher-quality (lower enum value) of scored vs forced
    SimTier desired = (scoredTier < forced || forced == SimTier::Frozen)
                      ? scoredTier : forced;

    return tryAssign(desired);
}

// ─────────────────────────────────────────────────────────────────────────
// update — main tick
// ─────────────────────────────────────────────────────────────────────────
void AttentionManager::update(Vec3 camPos, Vec3 camFwd, float camAngSpeed,
                               float gameTime, TierBudget budget)
{
    _tierChanges.clear();
    _prewarmIds.clear();

    float turnSpeed01 = clamp01(camAngSpeed / 2.5f); // normalise ~2.5 rad/s = 1.0

    // 1. Score all objects
    for (auto& o : _objects) {
        o.priorityScore = computePriority(o, camPos, camFwd, turnSpeed01);
    }

    // 2. Sort by priority descending
    std::sort(_objects.begin(), _objects.end(),
              [](const AttentionObject& a, const AttentionObject& b){
                  return a.priorityScore > b.priorityScore;
              });

    // 3. Assign tiers with budget counting
    int heroUsed = 0, activeUsed = 0, simUsed = 0;
    for (auto& o : _objects) {
        SimTier newTier = priorityToTier(o.priorityScore, o.flags,
                                         heroUsed, activeUsed, simUsed, budget);

        // Hysteresis: only allow downgrade after cooldown
        bool upgrading = (newTier < o.currentTier); // lower enum = better
        bool downgrading = (newTier > o.currentTier);

        if (downgrading) {
            if (gameTime - o.lastChangeTime < _hysteresis) {
                newTier = o.currentTier; // keep current, too soon to downgrade
            }
        }

        if (newTier != o.currentTier) {
            _tierChanges.emplace_back(o.id, static_cast<int>(newTier));
            o.currentTier = newTier;
            o.lastChangeTime = gameTime;
        }

        // Prewarm: if object is close to threshold for upgrading, request preload
        if (o.currentTier == SimTier::Simplified && o.priorityScore > 0.35f) {
            _prewarmIds.push_back(o.id);
        }
    }
}
