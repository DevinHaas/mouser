import type { APIRoute } from 'astro'
import { auth } from '@/lib/auth'

export const prerender = false

// Real server-side 302 to GitHub instead of a client-side `window.location`
// assignment. Some browser extensions hook the SPA/Navigation API and turn the
// cross-origin redirect into an in-page fetch, which GitHub 404s — leaving the
// callback without a `state`. A genuine anchor -> 302 hop sidesteps that.
export const GET: APIRoute = async ({ request, url }) => {
  const next = url.searchParams.get('next') ?? '/'
  try {
    const signIn = new Request(`${url.origin}/api/auth/sign-in/social`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        origin: url.origin,
        cookie: request.headers.get('cookie') ?? '',
      },
      body: JSON.stringify({ provider: 'github', callbackURL: next }),
    })

    const res = await auth.handler(signIn)
    const data = (await res.clone().json().catch(() => null)) as { url?: string } | null
    if (!data?.url) {
      return new Response(`github sign-in failed: ${res.status} ${await res.text()}`, { status: 502 })
    }

    // Carry the state cookie(s) better-auth set, swap the 200+body for a 302.
    const headers = new Headers(res.headers)
    headers.set('location', data.url)
    headers.delete('content-type')
    headers.delete('content-length')
    return new Response(null, { status: 302, headers })
  } catch (err) {
    return new Response(`github sign-in error: ${err instanceof Error ? err.stack : String(err)}`, {
      status: 502,
    })
  }
}
