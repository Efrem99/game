// AnimationBlender.cpp
#include "AnimationBlender.h"
#include <cmath>
#include <algorithm>

AnimationBlender::AnimationBlender() {
    for (auto& n : {"idle","walk","run","jump","fall","swim",
                    "attack_light","attack_heavy","attack_spin","attack_thrust",
                    "block","roll","wall_run","ledge_hang","ledge_climb","air_dash"}) {
        _layers.push_back({n, 0.f, 1.f, 0.f, true});
        _weights[n] = 0.f;
    }
}

void AnimationBlender::setLayerWeight(const std::string& name, float w, float spd, bool loop) {
    _weights[name] = w;
    for (auto& l : _layers)
        if (l.name == name) { l.weight = w; l.speed = spd; l.loop = loop; return; }
}

float AnimationBlender::smooth(float curr, float target, float rate, float dt) {
    return curr + (target - curr) * std::min(1.f, rate * dt);
}

void AnimationBlender::update(const CharacterState& cs,
                               const ParkourState&   ps,
                               const CombatSystem&   combat,
                               float dt) {
    bool moving    = cs.velocity.x*cs.velocity.x + cs.velocity.y*cs.velocity.y > 0.1f;
    float moveSp   = std::sqrt(cs.velocity.x*cs.velocity.x + cs.velocity.y*cs.velocity.y);
    bool running   = moveSp > 6.f;
    bool swimming  = cs.inWater;
    bool attacking = combat.isAttacking();

    // Reset all
    for (auto& l : _layers) l.weight = 0.f;

    if (swimming) {
        setLayerWeight("swim", 1.f, moveSp > 2.f ? 1.2f : 0.7f);
    } else if (ps.action != ParkourAction::None) {
        std::string anim = "idle";
        switch (ps.action) {
            case ParkourAction::WallRun:    anim = "wall_run";   break;
            case ParkourAction::LedgeGrab:  anim = "ledge_hang"; break;
            case ParkourAction::LedgeClimb: anim = "ledge_climb";break;
            case ParkourAction::Roll:       anim = "roll";       break;
            case ParkourAction::AirDash:    anim = "air_dash";   break;
            default: break;
        }
        setLayerWeight(anim, 1.f, 1.f, false);
    } else if (!cs.grounded) {
        setLayerWeight(cs.velocity.z > 0 ? "jump" : "fall", 1.f, 1.f, true);
    } else {
        if (attacking) {
            std::string atk = "attack_light";
            switch (combat.getCurrentCombo()) {
                case ComboStep::AA:  atk = "attack_heavy"; break;
                case ComboStep::AAA: atk = "attack_spin";  break;
                case ComboStep::AB:  atk = "attack_thrust";break;
                default: break;
            }
            setLayerWeight(atk, 1.f, 1.f, false);
        } else if (moving) {
            if (running) setLayerWeight("run",  1.f, moveSp / 8.f);
            else         setLayerWeight("walk", 1.f, moveSp / 4.5f);
        } else {
            setLayerWeight("idle", 1.f);
        }

        // Additive: block
        if (cs.stamina < cs.maxStamina * 0.1f)
            setLayerWeight("block", 0.f);  // guard broken
    }

    // Head look-at override
    _overrides.clear();
    _overrides.push_back({"head", cs.facingDir, 0.4f});

    // Walk phase for footstep sound
    _walkPhase += moveSp * dt;
    if (std::fmod(_walkPhase, 1.4f) < dt * moveSp) {
        _footstepPending = true;
    }
}

bool AnimationBlender::consumeFootstep() {
    bool r = _footstepPending;
    _footstepPending = false;
    return r;
}
