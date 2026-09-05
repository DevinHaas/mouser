import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy, bmesh, math, json, numpy as np
from mathutils import Matrix, Vector

D=json.load(open(os.path.join(WORK, "dims.json")))
SEAM=D['SEAM']
bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "s4.blend"))
body=bpy.data.objects["Chest_Body"]; lid=bpy.data.objects["Chest_Lid"]

# hinge x = back wall plane of the lid at the seam
co=np.array([v.co[:] for v in lid.data.vertices])
seamv=co[np.abs(co[:,2]-SEAM)<2e-4]
HX=float(np.percentile(seamv[:,0],4.0))
HZ=SEAM
print("HINGE x",round(HX,4),"z",round(HZ,4))

# re-origin the lid onto the hinge line
piv=Vector((HX,0.0,HZ))
lid.data.transform(Matrix.Translation(-piv))
lid.matrix_world = Matrix.Translation(piv)
lid.rotation_mode='XYZ'

m=bpy.data.materials["ChestAtlas"]
m.use_backface_culling=True
# emissive only needs the interior strip -> half res saves GPU memory
from PIL import Image as _I
_e=_I.open(os.path.join(WORK, "chest_atlas_emissive.png")); _e.resize((1024,1280),_I.LANCZOS).save(os.path.join(WORK, "chest_atlas_emissive_half.png"))
for n in m.node_tree.nodes:
    if n.type=='TEX_IMAGE' and 'emissive' in n.image.filepath:
        n.image=bpy.data.images.load(os.path.join(WORK, "chest_atlas_emissive_half.png"))
        n.image.colorspace_settings.name='sRGB'
# signed volume check (normals outward?)
import bmesh as _bm
for ob in (body,lid):
    b2=_bm.new(); b2.from_mesh(ob.data); _bm.ops.triangulate(b2,faces=b2.faces)
    vol=0.0
    for f in b2.faces:
        a,b_,c=[v.co for v in f.verts]
        vol+=a.dot(b_.cross(c))/6.0
    print("VOLUME",ob.name,round(vol,5)); b2.free()
sc=bpy.context.scene
sc.render.fps=FPS
sc.frame_start=0; sc.frame_end=OPEN_KEYS[-1][0]
lid.animation_data_clear()
keys=OPEN_KEYS
for f,deg in keys:
    lid.rotation_euler=(0.0, math.radians(deg), 0.0)
    lid.keyframe_insert(data_path="rotation_euler", frame=f)
act=lid.animation_data.action
act.name="Open"
for fc in act.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation='BEZIER'
        kp.handle_left_type='AUTO_CLAMPED'; kp.handle_right_type='AUTO_CLAMPED'
# ease out of rest, ease into settle
for fc in act.fcurves:
    fc.keyframe_points[0].handle_right_type='VECTOR'
    fc.keyframe_points[-1].handle_left_type='AUTO_CLAMPED'
lid.rotation_euler=(0,0,0)
sc.frame_set(0)

body.name="ChestBody"; lid.name="ChestLid"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "s5.blend"))

OUT=OUT_GLB
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
    export_animations=True, export_animation_mode='ACTIONS',
    export_bake_animation=False, export_optimize_animation_size=True,
    export_current_frame=False, export_frame_range=True,
    export_apply=False, export_yup=True,
    export_image_format='JPEG', export_jpeg_quality=92,
    export_materials='EXPORT', export_normals=True,
    export_texcoords=True, export_tangents=False,
    export_extras=False, export_cameras=False, export_lights=False)
import os
print("EXPORTED", OUT, round(os.path.getsize(OUT)/1e6,2),"MB")

# bpy-as-a-module can segfault during interpreter teardown; the work is done by here.
sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
