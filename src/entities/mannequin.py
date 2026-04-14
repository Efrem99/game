from panda3d.core import GeomNode, GeomVertexData, GeomVertexFormat, GeomVertexWriter, Geom, GeomTriangles, Texture
from utils.logger import logger

def build_mannequin(parent, name, sx, sy, sz, px, py, pz, r, g, b):
    """Build a mannequin from primitives."""
    hw, hh, hd = sx*.5, sy*.5, sz*.5
    fmt  = GeomVertexFormat.getV3n3c4()
    vd   = GeomVertexData(name, fmt, Geom.UHStatic)
    vd.setNumRows(24)
    vw = GeomVertexWriter(vd, "vertex")
    nw = GeomVertexWriter(vd, "normal")
    cw = GeomVertexWriter(vd, "color")
    faces = [
        ((0,0,1), [(-hw,-hd,hh),(hw,-hd,hh),(hw,hd,hh),(-hw,hd,hh)]),
        ((0,0,-1),[(-hw,hd,-hh),(hw,hd,-hh),(hw,-hd,-hh),(-hw,-hd,-hh)]),
        ((1,0,0), [(hw,-hd,-hh),(hw,hd,-hh),(hw,hd,hh),(hw,-hd,hh)]),
        ((-1,0,0),[(-hw,hd,-hh),(-hw,-hd,-hh),(-hw,-hd,hh),(-hw,hd,hh)]),
        ((0,1,0), [(-hw,hd,-hh),(hw,hd,-hh),(hw,hd,hh),(-hw,hd,hh)]),
        ((0,-1,0),[(-hw,-hd,hh),(hw,-hd,hh),(hw,-hd,-hh),(-hw,-hd,-hh)]),
    ]
    for n, vs in faces:
        for v in vs:
            vw.addData3f(*v); nw.addData3f(*n); cw.addData4f(r,g,b,1)
    tris = GeomTriangles(Geom.UHStatic)
    for i in range(6):
        b2 = i*4
        tris.addVertices(b2,b2+1,b2+2); tris.addVertices(b2,b2+2,b2+3)
    tris.closePrimitive()
    geom = Geom(vd); geom.addPrimitive(tris)
    gn = GeomNode(name); gn.addGeom(geom)
    np = parent.attachNewNode(gn)
    np.setPos(px, py, pz)
    return np

def create_procedural_actor(render, color=(0.44, 0.50, 0.63)):
    root = render.attachNewNode("char_root")

    # Defensive Shader Inputs
    root.set_shader_input("displacement_scale", 0.0, priority=1000)
    root.set_shader_input("displacement_map", Texture(), priority=1000)
    root.set_shader_input("ao", 1.0, priority=1000)
    root.set_shader_input("shadow_boost", 0.0, priority=1000)
    root.set_shader_input("specular_factor", 1.0, priority=1000)
    root.set_shader_input("roughness", 0.5, priority=1000)
    root.set_shader_input("metallic", 0.0, priority=1000)

    # Mannequin parts (procedural)
    build_mannequin(root, "torso", 0.8, 0.5, 1.0, 0, 0, 2.0, *color)
    build_mannequin(root, "head",  0.5, 0.5, 0.5, 0, 0, 2.8, 0.94, 0.75, 0.56)
    build_mannequin(root, "hip",   0.8, 0.5, 0.3, 0, 0, 1.35, *color)

    # Arms / legs joints for procedural animation
    r_arm = root.attachNewNode("rArm"); r_arm.setPos(0.55, 0, 2.0)
    build_mannequin(r_arm, "rUp", 0.25, 0.25, 0.7, 0, 0, -0.35, *color)
    r_elbow = r_arm.attachNewNode("rElbow"); r_elbow.setPos(0, 0, -0.7)
    build_mannequin(r_elbow, "rLow", 0.23, 0.23, 0.6, 0, 0, -0.3, *color)
    r_hand = r_elbow.attachNewNode("rHand"); r_hand.setPos(0, 0, -0.6)

    l_arm = root.attachNewNode("lArm"); l_arm.setPos(-0.55, 0, 2.0)
    build_mannequin(l_arm, "lUp", 0.25, 0.25, 0.7, 0, 0, -0.35, *color)

    r_leg = root.attachNewNode("rLeg"); r_leg.setPos(0.25, 0, 1.2)
    build_mannequin(r_leg, "rThigh", 0.3, 0.3, 0.85, 0, 0, -0.425, *color)
    r_knee = r_leg.attachNewNode("rKnee"); r_knee.setPos(0, 0, -0.85)
    build_mannequin(r_knee, "rShin", 0.28, 0.28, 0.75, 0, 0, -0.375, *color)

    l_leg = root.attachNewNode("lLeg"); l_leg.setPos(-0.25, 0, 1.2)
    build_mannequin(l_leg, "lThigh", 0.3, 0.3, 0.85, 0, 0, -0.425, *color)
    l_knee = l_leg.attachNewNode("lKnee"); l_knee.setPos(0, 0, -0.85)
    build_mannequin(l_knee, "lShin", 0.28, 0.28, 0.75, 0, 0, -0.375, *color)

    return root, r_leg, l_leg, r_arm, l_arm, r_hand

def dress_actor(root, role, gender="male", age="adult"):
    """Attach procedural 'clothing' blocks to the mannequin based on role."""
    from panda3d.core import LPoint3, LVector3
    from direct.actor.Actor import Actor
    from render.model_visuals import ensure_model_visual_defaults
    
    role = str(role or "").lower()
    logger.info(f"[Mannequin] Dressing NPC: {role} ({gender}, {age})")
    
    # Try discovery for bone anchoring if it's an Actor
    attachment_root = root
    spine_joint = None
    if isinstance(root, Actor):
        # Common bone names for Mixamo/Xbot
        for bone_name in ["mixamorig:Spine2", "Spine2", "spine.003", "Bip01 Spine2"]:
            joint = root.exposeJoint(None, "modelRoot", bone_name)
            if joint and not joint.isEmpty():
                spine_joint = joint
                break
    
    # Apply age-based scaling
    if age == "child":
        root.setScale(0.65, 0.65, 0.65)
    elif age == "elderly":
        root.setScale(0.92, 0.92, 0.92)
        # Add a slight hunch
        torso = root.find("**/torso")
        if not torso.isEmpty():
            torso.setP(12) # Hunch forward

    # Role-based attachments
    if "guard" in role or "captain" in role or "knight" in role:
        # Metallic Armor
        armor_color = (0.72, 0.74, 0.78)
        # Chestplate - prefer spine joint to follow animation
        armor_parent = spine_joint if spine_joint else root
        z_offset = 0.15 if spine_joint else 2.15
        
        chest = build_mannequin(armor_parent, "chestplate", 0.9, 0.6, 0.8, 0, 0.05, z_offset, *armor_color)
        ensure_model_visual_defaults(chest, debug_label="guard_plate")

        # Helmet (Head joint search)
        head_joint = None
        if isinstance(root, Actor):
            for bone_name in ["mixamorig:Head", "Head", "head", "Bip01 Head"]:
                joint = root.exposeJoint(None, "modelRoot", bone_name)
                if joint and not joint.isEmpty():
                    head_joint = joint
                    break
        
        helmet_parent = head_joint if head_joint else root
        hz = 0.2 if head_joint else 3.0
        helmet = build_mannequin(helmet_parent, "helmet", 0.55, 0.55, 0.4, 0, 0, hz, *armor_color)
        ensure_model_visual_defaults(helmet, debug_label="guard_helmet")

    elif "merchant" in role or "trader" in role or "adalin" in role:
        # Practical business/work clothes (apron/tunic)
        work_color = (0.42, 0.32, 0.22) # Brown/Leather
        z_off = 0.0 if spine_joint else 1.8
        apron = build_mannequin(spine_joint or root, "apron", 0.82, 0.52, 1.2, 0, 0.02, z_off, *work_color)
        ensure_model_visual_defaults(apron, debug_label="merchant_apron")

    elif "guide" in role or "commoner" in role or "villager" in role:
        # Simple civilian attire
        civ_color = (0.35, 0.45, 0.35) # Forest green-ish
        z_off = 0.0 if spine_joint else 1.7
        tunic = build_mannequin(spine_joint or root, "tunic", 0.8, 0.5, 1.3, 0, 0, z_off, *civ_color)
        ensure_model_visual_defaults(tunic, debug_label="civ_tunic")

    elif "sorceress" in role or "mage" in role or "witch" in role:
        # Sorceress: Red Cloak, Hood, and Ginger Hair
        cloak_color = (0.8, 0.1, 0.1) # Red
        hair_color = (0.9, 0.4, 0.1)  # Ginger/Red hair
        
        # Cloak - attached to spine
        cloak_parent = spine_joint if spine_joint else root
        cz = 0.0 if spine_joint else 1.8
        cloak = build_mannequin(cloak_parent, "cloak", 1.1, 0.6, 1.6, 0, -0.1, cz, *cloak_color)
        ensure_model_visual_defaults(cloak, debug_label="sorceress_cloak")
        
        # Hood & Hair - attached to head
        head_joint = None
        if isinstance(root, Actor):
            for bone_name in ["mixamorig:Head", "Head", "head", "Bip01 Head"]:
                joint = root.exposeJoint(None, "modelRoot", bone_name)
                if joint and not joint.isEmpty():
                    head_joint = joint
                    break
        
        head_parent = head_joint if head_joint else root
        hz = 0.2 if head_joint else 3.0
        
        hood = build_mannequin(head_parent, "hood", 0.65, 0.65, 0.5, 0, 0.05, hz + 0.05, *cloak_color)
        ensure_model_visual_defaults(hood, debug_label="sorceress_hood")
        
        hair = build_mannequin(head_parent, "hair", 0.5, 0.4, 0.6, 0, -0.15, hz - 0.1, *hair_color)
        ensure_model_visual_defaults(hair, debug_label="sorceress_hair")

    elif gender == "female" and "adalin" not in role:
        # Default female: Dress
        dress_color = (0.6, 0.3, 0.5) # Purple/Magenta
        # Skirt block starting from hips (search for hips)
        hips_joint = None
        if isinstance(root, Actor):
            for bone_name in ["mixamorig:Hips", "Hips", "pelvis"]:
                joint = root.exposeJoint(None, "modelRoot", bone_name)
                if joint and not joint.isEmpty():
                    hips_joint = joint
                    break
        skirt = build_mannequin(hips_joint or root, "skirt", 1.0, 0.8, 1.2, 0, 0, 0.8 if not hips_joint else -0.4, *dress_color)
        ensure_model_visual_defaults(skirt, debug_label="female_dress")

    elif "worker" in role or "miner" in role or "woodcutter" in role:
        # Working class uniform
        uniform_color = (0.2, 0.3, 0.4) # Dark Blue/Grey
        z_off = 0.0 if spine_joint else 1.6
        overalls = build_mannequin(spine_joint or root, "overalls", 0.85, 0.55, 1.4, 0, 0, z_off, *uniform_color)
        ensure_model_visual_defaults(overalls, debug_label="worker_uniform")
    
    else:
        # Default fallback so no one is "naked"
        fall_color = (0.5, 0.5, 0.5)
        z_off = 0.0 if spine_joint else 1.8
        shirt = build_mannequin(spine_joint or root, "fallback_shirt", 0.75, 0.45, 1.1, 0, 0, z_off, *fall_color)
        ensure_model_visual_defaults(shirt, debug_label="civ_fallback")
