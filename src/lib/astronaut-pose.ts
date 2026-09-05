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

    pose('Head', .025 * Math.sin(time * .43), yaw * .12, -bank * .035);
    for (const [side, sign] of [['L', -1], ['R', 1]] as const) {
      const drift = Math.sin(time * .78 + sign * .9);
      const counter = Math.sin(time * .61 + sign * 1.4);
      pose(`UpperArm_${side}`, .16 + thrust * .13 + fore * .09 + drift * .045,
        sign * yaw * .045, sign * (.12 + thrust * .06) - bank * .09);
      pose(`Forearm_${side}`, .28 + thrust * .19 + counter * .085 + sign * yaw * .07);
      pose(`Hand_${side}`, .025 + drift * .025, sign * .025);
      pose(`Thigh_${side}`, .12 + thrust * .12 - fore * .06 + counter * .045,
        0, sign * .045 - bank * .035);
      pose(`Shin_${side}`, -.24 - thrust * .19 - drift * .07);
      pose(`Foot_${side}`, .035 + counter * .025);
    }
  };
}
