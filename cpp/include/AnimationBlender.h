#pragma once
#include "PhysicsEngine.h"
#include "ParkourSystem.h"
#include "CombatSystem.h"
#include <string>
#include <unordered_map>
#include <vector>

// ───────────────────────────────────────────────
// One layer of animation with its weight
// ───────────────────────────────────────────────
struct AnimLayer {
    std::string name;
    float       weight  = 0.f;
    float       speed   = 1.f;
    float       time    = 0.f;
    bool        loop    = true;
};

// ───────────────────────────────────────────────
// Procedural bone override
// (e.g. head look-at, arm aim direction)
// ───────────────────────────────────────────────
struct BoneOverride {
    std::string boneName;
    Vec3        targetDir;   // world-space
    float       weight = 1.f;
};

// ───────────────────────────────────────────────
// AnimationBlender
// Computes which Panda3D animations to blend +
// which procedural overrides to apply.
// Python reads the result and calls setControlEffect / expose_joint.
// ───────────────────────────────────────────────
class AnimationBlender {
public:
    AnimationBlender();

    // Call each frame to update blend weights
    void update(const CharacterState& cs,
                const ParkourState&   ps,
                const CombatSystem&   combat,
                float dt);

    // Get layers for Python to apply to Actor
    const std::vector<AnimLayer>& getLayers() const { return _layers; }

    // Procedural overrides
    const std::vector<BoneOverride>& getOverrides() const { return _overrides; }

    // Footstep timing for sound
    bool consumeFootstep();

    // IK target for sword hand (world pos)
    Vec3 getSwordIKTarget() const { return _swordIK; }
    Vec3 getShieldIKTarget()const { return _shieldIK; }

private:
    std::vector<AnimLayer>   _layers;
    std::vector<BoneOverride>_overrides;
    bool  _footstepPending = false;
    float _walkPhase       = 0.f;
    Vec3  _swordIK         {};
    Vec3  _shieldIK        {};

    void  setLayerWeight(const std::string& name, float w, float spd = 1.f, bool loop = true);
    float smooth(float current, float target, float rate, float dt);
    std::unordered_map<std::string,float> _weights;
};
