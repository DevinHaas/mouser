/** Privacy-first PostHog: localStorage only (no cookies -> no cookie banner),
 *  no interaction autocapture, no session recording, anonymous events.
 *
 *  Doubles as the store for "has this visitor seen the intro?" — a persisted
 *  super property (`intro_seen`) that rides along on every event and is read
 *  back synchronously from localStorage on the next load. localStorage key
 *  `mouser:intro-seen` stays as a fallback for when PostHog isn't configured. */
import posthog from "posthog-js";

const LEGACY_KEY = "mouser:intro-seen";
const KEY = import.meta.env.PUBLIC_POSTHOG_KEY;

let started = false;

export function initAnalytics() {
  if (started || typeof window === "undefined" || !KEY) return;
  started = true;
  posthog.init(KEY, {
    api_host: import.meta.env.PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com",
    persistence: "localStorage",
    autocapture: false,
    capture_exceptions: {
      capture_unhandled_errors: true,
      capture_unhandled_rejections: true,
      capture_console_errors: false,
    },
    capture_pageview: true,
    disable_session_recording: true,
    disable_surveys: true,
    cross_subdomain_cookie: false,
    respect_dnt: true,
    person_profiles: "identified_only",
  });
}

// Fire on import too — the game island may read intro state before the layout
// script runs. Idempotent.
initAnalytics();

export function hasSeenIntro(): boolean {
  try {
    // ponytail: dev never consults PostHog — intro-seen is localStorage only
    if (!import.meta.env.DEV && started && posthog.get_property("intro_seen"))
      return true;
    return localStorage.getItem(LEGACY_KEY) === "1";
  } catch {
    return false;
  }
}

export function shouldShowIntro(search: string, seen = hasSeenIntro()): boolean {
  const q = new URLSearchParams(search);
  return q.has("intro") || (!seen && !q.has("play") && !q.has("train"));
}

export function markIntroSeen() {
  try {
    localStorage.setItem(LEGACY_KEY, "1");
  } catch {
    // private mode — the super property below still holds for this session
  }
  if (!import.meta.env.DEV && started) {
    posthog.register({ intro_seen: true });
    posthog.capture("intro_completed");
  }
}

export function trackIntroReplay() {
  if (started) posthog.capture("intro_replayed");
}

type ErrorContext = {
  operation: string;
  [key: string]: string | number | boolean | null | undefined;
};

/** Keeps caught failures visible locally and in PostHog error tracking. */
export function captureError(error: unknown, context: ErrorContext) {
  const exception = error instanceof Error ? error : new Error(String(error));
  console.error(`[mouser] ${context.operation}`, exception, context);
  if (started) posthog.captureException(exception, context);
}
