import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, bmesh, math, json, os
from mathutils import Vector

D=json.load(open(os.path.join(WORK, "dims.json")))
REG=json.load(open(os.path.join(WORK, "regions.json")))
AW,AH=ATLAS_W,ATLAS_H; TY=TILE_Y   # interior tile starts at row 2048
SEAM=D['SEAM']; IN=D['IN']; FLOOR=D['FLOOR']; LID_TOP=D['LID_TOP']
cx,cy=D['cx'],D['cy']
lenx=IN['x'][1]-IN['x'][0]; leny=IN['y'][1]-IN['y'][0]

# ---------- build atlas images ----------
from PIL import Image
def build(dst, ext_img, int_img):
    a=Image.new("RGB",(AW,AH),(0,0,0))
    a.paste(ext_img.resize((2048,2048)),(0,0))
    a.paste(int_img,(0,TY))
    a.save(dst)
build(os.path.join(WORK, "chest_atlas_basecolor.png"),
      Image.open(os.path.join(WORK, "orig_tex.png")).convert("RGB"),
      Image.open(os.path.join(WORK, "interior_col.png")).convert("RGB"))
build(os.path.join(WORK, "chest_atlas_emissive.png"),
      Image.new("RGB",(2048,2048),(0,0,0)),
      Image.open(os.path.join(WORK, "interior_emi.png")).convert("RGB"))
print("atlas written")

def px2uv(px,py):
    return (px/AW, 1.0-(TY+py)/AH)
def inreg(name,fu,fv):
    x0,y0,x1,y1=REG[name]
    return px2uv(x0+(x1-x0)*min(max(fu,0),1), y0+(y1-y0)*min(max(fv,0),1))

bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "s2.blend"))
body=bpy.data.objects["Chest_Body"]; lid=bpy.data.objects["Chest_Lid"]

def assign(ob):
    me=ob.data
    bm=bmesh.new(); bm.from_mesh(me)
    pid=bm.faces.layers.int.get("pid")
    uv=bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        p=f[pid] if pid else 0
        if p==100 or p==0:
            for l in f.loops:
                u,v=l[uv].uv; l[uv].uv=(u, 0.2+0.8*v)
            continue
        c=f.calc_center_median()
        base=math.atan2(c.y-cy, c.x-cx)
        for l in f.loops:
            co=l.vert.co
            if p==3:      # body floor  (top-down)
                fu=(co.y-IN['y'][0])/leny; fv=(co.x-IN['x'][0])/lenx
                l[uv].uv=inreg("A",fu,fv)
            elif p==6:    # lid inner panel
                fu=(co.y-IN['y'][0])/leny; fv=1.0-(co.x-IN['x'][0])/lenx
                l[uv].uv=inreg("B",fu,fv)
            elif p==2:    # inner walls
                a=math.atan2(co.y-cy, co.x-cx)
                while a-base> math.pi: a-=2*math.pi
                while a-base<-math.pi: a+=2*math.pi
                fu=(a+math.pi)/(2*math.pi)
                fv=1.0-(co.z-FLOOR)/(SEAM-FLOOR)
                l[uv].uv=inreg("C",fu,fv)
            elif p==4:    # divider walls
                fu=(co.x-IN['x'][0])/lenx
                fv=1.0-(co.z-FLOOR)/DIV_H
                l[uv].uv=inreg("E",fu,fv)
            else:         # rims / caps / lid inner sides -> generic metal
                a=math.atan2(co.y-cy, co.x-cx)
                while a-base> math.pi: a-=2*math.pi
                while a-base<-math.pi: a+=2*math.pi
                fu=(a+math.pi)/(2*math.pi)
                r=max(abs(co.x-cx)/max(1e-6,lenx/2), abs(co.y-cy)/max(1e-6,leny/2))
                l[uv].uv=inreg("D",fu, min(max((r-0.9)*3.0,0.05),0.95))
    bm.to_mesh(me); bm.free()

assign(body); assign(lid)

# ---------- single material ----------
for m in list(bpy.data.materials): bpy.data.materials.remove(m)
mat=bpy.data.materials.new("ChestAtlas"); mat.use_nodes=True
nt=mat.node_tree
for n in list(nt.nodes):
    if n.type not in ('OUTPUT_MATERIAL',): nt.nodes.remove(n)
out=[n for n in nt.nodes if n.type=='OUTPUT_MATERIAL'][0]
bsdf=nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location=(-300,0)
nt.links.new(bsdf.outputs[0], out.inputs[0])
imgc=bpy.data.images.load(os.path.join(WORK, "chest_atlas_basecolor.png"))
imge=bpy.data.images.load(os.path.join(WORK, "chest_atlas_emissive.png"))
imge.colorspace_settings.name='sRGB'
tc=nt.nodes.new('ShaderNodeTexImage'); tc.image=imgc; tc.location=(-800,200)
te=nt.nodes.new('ShaderNodeTexImage'); te.image=imge; te.location=(-800,-250)
nt.links.new(tc.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(te.outputs['Color'], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value=1.0
bsdf.inputs['Roughness'].default_value=0.85
bsdf.inputs['Metallic'].default_value=0.0
for ob in (body,lid):
    ob.data.materials.clear(); ob.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "s4.blend"))
print("DONE")

# bpy-as-a-module can segfault during interpreter teardown; the work is done by here.
sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
