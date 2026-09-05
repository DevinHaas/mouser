import { useEffect, useRef } from 'react'

const SITE_KEY = import.meta.env.PUBLIC_TURNSTILE_SITE_KEY as string | undefined
const API = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

type Turnstile = {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string
  reset: (id: string) => void
  remove: (id: string) => void
}
declare global {
  interface Window {
    turnstile?: Turnstile
  }
}

/** Loads api.js once per page, however many gates mount. */
function loadApi(): Promise<void> {
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${API}"]`)
  if (existing) return existing.dataset.ready ? Promise.resolve() : ready(existing)
  const s = document.createElement('script')
  s.src = API
  s.async = true
  s.defer = true
  document.head.appendChild(s)
  return ready(s)
}

const ready = (s: HTMLScriptElement) =>
  new Promise<void>((res, rej) => {
    s.addEventListener('load', () => {
      s.dataset.ready = '1'
      res()
    })
    s.addEventListener('error', () => rej(new Error('turnstile api')))
  })

/**
 * Solves a Turnstile challenge in the background while the player plays, so
 * the token is already in hand when the run is submitted.
 *
 * `appearance: interaction-only` keeps the widget invisible for everyone the
 * challenge clears silently; a visitor who actually has to click something
 * gets a real, visible widget in the corner rather than a silent failure.
 *
 * No-ops when PUBLIC_TURNSTILE_SITE_KEY is unset — see turnstileOk().
 */
export function TurnstileGate({ onToken }: { onToken: (t: string | null) => void }) {
  const box = useRef<HTMLDivElement>(null)
  // Kept in a ref so remounting doesn't re-run the effect on every render of
  // the parent when `onToken` is an inline arrow.
  const cb = useRef(onToken)
  cb.current = onToken

  useEffect(() => {
    if (!SITE_KEY || !box.current) return
    let id: string | undefined
    let dead = false

    loadApi()
      .then(() => {
        if (dead || !box.current || !window.turnstile) return
        id = window.turnstile.render(box.current, {
          sitekey: SITE_KEY,
          appearance: 'interaction-only',
          callback: (t: string) => cb.current(t),
          'error-callback': () => cb.current(null),
          // Tokens die after ~5 minutes; a slow run would submit an expired
          // one. Drop it and solve again so the token is always fresh.
          'expired-callback': () => {
            cb.current(null)
            if (id) window.turnstile?.reset(id)
          },
        })
      })
      .catch(() => cb.current(null))

    return () => {
      dead = true
      if (id) window.turnstile?.remove(id)
    }
  }, [])

  return <div ref={box} className="turnstile-gate" />
}
