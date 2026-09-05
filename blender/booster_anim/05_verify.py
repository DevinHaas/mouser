"""Round-trip check: import the exported glb back and render the loop.

Proves the clip, the morph targets and the materials survived the export -
this renders the shipped file, not the scene it was built from.
Writes _work/preview/loop.gif + loop.mp4 and a contact sheet.
"""
import sys, os, math, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, mathutils

VIEW  = sys.argv[1] if len(sys.argv) > 1 else "q34"
STEP  = int(sys.argv[2]) if len(sys.argv) > 2 else 2
outdir = os.path.join(WORK, "preview"); os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=OUT_GLB)
sc = bpy.context.scene

names = [o.name for o in bpy.data.objects]
acts  = [o for o in bpy.data.objects if o.animation_data and o.animation_data.action]
keyed = [o for o in bpy.data.objects
         if o.type == 'MESH' and o.data.shape_keys and o.data.shape_keys.animation_data]
print(f"  imported {len(names)} objects; {len(acts)} with transform actions, "
      f"{len(keyed)} with morph actions")
print(f"  actions: {len(bpy.data.actions)}   frame range {sc.frame_start}..{sc.frame_end} @ {sc.render.fps}fps")
missing = [n for n in ("Boosters", "Booster_L", "Booster_R",
                       "Booster_L_Core", "Booster_R_Halo") if n not in names]
print("  MISSING NODES:", missing if missing else "none")

sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 10
sc.render.resolution_x, sc.render.resolution_y = 420, 540
sc.render.fps = FPS

w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.030, 0.033, 0.040, 1)
for nm, loc, e in (("key", (1.4, -1.6, 1.5), 55), ("rim", (-1.9, 1.1, 0.9), 55),
                   ("fill", (-1.1, -1.5, 0.3), 16)):
    ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.size = 1.6
    lo = bpy.data.objects.new(nm, ld); sc.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (mathutils.Vector((0, 0, 0.12)) - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

VIEWS = {"back": (180, 4, (-0.09, 0.015, 0.045), 0.42),
         "q34":  (146, 11, (-0.07, 0.015, 0.040), 0.44),
         "side": (98, 6,  (-0.05, 0.015, 0.040), 0.44)}
az, el, tgt, sca = VIEWS[VIEW]
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = 'ORTHO'; cd.ortho_scale = sca
a, e = math.radians(az), math.radians(el)
t = mathutils.Vector(tgt)
loc = t + mathutils.Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * 3.0
cam.location = loc
cam.rotation_euler = (t - loc).to_track_quat('-Z', 'Y').to_euler()

# glTF nests everything under a converted-coordinate root, so match by suffix
boosters = [o for o in bpy.data.objects
            if o.name == "Boosters" or o.name.startswith("Booster_")]
suit = max((o for o in bpy.data.objects if o.type == "MESH" and o not in boosters),
           key=lambda o: len(o.data.vertices))

suitpng = os.path.join(outdir, f"_vsuit_{VIEW}.png")
for o in boosters: o.hide_render = True
sc.render.film_transparent = False
sc.render.filepath = suitpng; bpy.ops.render.render(write_still=True)
for o in boosters: o.hide_render = False
suit.hide_render = True
sc.render.film_transparent = True

frames = list(range(0, FRAMES, STEP))
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(outdir, f"_vfl_{f:03d}.png")
    bpy.ops.render.render(write_still=True)

from PIL import Image
import numpy as np
s = np.asarray(Image.open(suitpng).convert("RGB")).astype(np.float32) / 255
seq = []
for f in frames:
    fp = os.path.join(outdir, f"_vfl_{f:03d}.png")
    p = np.asarray(Image.open(fp).convert("RGBA")).astype(np.float32) / 255
    im = Image.fromarray((np.clip(s + p[..., :3] * p[..., 3:4] * 1.25, 0, 1) * 255 + .5).astype(np.uint8))
    im.save(os.path.join(outdir, f"loop_{f:03d}.png"))
    seq.append(im); os.remove(fp)

seq[0].save(os.path.join(outdir, "loop.gif"), save_all=True, append_images=seq[1:],
            duration=int(1000 * STEP / FPS), loop=0, optimize=True)
try:
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS // STEP),
                    "-pattern_type", "glob", "-i", os.path.join(outdir, "loop_*.png"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p",
                    "-crf", "20", os.path.join(outdir, "loop.mp4")],
                   check=True, capture_output=True)
except Exception as ex:
    print("  (no mp4:", ex, ")")

cols = 6
sheet = Image.new("RGB", (seq[0].width * cols, seq[0].height * ((len(seq) + cols - 1) // cols)))
for i, im in enumerate(seq):
    sheet.paste(im, ((i % cols) * im.width, (i // cols) * im.height))
sheet.save(os.path.join(outdir, "contact.png"))
print(f"  rendered {len(seq)} frames -> loop.gif / loop.mp4 / contact.png")
sys.stdout.flush(); os._exit(0)
