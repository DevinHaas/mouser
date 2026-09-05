"""Export ../astronaut_animated.glb, then verify (and if need be repair) it.

Blender's exporter is close but not guaranteed on the two things this asset
lives or dies by: the plume materials must be alphaMode BLEND with a black
base colour and an emissive texture, and the whole burn must land in ONE
animation clip.  So after the export we open the glb, check the JSON, patch
what's wrong and write it back.
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import bpy

bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "s3.blend"))
sc = bpy.context.scene
sc.frame_set(0)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB, export_format='GLB',
    export_animations=True, export_animation_mode='SCENE',
    export_frame_range=True, export_optimize_animation_size=True,
    export_morph=True, export_morph_normal=False, export_morph_tangent=False,
    export_apply=False, export_yup=True,
    export_image_format='AUTO',
    export_materials='EXPORT', export_normals=True, export_texcoords=True,
    export_tangents=False, export_extras=False,
    export_cameras=False, export_lights=False)

# ------------------------------------------------------------------ verify
def read_glb(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'glTF', "not a glb"
    off, chunks = 12, []
    while off < len(b):
        ln, ty = struct.unpack_from('<II', b, off)
        chunks.append((ty, b[off + 8: off + 8 + ln])); off += 8 + ln
    js = json.loads(chunks[0][1].decode('utf-8'))
    return js, chunks


def write_glb(path, js, chunks):
    raw = json.dumps(js, separators=(',', ':')).encode('utf-8')
    raw += b' ' * (-len(raw) % 4)
    out = [(0x4E4F534A, raw)] + [c for c in chunks[1:]]
    body = b''.join(struct.pack('<II', len(d), t) + d for t, d in out)
    open(path, 'wb').write(b'glTF' + struct.pack('<II', 2, 12 + len(body)) + body)


js, chunks = read_glb(OUT_GLB)
fixed = []

# --- one clip, correctly named --------------------------------------------
# Blender emits one animation per animated datablock whatever the export mode
# is set to, so fold them into a single clip: every channel already shares the
# same time range, only the sampler indices need rebasing.
anims = js.get("animations", [])
if not anims:
    fixed.append("!! no animation exported")
else:
    base = anims[0]
    for a in anims[1:]:
        off = len(base["samplers"])
        base["samplers"].extend(a["samplers"])
        for ch in a["channels"]:
            ch["sampler"] += off
            base["channels"].append(ch)
    if len(anims) > 1:
        fixed.append(f"merged {len(anims)} clips into one "
                     f"({len(base['channels'])} channels)")
    if base.get("name") != CLIP:
        fixed.append(f"renamed clip {base.get('name')!r} -> {CLIP!r}")
    base["name"] = CLIP
    js["animations"] = [base]

# --- plume materials -------------------------------------------------------
by_name = {m.get("name", ""): m for m in js.get("materials", [])}
for layer in PLUME:
    m = by_name.get(f"Booster{layer}")
    if m is None:
        fixed.append(f"!! material Booster{layer} missing from the glb"); continue
    pbr = m.setdefault("pbrMetallicRoughness", {})
    if pbr.get("baseColorFactor", [1, 1, 1, 1])[:3] != [0, 0, 0]:
        pbr["baseColorFactor"] = [0, 0, 0, 1]; fixed.append(f"{layer}: baseColorFactor -> black")
    if "baseColorTexture" not in pbr:
        fixed.append(f"!! {layer}: no baseColorTexture -> alpha would be flat")
    if m.get("alphaMode") != "BLEND":
        m["alphaMode"] = "BLEND"; fixed.append(f"{layer}: alphaMode -> BLEND")
    if not m.get("doubleSided"):
        m["doubleSided"] = True; fixed.append(f"{layer}: doubleSided -> true")
    if "emissiveTexture" not in m:
        fixed.append(f"!! {layer}: no emissiveTexture")
    if m.get("emissiveFactor", [0, 0, 0]) == [0, 0, 0]:
        m["emissiveFactor"] = [1, 1, 1]; fixed.append(f"{layer}: emissiveFactor -> white")
    ext = m.setdefault("extensions", {})
    want = PLUME[layer]["emit"]
    got = ext.get("KHR_materials_emissive_strength", {}).get("emissiveStrength")
    if got is None or abs(got - want) > 1e-4:
        ext["KHR_materials_emissive_strength"] = {"emissiveStrength": want}
        js.setdefault("extensionsUsed", [])
        if "KHR_materials_emissive_strength" not in js["extensionsUsed"]:
            js["extensionsUsed"].append("KHR_materials_emissive_strength")
        fixed.append(f"{layer}: emissiveStrength -> {want}")

sp = by_name.get("BoosterSpark")
if sp:
    sp["alphaMode"] = "BLEND"; sp["doubleSided"] = True
    sp.setdefault("pbrMetallicRoughness", {})["baseColorFactor"] = [0, 0, 0, 0.85]

if fixed:
    write_glb(OUT_GLB, js, chunks)
    for f in fixed:
        print("  patch:", f)
    js, chunks = read_glb(OUT_GLB)

# ------------------------------------------------------------------ report
nodes = [n.get("name", "?") for n in js["nodes"]]
anim  = js["animations"][0]
tmax  = 0.0
for s in anim["samplers"]:
    acc = js["accessors"][s["input"]]
    tmax = max(tmax, acc.get("max", [0])[0])
morphs = sum(len(m.get("targets", [])) for me in js["meshes"] for m in me["primitives"])
print(f"\n  {os.path.basename(OUT_GLB)}  {os.path.getsize(OUT_GLB)/1e6:.2f} MB")
print(f"  nodes      : {len(nodes)}  (Boosters group: "
      f"{sum(1 for n in nodes if n.startswith('Booster'))})")
print(f"  materials  : {[m.get('name') for m in js['materials']]}")
print(f"  clip       : {anim['name']!r}  {tmax:.3f}s  "
      f"{len(anim['channels'])} channels")
print(f"  morph tgts : {morphs}")
print(f"  extensions : {js.get('extensionsUsed', [])}")
sys.stdout.flush(); os._exit(0)
