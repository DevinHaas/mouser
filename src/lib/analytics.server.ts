import { PostHog } from 'posthog-node'

type Properties = Record<string, string | number | boolean | null | undefined>

const key = import.meta.env.PUBLIC_POSTHOG_KEY
const posthog = key
  ? new PostHog(key, {
      host: import.meta.env.PUBLIC_POSTHOG_HOST ?? 'https://eu.i.posthog.com',
      flushAt: 1,
      enableExceptionAutocapture: true,
    })
  : null

export function captureServerError(error: unknown, properties: Properties) {
  console.error(`[mouser] ${properties.operation ?? 'server_error'}`, error, properties)
  posthog?.captureException(error, undefined, properties)
}
