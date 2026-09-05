# chest_animated.glb

An openable version of `chest.glb` (Tripo3D scan) with a real interior and one
Three.js-controllable animation clip. Everything is baked into a single material
and a single texture atlas.

## What's in the file

| | |
|---|---|
| Nodes | `ChestBody`, `ChestLid` |
| Animation clip | `Open` — 1.667 s, 24 fps, 41 linear keys, rotation on `ChestLid` only |
| Materials | 1 (`ChestAtlas`), backface-culled (`doubleSided: false`) |
| Textures | `baseColor` 2048×2560 JPEG (~0.8 MB), `emissive` 1024×1280 JPEG (~0.1 MB) |
| Triangles | ~110 k (77 k body + 27 k lid + interior) |
| File size | ~3.5 MB |

The atlas keeps the original Tripo albedo at a **pixel-for-pixel 1:1** in the top
2048×2048, and adds the painted interior in a 2048×512 strip underneath — so the
exterior lost no detail, and the whole chest is one draw call per mesh.

The lid pivots on a hinge at the back-top edge (glTF-space `x = -0.375`,
`y = 0.168`). The clip swings it to ~105°, overshoots, and settles at 99°.

## Three.js

```js
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

const gltf  = await new GLTFLoader().loadAsync('/chest_animated.glb')
const chest = gltf.scene
scene.add(chest)

const mixer  = new THREE.AnimationMixer(chest)
const clip   = THREE.AnimationClip.findByName(gltf.animations, 'Open') ?? gltf.animations[0]
const action = mixer.clipAction(clip)
action.setLoop(THREE.LoopOnce, 1)
action.clampWhenFinished = true

// --- state control -------------------------------------------------------
function open () {
  action.paused = false
  action.timeScale = 1
  if (!action.isRunning()) { action.reset(); action.play() }
}

function close () {                       // same clip, played backwards
  action.paused = false
  action.timeScale = -1
  if (!action.isRunning()) { action.time = clip.duration; action.play() }
}

// or drive it straight from a 0..1 value (scroll, spring, drag, tween…)
function setOpenAmount (t) {
  action.play()
  action.paused = true
  action.time = THREE.MathUtils.clamp(t, 0, 1) * clip.duration
}

// render loop
mixer.update(delta)
```

### Light inside the chest

The interior is painted, not modelled, so it needs a light to read. Drop a point
light roughly in the middle of the tray (model space, chest is ~0.94 units on its
long axis — scale to taste):

```js
const glow = new THREE.PointLight(0x9ff4ff, 2.0, 1.4, 2)
glow.position.set(-0.06, 0.06, -0.04)
chest.add(glow)

// optionally fade it in with the lid
glow.intensity = 2.0 * openAmount
```

The orbs, crystals and lid gradient also carry an emissive map, so they stay
visible with no light at all. Tune it with:

```js
chest.traverse(o => { if (o.isMesh) o.material.emissiveIntensity = 1.2 })
```

### Optional: smaller textures

```bash
npx @gltf-transform/cli optimize chest_animated.glb chest_opt.glb \
  --texture-compress ktx2 --compress draco
```
That typically takes it well under 1 MB. Three.js then needs `KTX2Loader` +
`DRACOLoader` wired into the `GLTFLoader`.

## Rebuilding

```bash
pip install "bpy==4.2.23" pillow numpy   # needs Python 3.11
python3 chest_anim/build.py              # reads ../chest.glb, writes ../chest_animated.glb
```

Steps run in order and hand off through `_work/`:

| step | what it does |
|---|---|
| `00_split.py` | merges the glTF's UV-split verts (makes it watertight), bisects at the lid seam `z=0.168`, separates `Chest_Lid` |
| `01_interior.py` | caps the cut, extrudes the rim inward, builds inner walls + tray floor + two divider walls |
| `02_paint.py` | paints the interior atlas strip with PIL — orbs, crystal cluster, PCB stacks, lid gradient, wall/metal patches |
| `03_atlas.py` | composites the atlas, assigns UVs per face tag, builds the single `ChestAtlas` material |
| `04_export.py` | re-origins the lid on the hinge, keyframes `Open`, exports the glb |

All the knobs live in `_cfg.py` — seam height, cavity depth (`CAVITY`, lower =
contents sit higher and read at shallower camera angles), divider positions,
atlas size and the `Open` keyframes.
