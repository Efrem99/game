# Extended State Machine - Animation Plan

## 🎯 Created Extended player_states.json

### New States Added (14 total)
1. **idle** → Idle_Loop (breathing animation) ✅
2. **walking** → Walk_Loop
3. **running** → Sprint_Loop
4. **jumping** → Jump_Start (NEW)
5. **falling** → Fall_Loop (NEW)
6. **landing** → Jump_Land (NEW)
7. **attacking** → Sword_Slash (combat)
8. **dodging** → Dodge_Backward (combat)
9. **blocking** → Block_Idle (combat)
10. **casting** → Spell_Cast (magic)
11. **vaulting** → Vault_Over (parkour)
12. **climbing** → Ledge_Climb (parkour)
13. **wallrun** → Wall_Run (parkour)
14. **dead** → Death_Forward (NEW)

### Transitions Added (24 total)
- Movement: idle ↔ walk ↔ run
- Jumping: ground → jump → fall → land → idle
- Combat: idle → attack/dodge/block → idle
- Magic: idle → casting → idle
- Parkour: run → vault/wallrun → idle/fall
- Parkour: fall/jump → climb → idle
- Death: * → dead (hp <= 0)

---

## 🎨 Animation Details

### Idle Animation
**Name:** Idle_Loop
**Type:** Looping, breathing animation
**Duration:** ~2-3 seconds loop
**Features:** Slight torso movement, subtle breathing

This creates a "living" idle instead of static T-pose.

### Available in Xbot (7 animations confirmed)
Based on actor_anim.py aliases and assets.py:
- ✅ Idle_Loop
- ✅ Walk_Loop
- ✅ Sprint_Loop (run)
- ✅ Jump (jump/fall variations)
- ✅ Attack variations
- ✅ Block/Parry
- ✅ Death

### May Need to Add
Some animations might not exist in Xbot and need mapping:
- Vault_Over → Use dash/roll
- Ledge_Climb → Use jump + custom
- Wall_Run → Use sprint variant
- Spell_Cast → Use generic cast

**Solution:** Actor animation system has fallback aliases (lines 48-85 in actor_anim.py)

---

## 🐾 Pet/Animal Animations

### Dragon Animations
**File:** `game_spawn.py` line 90 - `load_dragon()`

**Needed States:**
- idle → Dragon idle pose
- fly → Flying/hovering
- attack → Breath attack / claw swipe
- roar → Intimidation
- death → Dragon death

### Pet Animations
**File:** `game_pet.py`

**Needed States:**
- follow → Walking behind player
- idle → Sitting/waiting
- attack → Helping in combat
- celebrate → After victory

**Action:** Create `data/states/dragon_states.json` and `data/states/pet_states.json`

---

## 🔗 Integration Needed

### Current Status
- ✅ State machine loads player_states.json
- ✅ State machine evaluates conditions
- ❌ State machine does NOT trigger animations yet

### Required Changes
**File:** `src/state/state_machine.py`

Add animation trigger in `_change_state()`:
```python
def _change_state(self, new_state, entity):
    if new_state not in self.states:
        return False

    self.current_state = new_state

    # Get animation for this state
    state_data = self.states[new_state]
    if "animation" in state_data and hasattr(entity, '_set_anim'):
        entity._set_anim(state_data["animation"], loop=True)
        print(f"[StateMachine] {new_state} → {state_data['animation']}")

    return True
```

---

## 📊 Testing Plan

### Phase 1: Basic Movement
- [ ] Idle animation plays when standing
- [ ] Walk plays when moving slow
- [ ] Run plays when shift+move

### Phase 2: Extended Animations
- [ ] Jump animation when jumping
- [ ] Fall animation in air
- [ ] Land animation on ground contact
- [ ] Verify breathing idle

### Phase 3: Combat
- [ ] Attack animation on mouse click
- [ ] Block animation on right-click hold
- [ ] Dodge animation on dodge key

### Phase 4: Parkour
- [ ] Vault animation on obstacle
- [ ] Wall run animation on wall contact
- [ ] Ledge climb on ledge grab

### Phase 5: Death
- [ ] Death animation when hp = 0
- [ ] No respawn until animation finishes

### Phase 6: Pets/Animals
- [ ] Dragon idle/fly/attack
- [ ] Pet follow/attack animations

---

## ✅ Next Steps

1. **Verify breathing idle** - Launch game, check if Idle_Loop has movement
2. **Integrate state machine** - Add _set_anim() call to StateMachine
3. **Test transitions** - Verify jump → fall → land chain
4. **Add pet states** - Create dragon_states.json
5. **Map missing animations** - Find aliases for vault/wallrun

---

## 📝 Animation Aliases Reference

From `actor_anim.py`:
```python
"idle": "Idle_Loop, Idle_Talking_Loop, Crouch_Idle_Loop"
"walk": "Walk_Loop, Walk_Formal_Loop, Crouch_Fwd_Loop"
"run": "Sprint_Loop, Jog_Fwd_Loop"
"jump": "Jump, Takeoff, Hop"
"air": "Air, Fall, Falling, Hang"
"land": "Land, Landing"
"attack": "Attack, Slash, Swing, Strike, Hit"
"block": "Block, Guard, Shield"
"death": "Death, Die"
```

System will automatically pick best available animation.

---

## Implementation Update (2026-02-23)

- `src/entities/player.py` now uses `data/states/player_states.json` as a runtime state machine source:
- state definitions are loaded (`states`) and transitions are executed (`trigger` + `condition`)
- `animation_finished` transitions are supported using duration lock timers
- a motion-blend crossfade is implemented via Panda3D Actor blend (`enableBlend` + `setControlEffect`)
- blend time is configurable in `data/controls.json` via `animation.blend_time`
- hard animation switches in movement/combat paths were replaced with state-driven `_set_anim(...)`
- optional external animation assets are auto-loaded from:
- `assets/anims/`
- `assets/models/xbot/`
- `models/animations/`
- input-edge triggers wired: `block_start`/`block_end` (press/release) and `wall_contact` (wallrun enter)
- `data/actors/player_animations.json` is used as priority state-to-clip override before other fallbacks
- automatic coverage report is generated: `data/states/ANIMATION_COVERAGE.md`
- missing states fallback to best available clips (`idle/walk/run`) so gameplay does not break when some assets are absent
