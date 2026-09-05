"""Render the Three.js flight model driving the shipped glb.

Reads frames dumped by the harness (position / attitude / gimbal / throttle,
produced by the real `sampleFlight` in src/components/astronaut-boosters.tsx)
and applies them to the imported glb, so what you see is the component's own
maths on the component's own asset. Draws the velocity (green) and the required
thrust direction (cyan) so you can check the plumes fire opposite the cyan one.

    python3 booster_anim/06_flight_check.py flight.json
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, mathutils
from mathutils import Vector, Quaternion

FRAMES = json.load(open(sys.argv[1]))
OUTDIR = os.path.join(WORK, "flight"); os.makedirs(OUTDIR, exist_ok=True)

# scene placement, matching mouser-game.tsx
ANCHOR = tuple(float(x) for x in os.environ.get("ANCHOR", "-5.8,2.6,-6.5").split(","))
SIZE = float(os.environ.get("SIZE", "4.6"))
CAM = (0.0, 0.0, 11.0)
FOV = 55.0                       # three.js fov is the VERTICAL angle
FOG = (14.0, 30.0)
FOG_RGB = (0x03 / 255, 0x04 / 255, 0x0c / 255)
ARROWS = os.environ.get("ARROWS", "1") == "1"

# glTF -> Blender:  v_b = (x, -z, y);  q_b = (x, -z, y, w)
g2b_v = lambda v: Vector((v[0], -v[2], v[1]))
g2b_q = lambda q: Quaternion((q[3], q[0], -q[2], q[1]))
g2b_s = lambda s: Vector((s[0], s[2], s[1]))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=OUT_GLB)
sc = bpy.context.scene

roots = [o for o in bpy.data.objects if o.parent is None and o.name in ("Astronaut", "Boosters")]
rig = bpy.data.objects.new("Rig", None); sc.collection.objects.link(rig)
for r in roots:
    r.parent = rig
    r.matrix_parent_inverse = mathutils.Matrix.Identity(4)
anchor = bpy.data.objects.new("Anchor", None); sc.collection.objects.link(anchor)
rig.parent = anchor
anchor.location = g2b_v(ANCHOR)
rig.rotation_mode = 'QUATERNION'

L = bpy.data.objects["Booster_L"]; R = bpy.data.objects["Booster_R"]
L.rotation_mode = R.rotation_mode = 'QUATERNION'
restL, restR = L.rotation_quaternion.copy(), R.rotation_quaternion.copy()
# glTF pitch axis (0,0,1) and yaw axis (1,0,0), expressed in Blender
AX_PITCH, AX_YAW = Vector((0, -1, 0)), Vector((1, 0, 0))


def arrow(name, colour):
    me = bpy.data.meshes.new(name)
    r, h = 0.035, 1.0
    v, f = [], []
    n = 10
    for i in range(n):
        a = 2 * math.pi * i / n
        v.append((r * math.cos(a), r * math.sin(a), 0))
        v.append((r * math.cos(a), r * math.sin(a), h * 0.78))
        v.append((r * 2.4 * math.cos(a), r * 2.4 * math.sin(a), h * 0.78))
    tip = len(v); v.append((0, 0, h))
    for i in range(n):
        j = (i + 1) % n
        f += [(i * 3, j * 3, j * 3 + 1, i * 3 + 1),
              (i * 3 + 1, j * 3 + 1, j * 3 + 2, i * 3 + 2),
              (i * 3 + 2, j * 3 + 2, tip)]
    me.from_pydata(v, [], f); me.update()
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0, 0, 0, 1)
    b.inputs["Emission Color"].default_value = colour
    b.inputs["Emission Strength"].default_value = 3.0
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    o.rotation_mode = 'QUATERNION'
    return o


vel_arrow = arrow("Vel", (0.2, 1.0, 0.3, 1))
frc_arrow = arrow("Force", (0.25, 0.85, 1.0, 1))


def aim(obj, at, direction, length):
    obj.location = at
    d = Vector(direction)
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    obj.scale = (1, 1, max(length, 0.01))


# --- lighting / camera ------------------------------------------------------
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = int(os.environ.get('SAMPLES', '12'))
sc.render.resolution_x = int(os.environ.get('RESX', '960'))
sc.render.resolution_y = int(os.environ.get('RESY', '540'))
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
# the game's own lighting. three point lights are candela with decay 2, so
# irradiance is I/d^2; Blender point lights are watts, P/(4*pi*d^2) -> P = 4*pi*I
# ambientLight intensity=1.1 is irradiance in three; a uniform white Blender
# world of strength S gives pi*S, so S ~ 1.1/pi. The scene background is drawn
# separately in the composite, hence film_transparent on the suit pass.
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.1 / math.pi
for nm, loc, cd_, col in (("key", (8, 6, 12), 260, (0.81, 0.88, 1.0)),
                          ("rim", (-9, -5, 6), 160, (0.69, 0.42, 1.0))):
    ld = bpy.data.lights.new(nm, 'POINT'); ld.energy = 4 * math.pi * cd_
    ld.color = col
    lo = bpy.data.objects.new(nm, ld); sc.collection.objects.link(lo)
    lo.location = g2b_v(loc)
sun = bpy.data.lights.new("sun", 'SUN'); sun.energy = 2.2
so = bpy.data.objects.new("sun", sun); sc.collection.objects.link(so)
so.rotation_euler = (g2b_v((0, 0, 0)) - g2b_v((0, 4, 8))).to_track_quat('-Z', 'Y').to_euler()
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.sensor_fit = 'VERTICAL'; cd.lens_unit = 'FOV'; cd.angle_y = math.radians(FOV)
cam.location = g2b_v(CAM)
cam.rotation_euler = (math.radians(90), 0, 0)

suit = bpy.data.objects["Astronaut"]
plume = [o for o in bpy.data.objects if o.name.startswith("Booster")]
arrows = [vel_arrow, frc_arrow]

from PIL import Image
import numpy as np
shots = []
for i, f in enumerate(FRAMES):
    if "clipFrame" in f:
        sc.frame_set(int(f["clipFrame"]), subframe=f["clipFrame"] % 1.0)
    rig.location = g2b_v(f["pos"])
    rig.rotation_quaternion = g2b_q(f["quat"])
    rig.scale = (SIZE, SIZE, SIZE)
    for node, rest, sign in ((L, restL, +1), (R, restR, -1)):
        qp = Quaternion(AX_PITCH, f["pitch"])
        qy = Quaternion(AX_YAW, f["roll"] + sign * f["diff"])
        node.rotation_quaternion = qp @ qy @ rest      # premultiply, model-space axes
        node.scale = g2b_s((f["width"], f["length"], f["width"]))
    base = anchor.location + g2b_v(f["pos"]) * 1.0
    aim(vel_arrow, base + Vector((0, 0, 1.2)), g2b_v(f["vel"]), 3.0 * Vector(f["vel"]).length + 0.4)
    aim(frc_arrow, base + Vector((0, 0, 1.2)), g2b_v(f["force"]), 2.2)

    bpy.context.view_layer.update()
    for o in plume + arrows: o.hide_render = True
    sc.render.film_transparent = True
    sc.render.filepath = os.path.join(OUTDIR, f"_a_{i}.png"); bpy.ops.render.render(write_still=True)
    for o in plume: o.hide_render = False
    suit.hide_render = True
    sc.render.film_transparent = True
    sc.render.filepath = os.path.join(OUTDIR, f"_b_{i}.png"); bpy.ops.render.render(write_still=True)
    if ARROWS:
        for o in arrows: o.hide_render = False
        for o in plume: o.hide_render = True
        sc.render.filepath = os.path.join(OUTDIR, f"_c_{i}.png"); bpy.ops.render.render(write_still=True)
    suit.hide_render = False
    for o in plume: o.hide_render = False

    ap = np.asarray(Image.open(os.path.join(OUTDIR, f"_a_{i}.png")).convert("RGBA")).astype(np.float32)/255
    b = np.asarray(Image.open(os.path.join(OUTDIR, f"_b_{i}.png")).convert("RGBA")).astype(np.float32)/255
    # the suit sits in the scene's linear fog; the plume materials have fog off
    dist = (cam.location - (anchor.location + g2b_v(f["pos"]))).length
    fog = min(1.0, max(0.0, (dist - FOG[0]) / (FOG[1] - FOG[0])))
    bg = np.array(FOG_RGB, np.float32)
    lit = ap[..., :3] * (1 - fog) + bg * fog          # suit, fogged
    a = lit * ap[..., 3:4] + bg * (1 - ap[..., 3:4])  # over the scene background
    img = a + b[..., :3]*b[..., 3:4]*1.5
    if ARROWS:
        c = np.asarray(Image.open(os.path.join(OUTDIR, f"_c_{i}.png")).convert("RGBA")).astype(np.float32)/255
        img = img + c[..., :3]*c[..., 3:4]*0.9
    img = np.clip(img, 0, 1)
    im = Image.fromarray((img*255+.5).astype(np.uint8))
    im.save(os.path.join(OUTDIR, f"f{i:03d}.png")); shots.append(im)
    for p in ("_a_", "_b_") + (("_c_",) if ARROWS else ()):
        os.remove(os.path.join(OUTDIR, f"{p}{i}.png"))
    print(f"  t={f['t']:5.1f}s throttle={f['throttle']:.2f} len={f['length']:.2f} "
          f"thrustErr={f.get('thrustErrDeg', 0):.2f}deg fog={fog:.2f} dist={dist:.1f}")

if len(shots) > 12:
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-framerate", "24", "-pattern_type", "glob",
                    "-i", os.path.join(OUTDIR, "f*.png"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p",
                    "-crf", "20", os.path.join(OUTDIR, "flight.mp4")], capture_output=True)
    print("wrote", os.path.join(OUTDIR, "flight.mp4"))
else:
    sheet = Image.new("RGB", (shots[0].width*len(shots), shots[0].height))
    for i, im in enumerate(shots): sheet.paste(im, (i*im.width, 0))
    sheet.save(os.path.join(OUTDIR, "sheet.png"))
    print("wrote", os.path.join(OUTDIR, "sheet.png"))
sys.stdout.flush(); os._exit(0)
