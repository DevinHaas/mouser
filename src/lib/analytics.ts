/** PostHog error tracking only: no product events, flags, recording, or persistence. */
import posthog from "posthog-js";

const LEGACY_KEY = "mouser:intro-seen";
const KEY = import.meta.env.PUBLIC_POSTHOG_KEY;

let started = false;

export function initAnalytics() {
  if (started || typeof window === "undefined" || !KEY) return;
  try {
    posthog.init(KEY, {
      api_host: import.meta.env.PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com",
      disable_persistence: true,
      autocapture: false,
      capture_exceptions: {
        capture_unhandled_errors: true,
        capture_unhandled_rejections: true,
        capture_console_errors: false,
      },
      capture_pageview: false,
      advanced_disable_flags: true,
      disable_session_recording: true,
      disable_surveys: true,
      cross_subdomain_cookie: false,
      person_profiles: "identified_only",
    });
    started = true;
  } catch (error) {
    console.error("[mouser] analytics_init", error);
  }
}

// Fire on import too — the game island may read intro state before the layout
// script runs. Idempotent.
initAnalytics();

export function hasSeenIntro(): boolean {
  try {
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
    // private mode
  }
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
