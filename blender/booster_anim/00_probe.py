"""Locate the two thruster nozzles on the astronaut's pack.

Reads ../astronaut.glb, fits each nozzle mouth (centre, axis, radius) and
writes _work/nozzles.json.  Everything downstream reads that file, so the
build survives the source mesh being re-exported or nudged.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, numpy as np

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
ob = next(o for o in bpy.data.objects if o.type == 'MESH')
ob.name = "Astronaut"; ob.data.name = "AstronautMesh"

V    = np.array([v.co[:] for v in ob.data.vertices])
cen  = np.array([p.center[:] for p in ob.data.polygons])
nrm  = np.array([p.normal[:] for p in ob.data.polygons])
area = np.array([p.area for p in ob.data.polygons])

out = []
for spec in NOZZLE_SEED:
    sx, sy = spec["seed_xy"]
    # walk the search disc onto the actual mouth centroid
    for _ in range(6):
        d = np.hypot(V[:, 0] - sx, V[:, 1] - sy)
        s = (d < PROBE_R) & (V[:, 2] > PROBE_Z[0]) & (V[:, 2] < PROBE_Z[1])
        if s.sum() < 12:
            raise SystemExit(f"nozzle {spec['name']}: nothing under the seed point")
        low = V[s]
        low = low[low[:, 2] <= np.percentile(low[:, 2], 35)]   # the mouth ring
        sx, sy = float(low[:, 0].mean()), float(low[:, 1].mean())
    zm = float(np.median(low[:, 2]))

    # axis = area-weighted normal of the down-facing faces around the mouth
    dm = np.hypot(cen[:, 0] - sx, cen[:, 1] - sy)
    f  = (dm < PROBE_R + 0.001) & (nrm[:, 2] < -0.5) & \
         (cen[:, 2] > PROBE_Z[0]) & (cen[:, 2] < PROBE_Z[1] - 0.005)
    ax = (nrm[f] * area[f, None]).sum(0) / area[f].sum()
    ax = ax / np.linalg.norm(ax)
    r  = float(np.percentile(np.hypot(cen[f][:, 0] - sx, cen[f][:, 1] - sy), 55))

    out.append(dict(name=spec["name"], pos=[sx, sy, zm],
                    axis=[float(a) for a in ax], radius=max(r, 0.006)))
    print(f"  {spec['name']}: pos=({sx:+.4f},{sy:+.4f},{zm:.4f}) "
          f"axis=({ax[0]:+.3f},{ax[1]:+.3f},{ax[2]:+.3f}) r={r:.4f} faces={f.sum()}")

# symmetrise the outward tilt so the two plumes splay evenly
mid_y = sum(n["pos"][1] for n in out) / len(out)
back  = sum(n["axis"][0] for n in out) / len(out)
splay = sum(abs(n["axis"][1]) for n in out) / len(out)
for n in out:
    side = 1.0 if n["pos"][1] > mid_y else -1.0
    a = np.array([back, side * splay, n["axis"][2]])
    n["axis"] = [float(x) for x in a / np.linalg.norm(a)]
print(f"  symmetrised: back={back:+.3f} splay=±{splay:.3f} about y={mid_y:+.4f}")

json.dump(dict(nozzles=out, mid_y=mid_y), open(os.path.join(WORK, "nozzles.json"), "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "s0.blend"))
print("wrote _work/nozzles.json + s0.blend")
sys.stdout.flush(); os._exit(0)
