import { useAnimations, useGLTF } from "@react-three/drei";
import { useFrame, type ThreeElements } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { clone } from "three/addons/utils/SkeletonUtils.js";
import { makeBodyRig } from "../lib/astronaut-pose";

const MODEL = "/astronaut_rigged.glb?v=2";
const CLIP = "BoosterLoop";

/** Each instance needs its own bones and independently throttled materials. */
function useAstronautScene() {
  const { scene: source, animations } = useGLTF(MODEL);
  const scene = useMemo(() => {
    const instance = clone(source);
    instance.traverse((node) => {
      if (!(node instanceof THREE.Mesh)) return;
      const copy = (material: THREE.Material) =>
        material.name.startsWith("Booster") ? material.clone() : material;
      node.material = Array.isArray(node.material) ? node.material.map(copy) : copy(node.material);
      // Limb poses extend beyond the scan's original rigid bounds.
      if (node instanceof THREE.SkinnedMesh) node.frustumCulled = false;
    });
    return instance;
  }, [source]);
  useEffect(() => () => {
    scene.traverse((node) => {
      if (!(node instanceof THREE.Mesh)) return;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.forEach((material) => {
        if (material.name.startsWith("Booster")) material.dispose();
      });
    });
  }, [scene]);
  const pose = useMemo(() => makeBodyRig(scene), [scene]);
  return { scene, animations, pose };
}

/** Draw order for the nested plume shells: widest first, hot core last. */
const SHELL_ORDER = ["Halo", "Veil", "Wash", "Mid", "Inner", "Core", "Spark"];

/* --------------------------------------------------------------------------
 * Axes in the shipped glb. The exporter's Y-up conversion re-expressed every
 * local frame, so these are NOT the axes the Blender build used:
 *
 *   model space   +X front, +Y up, +Z the astronaut's left
 *   Booster_L/R   the plume runs along the node's local -Y (not -Z)
 *   thrust        the reaction force on the body, in model space
 *
 * Verified by composing the node transforms straight out of the glb.
 * ------------------------------------------------------------------------ */
const THRUST_AXIS = new THREE.Vector3(0.4024, 0.9153, 0).normalize();
const AXIS_PITCH = new THREE.Vector3(0, 0, 1); // tilts a nozzle fore/aft
const AXIS_YAW = new THREE.Vector3(1, 0, 0); // tilts a nozzle left/right

type Rig = {
  root: THREE.Object3D | undefined;
  left: THREE.Object3D | undefined;
  right: THREE.Object3D | undefined;
  restL: THREE.Quaternion;
  restR: THREE.Quaternion;
  emissive: Map<THREE.MeshStandardMaterial, number>;
};

/**
 * Finds the booster nodes and fixes up their materials.
 *
 * The shells ship as `alphaMode: BLEND`, which three.js loads with
 * `depthWrite: true` — six nested transparent shells then fight over the depth
 * buffer and pop as the camera moves. Additive with depth writes off is both
 * the correct look for a flame and immune to sort order. Fog is off too: the
 * plume is emissive, it should not go grey with distance the way the suit does.
 */
function useBoosterRig(scene: THREE.Object3D): Rig {
  return useMemo(() => {
    const emissive = new Map<THREE.MeshStandardMaterial, number>();
    scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      mats.forEach((raw) => {
        if (!raw.name.startsWith("Booster")) return;
        const m = raw as THREE.MeshStandardMaterial;
        // useGLTF caches the scene, so capture the authored value only once
        m.userData.baseEmissive ??= m.emissiveIntensity;
        emissive.set(m, m.userData.baseEmissive as number);
        m.blending = THREE.AdditiveBlending;
        m.depthWrite = false;
        m.toneMapped = false;
        m.fog = false;
        m.side = THREE.DoubleSide;
        mesh.renderOrder = 10 + SHELL_ORDER.indexOf(raw.name.replace("Booster", ""));
      });
    });
    const left = scene.getObjectByName("Booster_L");
    const right = scene.getObjectByName("Booster_R");
    return {
      root: scene.getObjectByName("Boosters"),
      left,
      right,
      restL: left ? left.quaternion.clone() : new THREE.Quaternion(),
      restR: right ? right.quaternion.clone() : new THREE.Quaternion(),
      emissive,
    };
  }, [scene]);
}

/** Applies throttle + gimbal to one nozzle. Angles are in the model frame. */
function driveNozzle(
  node: THREE.Object3D | undefined,
  rest: THREE.Quaternion,
  pitch: number,
  yaw: number,
  length: number,
  width: number,
  q: THREE.Quaternion,
  tmp: THREE.Quaternion,
) {
  if (!node) return;
  // premultiply, so the angles are about model-space axes rather than about
  // whatever roll the baked nozzle aim happens to have
  q.setFromAxisAngle(AXIS_PITCH, pitch);
  tmp.setFromAxisAngle(AXIS_YAW, yaw);
  node.quaternion.copy(rest).premultiply(tmp).premultiply(q);
  // the plume runs along local -Y, so Y is length and X/Z are width
  node.scale.set(width, length, width);
}

export type AstronautProps = {
  burning?: boolean;
  /** Playback rate of the 2 s flicker loop. */
  speed?: number;
  /** Multiplies the authored emissive strength of every plume shell. */
  intensity?: number;
} & ThreeElements["group"];

/** The astronaut, boosters lit, holding still. */
export function Astronaut({ burning = true, speed = 1, intensity = 1, ...props }: AstronautProps) {
  const group = useRef<THREE.Group>(null);
  const { scene, animations, pose } = useAstronautScene();
  const { actions } = useAnimations(animations, group);
  const rig = useBoosterRig(scene);

  useFrame((state, dt) => pose(state.clock.elapsedTime, dt, burning ? .25 : 0));

  useEffect(() => {
    const action = actions[CLIP];
    if (!action) return;
    action.setLoop(THREE.LoopRepeat, Infinity).play();
    return () => void action.stop();
  }, [actions]);

  useEffect(() => {
    // Three.js scene objects are intentionally mutable outside React rendering.
    // eslint-disable-next-line react-hooks/immutability
    if (rig.root) rig.root.visible = burning;
  }, [rig, burning]);

  useEffect(() => {
    const action = actions[CLIP];
    action?.setEffectiveTimeScale(speed);
  }, [actions, speed]);

  useEffect(() => {
    rig.emissive.forEach((base, m) => (m.emissiveIntensity = base * intensity));
  }, [rig, intensity]);

  return (
    <group ref={group} {...props}>
      <primitive object={scene} />
    </group>
  );
}

/* ========================================================================== */

/**
 * Free drift, as a sum of sines per axis: [amplitude, rad/s, phase].
 *
 * Sines because they differentiate exactly — velocity and acceleration come out
 * in closed form instead of as noisy frame-to-frame differences, and the
 * boosters are driven off that acceleration. Frequencies are deliberately
 * unrelated so the path never visibly repeats.
 */
const DRIFT = {
  // x amplitudes ~2.4x the rest: he crosses the screen horizontally, not just drifts in place.
  x: [
    [4.5, 0.137, 0.0],
    [1.6, 0.291, 2.2],
    [0.65, 0.523, 4.1],
  ],
  y: [
    [1.25, 0.113, 1.3],
    [0.57, 0.347, 3.9],
    [0.26, 0.611, 0.7],
  ],
  z: [
    [1.5, 0.101, 2.6],
    [0.68, 0.239, 5.0],
    [0.31, 0.487, 1.6],
  ],
} as const;

/**
 * Turn on the spot. The first term is slow and wide enough (2.7 rad) to swing
 * him all the way around to face the camera every minute or so; the other two
 * are the faster small wobble so he doesn't hold dead still between turns.
 */
const YAW = [
  [2.7, 0.12, 3.6],
  [0.55, 0.083, 1.1],
  [0.22, 0.191, 4.4],
] as const;

/** How hard he holds himself up. Sets the resting throttle and the bank scale. */
const HOVER = 0.55;
/** Cap on how far the body leans away from upright. */
const MAX_TILT = THREE.MathUtils.degToRad(34);
/** Nozzle gimbal authority. */
const GIMBAL = THREE.MathUtils.degToRad(13);
/** Attitude damping, 1/s. Lower = the thrust lags the motion more. */
const SETTLE = 3.4;

const sum = (terms: readonly (readonly number[])[], t: number, d: 0 | 1 | 2) =>
  terms.reduce((acc, [a, w, p]) => {
    const phase = w * t + p;
    if (d === 0) return acc + a * Math.sin(phase);
    if (d === 1) return acc + a * w * Math.cos(phase);
    return acc - a * w * w * Math.sin(phase);
  }, 0);

const UP = new THREE.Vector3(0, 1, 0);
/** Base heading: +X is his front, so this turns his back — and the pack — to camera. */
const YAW0 = Math.PI / 2 - 0.45;

export type FlightState = {
  position: THREE.Vector3;
  accel: THREE.Vector3;
  /** Attitude that puts the thrust axis along the required force. Undamped. */
  target: THREE.Quaternion;
  /** 0..1 — how hard the thrusters are working right now. */
  throttle: number;
  /** Radians. Fore/aft and left/right nozzle gimbal, and the differential. */
  pitch: number;
  roll: number;
  diff: number;
};

export function makeFlightState(): FlightState {
  return {
    position: new THREE.Vector3(),
    accel: new THREE.Vector3(),
    target: new THREE.Quaternion(),
    throttle: 0,
    pitch: 0,
    roll: 0,
    diff: 0,
  };
}

const _f = {
  force: new THREE.Vector3(),
  thrust: new THREE.Vector3(),
  local: new THREE.Vector3(),
  qBase: new THREE.Quaternion(),
  qAlign: new THREE.Quaternion(),
  identity: new THREE.Quaternion(),
  euler: new THREE.Euler(),
  qInv: new THREE.Quaternion(),
};

/**
 * The whole flight model, as a pure function of time.
 *
 * Position, velocity and acceleration all come from the same sum of sines, so
 * the acceleration is exact rather than a noisy frame difference — which is
 * what makes it safe to steer the boosters with. `body` is the attitude
 * actually in use (damped, so the thrust lags the motion a little); pass the
 * target on the first frame.
 */
export function sampleFlight(
  t: number,
  wander: number,
  body: THREE.Quaternion,
  out: FlightState,
): FlightState {
  out.position.set(sum(DRIFT.x, t, 0) * wander, sum(DRIFT.y, t, 0) * wander, sum(DRIFT.z, t, 0) * wander);
  out.accel.set(sum(DRIFT.x, t, 2) * wander, sum(DRIFT.y, t, 2) * wander, sum(DRIFT.z, t, 2) * wander);

  // thrust has to cover his weight plus whatever the drift is demanding
  _f.force.copy(out.accel).addScaledVector(UP, HOVER);
  const demand = _f.force.length();
  _f.force.divideScalar(demand || 1);
  out.throttle = THREE.MathUtils.clamp((demand - 0.26) / 0.55, 0.05, 1);

  // point the body's thrust axis along that force
  _f.qBase.setFromEuler(_f.euler.set(0, YAW0 + sum(YAW, t, 0), 0));
  _f.thrust.copy(THRUST_AXIS).applyQuaternion(_f.qBase);
  _f.qAlign.setFromUnitVectors(_f.thrust, _f.force);
  const lean = _f.thrust.angleTo(_f.force);
  if (lean > MAX_TILT) _f.qAlign.slerp(_f.identity, 1 - MAX_TILT / lean);
  out.target.copy(_f.qAlign).multiply(_f.qBase);

  // gimbal: whatever the body attitude did not absorb, plus yaw authority
  _f.local.copy(out.accel).applyQuaternion(_f.qInv.copy(body).invert());
  out.pitch = THREE.MathUtils.clamp(_f.local.x * 2.6, -1, 1) * GIMBAL;
  out.roll = THREE.MathUtils.clamp(_f.local.z * 2.6, -1, 1) * GIMBAL;
  out.diff = THREE.MathUtils.clamp(sum(YAW, t, 1) * 3.2, -1, 1) * GIMBAL * 0.7;
  return out;
}

/** Plume length and width for a given throttle. */
export const plumeScale = (throttle: number) => ({
  length: 0.55 + 0.75 * throttle,
  width: 0.82 + 0.26 * throttle,
});

export type DriftingAstronautProps = {
  /** Model is 1.0 unit tall; this is his height in scene units. */
  size?: number;
  /** Multiplies the drift amplitudes. */
  wander?: number;
  /** Absolute intensity of the warm nozzle light. 0 drops it. */
  glow?: number;
  /** Seconds added to the clock, so two of them never move in step. */
  offset?: number;
} & ThreeElements["group"];

/**
 * An astronaut drifting under his own thrusters.
 *
 * The boosters are not decoration on top of the motion — they are derived from
 * it. Each frame the drift's exact acceleration is added to a constant hover
 * term, and the body is rotated so its thrust axis points along that vector.
 * So he banks into a change of direction and the plumes swing to follow, the
 * throttle (plume length, brightness and flicker rate) tracks how hard he is
 * pushing, and the two nozzles gimbal differentially against his yaw rate the
 * way real attitude thrusters do.
 */
export function DriftingAstronaut({
  size = 4,
  wander = 1,
  glow = 14,
  offset = 0,
  ...props
}: DriftingAstronautProps) {
  const body = useRef<THREE.Group>(null);
  const light = useRef<THREE.PointLight>(null);
  const { scene, animations, pose } = useAstronautScene();
  const { actions } = useAnimations(animations, body);
  const rig = useBoosterRig(scene);

  useEffect(() => {
    const action = actions[CLIP];
    if (!action) return;
    action.setLoop(THREE.LoopRepeat, Infinity).play();
    return () => void action.stop();
  }, [actions]);

  const st = useMemo(() => makeFlightState(), []);
  const qa = useMemo(() => new THREE.Quaternion(), []);
  const qb = useMemo(() => new THREE.Quaternion(), []);
  const primed = useRef(false);

  useFrame((state, dt) => {
    const g = body.current;
    if (!g) return;
    const t = state.clock.elapsedTime + offset;
    const step = Math.min(dt, 0.1); // a backgrounded tab must not snap him

    sampleFlight(t, wander, g.quaternion, st);
    pose(t, step, st.throttle, st.pitch, st.roll, st.diff);
    g.position.copy(st.position);
    if (primed.current) {
      g.quaternion.slerp(st.target, 1 - Math.exp(-SETTLE * step));
    } else {
      g.quaternion.copy(st.target);
      primed.current = true;
    }

    const { length, width } = plumeScale(st.throttle);
    driveNozzle(rig.left, rig.restL, st.pitch, st.roll + st.diff, length, width, qa, qb);
    driveNozzle(rig.right, rig.restR, st.pitch, st.roll - st.diff, length, width, qa, qb);

    rig.emissive.forEach((base, mat) => {
      mat.emissiveIntensity = base * (0.62 + 0.62 * st.throttle);
    });
    const action = actions[CLIP];
    action?.setEffectiveTimeScale(0.8 + 0.7 * st.throttle);

    if (light.current) {
      const flicker = 1 + Math.sin(t * 29) * 0.1 + Math.sin(t * 11.3) * 0.07;
      light.current.intensity = glow * st.throttle * flicker;
    }
  });

  return (
    <group {...props}>
      <group ref={body}>
        <group scale={size}>
          <primitive object={scene} />
        </group>
        {/* just inside the flame: nozzle mouths are at y≈0.15 in model units */}
        <pointLight
          ref={light}
          color="#ff7a22"
          decay={2}
          distance={1.6 * size}
          position={[-0.1 * size, 0.06 * size, 0.015 * size]}
        />
      </group>
    </group>
  );
}

useGLTF.preload(MODEL);
