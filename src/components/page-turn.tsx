import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useTexture } from "@react-three/drei";
import * as THREE from "three";

/** Seconds for one turn. The page-turn rustle in sfx.ts is cut to match. */
const DURATION = 0.9;
/** Curl radius in world units — smaller is a tighter, crisper fold. */
const RADIUS = 0.15;

const easeInOut = (k: number) =>
  k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;

/**
 * Wraps everything right of a moving fold line around a cylinder, then lets it
 * lie flat once it has gone past half a turn. That "wrap, then flatten" split is
 * what separates a page turn from a plain rotation: the sheet stays put on the
 * left while only the free edge lifts.
 */
const VERT = /* glsl */ `
  #define PI 3.141592653589793
  uniform float uProgress;
  uniform float uW;
  uniform float uR;
  varying vec2 vUv;
  varying float vTheta;

  void main() {
    vUv = uv;
    vec3 p = position;
    float foldX = mix(uW * 0.5, -uW * 0.5 - PI * uR, uProgress);
    float d = p.x - foldX;
    float theta = 0.0;

    if (d > 0.0) {
      theta = d / uR;
      if (theta < PI) {
        p.x = foldX + uR * sin(theta);
        p.z = uR * (1.0 - cos(theta));
      } else {
        // Past the crest the sheet is flipped over and flat again.
        p.x = foldX - (d - PI * uR);
        p.z = 2.0 * uR;
        theta = PI;
      }
    }

    vTheta = theta;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }
`;

const FRAG = /* glsl */ `
  #define PI 3.141592653589793
  uniform sampler2D uTex;
  uniform float uOpacity;
  varying vec2 vUv;
  varying float vTheta;

  void main() {
    // The reverse side of a sheet shows the same art mirrored and dimmed, the
    // way ink reads through paper.
    vec2 uv = gl_FrontFacing ? vUv : vec2(1.0 - vUv.x, vUv.y);
    vec3 c = texture2D(uTex, uv).rgb;
    if (!gl_FrontFacing) c = mix(c, vec3(0.05, 0.04, 0.08), 0.78);

    // Shading straight off the curl angle — no lights needed, and it peaks
    // exactly where the fold catches the most curvature.
    c *= 1.0 - 0.55 * sin(clamp(vTheta, 0.0, PI));

    // Frame drawn in the shader rather than as a CSS border, so the canvas can
    // stay bigger than the art and let the turning page fly past its edge.
    vec2 e = min(vUv, 1.0 - vUv);
    float edge = 1.0 - smoothstep(0.0, 0.004, min(e.x, e.y));
    c = mix(c, vec3(1.0, 0.48, 0.16), edge * 0.55);

    gl_FragColor = vec4(c, uOpacity);
  }
`;

function Sheet({
  url,
  turning,
  reverse,
  onDone,
}: {
  url: string;
  /** Static backing page when false; animates its curl when true. */
  turning?: boolean;
  /** Uncurl inwards (going back) instead of peeling away (going forward). */
  reverse?: boolean;
  onDone?: () => void;
}) {
  const tex = useTexture(url, (t) => {
    const one = Array.isArray(t) ? t[0] : t;
    one.colorSpace = THREE.SRGBColorSpace;
  });

  const { viewport } = useThree();
  const img = tex.image as { width: number; height: number };
  const aspect = img.width / img.height;
  // 0.88 leaves room for the turning page to swing outside the art box.
  const h = Math.min(viewport.height, viewport.width / aspect) * 0.88;
  const w = h * aspect;

  const uniforms = useMemo(
    () => ({
      uTex: { value: tex },
      uProgress: { value: turning && reverse ? 1 : 0 },
      uW: { value: w },
      uR: { value: RADIUS },
      uOpacity: { value: 1 },
    }),
    // Built once; every field below is kept current from useFrame instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // Driven through the material rather than the memo object: the curl changes
  // every frame, and pushing it through React state would re-render at 60fps.
  const mat = useRef<THREE.ShaderMaterial>(null);
  const t = useRef(0);
  const done = useRef(false);
  useFrame((_, dt) => {
    const u = mat.current?.uniforms;
    if (!u) return;
    u.uTex.value = tex;
    u.uW.value = w;
    if (!turning || done.current) return;

    t.current = Math.min(1, t.current + dt / DURATION);
    const k = easeInOut(t.current);
    const p = reverse ? 1 - k : k;
    u.uProgress.value = p;
    // Fade only at the very end, once the sheet is off the art anyway.
    u.uOpacity.value = 1 - Math.max(0, (p - 0.78) / 0.22);
    if (t.current >= 1) {
      done.current = true;
      onDone?.();
    }
  });

  return (
    <mesh position={[0, 0, turning ? 0.002 : 0]}>
      <planeGeometry args={[w, h, 90, 1]} />
      <shaderMaterial
        ref={mat}
        vertexShader={VERT}
        fragmentShader={FRAG}
        uniforms={uniforms}
        side={THREE.DoubleSide}
        transparent
        depthWrite={false}
      />
    </mesh>
  );
}

/**
 * Shows `src` as a sheet of paper and turns to it in 3D whenever it changes.
 * `dir` says which way: forward peels the old page away, back slides the new
 * one in from the left.
 */
export function PageTurn({
  src,
  dir,
  preload = [],
}: {
  src: string;
  dir: 1 | -1;
  preload?: string[];
}) {
  const shown = useRef(src);
  const [turn, setTurn] = useState<{
    base: string;
    fly: string;
    reverse: boolean;
  } | null>(null);

  useEffect(() => {
    if (preload.length) useTexture.preload(preload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (shown.current === src) return;
    const from = shown.current;
    shown.current = src;
    setTurn(
      dir < 0
        ? { base: from, fly: src, reverse: true }
        : { base: src, fly: from, reverse: false },
    );
  }, [src, dir]);

  return (
    <div className="page-turn">
      <Canvas
        dpr={[1, 2]}
        camera={{ fov: 40, position: [0, 0, 3.2] }}
        gl={{ alpha: true }}
      >
        <Suspense fallback={null}>
          <Sheet url={turn ? turn.base : src} />
        </Suspense>
        {turn && (
          <Suspense fallback={null}>
            <Sheet
              key={turn.fly + String(turn.reverse) + src}
              url={turn.fly}
              turning
              reverse={turn.reverse}
              onDone={() => setTurn(null)}
            />
          </Suspense>
        )}
      </Canvas>
    </div>
  );
}
