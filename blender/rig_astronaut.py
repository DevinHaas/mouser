"""Run with Blender --factory-startup --background --python blender/rig_astronaut.py.

Rig the existing suit, preserving its texture and animated booster geometry.
Joint coordinates are calibrated to this scan (Blender: +X front, +Z up).
"""
import json
from collections import defaultdict
from pathlib import Path
import struct

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'public/astronaut_rigged.glb'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT / 'public/astronaut_animated.glb'))
suit = bpy.data.objects['Astronaut']

armature = bpy.data.armatures.new('AstronautSkeleton')
rig = bpy.data.objects.new('AstronautRig', armature)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
rig.show_in_front = True
bpy.ops.object.mode_set(mode='EDIT')


def bone(name, head, tail, parent=None):
    b = armature.edit_bones.new(name)
    b.head, b.tail = head, tail
    b.align_roll(Vector((1, 0, 0)))
    if parent:
        b.parent = armature.edit_bones[parent]


bone('Torso', (0, 0, -.04), (0, 0, .30))
bone('Head', (0, 0, .325), (0, 0, .46), 'Torso')
for side, sign in [('L', -1), ('R', 1)]:
    bone('UpperArm_' + side, (0, sign * .12, .29), (0, sign * .166, .158), 'Torso')
    bone('Forearm_' + side, (0, sign * .166, .158), (.014, sign * .194, .043), 'UpperArm_' + side)
    bone('Hand_' + side, (.014, sign * .194, .043), (.025, sign * .19, -.07), 'Forearm_' + side)
    bone('Thigh_' + side, (0, sign * .069, -.015), (.009, sign * .077, -.195), 'Torso')
    bone('Shin_' + side, (.009, sign * .077, -.195), (-.013, sign * .087, -.405), 'Thigh_' + side)
    bone('Foot_' + side, (-.013, sign * .087, -.405), (.075, sign * .088, -.468), 'Shin_' + side)
bpy.ops.object.mode_set(mode='OBJECT')
groups = {b.name: suit.vertex_groups.new(name=b.name) for b in armature.bones}


def smooth(low, high, value):
    t = max(0, min(1, (value - low) / (high - low)))
    return t * t * (3 - 2 * t)


def chain(z, upper, lower, first, second, third, width):
    a = smooth(upper - width, upper + width, z)
    c = 1 - smooth(lower - width, lower + width, z)
    return {first: a, second: (1 - a) * (1 - c), third: (1 - a) * c}


# Below the elbows, connectivity separates gloves from the nearby thigh hose.
# Join coincident UV-seam vertices in this lookup only; preserve the actual mesh.
parents = list(range(len(suit.data.vertices)))


def root(index):
    while parents[index] != index:
        parents[index] = parents[parents[index]]
        index = parents[index]
    return index


coincident = {}
canonical = []
for v in suit.data.vertices:
    key = tuple(round(c, 5) for c in v.co)
    if key in coincident:
        parents[root(v.index)] = root(coincident[key])
    else:
        coincident[key] = v.index
    canonical.append(coincident[key])
for edge in suit.data.edges:
    a, b = edge.vertices
    if suit.data.vertices[a].co.z < .12 and suit.data.vertices[b].co.z < .12:
        parents[root(a)] = root(b)
regions = defaultdict(list)
for v in suit.data.vertices:
    if v.co.z < .12:
        regions[root(v.index)].append(v)
gloves = {key for key, vertices in regions.items()
          if len(vertices) > 1000 and min(v.co.z for v in vertices) > -.12
          and abs(sum(v.co.y for v in vertices) / len(vertices)) > .15}
assert len(gloves) == 2, 'Expected two disconnected glove/forearm regions'


# Blend arm membership over the actual surface, including across UV seams.
# Spatial thresholds alone leave a hard forearm/torso boundary that tears in poses.
arm_weights = np.zeros(len(suit.data.vertices))
fixed = np.zeros(len(suit.data.vertices), dtype=bool)
for v in suit.data.vertices:
    x, y, z = v.co
    side = 'L' if y < 0 else 'R'
    lateral = abs(y)
    arm_edge = .107 + .033 * (1 - smooth(.12, .28, z))
    arm_edge -= .014 * (1 - smooth(.04, .12, z))
    arm = smooth(arm_edge - .008, arm_edge + .008, lateral)
    arm *= smooth(-.15, -.125, z) * (1 - smooth(.29, .34, z))
    if z < .12:
        arm = 1 if root(v.index) in gloves else 0
    if x < -.055 and lateral < .117 and z > .12:
        arm = 0  # rigid backpack and nozzle mounts
    arm_weights[v.index] = arm
    fixed[v.index] = z < .075 or z > .33 or lateral < .075 or (x < -.055 and lateral < .11)
canonical = np.array(canonical)
edges = np.array([(canonical[e.vertices[0]], canonical[e.vertices[1]]) for e in suit.data.edges])
edges = np.unique(np.sort(edges, axis=1), axis=0)
edges = edges[edges[:, 0] != edges[:, 1]]
sources = np.concatenate((edges[:, 0], edges[:, 1]))
targets = np.concatenate((edges[:, 1], edges[:, 0]))
degree = np.bincount(sources, minlength=len(arm_weights))
for _ in range(120):
    average = np.bincount(sources, weights=arm_weights[targets], minlength=len(arm_weights)) / np.maximum(degree, 1)
    arm_weights = np.where(fixed | (degree == 0), arm_weights, average)[canonical]

for v in suit.data.vertices:
    x, y, z = v.co
    side = 'L' if y < 0 else 'R'
    arm = float(arm_weights[v.index])
    head = smooth(.305, .34, z)
    leg = (1 - smooth(-.08, .015, z)) * (1 - arm)
    weights = {'Torso': (1 - arm - leg) * (1 - head), 'Head': (1 - arm - leg) * head}
    for name, w in chain(z, .158, .043, 'UpperArm_' + side, 'Forearm_' + side, 'Hand_' + side, .025).items():
        weights[name] = w * arm
    for name, w in chain(z, -.195, -.405, 'Thigh_' + side, 'Shin_' + side, 'Foot_' + side, .034).items():
        weights[name] = w * leg
    # glTF's four influences: prune tiny weights and normalize explicitly.
    active = sorted(((n, w) for n, w in weights.items() if w > .0001), key=lambda item: -item[1])[:4]
    total = sum(w for _, w in active)
    assert total > 0
    for name, weight in active:
        groups[name].add([v.index], weight / total, 'REPLACE')

modifier = suit.modifiers.new('Astronaut skin', 'ARMATURE')
modifier.object = rig
suit.parent = rig
for v in suit.data.vertices:
    assert 1 <= len(v.groups) <= 4
    assert abs(sum(g.weight for g in v.groups) - 1) < .00001
assert len(armature.bones) == 14

bpy.context.scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_location = (0, 0, 0)
            area.spaces.active.region_3d.view_distance = 1.8
            area.spaces.active.region_3d.view_rotation = Vector((3, -3, 1)).to_track_quat('Z', 'Y')
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'blender/astronaut_rigged.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_animations=True,
                          export_animation_mode='NLA_TRACKS', export_force_sampling=True)

# Blender may split the imported booster loop by datablock; restore one clip.
data = OUTPUT.read_bytes()
json_size = struct.unpack_from('<I', data, 12)[0]
doc = json.loads(data[20:20 + json_size])
binary_chunks = data[20 + json_size:]
merged = {'name': 'BoosterLoop', 'channels': [], 'samplers': []}
for clip in doc.get('animations', []):
    offset = len(merged['samplers'])
    merged['samplers'].extend(clip['samplers'])
    for channel in clip['channels']:
        channel['sampler'] += offset
        merged['channels'].append(channel)
assert len(merged['channels']) == 68, 'Booster animation tracks were lost'
doc['animations'] = [merged]
assert len(doc['skins']) == 1 and len(doc['skins'][0]['joints']) == 14
encoded = json.dumps(doc, separators=(',', ':')).encode()
encoded += b' ' * (-len(encoded) % 4)
OUTPUT.write_bytes(struct.pack('<III', 0x46546C67, 2, 20 + len(encoded) + len(binary_chunks))
                   + struct.pack('<II', len(encoded), 0x4E4F534A) + encoded + binary_chunks)
print('VERIFIED: 14 bones, normalized skin weights, all 68 booster tracks.', flush=True)
