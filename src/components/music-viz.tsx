import { useEffect, useRef, useState } from "react";
import {
  attachMusic,
  getEffectsVolume,
  getMusicVolume,
  getNarratorVolume,
  musicBus,
  setEffectsVolume,
  setMusicVolume,
  setNarratorVolume,
} from "@/lib/sfx";

const BARS = 22;
// The top bins of a 128-point FFT are near-silent hiss — the music lives low.
const BINS = 44;

/** Bottom-left dock: neon spectrum bars plus the master music volume. */
export function MusicViz() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [vol, setVol] = useState(0.6);
  const muted = vol === 0;
  const last = useRef(0.6);

  const [sfxVol, setSfxVol] = useState(0.6);
  const sfxMuted = sfxVol === 0;
  const lastSfx = useRef(0.6);

  const [voVol, setVoVol] = useState(0.8);
  const voMuted = voVol === 0;
  const lastVo = useRef(0.8);

  useEffect(() => {
    setVol(getMusicVolume());
    last.current = getMusicVolume();
    setSfxVol(getEffectsVolume());
    lastSfx.current = getEffectsVolume();
    setVoVol(getNarratorVolume());
    lastVo.current = getNarratorVolume();
    document.querySelectorAll("audio").forEach(attachMusic);

    const { ac, analyser } = musicBus();
    const wake = () => ac.resume().catch(() => {});
    window.addEventListener("pointerdown", wake);
    window.addEventListener("keydown", wake);

    const el = canvas.current!;
    const c = el.getContext("2d")!;
    const dpr = Math.min(devicePixelRatio, 2);
    const w = el.clientWidth;
    const h = el.clientHeight;
    el.width = w * dpr;
    el.height = h * dpr;
    c.scale(dpr, dpr);

    const grad = c.createLinearGradient(0, h, 0, 0);
    grad.addColorStop(0, "#a01000");
    grad.addColorStop(0.45, "#ff4d14");
    grad.addColorStop(1, "#ffc06a");

    const freq = new Uint8Array(analyser.frequencyBinCount);
    const level = new Float32Array(BARS);
    const bw = w / BARS;
    let raf = 0;

    const draw = () => {
      raf = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(freq);
      c.clearRect(0, 0, w, h);
      c.fillStyle = grad;
      c.shadowColor = "rgba(255, 122, 40, 0.75)";
      c.shadowBlur = 8;

      for (let i = 0; i < BARS; i++) {
        // Log-ish bin spread: bass gets fewer bars than a linear map would give.
        const bin = Math.round(((i / (BARS - 1)) ** 1.7) * (BINS - 1));
        const target = (freq[bin] / 255) ** 1.4;
        // Fast attack, slow release — the classic VU feel.
        const k = target > level[i] ? 0.55 : 0.11;
        level[i] += (target - level[i]) * k;

        const bh = Math.max(2, level[i] * h);
        c.beginPath();
        c.roundRect(i * bw + 1, h - bh, bw - 2, bh, 1.5);
        c.fill();
      }
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointerdown", wake);
      window.removeEventListener("keydown", wake);
    };
  }, []);

  const apply = (v: number) => {
    setVol(v);
    setMusicVolume(v);
    if (v > 0) last.current = v;
  };

  const applySfx = (v: number) => {
    setSfxVol(v);
    setEffectsVolume(v);
    if (v > 0) lastSfx.current = v;
  };

  const applyVo = (v: number) => {
    setVoVol(v);
    setNarratorVolume(v);
    if (v > 0) lastVo.current = v;
  };

  return (
    <div className="music-dock">
      <canvas ref={canvas} className="music-bars" aria-hidden="true" />
      <div className="music-row">
        <button
          type="button"
          className="music-mute"
          aria-label={muted ? "unmute master volume" : "mute master volume"}
          title="master volume"
          onClick={() => apply(muted ? last.current || 0.6 : 0)}
        >
          {muted ? "✕" : "▶"}
        </button>
        <input
          className="music-slider"
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={vol}
          aria-label="master volume"
          onChange={(e) => apply(Number(e.target.value))}
          style={{ "--fill": `${vol * 100}%` } as React.CSSProperties}
        />
      </div>
      <div className="music-row">
        <button
          type="button"
          className="music-mute"
          aria-label={sfxMuted ? "unmute sound effects" : "mute sound effects"}
          title="sound effects volume"
          onClick={() => applySfx(sfxMuted ? lastSfx.current || 0.6 : 0)}
        >
          {sfxMuted ? "✕" : "FX"}
        </button>
        <input
          className="music-slider"
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={sfxVol}
          aria-label="sound effects volume"
          onChange={(e) => applySfx(Number(e.target.value))}
          style={{ "--fill": `${sfxVol * 100}%` } as React.CSSProperties}
        />
      </div>
      <div className="music-row">
        <button
          type="button"
          className="music-mute"
          aria-label={voMuted ? "unmute narrator voice" : "mute narrator voice"}
          title="narrator voice volume"
          onClick={() => applyVo(voMuted ? lastVo.current || 0.8 : 0)}
        >
          {voMuted ? "✕" : "VO"}
        </button>
        <input
          className="music-slider"
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={voVol}
          aria-label="narrator voice volume"
          onChange={(e) => applyVo(Number(e.target.value))}
          style={{ "--fill": `${voVol * 100}%` } as React.CSSProperties}
        />
      </div>
    </div>
  );
}
