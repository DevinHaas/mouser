/** Small audio helpers for UI cues. All failures are silent — audio is garnish. */

/** A looping cue that fades up from silence on enter and back down on leave. */
export function makeHoverSfx(src: string, peak = 1, ms = 700) {
  const audio = new Audio(src);
  audio.loop = true;
  audio.volume = 0;
  let raf = 0;

  const ramp = (to: number) => {
    cancelAnimationFrame(raf);
    const from = audio.volume;
    const t0 = performance.now();
    const step = () => {
      const k = Math.min(1, (performance.now() - t0) / ms);
      audio.volume = from + (to - from) * k;
      if (k < 1) raf = requestAnimationFrame(step);
      else if (to === 0) audio.pause();
    };
    raf = requestAnimationFrame(step);
  };

  return {
    enter: () => {
      // A blocked autoplay (the button is autoFocus'd, so onFocus fires before
      // any gesture) leaves the ramp finished on a paused element — restart it.
      if (audio.paused) {
        cancelAnimationFrame(raf);
        audio.currentTime = 0;
        audio.volume = 0;
      }
      audio.play().catch(() => {});
      ramp(peak * getEffectsVolume());
    },
    leave: () => ramp(0),
    stop: () => {
      cancelAnimationFrame(raf);
      audio.pause();
    },
  };
}

/** One-shot cue (explosions, chest, etc). Scaled by both the master and effects sliders. */
export function playOnce(src: string, volume = 1) {
  const audio = new Audio(src);
  audio.volume = volume * getMusicVolume() * getEffectsVolume();
  audio.play().catch(() => {});
}

/* -------------------------------------------------------------------------- */

/** Hard clip — a blown-out transmitter, driven well past the soft knee. */
const CLIP_CURVE = new Float32Array(1024).map((_, i) => {
  const x = (i / 1023) * 2 - 1;
  return Math.tanh(x * 8) / Math.tanh(8);
});

let ctx: AudioContext | undefined;
const buffers = new Map<string, Promise<AudioBuffer>>();

/**
 * Plays a clip as if it came over a helmet radio: band-limited to a voice
 * channel, pushed into clipping, with the mid presence peak a comms speaker has.
 */
export async function playRadio(src: string, volume = 1) {
  const ac = (ctx ??= new AudioContext());
  await ac.resume();

  let pending = buffers.get(src);
  if (!pending) {
    pending = fetch(src)
      .then((r) => r.arrayBuffer())
      .then((b) => ac.decodeAudioData(b));
    buffers.set(src, pending);
  }
  const buffer = await pending.catch(() => undefined);
  if (!buffer) return;

  const source = new AudioBufferSourceNode(ac, { buffer, playbackRate: 1.12 });

  // A slow ring-mod buzz — the growl under a barely-locked signal.
  const ringMod = new GainNode(ac, { gain: 0 });
  const ringLfo = new OscillatorNode(ac, { type: "sine", frequency: 45 });
  const ringDepth = new GainNode(ac, { gain: 0.6 });
  ringLfo.connect(ringDepth).connect(ringMod.gain);
  ringLfo.start();

  const chain = [
    new BiquadFilterNode(ac, { type: "highpass", frequency: 350 }),
    new BiquadFilterNode(ac, { type: "lowpass", frequency: 1500 }),
    new BiquadFilterNode(ac, { type: "peaking", frequency: 900, Q: 2.2, gain: 14 }),
    ringMod,
    new WaveShaperNode(ac, { curve: CLIP_CURVE, oversample: "4x" }),
    new BiquadFilterNode(ac, { type: "lowpass", frequency: 2200 }),
    new GainNode(ac, { gain: volume * getMusicVolume() * getEffectsVolume() }),
  ];
  chain.reduce<AudioNode>((prev, node) => prev.connect(node), source).connect(ac.destination);
  source.start();
  source.addEventListener("ended", () => ringLfo.stop());
}

/* -------------------------------------------------------------------------- */

/**
 * Music bus. Every looping track routes through one gain (the volume slider)
 * and one analyser (the bars), so both control all music with no bookkeeping.
 */
const VOL_KEY = "mouser:volume";
let bus: { ac: AudioContext; gain: GainNode; analyser: AnalyserNode } | undefined;

export function getMusicVolume() {
  const raw = localStorage.getItem(VOL_KEY);
  if (raw === null) return 0.6;
  const v = Number(raw);
  return Number.isFinite(v) ? Math.min(Math.max(v, 0), 1) : 0.6;
}

export function setMusicVolume(v: number) {
  localStorage.setItem(VOL_KEY, String(v));
  musicBus().gain.gain.value = v;
}

/** Separate multiplier for one-shot/loop cues (explosions, chest, hover, radio
 *  voice) — stacks on top of the master slider above rather than replacing it. */
const SFX_VOL_KEY = "mouser:sfxVolume";

export function getEffectsVolume() {
  const raw = localStorage.getItem(SFX_VOL_KEY);
  if (raw === null) return 0.6;
  const v = Number(raw);
  return Number.isFinite(v) ? Math.min(Math.max(v, 0), 1) : 0.6;
}

export function setEffectsVolume(v: number) {
  localStorage.setItem(SFX_VOL_KEY, String(v));
}

export function musicBus() {
  if (!bus) {
    const ac = (ctx ??= new AudioContext());
    const gain = new GainNode(ac, { gain: getMusicVolume() });
    const analyser = new AnalyserNode(ac, {
      fftSize: 128,
      smoothingTimeConstant: 0.75,
    });
    gain.connect(analyser).connect(ac.destination);
    bus = { ac, gain, analyser };
  }
  return bus;
}

// A media element can only ever have one MediaElementAudioSourceNode.
const routed = new WeakSet<HTMLMediaElement>();

/** Routes a track into the bus so the slider and the bars see it. */
export function attachMusic(el: HTMLMediaElement) {
  const { ac, gain } = musicBus();
  if (!routed.has(el)) {
    routed.add(el);
    new MediaElementAudioSourceNode(ac, { mediaElement: el }).connect(gain);
  }
  ac.resume().catch(() => {});
}

/**
 * Starts a looping track on the bus and returns its stop.
 *
 * The stop has to be a hard one: autoplay can leave `play()` blocked and
 * pending, and a bare `pause()` on that element does not stick — the track
 * comes back the moment a gesture wakes the context, which is exactly the
 * click that starts the game. Dropping the source ends it for good.
 */
export function playMusic(src: string) {
  const audio = new Audio(src);
  audio.loop = true;
  attachMusic(audio);
  audio.play().catch(() => {});

  return () => {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
  };
}
