import { useGLTF } from "@react-three/drei";
import { useFrame, useThree, type ThreeElements } from "@react-three/fiber";
import { useCallback, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

const MODEL = "/screen_display.glb";

/** The flat quad added to the Tripo scan; see blender/screen_build/. */
const SCREEN_NODE = "Screen";

/* --------------------------------------------------------------------------
 * Axes in the shipped glb, same caveat as the astronaut: the exporter's Y-up
 * conversion decides these, not the Blender build.
 *
 *   model space   +X out of the screen, +Y up, +Z across the device
 *   Screen        a 0.549 x 0.292 quad at x = 0.289, UVs filling 0-1
 *
 * ScrollCamera pins camera.rotation to identity, so the view always looks
 * down -Z and the device needs a quarter turn to face it.
 *
 * The panel's normal is its local +X, NOT +Z: after the quarter turn, local
 * +Z points at world -X and a camera placed along it lands on the device's
 * side. `open` reads the axis off the geometry rather than naming one.
 * ------------------------------------------------------------------------ */
const FACE_CAMERA: [number, number, number] = [0, -Math.PI / 2, 0];

/** Panel aspect is 1.878:1; the canvas matches so text is never stretched. */
const CANVAS_W = 1024;
const CANVAS_H = 545;
const PANEL_W = 0.5489;
const PANEL_H = 0.2922;

const ZOOM_IN = 0.85;
const ZOOM_OUT = 0.65;
const FILL = 0.82;

/**
 * The submit target, in canvas pixels. This is the whole point of the
 * interaction: the run is a mouse-skill drill, so the entry is committed by
 * clicking a target on the panel, never by the keyboard.
 */
export const SUBMIT_BUTTON = { x: 654, y: 396, w: 330, h: 108 };

const BG = "#05080b";
const AMBER = "#ffb347";
const AMBER_DIM = "#8a5a1e";
const CYAN = "#5ad7d0";
const RED = "#ff6b5a";
const GREEN = "#7ddc7d";
const GRID = "rgba(255,150,60,0.06)";

/** Unambiguous alphabet: no O/0, I/1, S/5 to argue about while retyping. */
const ALPHABET = "ABCDEFGHJKLMNPQRTUVWXYZ2346789";

export function makePassword(len = 8) {
  let out = "";
  for (let i = 0; i < len; i++) {
    out += ALPHABET[Math.floor(Math.random() * ALPHABET.length)];
  }
  return out;
}

export type TerminalView = {
  password: string;
  input: string;
  typing: boolean;
  message: string;
  tone: "info" | "bad" | "good";
  hover: boolean;
};

/** Is this UV over the submit target? Pure, so it can be tested directly. */
export function hitSubmit(u: number, v: number) {
  const px = u * CANVAS_W;
  const py = v * CANVAS_H;
  return (
    px >= SUBMIT_BUTTON.x &&
    px <= SUBMIT_BUTTON.x + SUBMIT_BUTTON.w &&
    py >= SUBMIT_BUTTON.y &&
    py <= SUBMIT_BUTTON.y + SUBMIT_BUTTON.h
  );
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/**
 * Paints the terminal. Pure: state in, pixels out, no renderer and no React,
 * so it can be exercised against an OffscreenCanvas in a test.
 */
export function drawTerminal(
  ctx: CanvasRenderingContext2D,
  view: TerminalView,
  t = 0,
) {
  const { width: w, height: h } = ctx.canvas;

  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = GRID;
  ctx.lineWidth = 1;
  for (let x = 0; x <= w; x += 32) {
    ctx.beginPath();
    ctx.moveTo(x + 0.5, 0);
    ctx.lineTo(x + 0.5, h);
    ctx.stroke();
  }
  for (let y = 0; y <= h; y += 32) {
    ctx.beginPath();
    ctx.moveTo(0, y + 0.5);
    ctx.lineTo(w, y + 0.5);
    ctx.stroke();
  }

  ctx.textBaseline = "top";

  // the thing to copy
  ctx.font = '26px "SFMono-Regular", Menlo, Consolas, monospace';
  ctx.fillStyle = CYAN;
  ctx.fillText("ENTER THIS PASSWORD", 40, 30);

  ctx.font = 'bold 62px "SFMono-Regular", Menlo, Consolas, monospace';
  ctx.fillStyle = AMBER;
  let x = 40;
  for (const ch of view.password) {
    ctx.fillText(ch, x, 68);
    x += 46; // hand-spaced: letterSpacing is not universally supported
  }

  ctx.strokeStyle = "rgba(255,179,71,0.25)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(40, 156);
  ctx.lineTo(w - 40, 156);
  ctx.stroke();

  // what they have typed
  ctx.font = '40px "SFMono-Regular", Menlo, Consolas, monospace';
  const caret = view.typing && Math.floor(t * 1.8) % 2 === 0 ? "\u2588" : "";
  ctx.fillStyle = view.typing ? AMBER : AMBER_DIM;
  ctx.fillText("> " + view.input + caret, 40, 196);

  if (view.message) {
    ctx.font = '26px "SFMono-Regular", Menlo, Consolas, monospace';
    ctx.fillStyle =
      view.tone === "bad" ? RED : view.tone === "good" ? GREEN : CYAN;
    ctx.fillText(view.message, 40, 268);
  }

  // the submit target
  const b = SUBMIT_BUTTON;
  const ready = view.input.length > 0;
  const lit = view.hover && ready;
  roundRect(ctx, b.x, b.y, b.w, b.h, 10);
  ctx.fillStyle = lit ? AMBER : ready ? "rgba(255,179,71,0.14)" : "rgba(255,179,71,0.05)";
  ctx.fill();
  ctx.strokeStyle = ready ? AMBER : AMBER_DIM;
  ctx.lineWidth = lit ? 4 : 2;
  ctx.stroke();

  ctx.font = 'bold 38px "SFMono-Regular", Menlo, Consolas, monospace';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = lit ? "#1a0f04" : ready ? AMBER : AMBER_DIM;
  ctx.fillText("SUBMIT", b.x + b.w / 2, b.y + b.h / 2 + 2);
  ctx.textAlign = "left";
  ctx.textBaseline = "top";

  ctx.fillStyle = "rgba(0,0,0,0.16)";
  for (let sy = 0; sy < h; sy += 4) ctx.fillRect(0, sy, w, 2);
}

export function framePanel(
  centre: THREE.Vector3,
  normal: THREE.Vector3,
  panelW: number,
  panelH: number,
  fov: number,
  aspect: number,
  fill = FILL,
) {
  const vfov = THREE.MathUtils.degToRad(fov);
  const byHeight = panelH / 2 / Math.tan(vfov / 2);
  const byWidth = panelW / 2 / (Math.tan(vfov / 2) * aspect);
  return centre.clone().addScaledVector(normal, Math.max(byHeight, byWidth) / fill);
}

export type Phase = "idle" | "zoomIn" | "typing" | "zoomOut";

export type TerminalScreenProps = Omit<ThreeElements["group"], "onSubmit"> & {
  size?: number;
  /** Pulses and accepts clicks — this is the player's current objective. */
  active?: boolean;
  /** Characters in the generated password. */
  length?: number;
  onLockChange?: (locked: boolean) => void;
  onSolved?: (value: string) => void;
  onClosed?: () => void;
};

export function TerminalScreen({
  size = 3.4,
  active = false,
  length = 8,
  onLockChange,
  onSolved,
  onClosed,
  ...props
}: TerminalScreenProps) {
  const { scene } = useGLTF(MODEL);
  const model = useMemo(() => scene.clone(true), [scene]);
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const viewport = useThree((s) => s.size);

  const body = useRef<THREE.Group>(null);
  const panel = useRef<THREE.Mesh | null>(null);
  const glow = useRef<THREE.PointLight>(null);
  const input = useRef<HTMLInputElement | null>(null);

  const phase = useRef<Phase>("idle");
  const view = useRef<TerminalView>({
    password: "",
    input: "",
    typing: false,
    message: "",
    tone: "info",
    hover: false,
  });

  const tween = useRef({
    from: new THREE.Vector3(),
    to: new THREE.Vector3(),
    fromQ: new THREE.Quaternion(),
    toQ: new THREE.Quaternion(),
    t: 0,
    dur: ZOOM_IN,
    run: false,
  });
  const home = useRef<{ p: THREE.Vector3; q: THREE.Quaternion } | null>(null);

  // Held in a ref, not useMemo: the texture is mutated every repaint
  // (`needsUpdate`), and react-hooks/immutability rightly objects to writing
  // to a memoised value after render.
  const gfx = useRef<{ ctx: CanvasRenderingContext2D; texture: THREE.CanvasTexture }>(null);
  if (gfx.current === null) {
    const canvas = document.createElement("canvas");
    canvas.width = CANVAS_W;
    canvas.height = CANVAS_H;
    const tex = new THREE.CanvasTexture(canvas);
    // GLTFLoader uses flipY=false for glTF UVs; a hand-made texture defaults
    // to true and would render the terminal upside down.
    tex.flipY = false;
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.minFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    tex.anisotropy = 8;
    gfx.current = { ctx: canvas.getContext("2d")!, texture: tex };
  }
  const { ctx } = gfx.current;

  useEffect(() => {
    const tex = gfx.current!.texture;
    let found: THREE.Mesh | undefined;
    model.traverse((o: THREE.Object3D) => {
      if ((o as THREE.Mesh).isMesh && o.name === SCREEN_NODE) found = o as THREE.Mesh;
    });
    if (!found) {
      console.warn(`[TerminalScreen] no mesh named "${SCREEN_NODE}" in ${MODEL}`);
      return;
    }
    const mat = (found.material as THREE.MeshStandardMaterial).clone();
    found.material = mat;
    mat.map = tex;
    mat.emissiveMap = tex;
    mat.emissive = new THREE.Color(0xffffff);
    mat.emissiveIntensity = 1;
    mat.toneMapped = false;
    mat.fog = false;
    mat.needsUpdate = true;
    panel.current = found;
    return () => {
      mat.dispose();
      panel.current = null;
    };
  }, [model]);

  useEffect(() => () => void gfx.current?.texture.dispose(), []);

  // A real input, off-screen. It exists for backspace, selection and the
  // mobile keyboard — it deliberately cannot commit the entry.
  useEffect(() => {
    const el = document.createElement("input");
    el.type = "text";
    el.autocapitalize = "characters";
    el.autocomplete = "off";
    el.spellcheck = false;
    el.setAttribute("aria-label", "Retype the password shown on the terminal");
    el.style.cssText =
      "position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;border:0;padding:0;z-index:-1";
    document.body.appendChild(el);
    input.current = el;
    return () => {
      el.remove();
      input.current = null;
    };
  }, []);

  const startTween = useCallback(
    (to: THREE.Vector3, toQ: THREE.Quaternion, dur: number) => {
      const tw = tween.current;
      tw.from.copy(camera.position);
      tw.fromQ.copy(camera.quaternion);
      tw.to.copy(to);
      tw.toQ.copy(toQ);
      tw.t = 0;
      tw.dur = dur;
      tw.run = true;
    },
    [camera],
  );

  const close = useCallback(() => {
    if (!home.current) return;
    phase.current = "zoomOut";
    view.current.typing = false;
    view.current.hover = false;
    input.current?.blur();
    startTween(home.current.p, home.current.q, ZOOM_OUT);
  }, [startTween]);

  const open = useCallback(() => {
    const p = panel.current;
    if (!p || phase.current !== "idle" || !active) return;

    p.updateWorldMatrix(true, false);
    if (!p.geometry.boundingBox) p.geometry.computeBoundingBox();
    const bb = p.geometry.boundingBox!;
    const centre = bb.getCenter(new THREE.Vector3()).applyMatrix4(p.matrixWorld);

    // Derive the facing axis from the geometry, do NOT assume one. The quad is
    // flat, so its thinnest local axis IS its normal — and that axis is +X
    // here, not +Z.
    const ext = bb.getSize(new THREE.Vector3());
    const local = new THREE.Vector3(1, 0, 0);
    if (ext.y <= ext.x && ext.y <= ext.z) local.set(0, 1, 0);
    else if (ext.z <= ext.x && ext.z <= ext.y) local.set(0, 0, 1);

    const normal = local
      .applyMatrix3(new THREE.Matrix3().getNormalMatrix(p.matrixWorld))
      .normalize();
    if (normal.dot(camera.position.clone().sub(centre)) < 0) normal.negate();

    const to = framePanel(
      centre,
      normal,
      PANEL_W * size,
      PANEL_H * size,
      camera.fov,
      viewport.width / viewport.height,
    );
    const look = new THREE.Matrix4().lookAt(to, centre, new THREE.Vector3(0, 1, 0));

    home.current = { p: camera.position.clone(), q: camera.quaternion.clone() };
    view.current = {
      password: makePassword(length),
      input: "",
      typing: false,
      message: "",
      tone: "info",
      hover: false,
    };
    phase.current = "zoomIn";
    onLockChange?.(true);
    startTween(to, new THREE.Quaternion().setFromRotationMatrix(look), ZOOM_IN);
  }, [active, camera, length, onLockChange, size, startTween, viewport]);

  const submit = useCallback(() => {
    if (phase.current !== "typing") return;
    const v = view.current;
    const value = v.input.trim();
    if (!value) {
      v.message = "NOTHING ENTERED";
      v.tone = "bad";
      return;
    }
    if (value.toUpperCase() !== v.password.toUpperCase()) {
      v.message = "INCORRECT \u2014 TRY AGAIN";
      v.tone = "bad";
      v.input = "";
      if (input.current) input.current.value = "";
      return;
    }
    v.message = "ACCEPTED";
    v.tone = "good";
    v.typing = false;
    onSolved?.(value);
    close();
  }, [close, onSolved]);

  useEffect(() => {
    const el = input.current;
    if (!el) return;
    const onInput = () => {
      if (phase.current !== "typing") return;
      view.current.input = el.value.slice(0, 24);
      view.current.message = "";
    };
    const onKey = (e: KeyboardEvent) => {
      if (phase.current !== "typing") return;
      if (e.key === "Enter") {
        // The drill is mouse work: the entry is committed by clicking the
        // target on the panel, so Enter is swallowed and says so.
        e.preventDefault();
        view.current.message = "PRESS THE SUBMIT BUTTON";
        view.current.tone = "info";
      } else if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    };
    el.addEventListener("input", onInput);
    el.addEventListener("keydown", onKey);
    return () => {
      el.removeEventListener("input", onInput);
      el.removeEventListener("keydown", onKey);
    };
  }, [close]);

  useEffect(() => {
    return () => {
      if (phase.current !== "idle") onLockChange?.(false);
      document.body.style.cursor = "";
    };
  }, [onLockChange]);

  const drawn = useRef("");
  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    const tw = tween.current;

    if (tw.run) {
      tw.t = Math.min(1, tw.t + Math.min(dt, 0.1) / tw.dur);
      const k = tw.t < 0.5 ? 4 * tw.t ** 3 : 1 - Math.pow(-2 * tw.t + 2, 3) / 2;
      camera.position.lerpVectors(tw.from, tw.to, k);
      camera.quaternion.slerpQuaternions(tw.fromQ, tw.toQ, k);
      if (tw.t >= 1) {
        tw.run = false;
        if (phase.current === "zoomIn") {
          phase.current = "typing";
          view.current.typing = true;
          input.current?.focus({ preventScroll: true });
        } else if (phase.current === "zoomOut") {
          phase.current = "idle";
          home.current = null;
          document.body.style.cursor = "";
          onLockChange?.(false);
          onClosed?.();
        }
      }
    }

    const g = body.current;
    if (g) {
      const pulse = active && phase.current === "idle" ? 1 + Math.sin(t * 3) * 0.05 : 1;
      g.scale.setScalar(size * pulse);
    }
    if (glow.current) {
      if (phase.current !== "idle") {
        // The cue exists to make the device findable from across the field.
        // Once the player has committed to it the camera ends up on the far
        // side of this light, so it burns a hotspot across the middle of the
        // glass and washes out the very text they are here to read. Snap it
        // out rather than easing — by the time the zoom lands it must be gone.
        glow.current.intensity = 0;
      } else {
        const want = active ? 14 + Math.sin(t * 3) * 7 : 0;
        glow.current.intensity += (want - glow.current.intensity) * 0.12;
      }
    }
    if (panel.current) {
      const mat = panel.current.material as THREE.MeshStandardMaterial;
      // no boost while reading: the panel is its own light source up close
      const want = phase.current !== "idle" ? 1.0 : active ? 1.05 : 0.75;
      mat.emissiveIntensity += (want - mat.emissiveIntensity) * 0.12;
    }

    const v = view.current;
    const key = `${v.password}|${v.input}|${v.message}|${v.hover}|${
      v.typing ? Math.floor(t * 1.8) : "s"
    }`;
    if (key !== drawn.current) {
      drawn.current = key;
      drawTerminal(ctx, v, t);
      gfx.current!.texture.needsUpdate = true;
    }
  });

  /** UV of a hit on the panel itself, or null for the casing. */
  const panelUv = (e: { object: THREE.Object3D; uv?: THREE.Vector2 }) =>
    e.object.name === SCREEN_NODE && e.uv ? e.uv : null;

  return (
    <group {...props}>
      <group
        ref={body}
        scale={size}
        rotation={FACE_CAMERA}
        onClick={(e) => {
          e.stopPropagation();
          if (phase.current === "idle") {
            open();
            return;
          }
          if (phase.current !== "typing") return;
          const uv = panelUv(e);
          if (uv && hitSubmit(uv.x, uv.y)) submit();
          // clicking anywhere else on the glass just restores focus
          else input.current?.focus({ preventScroll: true });
        }}
        onPointerMove={(e) => {
          if (phase.current !== "typing") return;
          const uv = panelUv(e);
          const over = !!uv && hitSubmit(uv.x, uv.y);
          if (over !== view.current.hover) view.current.hover = over;
          document.body.style.cursor = over ? "pointer" : "";
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          if (phase.current === "idle" && active) document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          view.current.hover = false;
          document.body.style.cursor = "";
        }}
      >
        <primitive object={model} />
      </group>
      <pointLight
        ref={glow}
        color="#ff8c1e"
        decay={2}
        distance={3.2 * size}
        intensity={0}
        position={[0, 0, 0.45 * size]}
      />
    </group>
  );
}
