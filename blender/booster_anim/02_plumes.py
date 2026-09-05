"""Build the plume shells, the ember sparks, the materials and the rig.

Hierarchy that ends up in the glb:

    Boosters                     <- one switch for on/off
      Booster_L                  <- empty at the nozzle, local -Z = thrust
        Booster_L_Wash           <- widest, faintest shell
        Booster_L_Mid
        Booster_L_Core           <- white-hot dart with shock diamonds
        Booster_L_Spark0..5
      Booster_R ...

Each shell carries two turbulence shape keys (TurbA / TurbB) that 03_anim.py
cross-fades, so the flame changes shape instead of just changing size.
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, numpy as np
from mathutils import Vector, Matrix

NZ = json.load(open(os.path.join(WORK, "nozzles.json")))
bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "s0.blend"))
sc = bpy.context.scene


# ---------------------------------------------------------------- materials
def flame_material(layer):
    """Black base + textured emission + textured alpha == additive-friendly."""
    m = bpy.data.materials.new(f"Booster{layer}")
    m.use_nodes = True
    m.blend_method = 'BLEND'
    m.use_backface_culling = False
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    img = bpy.data.images.load(os.path.join(WORK, f"plume_{layer.lower()}.png"))
    img.colorspace_settings.name = 'sRGB'
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = 'EXTEND'
    tex.location = (-420, 0)
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Emission Strength"].default_value = PLUME[layer]["emit"]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    # the exporter needs base colour driven by the same image to emit a
    # baseColorTexture, which is where glTF reads alpha from
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'; mix.location = (-200, -160)
    mix.inputs["Factor"].default_value = 0.0
    mix.inputs[6].default_value = (0, 0, 0, 1)
    nt.links.new(tex.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    return m


def spark_material():
    m = bpy.data.materials.new("BoosterSpark")
    m.use_nodes = True
    m.blend_method = 'BLEND'
    m.use_backface_culling = False
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0, 0, 0, 1)
    b.inputs["Emission Color"].default_value = (1.0, 0.52, 0.14, 1.0)
    b.inputs["Emission Strength"].default_value = SPARK_EMIT
    b.inputs["Alpha"].default_value = 0.80
    b.inputs["Roughness"].default_value = 1.0
    return m


MATS = {k: flame_material(k) for k in PLUME}
SPARK_MAT = spark_material()


# ---------------------------------------------------------------- geometry
def radius(p, t):
    return ((p["r0"] + p["grow"] * t ** p["gpow"])
            * max(1.0 - t ** p["tpow"], 0.0) ** p["taper"]
            * (1.0 + p["wave"] * math.sin(math.pi * p["wf"] * t)))


def value_noise(rng, shape, octaves=3):
    """Smooth periodic-in-theta noise on a (rings, sides) lattice."""
    out = np.zeros(shape)
    amp = 1.0
    for o in range(octaves):
        n = max(3, 2 ** (o + 2))
        s = max(3, min(shape[1], 2 ** (o + 2)))
        g = rng.standard_normal((n, s))
        gi = np.linspace(0, n - 1, shape[0])
        gj = np.linspace(0, s, shape[1], endpoint=False)
        i0 = np.floor(gi).astype(int); fi = (gi - i0)[:, None]
        j0 = np.floor(gj).astype(int); fj = (gj - j0)[None, :]
        fi = fi * fi * (3 - 2 * fi); fj = fj * fj * (3 - 2 * fj)
        i1 = np.minimum(i0 + 1, n - 1); j1 = (j0 + 1) % s
        a = g[np.ix_(i0, j0)] * (1 - fj) + g[np.ix_(i0, j1)] * fj
        b = g[np.ix_(i1, j0)] * (1 - fj) + g[np.ix_(i1, j1)] * fj
        out += amp * (a * (1 - fi) + b * fi)
        amp *= 0.55
    return out / np.abs(out).max()


def build_shell(layer, R, rng):
    p = PLUME[layer]
    rings, sides, L = p["rings"], p["sides"], p["length"]
    ts = np.linspace(0.0, 1.0, rings + 1)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)

    verts, uvs = [], []
    for t in ts:
        rr = radius(p, float(t)) * R
        z = -t * L
        for a in ang:
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
            uvs.append((float(t), 0.5))
    tip = len(verts); verts.append((0.0, 0.0, -L)); uvs.append((1.0, 0.5))
    hub = len(verts); verts.append((0.0, 0.0, 0.0)); uvs.append((0.0, 0.5))

    faces = []
    for i in range(rings):
        for j in range(sides):
            k = (j + 1) % sides
            faces.append((i * sides + j, i * sides + k,
                          (i + 1) * sides + k, (i + 1) * sides + j))
    last = rings * sides
    for j in range(sides):                       # collapse the tip
        faces.append((last + j, last + (j + 1) % sides, tip))
    for j in range(sides):                       # cap the throat
        faces.append((hub, (j + 1) % sides, j))

    me = bpy.data.meshes.new(f"{layer}Mesh")
    me.from_pydata(verts, [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    for lp in me.loops:
        uvl.data[lp.index].uv = uvs[lp.vertex_index]
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(MATS[layer])

    # ---- turbulence shape keys ---------------------------------------
    base = np.array(verts)
    ob = bpy.data.objects.new("tmp", me)
    sc.collection.objects.link(ob)
    ob.shape_key_add(name="Basis", from_mix=False)
    for kname, salt in (("TurbA", 0), ("TurbB", 991)):
        r2 = np.random.default_rng(TURB["seed"] + salt + hash(layer) % 1000)
        nr = value_noise(r2, (rings + 1, sides))
        nx = value_noise(r2, (rings + 1, sides))
        ny = value_noise(r2, (rings + 1, sides))
        key = ob.shape_key_add(name=kname, from_mix=False)
        env = (ts ** 0.7) * np.clip(1.0 - ts ** 4, 0, 1)      # 0 at throat & tip
        idx = 0
        for i, t in enumerate(ts):
            rr = radius(p, float(t)) * R
            for j in range(sides):
                a = ang[j]
                dr = TURB["amp"] * env[i] * nr[i, j] * rr
                dx = TURB["lat"] * env[i] * nx[i, j] * rr * 0.5
                dy = TURB["lat"] * env[i] * ny[i, j] * rr * 0.5
                key.data[idx].co = Vector((
                    base[idx][0] + dr * math.cos(a) + dx,
                    base[idx][1] + dr * math.sin(a) + dy,
                    base[idx][2]))
                idx += 1
        key.data[tip].co = Vector((base[tip][0] + TURB["lat"] * 0.35 * R * float(nx[-1, 0]),
                                   base[tip][1] + TURB["lat"] * 0.35 * R * float(ny[-1, 0]),
                                   base[tip][2]))
        key.value = 0.0
    bpy.data.objects.remove(ob)
    return me


def spark_mesh(size):
    """A tiny elongated octahedron - reads as a streaking ember."""
    h, w = size * 2.6, size * 0.5
    v = [(0, 0, h), (w, 0, 0), (0, w, 0), (-w, 0, 0), (0, -w, 0), (0, 0, -h)]
    f = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
         (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)]
    me = bpy.data.meshes.new("SparkMesh")
    me.from_pydata(v, [], f); me.update()
    me.materials.append(SPARK_MAT)
    return me


SPARK_ME = spark_mesh(SPARK_SIZE)

# ---------------------------------------------------------------- assemble
root = bpy.data.objects.new("Boosters", None)
root.empty_display_size = 0.05
sc.collection.objects.link(root)

rng = np.random.default_rng(TURB["seed"])
for nz in NZ["nozzles"]:
    name = nz["name"]
    pos  = Vector(nz["pos"])
    axis = Vector(nz["axis"]).normalized()
    pos  = pos - axis * RECESS                      # start inside the nozzle

    R    = max(nz["radius"], R_FALLBACK * 0.6)

    e = bpy.data.objects.new(f"Booster_{name}", None)
    e.empty_display_type = 'SINGLE_ARROW'; e.empty_display_size = 0.06
    sc.collection.objects.link(e)
    e.parent = root
    e.location = pos
    # aim: measured nozzle normal, tipped back and outboard by AIM
    side = 1.0 if nz["pos"][1] > NZ["mid_y"] else -1.0
    aim = (Matrix.Rotation(math.radians(side * AIM["out_deg"]), 3, 'X')
           @ Matrix.Rotation(math.radians(AIM["back_deg"]), 3, 'Y') @ axis).normalized()
    e.rotation_mode = 'QUATERNION'
    e.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(aim)

    for layer in reversed(list(PLUME)):             # outermost shell first
        ob = bpy.data.objects.new(f"Booster_{name}_{layer}", build_shell(layer, R, rng))
        sc.collection.objects.link(ob); ob.parent = e
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler.z = rng.uniform(0, 2 * math.pi)

    for k in range(SPARKS):
        ob = bpy.data.objects.new(f"Booster_{name}_Spark{k}", SPARK_ME)
        sc.collection.objects.link(ob); ob.parent = e
        ob.scale = (0, 0, 0)

print(f"  built {len(NZ['nozzles'])} boosters, "
      f"{sum(1 for o in bpy.data.objects if o.name.startswith('Booster_'))} nodes")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "s2.blend"))
print("wrote _work/s2.blend")
sys.stdout.flush(); os._exit(0)
