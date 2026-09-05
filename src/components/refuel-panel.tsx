import { useEffect, useRef, useState } from "react";
import { playOnce } from "@/lib/sfx";

/** Clicks needed to fill the tank. */
const CLICKS = 10;

const W = 190;
const H = 210;

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number;
  ttl: number;
  r: number;
  seed: number;
};

/**
 * Particle fire on a 2D canvas.
 *
 * A flame reads as real from three things, none of which a CSS gradient can
 * do: parcels of gas that rise and *accelerate* (buoyancy, not constant
 * speed), a horizontal wander that grows with height (turbulence — laminar at
 * the nozzle, chaotic at the tip), and a colour that walks down the
 * black-body ramp as each parcel cools. Everything is drawn additively so
 * overlapping parcels blow out to white in the core exactly like real
 * emission does.
 */
function makeFlame(ctx: CanvasRenderingContext2D) {
  const parts: Particle[] = [];
  let t = 0;

  /** Box-Muller — a normal spread packs the parcels into a core with a soft
   *  edge; a flat random() gives a flame with visible straight sides. */
  const gauss = () =>
    Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(2 * Math.PI * Math.random());

  const spawn = (heat: number) => {
    const n = Math.round(3 + heat * 5);
    for (let i = 0; i < n; i++) {
      parts.push({
        x: W / 2 + gauss() * 9,
        y: H - 26 + Math.random() * 6,
        vx: gauss() * 8,
        vy: -(30 + Math.random() * 30) * (0.8 + heat * 0.5),
        age: 0,
        ttl: 0.7 + Math.random() * 0.5,
        r: 9 + Math.random() * 9,
        seed: Math.random() * 100,
      });
    }
  };

  /** Black-body walk: white-hot core → yellow → orange → deep red ember. */
  const color = (k: number) => {
    const r = 255;
    const g = Math.round(250 - 210 * Math.min(1, k * 1.15));
    const b = Math.round(210 * Math.max(0, 1 - k * 2.6));
    return `${r},${g},${b}`;
  };

  return (dt: number, heat: number) => {
    t += dt;
    spawn(heat);

    // Trail rather than a hard clear: each frame keeps a dimmed copy of the
    // last, which is what gives the plume its continuous body.
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "rgba(4,4,10,0.34)";
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "lighter";

    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i];
      p.age += dt;
      const k = p.age / p.ttl;
      if (k >= 1) {
        parts.splice(i, 1);
        continue;
      }
      // turbulence grows as the parcel climbs away from the nozzle
      const rise = (H - p.y) / H;
      p.vx += Math.sin(p.y * 0.06 + t * 4 + p.seed) * 130 * rise * dt;
      p.vx *= 1 - 1.6 * dt; // drag
      p.vy -= (110 + 90 * heat) * dt; // buoyancy
      p.x += p.vx * dt;
      p.y += p.vy * dt;

      const radius = p.r * (0.55 + k * 1.5);
      const alpha = (1 - k) ** 1.7 * 0.5;
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius);
      g.addColorStop(0, `rgba(${color(k)},${alpha})`);
      g.addColorStop(1, `rgba(${color(k)},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
      ctx.fill();
    }

    // Nozzle: the hot blue root every real flame has where the gas is
    // burning fastest, plus the glow it throws on the metal.
    const root = ctx.createRadialGradient(W / 2, H - 24, 0, W / 2, H - 24, 26 + heat * 12);
    root.addColorStop(0, "rgba(220,240,255,0.75)");
    root.addColorStop(0.35, "rgba(90,160,255,0.32)");
    root.addColorStop(1, "rgba(90,160,255,0)");
    ctx.fillStyle = root;
    ctx.fillRect(0, H - 80, W, 80);
  };
}

/** Animated flame that flares on every click. */
function Flame({ onClick, done }: { onClick: () => void; done: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const heat = useRef(0);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    el.width = W * dpr;
    el.height = H * dpr;
    const ctx = el.getContext("2d")!;
    ctx.scale(dpr, dpr);
    const draw = makeFlame(ctx);
    let last = performance.now();
    let raf = 0;
    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      heat.current = Math.max(0, heat.current - dt * 2.2);
      draw(dt, heat.current);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <button
      type="button"
      className="refuel-flame"
      aria-label="Pump fuel into the boosters"
      disabled={done}
      onClick={() => {
        heat.current = Math.min(1.6, heat.current + 0.9);
        onClick();
      }}
    >
      <canvas ref={canvas} style={{ width: W, height: H }} />
    </button>
  );
}

export type RefuelPanelProps = {
  /** Viewport point to hang the panel over — where the astronaut was clicked. */
  at: { x: number; y: number };
  onDone: () => void;
  onDismiss: () => void;
};

/**
 * The refuel step: right-click the astronaut, pump his boosters back up.
 *
 * Full tank holds for a beat before it reports done, so the bar is actually
 * seen filled rather than vanishing on the last click.
 */
export function RefuelPanel({ at, onDone, onDismiss }: RefuelPanelProps) {
  const [clicks, setClicks] = useState(0);
  const full = clicks >= CLICKS;
  const fuel = Math.min(1, clicks / CLICKS);

  useEffect(() => {
    if (!full) return;
    const id = setTimeout(onDone, 900);
    return () => clearTimeout(id);
  }, [full, onDone]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDismiss]);

  // Keep the panel wholly on screen even when he drifts near an edge.
  const left = Math.min(Math.max(at.x, W / 2 + 20), window.innerWidth - W / 2 - 20);
  const top = Math.min(Math.max(at.y, H / 2 + 60), window.innerHeight - H / 2 - 90);

  return (
    <div className="refuel-panel" style={{ left, top }} role="dialog" aria-label="Booster refuel">
      <div className="refuel-title">BOOSTER REFUEL</div>
      <p className="refuel-hint">Click the flame repeatedly to fill the tank.</p>
      <Flame
        done={full}
        onClick={() => {
          playOnce("/music/charging1.mp3", 0.5);
          setClicks((c) => Math.min(CLICKS, c + 1));
        }}
      />
      <div className="refuel-bar">
        <div className="refuel-fill" style={{ transform: `scaleX(${fuel})` }} />
      </div>
      <div className={`refuel-read${full ? " refuel-read--full" : ""}`}>
        {full ? "TANK FULL" : `FUEL ${Math.round(fuel * 100)}%`}
      </div>
    </div>
  );
}
