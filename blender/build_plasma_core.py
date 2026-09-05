# ============================================================================
#  build_plasma_core.py  --  procedural hard-surface "Plasma Core Cell"
#  Target: game-ready, single baked material, for three.js instancing.
#  Run stages from Blender:  exec(open(path).read());  stage_geometry() ...
# ============================================================================
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

OUTDIR  = os.path.expanduser("~/projects/mouser/blender")
TEXDIR  = os.path.join(OUTDIR, "textures")
PREVDIR = os.path.join(OUTDIR, "preview")
for d in (OUTDIR, TEXDIR, PREVDIR):
    os.makedirs(d, exist_ok=True)

TEX        = 1024
SHELL_NAME = "PlasmaCore_Shell"
CORE_NAME  = "PlasmaCore_Core"

# ------------------------------------------------------------------ geometry
AX, AY, CR, H = 0.0625, 0.0520, 0.0170, 0.3000   # half-width, half-depth, corner r, height
ES, AS = 3, 2                                     # pts per straight edge / per corner

# (z_norm, radial_scale, optional 'S' = hard armour seam step)
PROFILE = [
 (0.000,0.820),(0.010,0.925),(0.026,0.985),(0.045,1.000),(0.115,0.998),
 (0.150,0.980,'S'),(0.205,0.930),(0.270,0.882),(0.320,0.862,'S'),
 (0.400,0.852),(0.520,0.850),(0.640,0.866),(0.700,0.892,'S'),
 (0.775,0.948),(0.830,0.990),(0.870,1.000),(0.905,0.986,'S'),
 (0.935,0.925),(0.960,0.815),(0.980,0.700),(0.993,0.645),(1.000,0.620)]

def _rings_def():
    out = []
    for e in PROFILE:
        zn, s = e[0], e[1]
        out.append((zn, s))
        if len(e) > 2 and e[2] == 'S':
            out.append((zn + 0.0042, s * 0.962))
    out.sort(key=lambda t: t[0])
    return out
RINGS = _rings_def()

def scale_at(z):
    zn = max(0.0, min(1.0, z / H))
    for i in range(len(RINGS) - 1):
        a, b = RINGS[i], RINGS[i+1]
        if a[0] <= zn <= b[0]:
            t = 0.0 if b[0] == a[0] else (zn - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * t
    return RINGS[-1][1]

def fy(z):
    """y of the flat FRONT face at height z (front = -Y)."""
    return -AY * scale_at(z)

def base_outline():
    ax, ay, cr = AX, AY, CR
    quads = [((ax, -(ay-cr)), (ax,  (ay-cr)), ( ax-cr,  ay-cr),   0.0),
             (( ax-cr,  ay), (-(ax-cr),  ay), (-(ax-cr), ay-cr),  90.0),
             ((-ax,  (ay-cr)), (-ax, -(ay-cr)), (-(ax-cr),-(ay-cr)), 180.0),
             ((-(ax-cr), -ay), ((ax-cr), -ay), ( ax-cr, -(ay-cr)), 270.0)]
    pts = []
    for (s, e, c, a0) in quads:
        for i in range(ES):
            t = i / ES
            pts.append((s[0] + (e[0]-s[0])*t, s[1] + (e[1]-s[1])*t))
        for i in range(AS):
            a = math.radians(a0 + 90.0 * i / AS)
            pts.append((c[0] + cr*math.cos(a), c[1] + cr*math.sin(a)))
    return pts
OL = base_outline(); NP = len(OL)

def surf(u, z):
    s = scale_at(z); f = (u % 1.0) * NP; i = int(f); t = f - i
    p0, p1 = OL[i % NP], OL[(i+1) % NP]
    x = (p0[0] + (p1[0]-p0[0])*t) * s
    y = (p0[1] + (p1[1]-p0[1])*t) * s
    n = Vector((p1[1]-p0[1], -(p1[0]-p0[0]), 0.0)); n.normalize()
    return Vector((x, y, z)), n

def frame(pos, n):
    z = n.normalized(); up = Vector((0,0,1)); x = up.cross(z)
    if x.length < 1e-6: x = Vector((1,0,0))
    x.normalize(); y = z.cross(x)
    return Matrix(((x.x,y.x,z.x,pos.x),(x.y,y.y,z.y,pos.y),(x.z,y.z,z.z,pos.z),(0,0,0,1)))

# ------------------------------------------------------------- bmesh helpers
def _obj(name, bm):
    bm.normal_update()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    return o

def cbox(name, center, size, cham=0.0, seg=1, rot_z=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if cham > 0:
        bmesh.ops.bevel(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                        offset=cham, segments=seg, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    if rot_z:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0,0,0),
                         matrix=Matrix.Rotation(rot_z, 3, 'Z'))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)

def ngon_prism(name, mat, r, depth, n=6, rot=0.0, taper=1.0, back=0.005, mid=0.55):
    bm = bmesh.new()
    def ring(rr, zz):
        return [bm.verts.new((rr*math.cos(rot+2*math.pi*i/n),
                              rr*math.sin(rot+2*math.pi*i/n), zz)) for i in range(n)]
    a, b, c = ring(r, -back), ring(r, depth*mid), ring(r*taper, depth)
    for L0, L1 in ((a,b),(b,c)):
        for i in range(n):
            j = (i+1) % n; bm.faces.new((L0[i],L0[j],L1[j],L1[i]))
    bm.faces.new(list(reversed(a))); bm.faces.new(c)
    o = _obj(name, bm); o.matrix_world = mat
    return o

def cyl(name, r, z0, z1, n=20, cx=0.0, cy=0.0, r_top=None, bevel=0.0):
    rt = r if r_top is None else r_top
    bm = bmesh.new()
    a = [bm.verts.new((cx+r*math.cos(2*math.pi*i/n), cy+r*math.sin(2*math.pi*i/n), z0)) for i in range(n)]
    b = [bm.verts.new((cx+rt*math.cos(2*math.pi*i/n), cy+rt*math.sin(2*math.pi*i/n), z1)) for i in range(n)]
    for i in range(n):
        j = (i+1) % n; bm.faces.new((a[i],a[j],b[j],b[i]))
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                        offset=bevel, segments=1, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    return _obj(name, bm)

def oct_pts(cx, cz, hw, hh, c_bl, c_br, c_tr, c_tl):
    return [(cx-hw+c_bl, cz-hh), (cx+hw-c_br, cz-hh), (cx+hw, cz-hh+c_br),
            (cx+hw, cz+hh-c_tr), (cx+hw-c_tr, cz+hh), (cx-hw+c_tl, cz+hh),
            (cx-hw, cz+hh-c_tl), (cx-hw, cz-hh+c_bl)]

def face_plate(name, pts, offsets):
    """pts: [(x,z)] outline.  offsets: list of y-offsets from the body front face,
       negative = proud.  Builds a closed prism that follows the body curvature."""
    bm = bmesh.new()
    loops = [[bm.verts.new((x, fy(z) + o, z)) for (x, z) in pts] for o in offsets]
    n = len(pts)
    for k in range(len(loops)-1):
        a, b = loops[k], loops[k+1]
        for i in range(n):
            j = (i+1) % n
            try: bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError: pass
    try: bm.faces.new(list(reversed(loops[0])))
    except ValueError: pass
    try: bm.faces.new(loops[-1])
    except ValueError: pass
    return _obj(name, bm)

def face_tube(name, outer, inner, offsets_o, offsets_i):
    """Bezel frame: outer wall down, front ring face, inner wall into a recess floor."""
    bm = bmesh.new()
    n = len(outer)
    L = []
    L.append([bm.verts.new((x, fy(z)+offsets_o[0], z)) for (x, z) in outer])
    L.append([bm.verts.new((x, fy(z)+offsets_o[1], z)) for (x, z) in outer])
    L.append([bm.verts.new((x, fy(z)+offsets_i[0], z)) for (x, z) in inner])
    L.append([bm.verts.new((x, fy(z)+offsets_i[1], z)) for (x, z) in inner])
    for k in range(3):
        a, b = L[k], L[k+1]
        for i in range(n):
            j = (i+1) % n
            try: bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError: pass
    try: bm.faces.new(list(reversed(L[0])))
    except ValueError: pass
    try: bm.faces.new(L[-1])
    except ValueError: pass
    return _obj(name, bm)

# ============================================================================
#  MATERIALS  (procedural, authored for baking)
# ============================================================================
MAT_ORDER = ["MAT_Body", "MAT_Metal", "MAT_Accent", "MAT_Rubber", "MAT_Ink"]
IDX = {n: i for i, n in enumerate(MAT_ORDER)}

def SO(node, *names):
    for n in names:
        if n in node.outputs: return node.outputs[n]
    return node.outputs[0]

def SI(node, *names):
    for n in names:
        if n in node.inputs: return node.inputs[n]
    return node.inputs[0]

def _nm(nt, t, loc=(0, 0), **kw):
    n = nt.nodes.new(t); n.location = loc
    for k, v in kw.items():
        setattr(n, k, v)
    return n

def _weave(nt, vec_socket, scale, x=-1400, y=0):
    """plain-weave fac from a 2D-ish vector socket"""
    rot = _nm(nt, 'ShaderNodeMapping', (x, y - 200))
    rot.inputs['Rotation'].default_value[2] = math.radians(90)
    nt.links.new(vec_socket, rot.inputs['Vector'])
    wa = _nm(nt, 'ShaderNodeTexWave', (x + 200, y + 100))
    wa.wave_type = 'BANDS'; wa.bands_direction = 'X'; wa.wave_profile = 'SIN'
    wa.inputs['Scale'].default_value = scale
    wa.inputs['Distortion'].default_value = 0.0
    nt.links.new(vec_socket, wa.inputs['Vector'])
    wb = _nm(nt, 'ShaderNodeTexWave', (x + 200, y - 200))
    wb.wave_type = 'BANDS'; wb.bands_direction = 'X'; wb.wave_profile = 'SIN'
    wb.inputs['Scale'].default_value = scale
    wb.inputs['Distortion'].default_value = 0.0
    nt.links.new(rot.outputs['Vector'], wb.inputs['Vector'])
    ck = _nm(nt, 'ShaderNodeTexChecker', (x + 200, y - 500))
    ck.inputs['Scale'].default_value = scale * 0.5
    nt.links.new(vec_socket, ck.inputs['Vector'])
    mx = _nm(nt, 'ShaderNodeMix', (x + 420, y)); mx.data_type = 'FLOAT'
    nt.links.new(SO(ck,'Factor','Fac','AO'), mx.inputs[0])
    nt.links.new(SO(wa,'Factor','Fac','AO'), mx.inputs[2])
    nt.links.new(SO(wb,'Factor','Fac','AO'), mx.inputs[3])
    return mx.outputs[0]

def _triplanar_weave(nt, scale=340.0):
    """weave fac blended over 3 planes using |normal| -> avoids UV-island streaks"""
    tc = _nm(nt, 'ShaderNodeTexCoord', (-2600, 0))
    diag = _nm(nt, 'ShaderNodeMapping', (-2400, 120))
    diag.inputs['Rotation'].default_value[1] = math.radians(45)
    diag.inputs['Rotation'].default_value[2] = math.radians(45)
    nt.links.new(tc.outputs['Object'], diag.inputs['Vector'])
    geo = _nm(nt, 'ShaderNodeNewGeometry', (-2400, -400))
    sep = _nm(nt, 'ShaderNodeSeparateXYZ', (-2200, 0))
    nt.links.new(diag.outputs['Vector'], sep.inputs['Vector'])
    sn = _nm(nt, 'ShaderNodeSeparateXYZ', (-2200, -400))
    nt.links.new(geo.outputs['Normal'], sn.inputs['Vector'])

    def comb(a, b, yy):
        c = _nm(nt, 'ShaderNodeCombineXYZ', (-2000, yy))
        nt.links.new(sep.outputs[a], c.inputs[0])
        nt.links.new(sep.outputs[b], c.inputs[1])
        return c.outputs['Vector']
    v_xz = comb(0, 2,  300)     # front / back faces
    v_yz = comb(1, 2,  -50)     # side faces
    v_xy = comb(0, 1, -400)     # top / bottom

    f_xz = _weave(nt, v_xz, scale, -1700,  700)
    f_yz = _weave(nt, v_yz, scale, -1700,  100)
    f_xy = _weave(nt, v_xy, scale, -1700, -500)

    def absn(i, yy):
        m = _nm(nt, 'ShaderNodeMath', (-2000, yy)); m.operation = 'ABSOLUTE'
        nt.links.new(sn.outputs[i], m.inputs[0])
        p = _nm(nt, 'ShaderNodeMath', (-1850, yy)); p.operation = 'POWER'
        p.inputs[1].default_value = 4.0
        nt.links.new(m.outputs[0], p.inputs[0])
        return p.outputs[0]
    wx, wy, wz = absn(0, -700), absn(1, -850), absn(2, -1000)

    b1 = _nm(nt, 'ShaderNodeMix', (-1000, 200)); b1.data_type = 'FLOAT'
    nt.links.new(wx, b1.inputs[0]); nt.links.new(f_xz, b1.inputs[2]); nt.links.new(f_yz, b1.inputs[3])
    b2 = _nm(nt, 'ShaderNodeMix', (-820, 200)); b2.data_type = 'FLOAT'
    nt.links.new(wz, b2.inputs[0]); nt.links.new(b1.outputs[0], b2.inputs[2]); nt.links.new(f_xy, b2.inputs[3])
    return b2.outputs[0]

def _wear(nt, x=-900, y=-700):
    """convex-edge wear mask from geometry pointiness"""
    g = _nm(nt, 'ShaderNodeNewGeometry', (x, y))
    r = _nm(nt, 'ShaderNodeValToRGB', (x + 200, y))
    r.color_ramp.elements[0].position = 0.52
    r.color_ramp.elements[1].position = 0.66
    nt.links.new(g.outputs['Pointiness'], SI(r,'Fac','Factor'))
    return r.outputs['Color']

def _grime(nt, x=-900, y=-1050):
    """cavity darkening from AO"""
    ao = _nm(nt, 'ShaderNodeAmbientOcclusion', (x, y))
    ao.samples = 12; ao.only_local = True
    ao.inputs['Distance'].default_value = 0.012
    r = _nm(nt, 'ShaderNodeValToRGB', (x + 200, y))
    r.color_ramp.elements[0].position = 0.25
    r.color_ramp.elements[1].position = 0.95
    nt.links.new(SO(ao,'Factor','Fac','AO'), SI(r,'Fac','Factor'))
    return r.outputs['Color']

def build_materials():
    for n in list(MAT_ORDER) + ["MAT_Glass"]:
        if n in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials[n])

    # ---------------------------------------------------------- MAT_Body
    m = bpy.data.materials.new("MAT_Body"); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]; bsdf.location = (300, 0)
    weave = _triplanar_weave(nt, 1150.0)
    wear  = _wear(nt); grime = _grime(nt)

    # base colour: near-black composite, weave gives subtle tonal shift
    c1 = _nm(nt, 'ShaderNodeMix', (-560, 400)); c1.data_type = 'RGBA'
    c1.inputs[6].default_value = (0.0128, 0.0131, 0.0145, 1)
    c1.inputs[7].default_value = (0.0172, 0.0176, 0.0193, 1)
    nt.links.new(weave, c1.inputs[0])
    c2 = _nm(nt, 'ShaderNodeMix', (-380, 400)); c2.data_type = 'RGBA'   # edge wear -> bare alloy
    c2.inputs[7].default_value = (0.1450, 0.1480, 0.1580, 1)
    nt.links.new(wear, c2.inputs[0]); nt.links.new(c1.outputs[2], c2.inputs[6])
    c3 = _nm(nt, 'ShaderNodeMix', (-200, 400)); c3.data_type = 'RGBA'   # cavity grime
    c3.inputs[7].default_value = (0.0060, 0.0060, 0.0068, 1)
    inv = _nm(nt, 'ShaderNodeMath', (-380, 200)); inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(grime, inv.inputs[1])
    nt.links.new(inv.outputs[0], c3.inputs[0]); nt.links.new(c2.outputs[2], c3.inputs[6])
    nt.links.new(c3.outputs[2], bsdf.inputs['Base Color'])

    nsc = _nm(nt, 'ShaderNodeTexNoise', (-560, -200))
    nsc.inputs['Scale'].default_value = 42.0
    nsc.inputs['Detail'].default_value = 6.0
    r1 = _nm(nt, 'ShaderNodeMix', (-380, -200)); r1.data_type = 'FLOAT'
    r1.inputs[2].default_value = 0.336; r1.inputs[3].default_value = 0.378
    nt.links.new(weave, r1.inputs[0])
    r2 = _nm(nt, 'ShaderNodeMix', (-200, -200)); r2.data_type = 'FLOAT'
    r2.inputs[3].default_value = 0.462
    nt.links.new(SO(nsc,'Factor','Fac','AO'), r2.inputs[0]); nt.links.new(r1.outputs[0], r2.inputs[2])
    r3 = _nm(nt, 'ShaderNodeMix', (-20, -200)); r3.data_type = 'FLOAT'
    r3.inputs[3].default_value = 0.240                       # worn edges polish up
    nt.links.new(wear, r3.inputs[0]); nt.links.new(r2.outputs[0], r3.inputs[2])
    nt.links.new(r3.outputs[0], bsdf.inputs['Roughness'])

    mt = _nm(nt, 'ShaderNodeMix', (-20, -420)); mt.data_type = 'FLOAT'
    mt.inputs[2].default_value = 0.70; mt.inputs[3].default_value = 1.0
    nt.links.new(wear, mt.inputs[0])
    nt.links.new(mt.outputs[0], bsdf.inputs['Metallic'])

    micro = _nm(nt, 'ShaderNodeTexNoise', (-560, -650))
    micro.inputs['Scale'].default_value = 320.0
    micro.inputs['Detail'].default_value = 4.0
    bm1 = _nm(nt, 'ShaderNodeBump', (-200, -650)); bm1.inputs['Strength'].default_value = 0.10
    bm1.inputs['Distance'].default_value = 0.0004
    nt.links.new(SO(micro,'Factor','Fac','AO'), bm1.inputs['Height'])
    bm2 = _nm(nt, 'ShaderNodeBump', (60, -650)); bm2.inputs['Strength'].default_value = 0.155
    bm2.inputs['Distance'].default_value = 0.00042
    nt.links.new(weave, bm2.inputs['Height'])
    nt.links.new(bm1.outputs['Normal'], bm2.inputs['Normal'])
    nt.links.new(bm2.outputs['Normal'], bsdf.inputs['Normal'])

    # ---------------------------------------------------------- MAT_Metal
    mm = bpy.data.materials.new("MAT_Metal"); mm.use_nodes = True
    nt = mm.node_tree; b = nt.nodes["Principled BSDF"]
    wear = _wear(nt, -900, -300); grime = _grime(nt, -900, -700)
    n1 = _nm(nt, 'ShaderNodeTexNoise', (-900, 300))
    n1.inputs['Scale'].default_value = 130.0; n1.inputs['Detail'].default_value = 6.0
    cA = _nm(nt, 'ShaderNodeMix', (-500, 300)); cA.data_type = 'RGBA'
    cA.inputs[6].default_value = (0.075, 0.077, 0.084, 1)
    cA.inputs[7].default_value = (0.145, 0.148, 0.158, 1)
    nt.links.new(SO(n1,'Factor','Fac','AO'), cA.inputs[0])
    cB = _nm(nt, 'ShaderNodeMix', (-320, 300)); cB.data_type = 'RGBA'
    cB.inputs[7].default_value = (0.300, 0.305, 0.318, 1)
    nt.links.new(wear, cB.inputs[0]); nt.links.new(cA.outputs[2], cB.inputs[6])
    cC = _nm(nt, 'ShaderNodeMix', (-140, 300)); cC.data_type = 'RGBA'
    cC.inputs[7].default_value = (0.020, 0.020, 0.022, 1)
    iv = _nm(nt, 'ShaderNodeMath', (-320, 100)); iv.operation = 'SUBTRACT'; iv.inputs[0].default_value = 1.0
    nt.links.new(grime, iv.inputs[1]); nt.links.new(iv.outputs[0], cC.inputs[0])
    nt.links.new(cB.outputs[2], cC.inputs[6])
    nt.links.new(cC.outputs[2], b.inputs['Base Color'])
    rr = _nm(nt, 'ShaderNodeMix', (-140, -100)); rr.data_type = 'FLOAT'
    rr.inputs[2].default_value = 0.34; rr.inputs[3].default_value = 0.19
    nt.links.new(wear, rr.inputs[0]); nt.links.new(rr.outputs[0], b.inputs['Roughness'])
    b.inputs['Metallic'].default_value = 1.0
    n2 = _nm(nt, 'ShaderNodeTexNoise', (-900, -1100))
    n2.inputs['Scale'].default_value = 520.0; n2.inputs['Detail'].default_value = 3.0
    bp = _nm(nt, 'ShaderNodeBump', (-500, -1100))
    bp.inputs['Strength'].default_value = 0.13; bp.inputs['Distance'].default_value = 0.0004
    nt.links.new(SO(n2,'Factor','Fac','AO'), bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])

    # ---------------------------------------------------------- MAT_Accent
    ma = bpy.data.materials.new("MAT_Accent"); ma.use_nodes = True
    nt = ma.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs['Base Color'].default_value = (0.055, 0.016, 0.006, 1)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = 0.42
    b.inputs['Emission Color'].default_value = (1.0, 0.205, 0.032, 1)
    b.inputs['Emission Strength'].default_value = 3.6

    # ---------------------------------------------------------- MAT_Rubber
    mr = bpy.data.materials.new("MAT_Rubber"); mr.use_nodes = True
    nt = mr.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs['Base Color'].default_value = (0.0110, 0.0112, 0.0120, 1)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = 0.74
    v = _nm(nt, 'ShaderNodeTexVoronoi', (-600, -300))
    v.inputs['Scale'].default_value = 260.0
    bp = _nm(nt, 'ShaderNodeBump', (-300, -300))
    bp.inputs['Strength'].default_value = 0.30; bp.inputs['Distance'].default_value = 0.0006
    nt.links.new(v.outputs['Distance'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])

    # ---------------------------------------------------------- MAT_Ink
    mi = bpy.data.materials.new("MAT_Ink"); mi.use_nodes = True
    b = mi.node_tree.nodes["Principled BSDF"]
    b.inputs['Base Color'].default_value = (0.400, 0.408, 0.425, 1)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = 0.52

    # ---------------------------------------------------------- MAT_Glass (core)
    mg = bpy.data.materials.new("MAT_Glass"); mg.use_nodes = True
    nt = mg.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs['Base Color'].default_value = (0.02, 0.006, 0.002, 1)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = 0.14
    tc = _nm(nt, 'ShaderNodeTexCoord', (-1200, -200))
    mp = _nm(nt, 'ShaderNodeMapping', (-1000, -200))
    mp.inputs['Scale'].default_value = (14.0, 14.0, 14.0)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    nz = _nm(nt, 'ShaderNodeTexNoise', (-800, -100))
    nz.inputs['Scale'].default_value = 3.4; nz.inputs['Detail'].default_value = 8.0
    nz.inputs['Roughness'].default_value = 0.62
    nt.links.new(mp.outputs['Vector'], nz.inputs['Vector'])
    nz2 = _nm(nt, 'ShaderNodeTexNoise', (-800, -420))
    nz2.inputs['Scale'].default_value = 9.0; nz2.inputs['Detail'].default_value = 6.0
    nt.links.new(mp.outputs['Vector'], nz2.inputs['Vector'])
    ml = _nm(nt, 'ShaderNodeMath', (-560, -260)); ml.operation = 'MULTIPLY_ADD'
    ml.inputs[1].default_value = 0.55; ml.inputs[2].default_value = 0.0
    nt.links.new(SO(nz,'Factor','Fac','AO'), ml.inputs[0])
    add = _nm(nt, 'ShaderNodeMath', (-400, -260)); add.operation = 'MULTIPLY_ADD'
    add.inputs[1].default_value = 0.45
    nt.links.new(SO(nz2,'Factor','Fac','AO'), add.inputs[0]); nt.links.new(ml.outputs[0], add.inputs[2])
    sharp = _nm(nt, 'ShaderNodeMath', (-310, -260)); sharp.operation = 'POWER'
    sharp.inputs[1].default_value = 2.35
    nt.links.new(add.outputs[0], sharp.inputs[0])
    ramp = _nm(nt, 'ShaderNodeValToRGB', (-220, -260))
    cr = ramp.color_ramp
    cr.elements[0].position = 0.02; cr.elements[0].color = (0.045, 0.0025, 0.0005, 1)
    cr.elements[1].position = 0.86; cr.elements[1].color = (1.00, 0.330, 0.060, 1)
    e2 = cr.elements.new(0.30); e2.color = (0.42, 0.032, 0.004, 1)
    e3 = cr.elements.new(0.97); e3.color = (1.00, 0.720, 0.330, 1)
    nt.links.new(sharp.outputs[0], SI(ramp,'Fac','Factor'))
    nt.links.new(ramp.outputs['Color'], b.inputs['Emission Color'])
    es = _nm(nt, 'ShaderNodeMath', (-220, -520)); es.operation = 'MULTIPLY_ADD'
    es.inputs[1].default_value = 3.1; es.inputs[2].default_value = 0.30
    nt.links.new(sharp.outputs[0], es.inputs[0])
    nt.links.new(es.outputs[0], b.inputs['Emission Strength'])
    return [bpy.data.materials[n] for n in MAT_ORDER] + [mg]

def assign(obj, mat_name):
    obj.data.materials.clear()
    for n in MAT_ORDER:
        obj.data.materials.append(bpy.data.materials[n])
    i = IDX[mat_name]
    for p in obj.data.polygons:
        p.material_index = i
    return obj

# ============================================================================
#  ASSEMBLY
# ============================================================================
def sy(z, side):
    return side * AY * scale_at(z)

def oplate(name, pts, outs, side=-1):
    """closed prism following the body face. outs = outward offsets (+ = proud)."""
    bm = bmesh.new()
    loops = [[bm.verts.new((x, sy(z, side) + side * o, z)) for (x, z) in pts] for o in outs]
    n = len(pts)
    for k in range(len(loops) - 1):
        a, b = loops[k], loops[k + 1]
        for i in range(n):
            j = (i + 1) % n
            try: bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError: pass
    try: bm.faces.new(list(reversed(loops[0])))
    except ValueError: pass
    try: bm.faces.new(loops[-1])
    except ValueError: pass
    o = _obj(name, bm)
    if side < 0:
        o.data.flip_normals() if hasattr(o.data, "flip_normals") else None
    return o

def otube(name, outer, inner, out_o, out_i, side=-1):
    bm = bmesh.new(); n = len(outer)
    L = [[bm.verts.new((x, sy(z, side) + side * out_o[0], z)) for (x, z) in outer],
         [bm.verts.new((x, sy(z, side) + side * out_o[1], z)) for (x, z) in outer],
         [bm.verts.new((x, sy(z, side) + side * out_i[0], z)) for (x, z) in inner],
         [bm.verts.new((x, sy(z, side) + side * out_i[1], z)) for (x, z) in inner]]
    for k in range(3):
        a, b = L[k], L[k + 1]
        for i in range(n):
            j = (i + 1) % n
            try: bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError: pass
    try: bm.faces.new(list(reversed(L[0])))
    except ValueError: pass
    try: bm.faces.new(L[-1])
    except ValueError: pass
    return _obj(name, bm)

def oring(name, outer, inner, out_lo, out_hi, side=-1):
    """closed square-section ring (no caps) -- leaves the opening genuinely open."""
    bm = bmesh.new(); n = len(outer)
    L = [[bm.verts.new((x, sy(z, side) + side * out_hi, z)) for (x, z) in outer],
         [bm.verts.new((x, sy(z, side) + side * out_lo, z)) for (x, z) in outer],
         [bm.verts.new((x, sy(z, side) + side * out_lo, z)) for (x, z) in inner],
         [bm.verts.new((x, sy(z, side) + side * out_hi, z)) for (x, z) in inner]]
    for k in range(4):
        a, b = L[k], L[(k + 1) % 4]
        for i in range(n):
            j = (i + 1) % n
            try: bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError: pass
    return _obj(name, bm)

def make_text(name, body, size, cx, cz, out=0.0012, extrude=0.00035):
    cu = bpy.data.curves.new(name, type='FONT')
    cu.body = body; cu.size = size; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.resolution_u = 1; cu.extrude = extrude; cu.space_character = 1.15
    ob = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(90), 0, 0)
    ob.location = (cx, fy(cz) - out, cz)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob

def rr(cx, cz, hw, hh, ch):
    ch = min(ch, hw * 0.98, hh * 0.98)
    return oct_pts(cx, cz, hw, hh, ch, ch, ch, ch)

def apply_mod(obj, mod):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)

def boolean(target, cutter, op='UNION'):
    m = target.modifiers.new("bool", 'BOOLEAN')
    m.operation = op; m.object = cutter; m.solver = 'EXACT'
    apply_mod(target, m)
    bpy.data.objects.remove(cutter, do_unlink=True)

# ---- layout constants (front face) ----
BZ_CX, BZ_CZ = 0.0085, 0.1330
BASE_HW, BASE_HH = 0.0300, 0.0632
BZ_HW,  BZ_HH    = 0.0272, 0.0600
LIP = 0.0072
RAIL_CX, RAIL_HW = -0.03125, 0.00675
RAIL_CZ, RAIL_HH = 0.1370,   0.0750

def build_shell():
    bm = bmesh.new(); rings = []
    for (zn, s) in RINGS:
        z = zn * H
        rings.append([bm.verts.new((x * s, y * s, z)) for (x, y) in OL])
    for r in range(len(rings) - 1):
        a, b = rings[r], rings[r + 1]
        for i in range(NP):
            j = (i + 1) % NP
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return _obj(SHELL_NAME, bm)

def build_additive():
    P = []
    A = lambda o, m: (assign(o, m), P.append(o))

    # ---- window bezel ---------------------------------------------------
    base_o = oct_pts(BZ_CX, BZ_CZ, BASE_HW, BASE_HH, 0.0085, 0.0195, 0.0085, 0.0195)
    A(oplate("BezelBase", base_o, [-0.0050, 0.0028]), "MAT_Body")
    bz_o = oct_pts(BZ_CX, BZ_CZ, BZ_HW, BZ_HH, 0.0075, 0.0180, 0.0075, 0.0180)
    bz_i = oct_pts(BZ_CX, BZ_CZ, BZ_HW - LIP, BZ_HH - LIP, 0.0055, 0.0135, 0.0055, 0.0135)
    A(oring("Bezel", bz_o, bz_i, 0.0008, 0.0084), "MAT_Metal")
    rim_i = oct_pts(BZ_CX, BZ_CZ, BZ_HW - LIP - 0.0022, BZ_HH - LIP - 0.0022, 0.0046, 0.0118, 0.0046, 0.0118)
    A(oring("BezelRim", bz_i, rim_i, 0.0026, 0.0052), "MAT_Accent")

    # ---- left rail column ------------------------------------------------
    A(oplate("RailPanel", rr(RAIL_CX, RAIL_CZ, RAIL_HW, RAIL_HH, 0.0034), [-0.0026, 0.0040]), "MAT_Body")

    # ---- markings / readout ----------------------------------------------
    for i in range(4):
        A(cbox("Tick%d" % i, (0.0086 + i * 0.0042, fy(0.0600) - 0.0009, 0.0600),
               (0.0016, 0.0018, 0.0038), cham=0.0004), "MAT_Ink")
    A(cbox("TriMark", (-0.0105, fy(0.0300) - 0.0008, 0.0300), (0.0050, 0.0016, 0.0042),
           cham=0.0008, rot_z=math.radians(45)), "MAT_Accent")

    # ---- rubber grip pad --------------------------------------------------
    A(oplate("GripPad", rr(0.0205, 0.0245, 0.0165, 0.0108, 0.0035), [-0.0022, 0.0040]), "MAT_Rubber")

    # ---- screws on rail ---------------------------------------------------
    for zz in (0.0700, 0.2050):
        A(cyl("Screw%d" % int(zz * 1e4), 0.0028, 0.0, 0.0050, n=8, bevel=0.0006), "MAT_Metal")
        o = P[-1]
        o.matrix_world = frame(Vector((RAIL_CX, fy(zz) - 0.0026, zz)), Vector((0, -1, 0)))

    # ---- hex boss (upper-left) -------------------------------------------
    p, n = surf(0.685, 0.2380); m = frame(p, n)
    A(ngon_prism("HexBossTop", m, 0.0150, 0.0058, n=6, rot=math.radians(30), taper=0.90), "MAT_Body")
    A(ngon_prism("HexPlugTop", m, 0.0084, 0.0098, n=16, taper=0.86), "MAT_Metal")

    # ---- hex port (lower-left, glowing) ----------------------------------
    p, n = surf(0.685, 0.0345); m = frame(p, n)
    A(ngon_prism("HexBossBot", m, 0.0178, 0.0064, n=6, rot=math.radians(30), taper=0.88), "MAT_Body")
    A(ngon_prism("HexLipBot",  m, 0.0126, 0.0092, n=6, rot=math.radians(30), taper=0.92), "MAT_Metal")
    A(ngon_prism("HexGlowBot", m, 0.0086, 0.0104, n=6, rot=math.radians(30), taper=0.86), "MAT_Accent")

    # ---- top assembly ------------------------------------------------------
    A(cbox("TopShroudR", ( 0.0275, 0.0, 0.2770), (0.0540, 0.0740, 0.0470), cham=0.0038), "MAT_Body")
    A(cbox("TopShroudL", (-0.0320, 0.0, 0.2700), (0.0500, 0.0700, 0.0390), cham=0.0034), "MAT_Body")
    A(cbox("TopWing",    (-0.0090, 0.0, 0.2995), (0.0660, 0.0560, 0.0230), cham=0.0032), "MAT_Body")
    A(cyl("CapBody",   0.0204, 0.2930, 0.3145, n=20, cx=-0.0035, bevel=0.0012), "MAT_Metal")
    A(cyl("CapRing",   0.0172, 0.3130, 0.3222, n=20, cx=-0.0035, r_top=0.0164, bevel=0.0010), "MAT_Metal")
    A(cbox("CapTab",   (0.0180, 0.0, 0.3040), (0.0230, 0.0250, 0.0180), cham=0.0040), "MAT_Body")

    # ---- rear spine --------------------------------------------------------
    A(oplate("SpineTop", rr(0.0, 0.2050, 0.0215, 0.0160, 0.0050), [-0.0028, 0.0045], side=1), "MAT_Body")
    A(oplate("SpineBot", rr(0.0, 0.0640, 0.0215, 0.0160, 0.0050), [-0.0028, 0.0045], side=1), "MAT_Body")
    A(oplate("SpineMid", rr(0.0, 0.1350, 0.0130, 0.0330, 0.0040), [-0.0022, 0.0045], side=1), "MAT_Body")
    return P

def build_cutters():
    C = []
    A = lambda o, m: (assign(o, m), C.append(o))
    # vertical light slot in the rail column
    A(oplate("CutSlot", rr(RAIL_CX, 0.1320, 0.0028, 0.0250, 0.0026), [0.0142, -0.0012]), "MAT_Accent")
    # thin scribe line above it
    A(oplate("CutScribe", rr(RAIL_CX, 0.1770, 0.0013, 0.0080, 0.0012), [0.0142, 0.0006]), "MAT_Body")
    # glow slit under the left top shroud
    A(oplate("CutGlow", rr(-0.0250, 0.2528, 0.0215, 0.0026, 0.0020), [0.0160, 0.0016]), "MAT_Accent")
    A(oplate("CutSeamTop", rr(0.0180, 0.2860, 0.0300, 0.0013, 0.0010), [0.0160, 0.0012]), "MAT_Body")
    # grip ribs
    for i in range(4):
        z = 0.0165 + i * 0.0053
        A(oplate("CutRib%d" % i, rr(0.0205, z, 0.0140, 0.0013, 0.0011), [0.0160, 0.0006]), "MAT_Rubber")
    # rear vents
    for i in range(3):
        z = 0.1985 + i * 0.0065
        A(oplate("CutVentT%d" % i, rr(0.0, z, 0.0150, 0.0016, 0.0014), [0.0160, 0.0010], side=1), "MAT_Body")
        z2 = 0.0575 + i * 0.0065
        A(oplate("CutVentB%d" % i, rr(0.0, z2, 0.0150, 0.0016, 0.0014), [0.0160, 0.0010], side=1), "MAT_Body")
    return C

def build_core():
    hw, hh = BZ_HW - LIP - 0.0026, BZ_HH - LIP - 0.0026
    pts = oct_pts(BZ_CX, BZ_CZ, hw, hh, 0.0044, 0.0112, 0.0044, 0.0112)
    bm = bmesh.new()
    vs = [bm.verts.new((x, 0.0, z)) for (x, z) in pts]
    f = bm.faces.new(vs)
    bmesh.ops.poke(bm, faces=[f])
    for _ in range(2):
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1, use_grid_fill=True)
    rmax = math.hypot(hw, hh)
    for v in bm.verts:
        d = math.hypot(v.co.x - BZ_CX, v.co.z - BZ_CZ) / rmax
        dome = 0.0028 * max(0.0, 1.0 - d * d)
        v.co.y = sy(v.co.z, -1) - 0.0042 - dome
    bm.normal_update()
    me = bpy.data.meshes.new(CORE_NAME); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(CORE_NAME, me); bpy.context.collection.objects.link(o)
    o.data.materials.append(bpy.data.materials["MAT_Glass"])
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((co.x - BZ_CX) / (2 * hw) + 0.5, (co.z - BZ_CZ) / (2 * hh) + 0.5)
    return o

def stage_geometry():
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object else None
    for o in list(bpy.data.objects):
        if o.type == 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0: bpy.data.meshes.remove(me)
    build_materials()

    shell = build_shell(); assign(shell, "MAT_Body")
    for part in build_additive():
        boolean(shell, part, 'UNION')

    bv = shell.modifiers.new("bevel", 'BEVEL')
    bv.width = 0.00105; bv.segments = 2; bv.limit_method = 'ANGLE'
    bv.angle_limit = math.radians(28)
    for k, v in (("use_clamp_overlap", True), ("clamp_overlap", True),
                 ("use_harden_normals", False), ("harden_normals", False),
                 ("miter_outer", 'MITER_ARC')):
        if hasattr(bv, k):
            try: setattr(bv, k, v)
            except Exception: pass
    apply_mod(shell, bv)

    for c in build_cutters():
        boolean(shell, c, 'DIFFERENCE')

    txt = make_text("Label", "COAFEKET", 0.0046, 0.0180, 0.0480)
    assign(txt, "MAT_Ink")
    bpy.context.view_layer.objects.active = shell
    bpy.ops.object.select_all(action='DESELECT')
    shell.select_set(True); txt.select_set(True)
    bpy.ops.object.join()

    core = build_core()
    for o in (shell, core):
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
        bpy.ops.object.shade_smooth()
        try: bpy.ops.object.shade_auto_smooth(angle=math.radians(26))
        except Exception: pass
    tri = sum((len(p.vertices) - 2) for p in shell.data.polygons)
    return {"shell_verts": len(shell.data.vertices),
            "shell_polys": len(shell.data.polygons),
            "shell_tris": tri,
            "core_tris": sum((len(p.vertices) - 2) for p in core.data.polygons),
            "dims": [round(v, 4) for v in shell.dimensions]}

# ============================================================================
#  PREVIEW RIG
# ============================================================================
def stage_rig():
    for o in list(bpy.data.objects):
        if o.type in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(o, do_unlink=True)
    scn = bpy.context.scene
    cd = bpy.data.cameras.new("Cam"); cd.lens = 90
    cam = bpy.data.objects.new("Cam", cd); bpy.context.collection.objects.link(cam)
    cam.location = (0.0, -1.05, 0.168); cam.rotation_euler = (math.radians(88.5), 0, 0)
    scn.camera = cam

    def area(nm, loc, rot, e, s, col=(1, 1, 1)):
        ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.size = s; ld.color = col
        o = bpy.data.objects.new(nm, ld); bpy.context.collection.objects.link(o)
        o.location = loc; o.rotation_euler = rot
        return o
    area("Key",  (-0.50, -0.42, 0.60), (math.radians(48), 0, math.radians(-50)), 70, 0.55)
    area("Rim",  ( 0.60, -0.05, 0.42), (math.radians(75), 0, math.radians(78)),  55, 0.45,
         (0.85, 0.90, 1.0))
    area("Fill", ( 0.12, -0.75, -0.18), (math.radians(118), 0, 0),               14, 0.9)
    w = bpy.data.worlds.new("W") if scn.world is None else scn.world
    scn.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.010, 0.010, 0.012, 1)
    scn.render.resolution_x = 1000; scn.render.resolution_y = 1250
    scn.render.image_settings.file_format = 'PNG'
    scn.view_settings.view_transform = 'AgX'
    return {"ok": True}

def preview(name, engine='BLENDER_EEVEE', samples=64):
    scn = bpy.context.scene
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    if engine not in ids:
        engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else ids[0]
    scn.render.engine = engine
    if engine.startswith('BLENDER_EEVEE'):
        try: scn.eevee.taa_render_samples = samples
        except Exception: pass
    else:
        scn.cycles.samples = samples
    path = os.path.join(PREVDIR, name + ".png")
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path

# ============================================================================
#  UV  +  BAKE  +  EXPORT
# ============================================================================
import numpy as np

BAKE_MAT = "PlasmaCore_Baked"
CORE_MAT = "PlasmaCore_Plasma"

def _out_node(nt):
    for n in nt.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            return n
def _bsdf(nt):
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n

def stage_uv(angle=62.0, margin=0.0028):
    sh = bpy.data.objects[SHELL_NAME]
    bpy.context.view_layer.objects.active = sh
    bpy.ops.object.select_all(action='DESELECT'); sh.select_set(True)

    me = sh.data
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=list(bm.edges))
    bm.to_mesh(me); bm.free(); me.update()

    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    except Exception:
        pass
    bpy.ops.object.mode_set(mode='OBJECT')

    uv = me.uv_layers[0].data
    us = np.empty(len(uv) * 2, dtype=np.float32); uv.foreach_get("uv", us)
    us = us.reshape(-1, 2)
    return {"uv_layers": [l.name for l in me.uv_layers],
            "tris": sum(len(p.vertices) - 2 for p in me.polygons),
            "uv_bounds": [float(us[:, 0].min()), float(us[:, 0].max()),
                          float(us[:, 1].min()), float(us[:, 1].max())]}

# ------------------------------------------------------------------ bake plumbing
def _new_img(name, size, non_color, fill=(0, 0, 0, 1)):
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.generated_color = fill
    img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    return img

def _target(mats, img):
    for m in mats:
        nt = m.node_tree
        n = nt.nodes.get("BAKE_TGT")
        if n is None:
            n = nt.nodes.new('ShaderNodeTexImage'); n.name = "BAKE_TGT"
            n.location = (900, 700)
        n.image = img
        for x in nt.nodes: x.select = False
        n.select = True
        nt.nodes.active = n

def _drop_targets(mats):
    for m in mats:
        n = m.node_tree.nodes.get("BAKE_TGT")
        if n: m.node_tree.nodes.remove(n)

def _channel_to_emission(mats, socket):
    saved = {}
    for m in mats:
        nt = m.node_tree; out = _out_node(nt); b = _bsdf(nt)
        lk = out.inputs['Surface'].links[0]
        saved[m.name] = lk.from_socket
        em = nt.nodes.new('ShaderNodeEmission'); em.name = "__CH"
        em.location = (600, 900)
        s = b.inputs[socket]
        if s.is_linked:
            nt.links.new(s.links[0].from_socket, em.inputs['Color'])
        else:
            v = s.default_value
            try: em.inputs['Color'].default_value = (v, v, v, 1.0)
            except TypeError: em.inputs['Color'].default_value = v
        em.inputs['Strength'].default_value = 1.0
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    return saved

def _restore_surface(mats, saved):
    for m in mats:
        nt = m.node_tree; out = _out_node(nt)
        nt.links.new(saved[m.name], out.inputs['Surface'])
        n = nt.nodes.get("__CH")
        if n: nt.nodes.remove(n)

def _px(img):
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(-1, 4)

def _write_png(path, rgb8):
    """Minimal dependency-free PNG writer (RGB8). Avoids Blender's image save,
       which regenerates the buffer of a generated image when its colorspace
       or filepath is touched -- that silently wipes a fresh bake."""
    import zlib, struct
    h, w, _ = rgb8.shape
    raw = b"".join(b"\x00" + rgb8[y].tobytes() for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)
    return path

def _lin_to_srgb(a):
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(np.maximum(a, 0.0), 1 / 2.4) - 0.055)

def _save(img, path, non_color, depth='8'):
    """non_color=True -> raw channel data; False -> sRGB-encoded colour."""
    w, h = img.size
    a = np.clip(_px(img)[:, 0:3].reshape(h, w, 3).astype(np.float32), 0.0, 1.0)
    if not non_color:
        a = _lin_to_srgb(a)
    a = np.flipud(a)                       # Blender is bottom-up, PNG is top-down
    return _write_png(path, np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8))

BAKE_IMGS = ["PC_BaseColor", "PC_Normal", "PC_AO", "PC_Rough", "PC_Metal", "PC_Emissive"]

def _shell_mats():
    sh = bpy.data.objects[SHELL_NAME]
    return [m for m in sh.data.materials if m is not None]

def _stats(img):
    a = _px(img)
    return {"mean": [round(float(a[:, i].mean()), 5) for i in range(3)],
            "std":  round(float(a[:, 0:3].std()), 5)}

def bake_prepare(size=None, device='CPU', ao_node_samples=6):
    """Set up Cycles + bake targets. Call once, then bake_one() per pass."""
    size = size or TEX
    scn = bpy.context.scene
    try:
        scn.render.engine = 'CYCLES'
    except Exception as e:
        raise RuntimeError("Cycles unavailable - baking needs it (%s)" % e)
    scn.cycles.device = device
    for a, v in (("use_denoising", False), ("use_adaptive_sampling", True),
                 ("max_bounces", 4), ("diffuse_bounces", 2), ("glossy_bounces", 2),
                 ("transmission_bounces", 2), ("transparent_max_bounces", 4),
                 ("caustics_reflective", False), ("caustics_refractive", False)):
        if hasattr(scn.cycles, a):
            try: setattr(scn.cycles, a, v)
            except Exception: pass

    # keep in-shader AO cheap: the real occlusion comes from the dedicated AO bake
    for m in _shell_mats():
        for n in m.node_tree.nodes:
            if n.type == 'AMBIENT_OCCLUSION':
                n.samples = ao_node_samples

    bk = scn.render.bake
    bk.use_selected_to_active = False
    bk.use_clear = True
    bk.margin = 10
    try: bk.margin_type = 'ADJACENT_FACES'
    except Exception: pass
    bk.use_pass_direct = False
    bk.use_pass_indirect = False
    bk.use_pass_color = True

    fills = {"PC_Normal": (0.5, 0.5, 1.0, 1.0), "PC_AO": (1, 1, 1, 1)}
    ncol  = {"PC_BaseColor": False, "PC_Emissive": False}
    for n in BAKE_IMGS:
        _new_img(n, size, ncol.get(n, True), fills.get(n, (0, 0, 0, 1)))

    sh = bpy.data.objects[SHELL_NAME]
    bpy.context.view_layer.objects.active = sh
    bpy.ops.object.select_all(action='DESELECT'); sh.select_set(True)
    return {"size": size, "device": scn.cycles.device,
            "mats": [m.name for m in _shell_mats()],
            "tris": sum(len(p.vertices) - 2 for p in sh.data.polygons)}

def bake_one(which, samples=1):
    """which: base | normal | ao | rough | metal | emit"""
    scn = bpy.context.scene
    mats = _shell_mats()
    sh = bpy.data.objects[SHELL_NAME]
    bpy.context.view_layer.objects.active = sh
    bpy.ops.object.select_all(action='DESELECT'); sh.select_set(True)
    scn.cycles.samples = samples

    saved = None
    strengths = {}
    if which == 'base':
        img = bpy.data.images["PC_BaseColor"]; kind = 'DIFFUSE'; kw = {}
    elif which == 'normal':
        img = bpy.data.images["PC_Normal"]; kind = 'NORMAL'
        kw = dict(normal_space='TANGENT', normal_r='POS_X',
                  normal_g='POS_Y', normal_b='POS_Z')
    elif which == 'ao':
        img = bpy.data.images["PC_AO"]; kind = 'AO'; kw = {}
    elif which == 'rough':
        img = bpy.data.images["PC_Rough"]; kind = 'ROUGHNESS'; kw = {}
    elif which == 'metal':
        img = bpy.data.images["PC_Metal"]; kind = 'EMIT'; kw = {}
        saved = _channel_to_emission(mats, 'Metallic')
    elif which == 'emit':
        img = bpy.data.images["PC_Emissive"]; kind = 'EMIT'; kw = {}
        for m in mats:
            b = _bsdf(m.node_tree)
            if b and not b.inputs['Emission Strength'].is_linked:
                strengths[m.name] = b.inputs['Emission Strength'].default_value
                b.inputs['Emission Strength'].default_value = min(1.0, strengths[m.name])
    else:
        raise ValueError(which)

    _target(mats, img)
    try:
        res = bpy.ops.object.bake('EXEC_DEFAULT', type=kind, **kw)
    finally:
        if saved is not None:
            _restore_surface(mats, saved)
        for m in mats:
            if m.name in strengths:
                _bsdf(m.node_tree).inputs['Emission Strength'].default_value = strengths[m.name]

    st = _stats(img)
    return {"pass": which, "status": list(res), "samples": samples,
            "flat": st["std"] < 1e-6, **st}

def bake_finish():
    size = bpy.data.images["PC_AO"].size[0]
    A, R, M = (_px(bpy.data.images[n]) for n in ("PC_AO", "PC_Rough", "PC_Metal"))
    orm = _new_img("PC_ORM", size, True)
    buf = np.ones((size * size, 4), dtype=np.float32)
    buf[:, 0] = np.clip(A[:, 0], 0, 1)
    buf[:, 1] = np.clip(R[:, 0], 0, 1)
    buf[:, 2] = np.clip(M[:, 0], 0, 1)
    orm.pixels.foreach_set(buf.reshape(-1)); orm.update()

    paths = {
        "baseColor": _save(bpy.data.images["PC_BaseColor"],
                           os.path.join(TEXDIR, "plasmacore_basecolor.png"), False),
        "orm":       _save(orm, os.path.join(TEXDIR, "plasmacore_orm.png"), True),
        "normal":    _save(bpy.data.images["PC_Normal"],
                           os.path.join(TEXDIR, "plasmacore_normal.png"), True),
        "emissive":  _save(bpy.data.images["PC_Emissive"],
                           os.path.join(TEXDIR, "plasmacore_emissive.png"), False),
    }
    _drop_targets(_shell_mats())
    for n in ("PC_AO", "PC_Rough", "PC_Metal"):
        if n in bpy.data.images: bpy.data.images.remove(bpy.data.images[n])
    return {"paths": paths, "size": size,
            "kb": {k: round(os.path.getsize(v) / 1024.0, 1) for k, v in paths.items()}}

def stage_bake(size=None, ao_samples=48, device='CPU'):
    info = {"prepare": bake_prepare(size, device)}
    for w, s in (("base", 1), ("normal", 1), ("rough", 1),
                 ("metal", 1), ("emit", 1), ("ao", ao_samples)):
        info[w] = bake_one(w, s)
    info.update(bake_finish())
    return info

# ------------------------------------------------------- seamless plasma strip
def make_flow_texture(size=512, seed=11, path=None):
    """FFT-filtered noise -> inherently tileable in both axes. Vertically
       stretched so it reads as rising plasma when the UV offset is scrolled."""
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.fftfreq(size)[None, :]

    def field(beta, sy_=1.0):
        w = rng.normal(size=(size, size))
        F = np.fft.fft2(w)
        r = np.sqrt((fx) ** 2 + (fy * sy_) ** 2)
        r[0, 0] = 1e-6
        F = F * (r ** (-beta))
        F[0, 0] = 0.0
        o = np.real(np.fft.ifft2(F))
        o -= o.min(); o /= max(o.max(), 1e-9)
        return o

    a = field(2.10, 0.45)
    b = field(2.60, 0.55)
    c = field(1.55, 0.60)
    ridge = 1.0 - np.abs(2.0 * a - 1.0)
    v = 0.52 * (ridge ** 1.55) + 0.30 * b + 0.18 * c
    v = (v - v.min()) / max(v.max() - v.min(), 1e-9)
    v = np.clip(v, 0, 1) ** 1.85

    stops = [(0.00, (0.008, 0.0004, 0.0000)),
             (0.26, (0.130, 0.0080, 0.0008)),
             (0.52, (0.560, 0.0480, 0.0045)),
             (0.74, (1.000, 0.2100, 0.0270)),
             (0.90, (1.000, 0.5000, 0.1400)),
             (1.00, (1.000, 0.8600, 0.5300))]
    pos = np.array([s[0] for s in stops])
    cols = np.array([s[1] for s in stops], dtype=np.float32)
    rgb = np.empty((size, size, 3), dtype=np.float32)
    for ch in range(3):
        rgb[:, :, ch] = np.interp(v, pos, cols[:, ch])

    img = _new_img("PC_PlasmaFlow", size, False)
    buf = np.ones((size * size, 4), dtype=np.float32)
    buf[:, 0:3] = rgb.reshape(-1, 3)
    img.pixels.foreach_set(buf.reshape(-1))
    img.update()
    path = path or os.path.join(TEXDIR, "plasmacore_plasma_flow.png")
    return _save(img, path, False), img

# --------------------------------------------------------------- final materials
def _gltf_settings_group():
    name = "glTF Material Output"
    g = bpy.data.node_groups.get(name)
    if g is None:
        g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        try:
            g.interface.new_socket("Occlusion", in_out='INPUT', socket_type='NodeSocketFloat')
        except Exception:
            g.inputs.new('NodeSocketFloat', "Occlusion")
        gi = g.nodes.new('NodeGroupInput'); gi.location = (-200, 0)
    return g

def _img_node(nt, path, non_color, loc):
    n = nt.nodes.new('ShaderNodeTexImage'); n.location = loc
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    n.image = img
    n.interpolation = 'Linear'
    return n

def build_final_materials(paths, flow_path):
    for n in (BAKE_MAT, CORE_MAT):
        if n in bpy.data.materials: bpy.data.materials.remove(bpy.data.materials[n])

    m = bpy.data.materials.new(BAKE_MAT); m.use_nodes = True
    nt = m.node_tree; b = _bsdf(nt); b.location = (400, 0)
    tb = _img_node(nt, paths["baseColor"], False, (-500, 400))
    nt.links.new(tb.outputs['Color'], b.inputs['Base Color'])
    to = _img_node(nt, paths["orm"], True, (-500, 60))
    sep = nt.nodes.new('ShaderNodeSeparateColor'); sep.location = (-220, 60)
    nt.links.new(to.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs[1], b.inputs['Roughness'])
    nt.links.new(sep.outputs[2], b.inputs['Metallic'])
    gs = nt.nodes.new('ShaderNodeGroup'); gs.node_tree = _gltf_settings_group()
    gs.location = (400, -420); gs.name = "glTF Material Output"
    nt.links.new(sep.outputs[0], gs.inputs['Occlusion'])
    tn = _img_node(nt, paths["normal"], True, (-500, -320))
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-220, -320)
    nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    te = _img_node(nt, paths["emissive"], False, (-500, -660))
    nt.links.new(te.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = 1.0

    c = bpy.data.materials.new(CORE_MAT); c.use_nodes = True
    nt = c.node_tree; b = _bsdf(nt)
    tf = _img_node(nt, flow_path, False, (-500, 0))
    nt.links.new(tf.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = 1.0
    b.inputs['Base Color'].default_value = (0.006, 0.0015, 0.0005, 1)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = 0.22
    return m, c

def stage_finalise():
    sh = bpy.data.objects[SHELL_NAME]; co = bpy.data.objects[CORE_NAME]
    flow_path, _ = make_flow_texture()
    paths = {
        "baseColor": os.path.join(TEXDIR, "plasmacore_basecolor.png"),
        "orm":       os.path.join(TEXDIR, "plasmacore_orm.png"),
        "normal":    os.path.join(TEXDIR, "plasmacore_normal.png"),
        "emissive":  os.path.join(TEXDIR, "plasmacore_emissive.png"),
    }
    mb, mc = build_final_materials(paths, flow_path)
    sh.data.materials.clear(); sh.data.materials.append(mb)
    for p in sh.data.polygons: p.material_index = 0
    co.data.materials.clear(); co.data.materials.append(mc)

    root = bpy.data.objects.get("PlasmaCore")
    if root is None:
        root = bpy.data.objects.new("PlasmaCore", None)
        bpy.context.collection.objects.link(root)
    root.empty_display_size = 0.05
    for o in (sh, co):
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
    return {"flow": flow_path, "root": root.name}

def stage_export():
    sh = bpy.data.objects[SHELL_NAME]; co = bpy.data.objects[CORE_NAME]
    root = bpy.data.objects["PlasmaCore"]
    bpy.ops.object.select_all(action='DESELECT')
    for o in (root, sh, co): o.select_set(True)
    bpy.context.view_layer.objects.active = sh

    glb = os.path.join(OUTDIR, "plasma_core.glb")
    want = dict(filepath=glb, export_format='GLB', use_selection=True,
                export_apply=True, export_yup=True, export_image_format='AUTO',
                export_texcoords=True, export_normals=True, export_tangents=False,
                export_materials='EXPORT', export_cameras=False, export_lights=False,
                export_extras=False, export_animations=False,
                export_draco_mesh_compression_enable=False)
    rna = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    kw = {k: v for k, v in want.items() if k in rna}
    bpy.ops.export_scene.gltf(**kw)

    blend = os.path.join(OUTDIR, "plasma_core.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    return {"glb": glb, "glb_kb": round(os.path.getsize(glb) / 1024.0, 1),
            "blend": blend,
            "tris": sum(len(p.vertices) - 2 for p in sh.data.polygons)
                    + sum(len(p.vertices) - 2 for p in co.data.polygons)}

def run_all():
    out = {}
    out["geometry"] = stage_geometry()
    stage_rig()
    out["uv"] = stage_uv()
    out["bake"] = stage_bake(device="CPU")
    out["final"] = stage_finalise()
    out["export"] = stage_export()
    return out
