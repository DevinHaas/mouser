import type { APIRoute } from 'astro'
import { auth } from '@/lib/auth'

export const prerender = false

// Real server-side 302 to GitHub instead of a client-side `window.location`
// assignment. Some browser extensions hook the SPA/Navigation API and turn the
// cross-origin redirect into an in-page fetch, which GitHub 404s — leaving the
// callback without a `state`. A genuine anchor -> 302 hop sidesteps that.
export const GET: APIRoute = async ({ request, url }) => {
  const next = url.searchParams.get('next') ?? '/'
  const res = await auth.api.signInSocial({
    body: { provider: 'github', callbackURL: next },
    headers: request.headers,
    asResponse: true,
  })

  const location = res.headers.get('location')
  if (!location) {
    return new Response(`github sign-in failed: ${res.status} ${await res.text()}`, { status: 502 })
  }

  // better-auth already put the state cookie on `res`; swap 200+body for a 302.
  const headers = new Headers(res.headers)
  headers.set('location', location)
  headers.delete('content-type')
  headers.delete('content-length')
  return new Response(null, { status: 302, headers })
}
