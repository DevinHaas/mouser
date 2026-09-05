# astronaut_animated.glb

`astronaut.glb` (Tripo3D scan) with two animated thruster plumes burning out of
the jetpack nozzles on the underside of the pack. One looping animation clip,
one on/off switch, and the original suit mesh and texture passed through
untouched.

## What's in the file

| | |
|---|---|
| Nodes | `Astronaut`, `Boosters` → `Booster_L` / `Booster_R` → 6 shells + 5 sparks each |
| Animation clip | `BoosterLoop` — 2.000 s, 24 fps, 68 channels, seamless (frame 0 ≡ frame 48) |
| Materials | suit (untouched) + `BoosterCore/Inner/Mid/Wash/Veil/Halo` + `BoosterSpark` |
| Textures | suit JPEG passed through byte-for-byte; 6 plume gradients, ~1.9 KB total |
| Triangles | 118 320 (100 672 suit + 17 648 plumes) |
| Draw calls | 14 |
| File size | 3.46 MB — 25 KB more than the source glb |

Validated with `gltf-validator` 2.0.0: **0 errors, 0 warnings**.

### How the flame is built

glTF has no particle systems, so the plume is geometry. Each nozzle carries six
nested lathe shells — a white-hot dart (`Core`) inside progressively wider and
fainter orange sleeves out to `Halo`. Each shell is black base colour plus an
emissive gradient texture running from the throat to the tip, so it needs no
scene light to read. Stacked and blended additively, the overlapping shells
accumulate into a smooth volumetric falloff instead of looking like a stack of
hard-edged cones. The `Core` gradient also carries shock-diamond banding, the
periodic bright/dark bands a real underexpanded jet shows near the throat.

Movement comes from three places, all of it transform and morph animation
because glTF cannot animate materials:

* each shell stretches and necks on three incommensurate sine rates,
* two turbulence **shape keys** cross-fade (their weights always sum to 1.0), so
  the plume changes *shape*, not just size,
* five embers per nozzle ride the flow from throat to tip and loop.

Nozzle positions are not hard-coded — `00_probe.py` fits them off the mesh, so
the build survives the source model being re-exported.

## Using it

**Axes in the glb, which are not the axes the Blender build used.** The
exporter's Y-up conversion re-expressed every local frame, so:

| | |
|---|---|
| model space | `+X` front, `+Y` up, `+Z` his left; 1.0 unit tall |
| nozzle mouths | `(-0.083, 0.153, +0.017)` and `(-0.082, 0.151, -0.047)` |
| plume direction | the **local −Y** of `Booster_L` / `Booster_R` — *not* −Z |
| thrust on the body | `(0.402, 0.915, 0)` in model space: up and forward |

That last row is why he hovers nose-down by about 24°: the thrusters fire down
*and backward*, so holding station means leaning into them.

### React Three Fiber

`src/components/astronaut-boosters.tsx` exports two components.

**`<DriftingAstronaut />`** — what the game scene uses. He floats under his own
thrusters, and the boosters are derived from that motion rather than decorated
on top of it:

```tsx
<DriftingAstronaut position={[-5.8, 2.6, -6.5]} size={4.6} />
```

| prop | |
|---|---|
| `size` | his height in scene units (the model is 1.0 unit tall) |
| `wander` | multiplies the drift amplitudes; 1 gives roughly ±2.8 / ±1.6 / ±1.9 units |
| `glow` | absolute intensity of the warm nozzle light; `0` drops it |
| `offset` | seconds added to the clock, so two of them never move in step |

**`<Astronaut />`** — the same model holding still, with `burning`, `speed` and
`intensity` props, for when you want to drive it yourself.

### The flight model

Position comes from a sum of sines per axis, three unrelated frequencies each,
so the path never visibly repeats. Sines because they **differentiate exactly**:
velocity and acceleration come out in closed form instead of as noisy
frame-to-frame differences, which is what makes it safe to steer the thrusters
off the acceleration.

Each frame:

1. the force he needs is `acceleration + HOVER * up` — the drift plus his weight;
2. the body is rotated so its **thrust axis** points along that force, damped at
   `SETTLE` per second so the thrust lags the motion slightly, and clamped at
   `MAX_TILT` so he never tips absurdly;
3. `throttle` is how hard he is pushing, and drives plume length and width, the
   emissive strength of every shell, the flicker playback rate and the nozzle light;
4. the two nozzles gimbal — together for the acceleration the body attitude did
   not absorb, and *differentially* against his yaw rate, the way real attitude
   thrusters do.

So he banks into a change of direction, the plumes swing round to follow, and
they flare when he pushes harder. Measured over ten minutes of simulated drift:
throttle stays in 0.30–0.79 and the plumes track the required thrust direction
to within 1.7°, that residual being the deliberate damping lag.

The model is exported as pure functions — `sampleFlight(t, wander, body, out)`,
`makeFlightState()`, `plumeScale(throttle)` — so it can be tested, or reused to
drive something else, without a renderer. `booster_anim/06_flight_check.py`
does exactly that: it runs the real `sampleFlight` in Node, feeds the frames to
Blender and renders them on the shipped glb under the game's own camera, fog
and lighting.

The tunables sit together at the top of the drift section: `DRIFT`, `YAW`,
`HOVER`, `MAX_TILT`, `GIMBAL`, `SETTLE`.

### Plain three.js

```js
const gltf  = await new GLTFLoader().loadAsync('/astronaut_animated.glb')
const model = gltf.scene
scene.add(model)

const mixer = new THREE.AnimationMixer(model)
mixer.clipAction(THREE.AnimationClip.findByName(gltf.animations, 'BoosterLoop'))
     .setLoop(THREE.LoopRepeat, Infinity).play()

// --- REQUIRED: additive, no depth writes -------------------------------
const ORDER = ['Halo', 'Veil', 'Wash', 'Mid', 'Inner', 'Core', 'Spark']
model.traverse(o => {
  if (!o.isMesh || !o.material.name.startsWith('Booster')) return
  o.material.blending  = THREE.AdditiveBlending
  o.material.depthWrite = false
  o.material.toneMapped = false
  o.renderOrder = 10 + ORDER.indexOf(o.material.name.replace('Booster', ''))
})

const boosters = model.getObjectByName('Boosters')
boosters.visible = false          // off
mixer.update(delta)               // in the render loop
```

**The `depthWrite: false` line is not optional.** The shells ship as
`alphaMode: BLEND`, which three.js loads with `depthWrite: true`; six nested
transparent shells then fight over the depth buffer and pop as the camera
moves. Additive blending is also simply what a flame does to what is behind it,
and it removes sort order from the picture entirely.

Other things you can reach from code:

```js
// aim one thruster (e.g. steering) — local -Z is the thrust direction
model.getObjectByName('Booster_L').rotation.x = 0.15

// throttle: scale the rig, and push the emissive with it
boosters.scale.setScalar(0.4 + 0.6 * throttle)
```

If you add bloom, the shells already carry `KHR_materials_emissive_strength`
above 1.0, so they bloom and the suit does not.

## Rebuilding

```bash
pip install "bpy==4.2.23" pillow numpy   # needs Python 3.11
python3 booster_anim/build.py            # reads ../astronaut.glb, writes ../astronaut_animated.glb
python3 booster_anim/build.py --verify   # ...and re-imports the result to render _work/preview/loop.gif
```

Steps run in order and hand off through `_work/`:

| step | what it does |
|---|---|
| `00_probe.py` | fits the two nozzle mouths off the mesh — centre, axis, radius — into `_work/nozzles.json`, and symmetrises the splay |
| `01_texture.py` | paints the six emissive gradient strips with PIL, including the shock-diamond banding |
| `02_plumes.py` | lathes the shells, builds the turbulence shape keys and the materials, parents everything under `Boosters` |
| `03_anim.py` | keyframes the seamless 2 s loop: shell pulse, roll wobble, shape-key cross-fade, ember flow |
| `04_export.py` | exports the glb, then **verifies and patches the JSON** — Blender emits one animation per datablock whatever the export mode, so the 22 clips get folded into one, and the plume materials get checked for `BLEND` / black base colour / emissive strength |
| `05_verify.py` | re-imports the shipped glb and renders `loop.gif`, `loop.mp4` and `contact.png` — this renders the file you ship, not the scene it came from |
| `06_flight_check.py` | drives the shipped glb with the Three.js flight model's own output, in the game's camera / fog / lighting, so the drift and the thrust coupling can be eyeballed before it goes in the browser |

`preview.py` renders single check frames; it renders one pass per shell and sums
them, because EEVEE has no additive blend mode and a straight render would lie
to you about how the stack looks.

All the knobs live in `_cfg.py`:

| | |
|---|---|
| `PLUME` | per-shell length, radial profile, tessellation, emissive strength |
| `ALPHA` | per-shell opacity curve, slice of the colour ramp, shock-diamond depth |
| `RAMP` | the shared flame-temperature ramp — white-hot throat → orange → ember |
| `AIM` | extra back/outboard tilt on top of the measured nozzle normals |
| `TURB` | shape-key turbulence amplitude |
| `SPARKS`, `SPARK_SIZE`, `SPARK_EMIT` | the embers |
| `FRAMES`, `FPS`, `PULSE`, `SPIN` | loop length and the motion rates |

Shorter, angrier burn: drop every `length` in `PLUME` and raise the `PULSE`
amplitudes. Cooler/bluer: edit `RAMP` only — nothing else reads colour.

### Optional: smaller file

```bash
npx @gltf-transform/cli optimize astronaut_animated.glb astronaut_opt.glb \
  --texture-compress ktx2 --compress draco
```

Draco does not compress morph targets as well as it does base geometry, so
check the plumes still deform after optimising.
