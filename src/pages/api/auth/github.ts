import type { APIRoute } from 'astro'
import { auth } from '@/lib/auth'

export const prerender = false

// Real server-side 302 to GitHub instead of a client-side `window.location`
// assignment. Some browser extensions hook the SPA/Navigation API and turn the
// cross-origin redirect into an in-page fetch, which GitHub 404s — leaving the
// callback without a `state`. A genuine anchor -> 302 hop sidesteps that.
export const GET: APIRoute = async ({ request, url }) => {
  const next = url.searchParams.get('next') ?? '/'
  const signIn = new Request(new URL('/api/auth/sign-in/social', url), {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      // better-auth runs a CSRF origin check on POST; this call is same-origin.
      origin: url.origin,
      cookie: request.headers.get('cookie') ?? '',
    },
    body: JSON.stringify({ provider: 'github', callbackURL: next }),
  })

  const res = await auth.handler(signIn)
  const data = (await res.json().catch(() => null)) as { url?: string } | null
  if (!data?.url) return new Response('github sign-in unavailable', { status: 502 })

  const headers = new Headers({ location: data.url })
  for (const cookie of res.headers.getSetCookie()) headers.append('set-cookie', cookie)
  return new Response(null, { status: 302, headers })
}
