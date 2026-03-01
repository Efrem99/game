from panda3d.core import GeomNode, GeomVertexData, GeomVertexFormat, GeomVertexWriter, Geom, GeomTriangles, Texture

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
