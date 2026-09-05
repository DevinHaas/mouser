"""Render check frames.  Usage: python3 preview.py [blend] [frame] [views]

Renders the suit and the plumes as two passes and adds them together, which
is what additive blending in Three.js actually looks like -- Blender's EEVEE
has no additive blend mode, so a straight render lies to you.
The suit pass is cached in _work/preview/_suit_<view>.png.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, mathutils

blend  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK, "s2.blend")
frame  = int(sys.argv[2]) if len(sys.argv) > 2 else 0
want   = (sys.argv[3].split(",") if len(sys.argv) > 3 else ["back", "q34"])
turb   = float(sys.argv[4]) if len(sys.argv) > 4 else None
outdir = os.path.join(WORK, "preview"); os.makedirs(outdir, exist_ok=True)

VIEWS = {"back": (180, 4,  (-0.09, 0.015, 0.055), 0.40),
         "q34":  (145, 12, (-0.07, 0.015, 0.050), 0.42),
         "side": (95,  6,  (-0.05, 0.015, 0.050), 0.42),
         "low":  (165, -18,(-0.08, 0.015, 0.060), 0.40),
         "wide": (160, 8,  (-0.02, 0.010, 0.010), 1.05)}

bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 16
sc.render.resolution_x, sc.render.resolution_y = 560, 660
sc.frame_set(frame)

w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.030, 0.033, 0.040, 1)
for nm, loc, e in (("key", (1.4, -1.6, 1.5), 55), ("rim", (-1.9, 1.1, 0.9), 55),
                   ("fill", (-1.1, -1.5, 0.3), 16)):
    ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.size = 1.6
    lo = bpy.data.objects.new(nm, ld); sc.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (mathutils.Vector((0, 0, 0.12)) - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam; cd.type = 'ORTHO'

if turb is not None:
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys and "TurbA" in o.data.shape_keys.key_blocks:
            o.data.shape_keys.key_blocks["TurbA"].value = turb
            o.data.shape_keys.key_blocks["TurbB"].value = max(0.0, 1.0 - turb)

boosters = [o for o in bpy.data.objects if o.name.startswith("Boosters") or o.name.startswith("Booster_")]
suit     = bpy.data.objects["Astronaut"]

def place(view):
    az, el, tgt, sca = VIEWS[view]
    cd.ortho_scale = sca
    a, e = math.radians(az), math.radians(el)
    t = mathutils.Vector(tgt)
    loc = t + mathutils.Vector((math.cos(e)*math.cos(a), math.cos(e)*math.sin(a), math.sin(e))) * 3.0
    cam.location = loc
    cam.rotation_euler = (t - loc).to_track_quat('-Z', 'Y').to_euler()

from PIL import Image
import numpy as np

shells = {k: [o for o in boosters if o.name.endswith("_" + k)] for k in PLUME}
sparks = [o for o in boosters if "_Spark" in o.name]

for view in want:
    place(view)

    # --- suit pass (cached) -------------------------------------------
    suitpng = os.path.join(outdir, f"_suit_{view}.png")
    if not os.path.exists(suitpng):
        for o in boosters: o.hide_render = True
        sc.render.film_transparent = False
        sc.render.filepath = suitpng; bpy.ops.render.render(write_still=True)

    # --- one pass per shell, summed = true additive blending ----------
    suit.hide_render = True
    sc.render.film_transparent = True
    acc = None
    groups = [(k, v) for k, v in shells.items()] + [("Spark", sparks)]
    for gname, objs in groups:
        for o in boosters: o.hide_render = True
        for o in objs: o.hide_render = False
        f = os.path.join(outdir, f"_g_{view}_{gname}.png")
        sc.render.filepath = f; bpy.ops.render.render(write_still=True)
        p = np.asarray(Image.open(f).convert("RGBA")).astype(np.float32) / 255
        lay = p[..., :3] * p[..., 3:4]
        acc = lay if acc is None else acc + lay
        os.remove(f)
    suit.hide_render = False
    for o in boosters: o.hide_render = False

    s = np.asarray(Image.open(suitpng).convert("RGB")).astype(np.float32) / 255
    Image.fromarray((np.clip(s + acc, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(outdir, f"{view}_{frame:03d}.png"))
    Image.fromarray((np.clip(acc, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(outdir, f"flame_{view}_{frame:03d}.png"))

print("preview ->", outdir, want, "frame", frame)
sys.stdout.flush(); os._exit(0)
