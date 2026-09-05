import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Clone, Stars, useAnimations, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { actions } from "astro:actions";
import { authClient } from "@/lib/auth-client";
import { makeHoverSfx, playMusic, playOnce, playRadio } from "@/lib/sfx";
import { MusicViz } from "./music-viz";
import { LeaderboardDock } from "./leaderboard-dock";
import { AuthWidget } from "./auth-widget";
import { DriftingAstronaut } from "./astronaut-boosters";
import { TerminalScreen } from "./terminal-screen";
import { RefuelPanel } from "./refuel-panel";
import { IntroSequence } from "./intro-sequence";
import { TurnstileGate } from "./turnstile-gate";
import { hasSeenIntro, markIntroSeen, trackIntroReplay } from "@/lib/analytics";

const TARGET = 10;
const MODEL = "/capsule.glb";
const CHEST = "/chest_animated.glb";
const ARROW = "/up.glb";
const ACCENT = "#B03422";
const GLOW = "#ff8c1e";

/** How many viewport-heights tall the play field is — forces scrolling. */
const LEVELS = 3;

/** Half the vertical span of the play field, in world units. The camera pans
 *  between +BAND_Y and -BAND_Y as the page scrolls. */
const BAND_Y = 4 * LEVELS;

/* A long lens far back is nearly orthographic: every tube is seen square-on
   instead of from below/above like a wide lens up close does. */
const CAM_Z = 16;
const CAM_FOV = 40;

/** Half the world-height the camera can see at the play plane. */
const VIEW_HALF_H = Math.tan((CAM_FOV * Math.PI) / 360) * CAM_Z;

/** Where the chest sits (bottom of the field), and the arc its tubes settle into.
 *  x is randomised per round (a round is one page load — PLAY AGAIN reloads). */
const CHEST_POS = new THREE.Vector3(
  (Math.random() - 0.5) * 7,
  -BAND_Y + 1.5,
  0,
);

/** Terminal: a fixed spot in the field on the tubes' own z-plane, so the page
 *  scrolls past it like everything else. Offset from centre and clear of the
 *  chest's tube arc; x stays inside the 4:3 half-view (7.76) with room for the
 *  3.0-wide body (max |x| here is 5.6). */
// Randomised per round, and always on the opposite side of centre from the
// chest so its tube arc can't overlap the terminal body.
const TERMINAL_POS = new THREE.Vector3(
  (CHEST_POS.x > 0 ? -1 : 1) * (3.8 + Math.random() * 1.8),
  -9.2 + (Math.random() - 0.5) * 2.6,
  0,
);
const CHEST_ARC = [
  [-1.8, 1.9],
  [0, 2.6],
  [1.8, 1.9],
] as const;

/** Chest timeline, seconds from the click. The GLB "Open" clip is 1.67s. */
const T_RELEASE = 1.5;
const T_CLOSE = 2.8;
const T_EXIT = 4.6;
const T_GONE = 6.4;

/** Half a tube plus its drift wobble — how much room it needs inside the edge. */
const X_MARGIN = 1.3;

type Tube = {
  id: number;
  /** Free tubes place themselves as a -1..1 fraction of the visible half-width,
   *  so no tube can ever sit off the side of the viewport. Only the vertical
   *  axis is allowed to run off-screen — that's what the scrolling is for. */
  xFrac?: number;
  base: THREE.Vector3;
  phase: number;
  spin: number;
  fromChest?: boolean;
};

const rand = (a: number, b: number) => a + Math.random() * (b - a);

function makeTubes(): Tube[] {
  const drift = () => ({
    phase: Math.random() * Math.PI * 2,
    spin: rand(0.2, 0.7) * (Math.random() < 0.5 ? -1 : 1),
  });
  // Free tubes are spread evenly top-to-bottom across LEVELS viewport-heights,
  // but the slots are shuffled before ids are handed out, so click order runs
  // up and down the field instead of straight down it.
  const freeCount = TARGET - CHEST_ARC.length;
  const slots = Array.from({ length: freeCount }, (_, i) => {
    const t = freeCount > 1 ? i / (freeCount - 1) : 0.5;
    return BAND_Y - t * (2 * BAND_Y) + rand(-2, 2);
  });
  for (let i = slots.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [slots[i], slots[j]] = [slots[j], slots[i]];
  }
  const free = slots.map((y, id) => ({
    id,
    xFrac: rand(-0.92, 0.92),
    base: new THREE.Vector3(
      0, // x comes from xFrac at render time, once the aspect is known
      y,
      0, // every tube on the same z-plane, so none is seen at an angle
    ),
    ...drift(),
  }));
  const chest = CHEST_ARC.map(([dx, dy], i) => ({
    id: free.length + i,
    base: CHEST_POS.clone().add(new THREE.Vector3(dx, dy, 0)),
    fromChest: true,
    ...drift(),
  }));
  return [...free, ...chest];
}

/**
 * Normalized copy of the Blender capsule, original GLB material/texture kept.
 * `dim` grays out tubes that are out of click order — locked, not yet due.
 * `deep="materialsOnly"` makes Clone hand each instance its own material (the
 * default shares one material object across every clone), so the tint here
 * can't bleed into other tubes.
 */
function TubeModel({ dim }: { dim?: boolean }) {
  const { scene } = useGLTF(MODEL);
  const normalized = useMemo(() => {
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const s = 1.6 / Math.max(size.x, size.y, size.z);
    return { scene, s, center };
  }, [scene]);
  const group = useRef<THREE.Group>(null);

  useEffect(() => {
    const g = group.current;
    if (!g || !dim) return;
    // Each Clone render starts from the pristine GLB color, so graying out
    // just needs a one-way desaturate — no original to restore.
    g.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mats = Array.isArray(mesh.material)
        ? mesh.material
        : [mesh.material];
      for (const m of mats) {
        const mat = m as THREE.MeshStandardMaterial;
        if (!mat.color) continue;
        const gray =
          mat.color.r * 0.299 + mat.color.g * 0.587 + mat.color.b * 0.114;
        mat.color.setScalar(gray * 0.45);
        mat.emissive?.setScalar(0);
      }
    });
    // Deps matter: without them this re-ran every render and darkened the same
    // materials again and again until locked tubes were pure black.
  }, [dim]);

  return (
    <group
      ref={group}
      scale={normalized.s}
      position={normalized.center.clone().multiplyScalar(-normalized.s)}
    >
      <Clone object={normalized.scene} deep="materialsOnly" />
    </group>
  );
}

/** Three star layers: different sizes, hues and drift speeds. */
function Starfield() {
  const near = useRef<THREE.Group>(null);
  const mid = useRef<THREE.Group>(null);
  const far = useRef<THREE.Group>(null);

  useFrame((_, dt) => {
    if (near.current) near.current.rotation.y += dt * 0.012;
    if (mid.current) {
      mid.current.rotation.y -= dt * 0.006;
      mid.current.rotation.x += dt * 0.002;
    }
    if (far.current) far.current.rotation.z += dt * 0.003;
  });

  return (
    <>
      <group ref={far}>
        <Stars
          radius={140}
          depth={80}
          count={4500}
          factor={1.6}
          saturation={0}
          fade
          speed={0.3}
        />
      </group>
      <group ref={mid}>
        <Stars
          radius={95}
          depth={55}
          count={2200}
          factor={3.4}
          saturation={0.8}
          fade
          speed={0.9}
        />
      </group>
      <group ref={near}>
        <Stars
          radius={60}
          depth={35}
          count={700}
          factor={6.5}
          saturation={1}
          fade
          speed={1.6}
        />
      </group>
    </>
  );
}

/** Spark colors — these vary freely; the ring/light stay in the orange family. */
const SPARK_COLORS = [
  "#ff9c86",
  "#ffd27a",
  "#fff2b0",
  "#ff7a4a",
  "#ffe0c2",
  "#ffb347",
];

/** Expanding ring + light flash where a tube popped. Color, size, spark count and speed roll fresh each time. */
function Burst({ at }: { at: THREE.Vector3 }) {
  const ring = useRef<THREE.Mesh>(null);
  const light = useRef<THREE.PointLight>(null);
  const sparks = useRef<THREE.Points>(null);
  const t = useRef(0);

  const fx = useMemo(() => {
    const ringColor = new THREE.Color().setHSL(
      rand(0.03, 0.08), // hue: orange-red to amber
      rand(0.75, 1),
      rand(0.42, 0.62),
    );
    const sparkColor = SPARK_COLORS[Math.floor(rand(0, SPARK_COLORS.length))];
    const count = Math.round(rand(14, 32));
    const dirs = Array.from({ length: count }, () =>
      new THREE.Vector3(rand(-1, 1), rand(-1, 1), rand(-1, 1))
        .normalize()
        .multiplyScalar(rand(0.5, 1)),
    );
    const geo = new THREE.BufferGeometry().setFromPoints(
      dirs.map(() => new THREE.Vector3()),
    );
    return {
      dirs,
      geo,
      ringColor,
      sparkColor,
      maxScale: rand(1.3, 2.4),
      reach: rand(1.1, 2.2),
      sparkSize: rand(0.05, 0.1),
      duration: rand(0.6, 0.95),
      intensity: rand(10, 20),
    };
  }, []);

  useFrame((_, dt) => {
    t.current = Math.min(1, t.current + dt / fx.duration);
    const k = t.current;
    const ease = 1 - Math.pow(1 - k, 3);
    if (ring.current) {
      ring.current.scale.setScalar(0.3 + ease * fx.maxScale);
      (ring.current.material as THREE.MeshBasicMaterial).opacity = 1 - k;
    }
    if (light.current) light.current.intensity = fx.intensity * (1 - k) ** 2;
    if (sparks.current) {
      const pos = fx.geo.attributes.position as THREE.BufferAttribute;
      fx.dirs.forEach((d, i) =>
        pos.setXYZ(
          i,
          d.x * ease * fx.reach,
          d.y * ease * fx.reach,
          d.z * ease * fx.reach,
        ),
      );
      pos.needsUpdate = true;
      (sparks.current.material as THREE.PointsMaterial).opacity = 1 - k;
    }
  });

  return (
    <group position={at}>
      <pointLight ref={light} color={fx.ringColor} distance={14} />
      <mesh ref={ring}>
        <torusGeometry args={[0.6, 0.035, 8, 64]} />
        <meshBasicMaterial
          color={fx.ringColor}
          transparent
          toneMapped={false}
        />
      </mesh>
      <points ref={sparks} geometry={fx.geo}>
        <pointsMaterial
          color={fx.sparkColor}
          size={fx.sparkSize}
          transparent
          toneMapped={false}
        />
      </points>
    </group>
  );
}

/** Projects a world position onto the HTML hit-button that shadows it. */
function placeButton(
  btn: HTMLButtonElement,
  at: THREE.Vector3,
  camera: THREE.Camera,
  size: { width: number; height: number },
  worldSize: number,
) {
  const v = new THREE.Vector3().copy(at).project(camera);
  const fov = (camera as THREE.PerspectiveCamera).fov;
  const fovScale = size.height / (2 * Math.tan((fov * Math.PI) / 360));
  const px = Math.round(
    (fovScale * worldSize) / camera.position.distanceTo(at),
  );
  btn.style.left = `${(v.x * 0.5 + 0.5) * size.width}px`;
  btn.style.top = `${(-v.y * 0.5 + 0.5) * size.height}px`;
  btn.style.width = `${px}px`;
  btn.style.height = `${px}px`;
}

/**
 * Owns tube drift + projects each live tube onto its HTML hit-button.
 * The buttons — not the canvas — are the click targets, so keyboard tools
 * (Homerow, Shortcat, Vimium) can see and activate them. WebGL is invisible to them.
 */
function Field({
  tubes,
  live,
  activeId,
  hits,
  livePos,
}: {
  tubes: Tube[];
  live: number[];
  activeId: number | null;
  hits: React.RefObject<Record<number, HTMLButtonElement | null>>;
  livePos: React.RefObject<Record<number, THREE.Vector3>>;
}) {
  const groups = useRef<Record<number, THREE.Group | null>>({});
  const spawn = useRef<number | null>(null);
  const { camera, size } = useThree();

  useFrame((state) => {
    const time = state.clock.elapsedTime;
    for (const tube of tubes) {
      const g = groups.current[tube.id];
      const btn = hits.current[tube.id];
      if (!g) continue;
      // Widest x a tube may occupy at the current aspect. Free tubes scale into
      // it; the chest's arc is clamped to it.
      const limit = Math.max(
        0.6,
        VIEW_HALF_H * (size.width / size.height) - X_MARGIN,
      );
      const x =
        tube.xFrac !== undefined
          ? tube.xFrac * limit
          : THREE.MathUtils.clamp(tube.base.x, -limit, limit);
      g.position.set(
        x + Math.sin(time * 0.4 + tube.phase) * 0.35,
        tube.base.y + Math.cos(time * 0.32 + tube.phase) * 0.4,
        tube.base.z,
      );
      // Clickable tubes breathe; locked ones sit still and desaturated, so the
      // one you're allowed to hit right now reads at a glance.
      const active = tube.id === activeId;
      let scale = active ? 1 + Math.sin(time * 3) * 0.07 : 1;
      // Chest tubes fly up out of the lid and grow into their arc slot.
      if (tube.fromChest) {
        if (spawn.current === null) spawn.current = time;
        const ease =
          1 - Math.pow(1 - Math.min(1, (time - spawn.current) / 0.9), 3);
        g.position.lerpVectors(CHEST_POS, g.position, ease);
        scale *= ease;
      }
      g.scale.setScalar(scale);
      livePos.current[tube.id] = g.position.clone();
      // In-plane rock only. Free tumbling on x/y pitched tubes toward and away
      // from the camera, which read as the whole field being off-axis.
      g.rotation.set(
        0,
        0,
        Math.sin(time * 0.35 + tube.phase) * 0.3 * Math.sign(tube.spin),
      );
      if (btn) placeButton(btn, g.position, camera, size, 1.5);
    }
  });

  return (
    <>
      {tubes
        .filter((t) => live.includes(t.id))
        .map((t) => {
          const active = t.id === activeId;
          return (
            <group
              key={t.id}
              ref={(el) => {
                groups.current[t.id] = el;
              }}
            >
              <TubeModel dim={!active} />
              {active && (
                <pointLight color={GLOW} distance={5} intensity={16} />
              )}
            </group>
          );
        })}
    </>
  );
}

/** Soft radial falloff used for the chest bloom — many stops so no ring shows. */
function useGlowTexture() {
  return useMemo(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    const ctx = c.getContext("2d")!;
    const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
    for (let i = 0; i <= 24; i++) {
      const k = i / 24;
      // alpha falls off on a steep curve, so the edge dissolves instead of ending
      g.addColorStop(
        k,
        `rgba(255, ${Math.round(190 - k * 90)}, ${Math.round(110 - k * 90)}, ${Math.pow(1 - k, 3.2)})`,
      );
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 256, 256);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, []);
}

/**
 * The reward chest: click it, the lid lifts on an orange bloom, three tubes
 * float out into an arc above it, then the lid shuts and it plops away.
 */
function Chest({
  opened,
  onRelease,
  onGone,
  hitRef,
}: {
  opened: boolean;
  onRelease: () => void;
  onGone: () => void;
  hitRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const root = useRef<THREE.Group>(null);
  const aura = useRef<THREE.Group>(null);
  const glow = useRef<THREE.PointLight>(null);
  const orb = useRef<THREE.Group>(null);
  const glowTex = useGlowTexture();
  const t = useRef(0);
  const stage = useRef({ released: false, closing: false, gone: false });
  const { camera, size } = useThree();
  const { scene, animations } = useGLTF(CHEST);
  const { actions: clips } = useAnimations(animations, root);

  const fit = useMemo(() => {
    const box = new THREE.Box3().setFromObject(scene);
    const dim = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    return { s: 2.6 / Math.max(dim.x, dim.y, dim.z), offset: center.negate() };
  }, [scene]);

  useEffect(() => {
    const a = opened && clips.Open;
    if (!a) return;
    a.reset();
    a.setLoop(THREE.LoopOnce, 1);
    a.clampWhenFinished = true;
    a.timeScale = 1;
    a.play();
  }, [opened, clips]);

  useFrame((state, dt) => {
    const time = state.clock.elapsedTime;

    // Idle float: a slow bob with a touch of sway, running the whole time.
    if (root.current && !stage.current.gone) {
      const bob = Math.sin(time * 1.1) * 0.12;
      root.current.position.y = CHEST_POS.y + bob;
      root.current.rotation.y = -Math.PI / 2 + Math.sin(time * 0.5) * 0.05;
      root.current.rotation.z = Math.sin(time * 0.7) * 0.025;
      if (aura.current) aura.current.position.y = CHEST_POS.y + bob + 0.5;
      if (hitRef.current && !opened)
        placeButton(hitRef.current, root.current.position, camera, size, 2.6);
    }
    if (!opened || stage.current.gone) return;
    t.current += dt;
    const k = t.current;

    // Bloom swells while the lid is up, dies back as it shuts.
    const lit =
      THREE.MathUtils.clamp((k - 0.5) / 0.8, 0, 1) *
      (1 - THREE.MathUtils.clamp((k - T_CLOSE) / 1.2, 0, 1));
    if (glow.current) glow.current.intensity = 90 * lit;
    if (orb.current)
      orb.current.scale.setScalar(lit * (1 + Math.sin(k * 9) * 0.07));

    if (!stage.current.released && k >= T_RELEASE) {
      stage.current.released = true;
      onRelease();
    }
    if (!stage.current.closing && k >= T_CLOSE) {
      stage.current.closing = true;
      const a = clips.Open;
      if (a) {
        a.paused = false;
        a.time = a.getClip().duration;
        a.timeScale = -1;
        a.play();
      }
    }
    // Sails out of frame the short way — chest x decides which side that is.
    if (root.current && k >= T_EXIT) {
      const p = Math.min(1, (k - T_EXIT) / (T_GONE - T_EXIT));
      const ease = p * p;
      const dir = CHEST_POS.x >= 0 ? 1 : -1;
      root.current.position.x = CHEST_POS.x + dir * ease * 16;
      root.current.position.y += ease * 1.8;
      root.current.rotation.z += dir * ease * 0.5;
    }
    if (k >= T_GONE) {
      stage.current.gone = true;
      onGone();
    }
  });

  return (
    <>
      <group
        ref={root}
        position={CHEST_POS}
        rotation={[0, -Math.PI / 2, 0]}
        scale={fit.s}
      >
        <primitive object={scene} position={fit.offset} />
      </group>
      <group
        ref={aura}
        position={[CHEST_POS.x, CHEST_POS.y + 0.5, CHEST_POS.z]}
      >
        <pointLight ref={glow} color={GLOW} distance={16} intensity={0} />
        <group ref={orb} scale={0}>
          {/* neon core plus two ever-wider haloes: overlapping falloffs read as one beam */}
          <sprite scale={[1.1, 1.6, 1]}>
            <spriteMaterial
              map={glowTex}
              color="#fff0d0"
              transparent
              opacity={0.95}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
              toneMapped={false}
            />
          </sprite>
          <sprite scale={[3.2, 4.6, 1]}>
            <spriteMaterial
              map={glowTex}
              color={GLOW}
              transparent
              opacity={0.5}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
              toneMapped={false}
            />
          </sprite>
          <sprite scale={[7.5, 9, 1]} position={[0, 0.6, 0]}>
            <spriteMaterial
              map={glowTex}
              color="#ff5a00"
              transparent
              opacity={0.22}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
              toneMapped={false}
            />
          </sprite>
        </group>
      </group>
    </>
  );
}

/** The arrow GLB, spinning slowly, alone in its own tiny canvas. */
function ArrowModel({ dir }: { dir: "up" | "down" }) {
  const { scene } = useGLTF(ARROW);
  const g = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (g.current) g.current.rotation.y += dt * 0.9;
  });
  return (
    <group rotation={[0, 0, dir === "down" ? Math.PI : 0]}>
      <group ref={g}>
        <Clone object={scene} />
      </group>
    </group>
  );
}

/**
 * Scroll cue. Its own DOM element pinned to the top or bottom edge with plain
 * CSS — nothing to reproject per frame, and it can't drift with the camera.
 * The bob is a CSS keyframe for the same reason.
 */
function ArrowCue({ dir }: { dir: "up" | "down" | null }) {
  if (!dir) return null;
  return (
    <div className={`arrow-cue arrow-cue--${dir}`} aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0, 3.2], fov: 45 }}
        dpr={[1, 1.5]}
        gl={{ alpha: true }}
      >
        <ambientLight intensity={2} />
        <directionalLight position={[2, 3, 4]} intensity={3} />
        <ArrowModel dir={dir} />
      </Canvas>
    </div>
  );
}

/**
 * Page scroll pans the camera down the field. The canvas itself is viewport
 * sized and fixed — a canvas as tall as the document renders 3x the pixels and
 * squeezes the horizontal FOV to a third, which is what made it slow and zoomed.
 */
function ScrollCamera({
  locked,
  children,
}: {
  /** Something else is driving the camera (the terminal). Hands off entirely:
   *  the rig stops tracking too, otherwise the props parented to it would
   *  chase the camera into its own zoom. */
  locked?: boolean;
  children?: React.ReactNode;
}) {
  const { camera } = useThree();
  const rig = useRef<THREE.Group>(null);
  useFrame(() => {
    if (locked) return;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const p = max > 0 ? THREE.MathUtils.clamp(window.scrollY / max, 0, 1) : 0;
    const want = BAND_Y - p * 2 * BAND_Y;
    camera.position.y += (want - camera.position.y) * 0.12; // ease, not snap
    // R3F aims a camera created from the `camera` prop at the origin, so this
    // one sat tilted ~37° down and kept that tilt while panning: the topmost
    // tube projected above the viewport and could never be clicked (and every
    // tube was seen off-axis). Level it — the pan alone moves the view.
    camera.rotation.set(0, 0, 0);
    // Children (lights, background dressing) ride along, otherwise the lower
    // half of the field is unlit and the astronaut is only visible at the top.
    if (rig.current) rig.current.position.y = camera.position.y;
  });
  return <group ref={rig}>{children}</group>;
}

/**
 * Mouse-usage sniffer. Real hands emit a stream of pointermove events right
 * before a click; keyboard tools either activate with no pointer at all
 * (event.detail === 0) or teleport the cursor in a single jump.
 */
function useMouseWatch() {
  const burst = useRef(0);
  const last = useRef(0);
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!e.isTrusted || e.pointerType !== "mouse") return;
      const now = performance.now();
      burst.current = now - last.current < 150 ? burst.current + 1 : 1;
      last.current = now;
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, []);
  return (e: React.MouseEvent) =>
    e.detail > 0 &&
    burst.current >= 3 &&
    performance.now() - last.current < 400;
}

/** Cyberpunk landing overlay: title, start button, and an optional login. */
function StartScreen({ onStart }: { onStart: () => void }) {
  const { data: session, isPending } = authClient.useSession();
  const [showAuth, setShowAuth] = useState(false);
  // ponytail: hide the sign-in affordances until we know the auth state, so a
  // logged-in user never sees a flash of "sign in" / "no account needed".
  const showSignIn = !isPending && !session;

  const hover = useMemo(() => makeHoverSfx("/music/hover.mp3"), []);
  useEffect(() => hover.stop, [hover]);

  useEffect(() => {
    return playMusic("/music/intro.mp3");
  }, []);

  const start = () => {
    hover.stop();
    playOnce("/music/primary_start.mp3");
    onStart();
  };

  // Monkeytype-style: Enter starts the game, unless it's being typed into a
  // form field (e.g. the sign-in widget).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Enter") return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      start();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="start-screen">
      <h1 className="title-fx">
        <span className="t-sticker">MOUSER</span>
        <span className="t-extrude">MOUSER</span>
        <span className="t-highlight">MOUSER</span>
        <span className="t-fill">MOUSER</span>
      </h1>
      <p className="start-sub">Test your mousless skills in space</p>
      <button
        type="button"
        className="start-btn frame-btn"
        // ponytail: autofocus only on a cold/external load — coming back from
        // the leaderboard's PLAY AGAIN would otherwise grab focus and fire the
        // hover sfx unprompted.
        autoFocus={!document.referrer.startsWith(location.origin)}
        onMouseEnter={hover.enter}
        onMouseLeave={hover.leave}
        onFocus={hover.enter}
        onBlur={hover.leave}
        onClick={start}
      >
        START GAME
      </button>
      {showSignIn && (
        <p className="start-hint">
          no account needed — sign in only to save your time
        </p>
      )}

      {!showSignIn ? null : showAuth ? (
        <AuthWidget />
      ) : (
        <button
          type="button"
          className="start-link"
          onClick={() => setShowAuth(true)}
        >
          sign in
        </button>
      )}

      <p className="start-footer-hint">
        <kbd className="key-enter" aria-label="enter">
          ↵
        </kbd>{" "}
        to start
      </p>
    </div>
  );
}

export function MouserGame() {
  const [tubes] = useState(makeTubes);
  const [live, setLive] = useState(() =>
    tubes.filter((t) => !t.fromChest).map((t) => t.id),
  );
  const [chestOpen, setChestOpen] = useState(false);
  const [chestGone, setChestGone] = useState(false);
  const [bursts, setBursts] = useState<{ key: number; at: THREE.Vector3 }[]>(
    [],
  );
  const [cheats, setCheats] = useState(0);
  const [warn, setWarn] = useState(false);
  const [finalTime, setFinalTime] = useState<number | null>(null);
  // ponytail: PLAY AGAIN links to /?play=1 — skip the start screen on return.
  const [started, setStarted] = useState(() =>
    new URLSearchParams(location.search).has("play"),
  );
  const [paused, setPaused] = useState(false);
  // Story panels between START and level 1 — shown until the player has seen
  // them once, and re-openable only via the ⌘K command bar (/?intro=1).
  const [intro, setIntro] = useState(() =>
    new URLSearchParams(location.search).has("intro"),
  );
  // Terminal: `camLocked` is camera ownership (held across both zooms),
  // `terminalDone` is the level gate.
  const [camLocked, setCamLocked] = useState(false);
  const [terminalDone, setTerminalDone] = useState(false);
  // Refuel step: `refuelAt` is the viewport point the panel hangs off (null =
  // shut), `fuelDone` is the level gate.
  const [refuelAt, setRefuelAt] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [fuelDone, setFuelDone] = useState(false);
  const hits = useRef<Record<number, HTMLButtonElement | null>>({});
  const chestHit = useRef<HTMLButtonElement | null>(null);
  const livePos = useRef<Record<number, THREE.Vector3>>({});
  const burstId = useRef(0);
  const clock = useRef<HTMLSpanElement>(null);
  const start = useRef(performance.now());
  const pauseStart = useRef<number | null>(null);
  const wasMouse = useMouseWatch();
  // Bot screening: one mark per collected tube (ms into the run) plus a
  // background Turnstile token, both checked server-side in submitRun.
  const marks = useRef<number[]>([]);
  const botToken = useRef<string | null>(null);

  // Counted, not derived from `live.length`: the chest's three tubes don't
  // exist in `live` until the chest is opened, so deriving it both showed 3/10
  // on the first frame and ended the run the moment the free tubes ran out —
  // before the chest had ever been clicked.
  const [collected, setCollected] = useState(0);
  const done = finalTime !== null;

  useEffect(() => {
    if (collected >= TARGET) setFinalTime(performance.now() - start.current);
  }, [collected]);

  // Lowest-id live tube — the one the player must click next. Chest tubes are
  // part of the same chain; their ids sit above every free tube, so they come
  // last and are collected one at a time in arc order.
  const nextRequiredId = useMemo(
    () => (live.length ? Math.min(...live) : null),
    [live],
  );

  // The chest is the next step once every free tube is gone — that's when it
  // gets the ring. It vanishes on open, taking the ring with it, and the
  // highlight moves on to the tubes it released.
  const chestNext = useMemo(
    () => fuelDone && !tubes.some((t) => !t.fromChest && live.includes(t.id)),
    [tubes, live, fuelDone],
  );

  // The terminal takes its turn between the last free tube and the chest.
  // Move this one expression to re-slot it anywhere in the chain.
  const terminalNext = useMemo(
    () =>
      started &&
      !done &&
      !paused &&
      !terminalDone &&
      !tubes.some((t) => !t.fromChest && live.includes(t.id)),
    [started, done, paused, terminalDone, tubes, live],
  );

  // …and the astronaut takes his between the terminal and the chest.
  const refuelNext = useMemo(
    () => started && !done && !paused && terminalDone && !fuelDone,
    [started, done, paused, terminalDone, fuelDone],
  );

  // World-Y of whatever the player has to reach next: the required free tube,
  // the terminal while it holds the chest shut, or the chest itself (and the
  // tubes it spits out, which sit right above it).
  const targetY = useMemo(() => {
    if (terminalNext) return TERMINAL_POS.y;
    // The astronaut is parented to the camera rig — he is always on screen, so
    // there is never a direction to point the player in during his step.
    if (refuelNext) return null;
    const next =
      tubes.find((t) => t.id === nextRequiredId) ??
      tubes.find((t) => live.includes(t.id));
    if (!next) return chestGone ? null : CHEST_POS.y;
    return next.fromChest ? CHEST_POS.y : next.base.y;
  }, [tubes, live, nextRequiredId, chestGone, terminalNext, refuelNext]);

  // Compare that Y against the camera's scroll-driven Y: above the view → scroll
  // up, below it → scroll down, inside it → no arrow. Recomputed on scroll only.
  const [scrollHint, setScrollHint] = useState<"up" | "down" | null>(null);
  useEffect(() => {
    if (!started || done || targetY === null) {
      setScrollHint(null);
      return;
    }
    const update = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const p = max > 0 ? THREE.MathUtils.clamp(window.scrollY / max, 0, 1) : 0;
      const camY = BAND_Y - p * 2 * BAND_Y;
      const d = targetY - camY;
      // 0.7 of the half-view: the arrow gives up a little before the tube is
      // flush with the edge, so it's gone by the time the tube is properly read.
      const edge = VIEW_HALF_H * 0.7;
      setScrollHint(d > edge ? "up" : d < -edge ? "down" : null);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [started, done, targetY]);

  useEffect(() => {
    if (!started || done) return;
    return playMusic("/music/game.mp3");
  }, [started, done]);

  // Replaying the intro from the command bar (/?intro=1) is a distinct signal.
  useEffect(() => {
    if (new URLSearchParams(location.search).has("intro")) trackIntroReplay();
  }, []);

  const beginGame = () => {
    if (!hasSeenIntro() && !new URLSearchParams(location.search).has("play")) {
      setIntro(true);
      return;
    }
    start.current = performance.now();
    marks.current = [];
    setStarted(true);
  };

  const finishIntro = () => {
    markIntroSeen();
    setIntro(false);
    start.current = performance.now();
    marks.current = [];
    setStarted(true);
  };

  // The overlays sit on top of the canvas but the page itself keeps scrolling
  // underneath them — that scroll drives ScrollCamera, so it pans the visible
  // background right through the dim backdrop. Lock the page while any
  // overlay (start screen, pause, endcard) covers it.
  useEffect(() => {
    document.body.style.overflow =
      !started || paused || done || camLocked || refuelAt ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [started, paused, done, camLocked, refuelAt]);

  // While the story panels are up, hide the page chrome that lives outside this
  // component (account menu, ⌘K nav hint) so the overlay reads clean.
  useEffect(() => {
    document.body.classList.toggle("intro-active", intro);
    return () => document.body.classList.remove("intro-active");
  }, [intro]);

  // The in-scene timer HUD lives top-right where the account menu sits — hide
  // the menu once the run is underway so it doesn't cover the clock.
  useEffect(() => {
    const playing = started && !done;
    document.body.classList.toggle("game-active", playing);
    return () => document.body.classList.remove("game-active");
  }, [started, done]);

  useEffect(() => {
    if (!started || done || paused) return;
    const id = setInterval(() => {
      if (clock.current)
        clock.current.textContent = fmt(performance.now() - start.current);
    }, 47);
    return () => clearInterval(id);
  }, [started, done, paused]);

  // Toggles pause; shifts `start` forward by the paused duration on resume so
  // the displayed clock and final time skip the paused interval entirely.
  const togglePause = () => {
    if (!started || done) return;
    setPaused((p) => {
      if (p && pauseStart.current !== null) {
        start.current += performance.now() - pauseStart.current;
        pauseStart.current = null;
      } else {
        pauseStart.current = performance.now();
      }
      return !p;
    });
  };

  // Space toggles pause during play, like Monkeytype's tab-to-restart.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON") return;
      e.preventDefault(); // stop the page from scrolling
      togglePause();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // ponytail: abort just reloads to the start screen instead of hand-resetting
  // every piece of run state — simplest way back to a clean slate.
  const abortGame = () => location.reload();

  // Fires once a run is finished: saves it when logged in, then jumps straight
  // to the leaderboard. ponytail: logged-out runs just go unsaved, no endcard
  // detour for a login prompt — add one back if that flow is needed.
  useEffect(() => {
    if (finalTime === null) return;
    actions
      .submitRun({
        timeMs: Math.round(finalTime),
        cheats,
        marks: marks.current.map(Math.round),
        token: botToken.current,
      })
      .catch(() => {})
      .then(() => {
        location.href = "/leaderboard";
      });
  }, [finalTime, cheats]);

  const flagMouse = (e: React.MouseEvent) => {
    if (!wasMouse(e)) return;
    setCheats((c) => c + 1);
    setWarn(true);
    setTimeout(() => setWarn(false), 1600);
  };

  const openChest = (e: React.MouseEvent) => {
    if (!started || done || paused || chestOpen || !chestNext) return;
    flagMouse(e);
    playOnce("/music/chest.mp3");
    setChestOpen(true);
  };

  const collect = (tube: Tube, e: React.MouseEvent) => {
    if (!started || done || paused || !live.includes(tube.id)) return;
    if (tube.id !== nextRequiredId) return; // locked, out of order
    marks.current.push(performance.now() - start.current);
    flagMouse(e);
    const at = livePos.current[tube.id] ?? tube.base.clone();
    playOnce(
      Math.random() < 0.5 ? "/music/explosion.mp3" : "/music/explosion2.mp3",
      0.25,
    );
    const key = ++burstId.current;
    setBursts((b) => [...b, { key, at }]);
    setTimeout(() => setBursts((b) => b.filter((x) => x.key !== key)), 1200);
    setLive((l) => l.filter((id) => id !== tube.id));
    setCollected((n) => n + 1);
  };

  return (
    <>
      <TurnstileGate onToken={(t) => (botToken.current = t)} />
      {/* Tall enough to force scrolling: tubes are spread across LEVELS
          viewport-heights, so this and the canvas below both need the room. */}
      <div className="game-area" style={{ height: `${LEVELS * 100}vh` }}>
        <Canvas
          className="game-canvas"
          style={{
            position: "fixed",
            inset: 0,
            width: "100vw",
            height: "100vh",
          }}
          camera={{ position: [0, BAND_Y, CAM_Z], fov: CAM_FOV }}
          dpr={[1, 1.75]}
        >
          <color attach="background" args={["#03040c"]} />
          {/* ponytail: no fog — it started at 14 units and the starfield lives at
              60-140, so every star was fogged out to background black. */}
          <ambientLight intensity={1.1} />
          <ScrollCamera locked={camLocked}>
            <pointLight position={[8, 6, 12]} intensity={260} color="#cfe0ff" />
            <pointLight
              position={[-9, -5, 6]}
              intensity={160}
              color="#b06cff"
            />
            <directionalLight position={[0, 4, 8]} intensity={2.2} />
            {/* Background: drifts on his own thrusters, well behind the play field.
                The boosters are driven by his acceleration, so he banks into every
                turn and the plumes swing and flare to match. */}
            <DriftingAstronaut
              position={[-5.8, -2.6, -6.5]}
              size={4.6}
              onContextMenu={(e) => {
                e.stopPropagation();
                e.nativeEvent.preventDefault();
                playRadio("/music/astronaut_voice.mp3");
                // Anchor the panel where he was actually hit rather than to his
                // node: he keeps drifting, and a panel that slides out from
                // under the cursor can't be clicked.
                if (refuelNext) setRefuelAt({ x: e.clientX, y: e.clientY });
              }}
            />
          </ScrollCamera>
          <Starfield />
          <Field
            tubes={tubes}
            live={live}
            activeId={nextRequiredId}
            hits={hits}
            livePos={livePos}
          />
          {/* Outside ScrollCamera on purpose: parented to the rig it would ride
              the camera and never scroll past. Here it sits in the field on the
              tubes' z-plane. The screen faces +X in model space; TerminalScreen
              turns it to face the camera itself. */}
          <TerminalScreen
            position={TERMINAL_POS.toArray()}
            size={3.4}
            active={terminalNext}
            length={8}
            onLockChange={setCamLocked}
            onSolved={() => setTerminalDone(true)}
          />
          {started && !chestGone && (
            <Chest
              opened={chestOpen}
              hitRef={chestHit}
              onRelease={() =>
                setLive((l) => [
                  ...l,
                  ...tubes.filter((t) => t.fromChest).map((t) => t.id),
                ])
              }
              onGone={() => setChestGone(true)}
            />
          )}
          {bursts.map((b) => (
            <Burst key={b.key} at={b.at} />
          ))}
        </Canvas>

        {started && !done && !camLocked && <ArrowCue dir={scrollHint} />}

        {started &&
          tubes
            .filter((t) => live.includes(t.id))
            .map((t) => {
              const locked = t.id !== nextRequiredId;
              return (
                <button
                  key={t.id}
                  type="button"
                  className={`tube-hit${locked ? " tube-hit--locked" : " tube-hit--active"}`}
                  aria-label={
                    locked
                      ? `Tube ${t.id + 1} — locked, click tubes in order`
                      : `Collect tube ${t.id + 1}`
                  }
                  aria-disabled={locked}
                  disabled={locked}
                  ref={(el) => {
                    hits.current[t.id] = el;
                  }}
                  onClick={(e) => collect(t, e)}
                >
                  {t.id + 1}
                </button>
              );
            })}

        {started && !chestOpen && !done && !camLocked && (
          <button
            type="button"
            className={`tube-hit chest-hit${chestNext ? " tube-hit--active" : " tube-hit--locked"}`}
            aria-label={
              chestNext
                ? "Open the chest"
                : "Chest — locked, collect the other tubes first"
            }
            aria-disabled={!chestNext}
            disabled={!chestNext}
            ref={chestHit}
            onClick={openChest}
          >
            CHEST
          </button>
        )}
      </div>

      <div className="hud">
        <div className="hud-bar">
          <span>
            TUBES {collected}/{TARGET}
          </span>
          <span ref={clock}>0:00.00</span>
        </div>
        {warn && <div className="warn">MOUSE DETECTED — KEYBOARD ONLY</div>}

        {refuelNext && !refuelAt && (
          <div className="refuel-cue">
            RIGHT-CLICK THE ASTRONAUT TO REFUEL HIS BOOSTERS
          </div>
        )}

        {refuelAt && (
          <RefuelPanel
            at={refuelAt}
            onDismiss={() => setRefuelAt(null)}
            onDone={() => {
              setFuelDone(true);
              setRefuelAt(null);
            }}
          />
        )}

        {started && !done && (
          <button
            type="button"
            className="pause-btn frame-btn"
            aria-label={paused ? "Resume" : "Pause"}
            onClick={togglePause}
          >
            {paused ? "▶" : "❚❚"}
          </button>
        )}

        {started && !done && (
          <p className="game-footer-hint">
            <kbd className="key-space" aria-label="space">
              space
            </kbd>{" "}
            to {paused ? "resume" : "pause"}
          </p>
        )}

        {paused && (
          <div className="pause-overlay">
            <div className="pause-title">PAUSED</div>
            <div className="pause-controls">
              <button
                type="button"
                className="frame-btn icon-btn"
                aria-label="Resume"
                onClick={togglePause}
              >
                ▶
              </button>
              <button
                type="button"
                className="frame-btn icon-btn"
                aria-label="Abort"
                onClick={abortGame}
              >
                ■
              </button>
            </div>
          </div>
        )}

        {!started && !intro && <StartScreen onStart={beginGame} />}

        {intro && (
          <IntroSequence onDone={finishIntro} onExit={() => setIntro(false)} />
        )}

        {done && (
          <div className="endcard">
            <div className="time">{fmt(finalTime!)}</div>
            <div className="endcard-sub">TO THE LEADERBOARD…</div>
          </div>
        )}
      </div>
      <MusicViz />
      {!started && !intro && <LeaderboardDock />}
    </>
  );
}

function fmt(ms: number) {
  const s = ms / 1000;
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}.${String(Math.floor((ms % 1000) / 10)).padStart(2, "0")}`;
}

useGLTF.preload(MODEL);
useGLTF.preload(CHEST);
useGLTF.preload(ARROW);
