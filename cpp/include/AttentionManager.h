#pragma once
#include "PhysicsEngine.h"
#include <vector>
#include <utility>
#include <cstdint>
#include <limits>

// ─────────────────────────────────────────────────────────────────────────
// SimTier — simulation fidelity level assigned to each entity
// ─────────────────────────────────────────────────────────────────────────
enum class SimTier : uint8_t {
    Hero       = 0,   // Full: anims + AI + FX + physics
    Active     = 1,   // Reduced AI tick-rate, LOD1 mesh
    Simplified = 2,   // Pose-only, no logic
    Frozen     = 3,   // No update; hidden or position-only
};

// ─────────────────────────────────────────────────────────────────────────
// Attention flags — bitfield on each AttentionObject
// ─────────────────────────────────────────────────────────────────────────
constexpr uint32_t ATT_IN_COMBAT = 1u << 0;  // entity is actively fighting
constexpr uint32_t ATT_RECENT    = 1u << 1;  // entity was recently interacted with / hit
constexpr uint32_t ATT_QUEST     = 1u << 2;  // quest-relevant entity (always stay >= Active)
constexpr uint32_t ATT_IN_AOE    = 1u << 3;  // inside an active AoE zone
constexpr uint32_t ATT_TARGETED  = 1u << 4;  // player has locked-on / targeted this entity
constexpr uint32_t ATT_HOMING    = 1u << 5;  // homing spell heading toward this entity

// ─────────────────────────────────────────────────────────────────────────
// Per-object descriptor (updated from Python each frame)
// ─────────────────────────────────────────────────────────────────────────
struct AttentionObject {
    int      id            = -1;
    Vec3     pos;
    float    radius        = 1.0f;  // bounding sphere radius
    uint32_t flags         = 0u;
    SimTier  currentTier   = SimTier::Frozen;
    float    lastChangeTime = -999.f; // for hysteresis
    float    priorityScore = 0.f;   // cached, set by update()
};

// ─────────────────────────────────────────────────────────────────────────
// Budget — how many objects can be assigned to each tier
// ─────────────────────────────────────────────────────────────────────────
struct TierBudget {
    int maxHero       = 8;
    int maxActive     = 24;
    int maxSimplified = 128;
    // Frozen has no upper limit
};

// ─────────────────────────────────────────────────────────────────────────
// AttentionManager
// ─────────────────────────────────────────────────────────────────────────
class AttentionManager {
public:
    // maxDist    — beyond this, objects are always Frozen
    // dotMin     — objects outside this cos-angle from cam forward are less valued
    // hysteresis — seconds an object must stay below threshold before tier downgrade
    explicit AttentionManager(float maxDist       = 120.f,
                              float dotMin        = 0.20f,
                              float hysteresis    = 0.45f);

    // Replace tracked objects (call once per frame before update)
    void setObjects(std::vector<AttentionObject> objects);

    // Main tick:  camPos, camFwd, camAngSpeed in rad/s, elapsed game time
    void update(Vec3 camPos, Vec3 camFwd, float camAngSpeed, float gameTime,
                TierBudget budget);

    // Results (valid after update())
    const std::vector<std::pair<int,int>>& getTierChanges() const { return _tierChanges; }
    const std::vector<int>&                getPrewarmIds()  const { return _prewarmIds;  }

    // Read back current snapshot (for Python loop)
    const std::vector<AttentionObject>&    getObjects()     const { return _objects; }

    // Force-set flags from Python (e.g. AoE events)
    void setFlags(int id, uint32_t flags);
    void clearFlags(int id, uint32_t flags);

private:
    float _maxDist;
    float _dotMin;
    float _hysteresis;

    std::vector<AttentionObject>    _objects;
    std::vector<std::pair<int,int>> _tierChanges;
    std::vector<int>                _prewarmIds;

    float computePriority(const AttentionObject& o,
                          Vec3 camPos, Vec3 camFwd,
                          float turnSpeed01) const;

    SimTier priorityToTier(float priority, uint32_t flags,
                           int& heroUsed, int& activeUsed, int& simUsed,
                           const TierBudget& budget) const;
};
