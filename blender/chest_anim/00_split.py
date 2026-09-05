import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, bmesh, mathutils, numpy as np, json
from mathutils import Vector

def extract_source_texture():
    """Pull the source glb's baked albedo out so 03_atlas can composite it."""
    import struct, json as _j, io
    from PIL import Image
    with open(SRC_GLB, "rb") as f:
        struct.unpack("<III", f.read(12))
        clen, _ = struct.unpack("<II", f.read(8)); js = _j.loads(f.read(clen))
        blen, _ = struct.unpack("<II", f.read(8)); bin_ = f.read(blen)
    bv = js["bufferViews"][js["images"][0]["bufferView"]]
    off = bv.get("byteOffset", 0)
    img = Image.open(io.BytesIO(bin_[off:off + bv["byteLength"]])).convert("RGB")
    img.save(os.path.join(WORK, "orig_tex.png"))
extract_source_texture()



bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
o=[x for x in bpy.data.objects if x.type=='MESH'][0]
# apply transform so we work in world space
bpy.ops.object.select_all(action='DESELECT')
o.select_set(True); bpy.context.view_layer.objects.active=o
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
o.name="Chest_Body"; o.data.name="Chest_Body"

co=np.array([v.co[:] for v in o.data.vertices])
# core box: robust percentiles of vertices that lie in the main body slab
slab = co[(co[:,2]>-0.10)&(co[:,2]<0.10)]
core = {
 "x": [float(np.percentile(slab[:,0],0.5)), float(np.percentile(slab[:,0],99.5))],
 "y": [float(np.percentile(slab[:,1],0.5)), float(np.percentile(slab[:,1],99.5))],
 "z": [float(co[:,2].min()), float(co[:,2].max())],
}
print("CORE", json.dumps(core))
print("full bbox", co.min(0).round(4).tolist(), co.max(0).round(4).tolist())

me=o.data
bm=bmesh.new(); bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
print("merged -> verts", len(bm.verts), "boundary", sum(1 for e in bm.edges if e.is_boundary))
geom=list(bm.verts)+list(bm.edges)+list(bm.faces)
res=bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6,
        plane_co=(0,0,SEAM), plane_no=(0,0,1), clear_inner=False, clear_outer=False)
bm.to_mesh(me); bm.free()
print("after bisect verts", len(me.vertices), "faces", len(me.polygons))

# select faces above seam
bpy.ops.object.mode_set(mode='EDIT')
bm=bmesh.from_edit_mesh(me)
bm.faces.ensure_lookup_table()
for f in bm.faces:
    f.select_set(f.calc_center_median().z > SEAM + 1e-6)
bmesh.update_edit_mesh(me)
bpy.ops.mesh.separate(type='SELECTED')
bpy.ops.object.mode_set(mode='OBJECT')
objs=[x for x in bpy.data.objects if x.type=='MESH']
print("objects after separate", [(x.name, len(x.data.polygons)) for x in objs])
lid=[x for x in objs if x is not o][0]
lid.name="Chest_Lid"; lid.data.name="Chest_Lid"

def loops(ob):
    bm=bmesh.new(); bm.from_mesh(ob.data)
    bnd=[e for e in bm.edges if e.is_boundary]
    seen=set(); out=[]
    emap={}
    for e in bnd:
        for v in e.verts: emap.setdefault(v, []).append(e)
    for e in bnd:
        if e in seen: continue
        stack=[e]; loop=[]
        while stack:
            x=stack.pop()
            if x in seen: continue
            seen.add(x); loop.append(x)
            for v in x.verts:
                for n in emap.get(v,[]):
                    if n not in seen: stack.append(n)
        per=sum(l.calc_length() for l in loop)
        zs=[v.co.z for l in loop for v in l.verts]
        out.append((len(loop), round(per,4), round(min(zs),3), round(max(zs),3)))
    bm.free()
    out.sort(key=lambda t:-t[1])
    return out
print("BODY loops", loops(o)[:8], "count", len(loops(o)))
print("LID  loops", loops(lid)[:8], "count", len(loops(lid)))
json.dump(core, open(os.path.join(WORK, "core.json"), "w"))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "s1.blend"))
print("DONE")

# bpy-as-a-module can segfault during interpreter teardown; the work is done by here.
sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
