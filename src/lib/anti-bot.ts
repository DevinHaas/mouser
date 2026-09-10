/**
 * Bot screening for submitted runs, in two layers:
 *
 *  1. Pace — the client sends one timestamp per collected tube (ms since the
 *     run started). Anything that moves faster than hands can, or with the
 *     metronome regularity of a script, is not counted.
 *  2. Turnstile — a challenge solved in the background while the player plays;
 *     the token rides along with the run and is verified here.
 *
 * ponytail: the clock and the marks still come from the client, so this raises
 * the cost of faking a run, it does not make it impossible. The only real fix
 * is a server-authoritative game loop — build that when the board is worth it.
 */

import { captureServerError } from '@/lib/analytics.server'

/** One mark per tube. Must match TARGET in mouser-game.tsx. */
export const MARK_COUNT = 10

/** Below any measured simple-reaction time — a human cannot hop focus and
 *  activate a target twice inside this window, a script does it in one tick. */
export const MIN_GAP_MS = 120

/** Human gaps scatter by hundreds of ms. A run whose gaps vary by less than
 *  this is a loop with a sleep in it. */
export const MIN_SPREAD_MS = 15

/**
 * Returns a short reason string when the run cannot have come from human
 * hands, or null when it looks real.
 *
 * @param timeMs final clock the client reported
 * @param marks  ms-since-start of each collected tube, ascending
 */
export function paceFault(timeMs: number, marks: number[]): string | null {
  if (marks.length !== MARK_COUNT) return 'mark-count'
  if (marks.some((m) => !Number.isFinite(m) || m < 0)) return 'mark-junk'
  // Last tube ends the run, so the clock can't be behind it. 250ms of slack
  // covers the render tick between the collect and the timer read.
  if (marks[marks.length - 1] > timeMs + 250) return 'marks-past-clock'

  const gaps = marks.map((m, i) => m - (i ? marks[i - 1] : 0))
  if (gaps.some((g) => g < MIN_GAP_MS)) return 'gap-too-fast'

  const mean = gaps.reduce((a, b) => a + b, 0) / gaps.length
  const spread = Math.sqrt(
    gaps.reduce((a, g) => a + (g - mean) ** 2, 0) / gaps.length,
  )
  if (spread < MIN_SPREAD_MS) return 'gaps-too-uniform'

  return null
}

/**
 * Cloudflare Turnstile siteverify. Open when TURNSTILE_SECRET_KEY is unset so
 * dev and self-hosted runs aren't gated on a Cloudflare account; set the key
 * (and PUBLIC_TURNSTILE_SITE_KEY) to turn it on.
 */
export async function turnstileOk(
  token: string | null,
  ip?: string | null,
): Promise<boolean> {
  const secret = import.meta.env.TURNSTILE_SECRET_KEY
  if (!secret) return true
  if (!token) return false
  try {
    const r = await fetch(
      'https://challenges.cloudflare.com/turnstile/v0/siteverify',
      {
        method: 'POST',
        headers: { 'content-type': 'application/x-www-form-urlencoded' },
        signal: AbortSignal.timeout(10_000),
        body: new URLSearchParams({
          secret,
          response: token,
          ...(ip ? { remoteip: ip } : {}),
        }),
      },
    )
    if (!r.ok) return false
    const body = (await r.json()) as { success?: boolean }
    return body.success === true
  } catch (error) {
    captureServerError(error, { operation: 'turnstile_verify' })
    return false
  }
}
