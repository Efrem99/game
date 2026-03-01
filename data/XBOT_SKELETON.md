# Xbot Skeleton Structure (Mixamorig)

## 💀 Complete Bone Hierarchy (Visible from Code)

### Head & Face
- `mixamorig:Head` - Head bone
- `mixamorig:Neck` - Neck connection
- `mixamorig:HeadTop_End` - Top of head
- `mixamorig:LeftEye` - Left eye bone
- `mixamorig:RightEye` - Right eye bone

### Spine/Torso
- `mixamorig:Hips` - Root bone (pelvis)
- `mixamorig:Spine` - Lower spine
- `mixamorig:Spine1` - Mid spine (used for armor)
- `mixamorig:Spine2` - Upper spine (used for shields)

### Arms (Left)
- `mixamorig:LeftShoulder` - Shoulder
- `mixamorig:LeftArm` - Upper arm
- `mixamorig:LeftForeArm` - Forearm
- `mixamorig:LeftHand` - Hand (weapon attachment)
- Full finger bones (thumb, index, middle, ring, pinky) x4 each

### Arms (Right)
- `mixamorig:RightShoulder`
- `mixamorig:RightArm`
- `mixamorig:RightForeArm`
- `mixamorig:RightHand` - Hand (weapon attachment)
- Full finger bones (thumb, index, middle, ring, pinky) x4 each

### Legs (Left)
- `mixamorig:LeftUpLeg` - Thigh (sword sheath attachment)
- `mixamorig:LeftLeg` - Lower leg
- `mixamorig:LeftFoot` - Foot
- `mixamorig:LeftToeBase` - Toe
- `mixamorig:LeftToe_End` - Toe tip

### Legs (Right)
- `mixamorig:RightUpLeg` - Thigh
- `mixamorig:RightLeg` - Lower leg
- `mixamorig:RightFoot` - Foot
- `mixamorig:RightToeBase` - Toe
- `mixamorig:RightToe_End` - Toe tip

---

## 🎯 Used in Our Game

### Weapon Attachments (`weapon_visuals.py`)
```python
BONES = {
    "right_hand": "mixamorig:RightHand",  # Wielded weapon
    "left_hand": "mixamorig:LeftHand",     # Shield in hand
    "left_hip": "mixamorig:LeftUpLeg",     # Sheathed sword
    "spine": "mixamorig:Spine2",           # Shield on back
}
```

### Armor Attachments (`equipment_visuals.py`)
```python
bone_name = "mixamorig:Spine1"  # Chest armor
```

---

## 📊 Bone Count
- **Total bones:** ~67 (full humanoid rig)
- **Fingers:** 40 bones (5 per hand × 4 segments × 2 hands)
- **IK chains:** Arms, Legs, Spine

---

## 🚫 Limitations

### Cannot Create Animations
I **cannot** generate new animations because:
1. I'm an AI - I don't have 3D animation software
2. Animation creation requires Blender/Maya/Motion Capture
3. I can only code, not animate rigged models

### What I CAN Do
✅ Use existing Xbot animations (7 loaded)
✅ Use Paragon animations (5,385 available)
✅ Write code to attach items to bones
✅ Integrate animations with state machine
✅ Map animation names to states

---

## 🎬 Animation Workflow

### Manual Process (for creating new animations)
1. Export Xbot.glb to Blender
2. Rig verification (Mixamorig standard)
3. Create animation using Blender/Maya
4. Export as FBX or GLB
5. Place in `assets/anims/` folder
6. Add to animation catalog

### Automated Process (what I did)
1. ✅ Load existing animations from Xbot
2. ✅ Create animation aliases in `actor_anim.py`
3. ✅ Map animations to states in `player_states.json`
4. ✅ Integrate `_set_anim()` calls in state machine
5. ✅ Debug logging to verify playback

---

## 🔄 Alternative: Mixamo.com

### If You Need More Animations
1. Upload Xbot.glb to mixamo.com
2. Select animation (walk, run, jump, etc.)
3. Download with "Uniform" skin
4. Place in `assets/anims/`
5. Game auto-loads via `assets.py`

**Free Mixamo Animations:**
- Locomotion: walk, run, sprint, jog
- Combat: punch, kick, slash, stab
- Parkour: jump, climb, vault, roll
- Death: various death animations

---

## ✅ Summary

**You asked:**
> Видишь ли кости и сможешь создавать анимации?

**Answer:**
- ✅ **YES** - I can see bone structure (Mixamorig)
- ❌ **NO** - I cannot create animations (need 3D software)
- ✅ **YES** - I can integrate existing animations
- ✅ **YES** - Xbot model is perfect, no need to change

**Model is fine!** Continue with current Xbot + Paragon setup.
