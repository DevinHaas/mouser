import { Sparkles } from "@react-three/drei";
import { useFrame, type ThreeElements } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

/**
 * Thruster exhaust: sparks + a flickering nozzle glow.
 * ponytail: no plume mesh — the GLB nozzles already read as emissive.
 */
export function Booster({
  color = "#66ccff",
  length = 0.9,
  radius = 0.18,
  ...props
}: { color?: string; length?: number; radius?: number } & ThreeElements["group"]) {
  const light = useRef<THREE.PointLight>(null);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    // two sines instead of noise — reads as flicker, costs nothing
    if (light.current) {
      light.current.intensity = 1.6 + Math.sin(t * 37) * 0.4 + Math.sin(t * 13.7) * 0.3;
    }
  });

  return (
    <group {...props}>
      <Sparkles
        count={18}
        scale={[radius * 3, length * 1.6, radius * 3]}
        position={[0, -length * 0.7, 0]}
        size={2}
        speed={2.5}
        color={color}
      />
      <pointLight ref={light} color={color} intensity={2} distance={2.2} position={[0, -0.15, 0]} />
    </group>
  );
}
