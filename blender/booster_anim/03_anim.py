"""Keyframe the looping burn.

Everything is driven by sums of sines whose frequencies are whole numbers of
cycles per loop, so frame 0 and frame FRAMES are bit-identical and the clip
tiles seamlessly under THREE.LoopRepeat.

Per shell:
  * scale Z  - the plume lengthens and shortens (three incommensurate rates)
  * scale XY - counter-pulses slightly, so it necks in as it stretches
  * rot Z    - a slow roll wobble, different sign per shell, so the layers
               shear against each other instead of moving as one lump
  * loc  Z   - a sub-millimetre bob at the throat
  * TurbA/TurbB - cross-faded shape keys; the sum is pinned to 1.0 so the
               plume changes shape without changing volume

Sparks ride the plume: each one loops from throat to tip on its own phase,
scaling up out of nothing and back down to nothing at the wrap point.
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, numpy as np

bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "s2.blend"))
sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 0, FRAMES
sc.name = CLIP                      # 'SCENE' export mode names the clip after it
PULSE_D = dict(PULSE)
TAU = 2.0 * math.pi
REF_L = PLUME["Wash"]["length"]


def key(ob, path, frame, index=-1):
    ob.keyframe_insert(data_path=path, frame=frame, index=index)


rng = np.random.default_rng(4242)
shells, sparks = [], []
for ob in bpy.data.objects:
    if not ob.name.startswith("Booster_") or ob.type != 'MESH':
        continue
    (sparks if "_Spark" in ob.name else shells).append(ob)
shells.sort(key=lambda o: o.name); sparks.sort(key=lambda o: o.name)

# stable per-object phase offsets
phase = {o.name: float(rng.uniform(0, TAU)) for o in shells}
sside = {o.name: float(rng.uniform(0, TAU)) for o in shells}

for ob in shells:
    layer = ob.name.rsplit("_", 1)[1]
    ph, ph2 = phase[ob.name], sside[ob.name]
    base_rz = ob.rotation_euler.z
    spin = math.radians(SPIN[layer])
    for f in range(FRAMES + 1):
        u = f / FRAMES
        d = sum(a * math.sin(TAU * c * u + ph + i * 1.7)
                for i, (c, a) in enumerate(PULSE_D[layer]))
        ob.scale = (1.0 - 0.34 * d, 1.0 - 0.34 * d, 1.0 + d)
        ob.rotation_euler.z = base_rz + spin * math.sin(TAU * u + ph2)
        ob.location.z = 0.0018 * REF_L / 0.215 * math.sin(TAU * 2 * u + ph)
        key(ob, "scale", f); key(ob, "rotation_euler", f, 2); key(ob, "location", f, 2)

    kb = ob.data.shape_keys.key_blocks
    for f in range(FRAMES + 1):
        u = f / FRAMES
        a = 0.5 + 0.34 * math.sin(TAU * u + ph) + 0.16 * math.sin(TAU * 3 * u + ph2)
        kb["TurbA"].value = a
        kb["TurbB"].value = 1.0 - a
        kb["TurbA"].keyframe_insert("value", frame=f)
        kb["TurbB"].keyframe_insert("value", frame=f)

# ---------------------------------------------------------------- sparks
def wash_radius(t):
    p = PLUME["Wash"]
    return ((p["r0"] + p["grow"] * t ** p["gpow"])
            * max(1.0 - t ** p["tpow"], 0.0) ** p["taper"])


NZ = json.load(open(os.path.join(WORK, "nozzles.json")))
RAD = {n["name"]: max(n["radius"], R_FALLBACK * 0.6) for n in NZ["nozzles"]}

for ob in sparks:
    _, side, tag = ob.name.split("_")
    k = int(tag.replace("Spark", ""))
    R = RAD[side]
    p0    = (k + (0.37 if side == "R" else 0.0)) / SPARKS
    theta = rng.uniform(0, TAU)
    swirl = rng.uniform(-1.6, 1.6)
    wob   = rng.uniform(0.55, 0.95)     # keep the embers inside the plume
    size  = rng.uniform(0.65, 1.15)
    for f in range(FRAMES + 1):
        u  = (p0 + f / FRAMES) % 1.0
        tt = 0.04 + 0.92 * u
        a  = theta + swirl * u
        rr = R * wash_radius(min(tt, 0.999)) * (0.30 + 0.62 * u ** 0.8) * wob
        ob.location = (rr * math.cos(a), rr * math.sin(a), -tt * REF_L * 1.06)
        s = size * math.sin(math.pi * min(u, 0.999)) ** 0.55
        s = 0.0 if u < 0.02 or u > 0.985 else s
        ob.scale = (s, s, s * (1.0 + 0.9 * u))
        key(ob, "location", f); key(ob, "scale", f)

# linear interpolation everywhere: the curves are already dense (one key per
# frame) and bezier handles would overshoot on the spark wrap
for act in bpy.data.actions:
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

sc.frame_set(0)
print(f"  {len(shells)} shells + {len(sparks)} sparks keyed over "
      f"{FRAMES} frames @ {FPS}fps = {FRAMES/FPS:.2f}s")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "s3.blend"))
print("wrote _work/s3.blend")
sys.stdout.flush(); os._exit(0)
