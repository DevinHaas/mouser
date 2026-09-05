import { Bone, Euler, MathUtils, Object3D, Quaternion } from 'three';

/** Bone-local axes authored by blender/rig_astronaut.py. */
export function makeBodyRig(scene: Object3D) {
  const joints = new Map<string, { bone: Bone; rest: Quaternion }>();
  scene.traverse((node) => {
    if (node instanceof Bone) joints.set(node.name, { bone: node, rest: node.quaternion.clone() });
  });
  const rotation = new Euler();
  const target = new Quaternion();

  return (time: number, dt: number, throttle = 0, pitch = 0, roll = 0, turn = 0) => {
    const settle = 1 - Math.exp(-3 * MathUtils.clamp(dt, 0, .1));
    const thrust = MathUtils.clamp(throttle, 0, 1);
    const fore = MathUtils.clamp(pitch / .23, -1, 1);
    const bank = MathUtils.clamp(roll / .23, -1, 1);
    const yaw = MathUtils.clamp(turn / .16, -1, 1);
    const pose = (name: string, x: number, y = 0, z = 0) => {
      const joint = joints.get(name);
      if (!joint) return;
      target.setFromEuler(rotation.set(x, y, z)).premultiply(joint.rest);
      joint.bone.quaternion.slerp(target, settle);
    };

    // Gestures ride bursts: ^4 turns a slow sine into a narrow pulse, so a limb
    // spends most of its cycle at rest and now and then makes one big move. The
    // rates are all unrelated, every burst is scaled by a slower sine, and the
    // phases are offset per side, so no two moves match and nothing visibly repeats.
    const pulse = (rate: number, phase: number) => Math.max(0, Math.sin(time * rate + phase)) ** 4;
    const glance = pulse(.31, 2.3) * (.7 + .3 * Math.sin(time * .19));
    pose('Head',
      .025 * Math.sin(time * .43) - glance * .13,
      yaw * .12 + .16 * Math.sin(time * .27 + 1.1) + glance * .5,
      -bank * .035 + glance * .11);
    for (const [side, sign] of [['L', -1], ['R', 1]] as const) {
      const drift = Math.sin(time * .78 + sign * .9);
      const counter = Math.sin(time * .61 + sign * 1.4);
      // `reach` folds the elbow to grab at something, `extend` throws the whole
      // arm straight out to the side.
      const reach = pulse(.41, sign * 1.7) * (.65 + .35 * Math.sin(time * .13 + sign * 2.4));
      const extend = pulse(.23, sign * 2.9 + 1.1) * (.6 + .4 * Math.sin(time * .17 + sign));
      pose(`UpperArm_${side}`,
        .05 + thrust * .06 + fore * .05 + drift * .02 + reach * .52 - extend * .1,
        sign * (yaw * .045 + extend * .12),
        // ponytail: .6 is the ceiling — past it the scan's shoulder weights tear.
        // Reweight the shoulder in blender/rig_astronaut.py to swing further.
        sign * (.06 + thrust * .03 - reach * .17 + extend * .6) - bank * .09);
      pose(`Forearm_${side}`,
        .07 + thrust * .08 + counter * .035 + sign * yaw * .07 + reach * .74 - extend * .06);
      pose(`Hand_${side}`, .02 + drift * .02 + reach * .3, sign * .025);
      // Legs trail nearly straight and now and then draw a knee up, the way they
      // do in freefall.
      // ponytail: knee travel is capped by the scan's hip weights — a tuck past
      // ~.3 rad tears there. Same fix as the shoulder: reweight in rig_astronaut.py.
      const tuck = pulse(.19, sign * 2.2 + .6) * (.6 + .4 * Math.sin(time * .11 + sign * 1.9));
      pose(`Thigh_${side}`, .06 + thrust * .1 - fore * .06 + counter * .035 + tuck * .25,
        0, sign * (.045 + tuck * .05) - bank * .035);
      pose(`Shin_${side}`, -.1 - thrust * .15 - drift * .05 - tuck * .28);
      pose(`Foot_${side}`, .035 + counter * .025 + tuck * .09);
    }
  };
}
