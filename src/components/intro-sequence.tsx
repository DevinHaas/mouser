import { useEffect, useRef, useState } from "react";
import { getNarratorVolume, playMusic, playOnce, playPageTurn } from "@/lib/sfx";
import { PageTurn } from "./page-turn";

/** Hand-drawn story panels shown once, between START and the first level.
 *  Images live in /public/intro and were generated to match the game models.
 *  Each panel has a narrator line (`vo`) recorded to /public/intro/vo-N.mp3. */
const PANELS = [
  {
    src: "/intro/panel-0.webp",
    vo: "/intro/vo-0.mp3",
    text: "Welcome to Mouser — the last human-operated space station left in the universe.",
  },
  {
    src: "/intro/panel-1.webp",
    vo: "/intro/vo-1.mp3",
    text: "This is Cage, one of the last people still in orbit.",
  },
  {
    src: "/intro/panel-2.webp",
    vo: "/intro/vo-2.mp3",
    text: "Far below, Earth's power grid has gone dark. Cage is going to bring it back online.",
  },
  {
    src: "/intro/panel-3.webp",
    vo: "/intro/vo-3.mp3",
    text: "The debris field around him is littered with energy tubes. He needs to recover them and carry them back to the station.",
  },
  {
    src: "/intro/panel-4.webp",
    vo: "/intro/vo-4.mp3",
    text: "There is no mouse up here. Jump from tube to tube with the keyboard alone, collecting them in the order they light up.",
  },
  {
    src: "/intro/panel-5.webp",
    vo: "/intro/vo-5.mp3",
    text: "The last three tubes are sealed inside a derelict supply cache. Clear the field first, then crack it open.",
  },
  {
    src: "/intro/panel-6.webp",
    vo: "/intro/vo-6.mp3",
    text: "Boot the terminal, refuel the boosters, and race the clock. Good luck, Cage.",
  },
  {
    src: "/intro/panel-7.webp",
    vo: "/intro/vo-7.mp3",
    text: "That's everything. Enjoy the game — and if you like it, feel free to support my work.",
    link: "https://ko-fi.com/devinhasler",
  },
] as const;

export function IntroSequence({
  onDone,
  onExit,
}: {
  onDone: () => void;
  onExit: () => void;
}) {
  const [i, setI] = useState(0);
  const [dir, setDir] = useState<1 | -1>(1);
  const last = i === PANELS.length - 1;

  useEffect(() => playMusic("/music/intro.mp3"), []);

  // One narrator element, retargeted per panel. Driven solely by its own slider
  // (see MusicViz) — the master and FX volumes don't touch it.
  const vo = useRef<HTMLAudioElement | null>(null);
  const voLevel = () => getNarratorVolume();
  useEffect(() => {
    const el = (vo.current ??= new Audio());
    el.src = PANELS[i].vo;
    el.volume = voLevel();
    el.currentTime = 0;
    el.play().catch(() => {});
    return () => el.pause();
  }, [i]);
  useEffect(() => {
    const onVol = () => {
      if (vo.current) vo.current.volume = voLevel();
    };
    window.addEventListener("mouser:vovol", onVol);
    return () => {
      window.removeEventListener("mouser:vovol", onVol);
      vo.current?.pause();
    };
  }, []);

  // Preload the next panel so advancing doesn't flash a blank frame.
  useEffect(() => {
    const next = PANELS[i + 1];
    if (next) new Image().src = next.src;
  }, [i]);

  const advance = () => {
    if (last) {
      playOnce("/music/primary_start.mp3");
      onDone();
    } else {
      setDir(1);
      playPageTurn();
      setI((n) => n + 1);
    }
  };
  const back = () => {
    if (i === 0) return;
    setDir(-1);
    playPageTurn();
    setI((n) => n - 1);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        advance();
      } else if (e.key === "ArrowLeft") {
        back();
      } else if (e.key === "Escape") {
        playOnce("/music/primary_start.mp3");
        onDone();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div
      className="intro-seq"
      role="dialog"
      aria-modal="true"
      aria-label="How to play"
    >
      <button type="button" className="back-link" onClick={onExit}>
        <span className="pixel-arrow" aria-hidden="true" />
        DASHBOARD
      </button>

      <figure className="intro-panel">
        <PageTurn
          src={PANELS[i].src}
          dir={dir}
          preload={PANELS.map((p) => p.src)}
        />
        <figcaption>
          {PANELS[i].text}
          {"link" in PANELS[i] && (
            <a
              href={(PANELS[i] as { link: string }).link}
              target="_blank"
              rel="noreferrer"
              className="intro-kofi"
            >
              ko-fi.com/devinhasler
            </a>
          )}
        </figcaption>
      </figure>

      <span className="intro-dots" aria-hidden="true">
        {PANELS.map((_, n) => (
          <span key={n} className={n === i ? "on" : ""} />
        ))}
      </span>

      <div className="intro-arrows">
        <button
          type="button"
          className="frame-btn"
          onClick={back}
          disabled={i === 0}
          aria-label="Previous panel"
        >
          ‹
        </button>
        <button
          type="button"
          className="frame-btn"
          onClick={advance}
          autoFocus
          aria-label={last ? "Start game" : "Next panel"}
        >
          {last ? "START" : "›"}
        </button>
      </div>

      <p className="intro-hint">
        <kbd>↵</kbd> next · <kbd>esc</kbd> skip
      </p>
    </div>
  );
}
