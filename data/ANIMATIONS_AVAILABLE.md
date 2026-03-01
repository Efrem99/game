# Animation Assets Summary

## 📦 Available Animations

### ✅ In `assets/anims/` (13 GLB files - READY)

#### Combat (6)
1. **attack_longsword_1.glb** - Primary sword attack
2. **attack_longsword_2.glb** - Secondary sword attack
3. **attack_slashes.glb** - Combo slashes
4. **attack_thrust.glb** - Thrust attack
5. **block_idle.glb** - Blocking stance
6. **parry.glb** - Parry deflection

#### Movement/Parkour (2)
7. **landing_run.glb** - Landing from jump while running
8. **midair.glb** - In-air/falling pose

#### Magic (2)
9. **sword_and_shield_casting.glb** - Casting with weapon
10. **sword_and_shield_casting_2.glb** - Alt casting

#### Draw/Sheath (2)
11. **sheath_sword_1.glb** - Sheathing sword animation
12. **sheath_sword_2.glb** - Alt sheath

#### Death (1)
13. **death.glb** - Death animation

---

## 🎮 Now Used in State Machine

Updated `player_states.json` to use these real animations:
- `falling` → `midair.glb`
- `landing` → `landing_run.glb`
- `attacking` → `attack_longsword_1.glb`
- `blocking` → `block_idle.glb`
- `casting` → `sword_and_shield_casting.glb`
- `dead` → `death.glb`

---

## 📋 Still Using Xbot (Fallbacks)
- `idle` → Idle_Loop (Xbot)
- `walking` → Walk_Loop (Xbot)
- `running` → Sprint_Loop (Xbot)
- `jumping` → Jump_Start (Xbot)
- `dodging` → Dodge_Backward (Xbot alias)
- `vaulting` → Vault_Over (needs custom)
- `climbing` → Ledge_Climb (needs custom)
- `wallrun` → Wall_Run (needs custom)

---

## 💡 Paragon Animations (Available!)

**Location:** ✅ FOUND! `assets/models/paragonanimationsretargetedtomanny/ParagonAnimationsRetargetedToManny/`  
**Count:** 5,385 FBX files  
**Catalog:** `animations_catalog.py` ready  
**Characters:** 32 Paragon heroes

### Top Characters (by animation count)
1. **TwinBlastManny** - 255 anims (dual pistols)
2. **CountessManny** - 234 anims (assassin)
3. **WraithManny** - 229 anims (sniper)
4. **RevenantManny** - 211 anims (gunslinger)
5. **gideonManny** - 201 anims (mage)
6. **MurdockManny** - 197 anims (ranger)
7. **FengMaoManny** - 196 anims (swordsman) ⚔️
8. **AuroraManny** - 191 anims (ice warrior)
9. **KallariManny** - 187 anims (ninja)
10. **steelmanny** - 186 anims (tank)

### Best for King Wizard
- **FengMaoManny** (196) - Sword combat animations
- **gideonManny** (201) - Magic/casting animations
- **minionsManny** (87) - Basic enemy animations
- **KallariManny** (187) - Stealth/dodge animations

### How to Use
```python
from animations_catalog import ParagonAnimationCatalog
from config import PARAGON_ANIMS_DIR

catalog = ParagonAnimationCatalog(PARAGON_ANIMS_DIR)

# Find specific animation
vault_anim = catalog.find_animation("vault", "FengMaoManny")
sword_attack = catalog.find_animation("attack", "FengMaoManny")

# Get all animations for character
feng_anims = catalog.get_character_animations("FengMaoManny")
```

---

## 🔧 Missing Animations to Create/Find

### Parkour (3)
- Vault over obstacle
- Ledge climb up
- Wall run

### Combat Variants (Optional)
- More attack combos (can use attack_slashes)
- Dodge roll variants
- Block reactions

### Magic (Optional)
- More spell variants (have 2 casts already)

---

## ✅ Status
**Current:** 13 GLB animations integrated  
**Next:** Test in-game and verify transitions  
**Future:** Add Paragon collection if needed
