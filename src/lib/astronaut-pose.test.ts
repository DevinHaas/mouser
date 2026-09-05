import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { AnimationMixer, Bone, Mesh, SkinnedMesh, Vector3 } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone } from 'three/addons/utils/SkeletonUtils.js';
import { makeBodyRig } from './astronaut-pose';

// Exercise the shipped skeleton with the actual Three.js loader; images need no GPU here.
const bytes = readFileSync(process.argv[2] ?? new URL('../../public/astronaut_rigged.glb', import.meta.url));
const doc = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString());
doc.images = [];
doc.textures = [];
doc.materials = [];
for (const mesh of doc.meshes) for (const primitive of mesh.primitives) delete primitive.material;
const json = Buffer.from(JSON.stringify(doc));
const padded = Buffer.alloc(Math.ceil(json.length / 4) * 4, 32);
json.copy(padded);
const binary = bytes.subarray(20 + bytes.readUInt32LE(12));
const header = Buffer.alloc(20);
header.writeUInt32LE(0x46546c67, 0);
header.writeUInt32LE(2, 4);
header.writeUInt32LE(20 + padded.length + binary.length, 8);
header.writeUInt32LE(padded.length, 12);
header.writeUInt32LE(0x4e4f534a, 16);
const buffer = Buffer.concat([header, padded, binary]);
const { scene, animations } = await new GLTFLoader().parseAsync(
  buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength), '');
assert.equal(animations[0].name, 'BoosterLoop');
assert.equal(animations[0].tracks.length, 68);
const suit = scene.getObjectByName('Astronaut') as SkinnedMesh;
assert.ok(suit.isSkinnedMesh);
assert.equal(suit.skeleton.bones.length, 14);
const other = clone(scene);
const elbow = scene.getObjectByName('Forearm_L') as Bone;
const rest = elbow.quaternion.clone();
const nozzle = scene.getObjectByName('Booster_L')!;
scene.updateMatrixWorld(true);
const nozzleRest = nozzle.getWorldPosition(new Vector3());
const original = new Vector3();
const deformed = new Vector3();
const weights = suit.geometry.getAttribute('skinWeight');
for (let i = 0; i < weights.count; i++) {
  assert.ok(Math.abs(weights.getX(i) + weights.getY(i) + weights.getZ(i) + weights.getW(i) - 1) < 1e-5);
}
const pose = makeBodyRig(scene);
for (let i = 0; i < 120; i++) pose(i / 60, 1 / 60, .8, .1, -.12, .08);
scene.updateMatrixWorld(true);
assert.ok(elbow.quaternion.angleTo(rest) > .2, 'elbow should bend');
assert.ok((other.getObjectByName('Forearm_L') as Bone).quaternion.equals(rest), 'clones must be independent');
assert.ok(nozzle.getWorldPosition(new Vector3()).distanceTo(nozzleRest) < 1e-6, 'nozzle stays attached to rigid pack');
let displaced = 0;
for (let i = 0; i < suit.geometry.getAttribute('position').count; i++) {
  original.fromBufferAttribute(suit.geometry.getAttribute('position'), i);
  suit.applyBoneTransform(i, deformed.copy(original));
  assert.ok(deformed.toArray().every(Number.isFinite));
  if (deformed.distanceTo(original) > .015) displaced++;
  assert.ok(deformed.distanceTo(original) < .3, 'bounded skin displacement');
}
assert.ok(displaced > 1000, 'bones must deform the suit');
const bent = elbow.quaternion.clone();
pose(20, 0, 0, 0, 0, 0);
assert.ok(elbow.quaternion.equals(bent), 'zero delta must not move joints');
const mixer = new AnimationMixer(scene);
mixer.clipAction(animations[0]).play();
mixer.update(.5);
assert.ok(elbow.quaternion.equals(bent), 'booster clip must not overwrite the pose');

// Cover both sides at the limits of steering/throttle, not just one idle pose.
// Bounded vertex travel alone misses triangles torn between neighboring bones.
const positions = suit.geometry.getAttribute('position');
const indices = suit.geometry.index!;
const posed = Array.from({ length: positions.count }, () => new Vector3());
const edgeStart = new Vector3();
const edgeEnd = new Vector3();
for (let direction = 0; direction < 8; direction++) {
  for (const throttle of [0, 1]) {
    for (const time of [0, 4, 12]) {
      for (let frame = 0; frame < 60; frame++) {
        pose(time, .1, throttle, direction & 1 ? .23 : -.23,
          direction & 2 ? .23 : -.23, direction & 4 ? .16 : -.16);
      }
      scene.updateMatrixWorld(true);
      for (let i = 0; i < positions.count; i++) {
        suit.applyBoneTransform(i, posed[i].fromBufferAttribute(positions, i));
      }
      for (let i = 0; i < indices.count; i += 3) {
        for (let corner = 0; corner < 3; corner++) {
          const a = indices.getX(i + corner);
          const b = indices.getX(i + (corner + 1) % 3);
          const before = edgeStart.fromBufferAttribute(positions, a)
            .distanceTo(edgeEnd.fromBufferAttribute(positions, b));
          const after = posed[a].distanceTo(posed[b]);
          assert.ok(after < before * 2.5 + .003,
            `torn edge ${a}/${b}: ${before.toFixed(5)} -> ${after.toFixed(5)}`);
        }
      }
    }
  }
}
scene.traverse((node) => {
  if (node instanceof Mesh) node.geometry.dispose();
});
console.log('Astronaut rig OK: skin deformation, independent clones, intact boosters, 48 tear-free poses.');
