import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, bmesh, numpy as np, json, math
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "s1.blend"))
body=bpy.data.objects["Chest_Body"]; lid=bpy.data.objects["Chest_Lid"]

def get_loops(bm):
    bnd=[e for e in bm.edges if e.is_boundary]
    emap={}
    for e in bnd:
        for v in e.verts: emap.setdefault(v.index,[]).append(e)
    seen=set(); out=[]
    for e in bnd:
        if e.index in seen: continue
        stack=[e]; loop=[]
        while stack:
            x=stack.pop()
            if x.index in seen: continue
            seen.add(x.index); loop.append(x)
            for v in x.verts:
                for n in emap.get(v.index,[]):
                    if n.index not in seen: stack.append(n)
        out.append(loop)
    out.sort(key=lambda L:-sum(e.calc_length() for e in L))
    return out

# ---- outline metrics from body main loop
bm=bmesh.new(); bm.from_mesh(body.data); bm.edges.ensure_lookup_table()
L=get_loops(bm)[0]
pts=np.array([v.co[:] for e in L for v in e.verts])
X=[float(np.percentile(pts[:,0],1.5)), float(np.percentile(pts[:,0],98.5))]
Y=[float(np.percentile(pts[:,1],1.5)), float(np.percentile(pts[:,1],98.5))]
allco=np.array([v.co[:] for v in bm.verts])
mid=allco[(np.abs(allco[:,0])<0.12)&(np.abs(allco[:,1])<0.15)]
zbot=float(np.percentile(mid[:,2],0.5))
bm.free()
IN={"x":[X[0]+WALL, X[1]-WALL], "y":[Y[0]+WALL, Y[1]-WALL]}
FLOOR=SEAM-CAVITY
print("OUTLINE x",[round(v,4) for v in X],"y",[round(v,4) for v in Y],"zbot",round(zbot,4))
print("INNER x",[round(v,4) for v in IN['x']],"y",[round(v,4) for v in IN['y']],"FLOOR",round(FLOOR,4))
cx=(IN['x'][0]+IN['x'][1])/2; cy=(IN['y'][0]+IN['y'][1])/2
hx=(IN['x'][1]-IN['x'][0])/2; hy=(IN['y'][1]-IN['y'][0])/2

def proj(co, cx,cy,hx,hy):
    dx=co.x-cx; dy=co.y-cy
    m=max(abs(dx)/hx, abs(dy)/hy, 1e-9)
    return cx+dx/m, cy+dy/m

def build(ob, kind):
    me=ob.data
    bm=bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    pid = bm.faces.layers.int.get("pid") or bm.faces.layers.int.new("pid")
    for f in bm.faces: f[pid]=100
    loops=get_loops(bm)
    main=loops[0]
    # fill the small holes (cuts through latch / cables / hinges)
    for sm in loops[1:]:
        made=[]
        try: made=bmesh.ops.triangle_fill(bm, edges=sm, use_beauty=True, use_dissolve=False).get('geom',[])
        except Exception as ex: print("trifill fail", ex)
        if not made:
            try: made=bmesh.ops.holes_fill(bm, edges=sm, sides=0).get('faces',[])
            except Exception as ex: print("holefill fail", ex)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        if f[pid]==0: f[pid]=9  # small hole caps
    # --- rim: extrude main loop and project inward
    ins = 0.0 if kind=='body' else 0.006
    ihx, ihy = hx-ins, hy-ins
    r=bmesh.ops.extrude_edge_only(bm, edges=main)
    nv=[g for g in r['geom'] if isinstance(g,bmesh.types.BMVert)]
    nf=[g for g in r['geom'] if isinstance(g,bmesh.types.BMFace)]
    for v in nv:
        px,py=proj(v.co,cx,cy,ihx,ihy); v.co=Vector((px,py,SEAM))
    for f in nf: f[pid]= 1 if kind=='body' else 5
    bmesh.ops.remove_doubles(bm, verts=nv, dist=1e-4)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    # delete degenerate faces
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bm.edges.ensure_lookup_table()
    # --- second loop = current boundary
    loops2=get_loops(bm); main2=loops2[0]
    zt = FLOOR if kind=='body' else LID_TOP
    r2=bmesh.ops.extrude_edge_only(bm, edges=main2)
    nv2=[g for g in r2['geom'] if isinstance(g,bmesh.types.BMVert)]
    nf2=[g for g in r2['geom'] if isinstance(g,bmesh.types.BMFace)]
    for v in nv2: v.co.z=zt
    for f in nf2: f[pid]= 2 if kind=='body' else 7
    bm.edges.ensure_lookup_table()
    loops3=get_loops(bm); main3=loops3[0]
    res=bmesh.ops.holes_fill(bm, edges=main3, sides=0)
    for f in res.get('faces',[]): f[pid]= 3 if kind=='body' else 6
    bm.faces.ensure_lookup_table()
    RIM = 1 if kind=='body' else 5
    WALLP = 2 if kind=='body' else 7
    CAP = 3 if kind=='body' else 6
    for f in bm.faces:
        if f[pid]!=0: continue
        z=f.calc_center_median().z
        if abs(z-zt)<2e-4: f[pid]=CAP
        elif abs(z-SEAM)<2e-4: f[pid]=RIM
        else: f[pid]=WALLP
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts)>4])
    bm.to_mesh(me); bm.free()
    print(kind,"faces",len(me.polygons))

build(body,'body')
build(lid,'lid')

# --- divider walls + compartment detail inside body
def add_box(name, x0,x1,y0,y1,z0,z1, pid_val, target):
    bm=bmesh.new()
    vs=[]
    for (x,y,z) in [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]:
        vs.append(bm.verts.new((x,y,z)))
    for f in [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]:
        bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    pid=bm.faces.layers.int.new("pid")
    for f in bm.faces: f[pid]=pid_val
    me=bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob=bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    return ob

DW=DIV_T
ys=[IN['y'][0]+(IN['y'][1]-IN['y'][0])*t for t in DIV_AT]
parts=[]
for i,yv in enumerate(ys):
    parts.append(add_box(f"Div{i}", IN['x'][0],IN['x'][1], yv-DW/2, yv+DW/2, FLOOR, FLOOR+DIV_H, 4, body))
# join dividers into body
bpy.ops.object.select_all(action='DESELECT')
for p in parts: p.select_set(True)
body.select_set(True); bpy.context.view_layer.objects.active=body
bpy.ops.object.join()

json.dump({"SEAM":SEAM,"IN":IN,"FLOOR":FLOOR,"LID_TOP":LID_TOP,"X":X,"Y":Y,
           "cx":cx,"cy":cy,"hx":hx,"hy":hy,"ys":ys,"DW":DW,"zbot":zbot},
          open(os.path.join(WORK, "dims.json"), "w"))
from collections import Counter
for ob in (body,lid):
    bmx=bmesh.new(); bmx.from_mesh(ob.data); pl=bmx.faces.layers.int.get("pid")
    print("PID",ob.name,Counter(f[pl] for f in bmx.faces)); bmx.free()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "s2.blend"))
print("DONE body",len(body.data.polygons),"lid",len(lid.data.polygons))

# bpy-as-a-module can segfault during interpreter teardown; the work is done by here.
sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
