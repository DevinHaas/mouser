import { Canvas, useFrame } from "@react-three/fiber";
import { Billboard, Clone, Text, useGLTF, useTexture } from "@react-three/drei";
import { useMemo, useRef, Suspense } from "react";
import * as THREE from "three";
import { Booster } from "./booster";
import { fmtTime } from "@/lib/format";
import { MOUSELESS_TOOL_BY_ID } from "@/lib/mouseless-tools";

const FLOATER = "/floater.glb";
/** Same face as the .title-fx headings (see index.css @font-face "Ryzes"). */
const TITLE_FONT = "/fonts/ryzes.ttf";
/** Body face — copied out of @fontsource/press-start-2p; troika needs a file URL. */
const BODY_FONT = "/fonts/press-start-2p.woff";

export type PodiumEntry = {
  rank: 1 | 2 | 3;
  name: string;
  timeMs: number;
  image: string | null;
  mouselessTool?: string | null;
  /** true = placeholder row shown only until the real board fills up */
  demo?: boolean;
};

/** Podium heights + plume colors per rank. */
const RANK = {
  1: { x: 0, y: 1.1, scale: 1.15, color: "#ffcc55" },
  2: { x: -2.6, y: 0.2, scale: 1.0, color: "#9fd8ff" },
  3: { x: 2.6, y: -0.3, scale: 1.0, color: "#ff8c66" },
} as const;

/** Normalized floater copy — GLB is a 1×0.72×1 disc centered near origin. */
function FloaterModel({ scale }: { scale: number }) {
  const { scene } = useGLTF(FLOATER);
  const norm = useMemo(() => {
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    return { s: 1.6 / Math.max(size.x, size.y, size.z), center, halfY: size.y / 2 };
  }, [scene]);

  return (
    <group scale={norm.s * scale} position={norm.center.clone().multiplyScalar(-norm.s * scale)}>
      <Clone object={scene} />
    </group>
  );
}

/** GitHub avatar as a lit disc riding on top of the floater. */
function Avatar({ url, y, color }: { url: string; y: number; color: string }) {
  const map = useTexture(url);
  return (
    <Billboard position={[0, y, 0.9]}>
      <mesh>
        <circleGeometry args={[0.38, 48]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, -0.01]}>
        <ringGeometry args={[0.38, 0.45, 48]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
    </Billboard>
  );
}

function AvatarFallback({ name, y, color }: { name: string; y: number; color: string }) {
  return (
    <Billboard position={[0, y, 0.9]}>
      <mesh>
        <circleGeometry args={[0.38, 48]} />
        <meshBasicMaterial color="#2a2f4a" />
      </mesh>
      <mesh position={[0, 0, -0.01]}>
        <ringGeometry args={[0.38, 0.45, 48]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <Text position={[0, 0, 0.01]} fontSize={0.3} color="#f0c4bc" anchorX="center" anchorY="middle">
        {name.slice(0, 1).toUpperCase()}
      </Text>
    </Billboard>
  );
}

function PodiumFloater({ entry }: { entry: PodiumEntry }) {
  const cfg = RANK[entry.rank];
  const tool = entry.mouselessTool ? MOUSELESS_TOOL_BY_ID.get(entry.mouselessTool) : null;
  const footer = tool?.name ?? entry.mouselessTool ?? (entry.demo ? "DEMO" : null);
  const group = useRef<THREE.Group>(null);
  const hull = useRef<THREE.Group>(null);
  const labels = useRef<THREE.Group>(null);

  // ponytail: bob in a ref instead of <Float> so boosters stay glued to the hull
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const yaw = Math.sin(t * 0.35 + entry.rank) * 0.25;
    if (group.current) group.current.position.y = cfg.y + Math.sin(t * 0.9 + entry.rank) * 0.08;
    if (hull.current) hull.current.rotation.y = yaw;
    // labels drift with the hull but stay near face-on so they keep reading
    if (labels.current) labels.current.rotation.y = yaw * 0.25;
  });

  return (
    <group ref={group} position={[cfg.x, cfg.y, 0]}>
      <group ref={hull} scale={cfg.scale}>
        <FloaterModel scale={1} />
        <Suspense fallback={<AvatarFallback name={entry.name} y={0.1} color={cfg.color} />}>
          {entry.image ? (
            <Avatar url={entry.image} y={0.1} color={cfg.color} />
          ) : (
            <AvatarFallback name={entry.name} y={0.1} color={cfg.color} />
          )}
        </Suspense>

        {/* two thrusters under the hull rim */}
        <Booster position={[-0.42, -0.45, 0]} color={cfg.color} length={0.8} radius={0.14} />
        <Booster position={[0.42, -0.45, 0]} color={cfg.color} length={0.8} radius={0.14} />
      </group>

      <group ref={labels}>
      <Text
        position={[0, 1.32, 0]}
        font={TITLE_FONT}
        fontSize={0.72}
        color={cfg.color}
        outlineWidth={0.02}
        outlineColor="#03040c"
        anchorX="center"
      >
        {`#${entry.rank}`}
      </Text>
      <Text
        position={[0, -1.6, 0]}
        font={TITLE_FONT}
        fontSize={0.4}
        color="#f0c4bc"
        outlineWidth={0.015}
        outlineColor="#03040c"
        anchorX="center"
      >
        {entry.name}
      </Text>
      <Text
        position={[0, -2.05, 0]}
        font={BODY_FONT}
        fontSize={0.2}
        color={cfg.color}
        outlineWidth={0.012}
        outlineColor="#03040c"
        anchorX="center"
      >
        {fmtTime(entry.timeMs)}
      </Text>
      {footer && (
        <Text
          position={[0, -2.4, 0]}
          font={BODY_FONT}
          fontSize={0.16}
          color={tool?.color ?? "#8a8fb0"}
          outlineWidth={0.01}
          outlineColor="#03040c"
          anchorX="center"
        >
          {footer}
        </Text>
      )}
      </group>
    </group>
  );
}

export function Podium({ entries }: { entries: PodiumEntry[] }) {
  return (
    <Canvas camera={{ position: [0, 0.4, 7.5], fov: 50 }} dpr={[1, 2]}>
      <color attach="background" args={["#03040c"]} />
      <ambientLight intensity={1.1} />
      <pointLight position={[6, 5, 8]} intensity={180} color="#cfe0ff" />
      <pointLight position={[-7, -4, 5]} intensity={120} color="#b06cff" />
      <directionalLight position={[0, 4, 8]} intensity={2} />
      <Suspense fallback={null}>
        {entries.map((e) => (
          <PodiumFloater key={e.rank} entry={e} />
        ))}
      </Suspense>
    </Canvas>
  );
}

useGLTF.preload(FLOATER);
