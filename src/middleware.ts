import { defineMiddleware } from 'astro:middleware'
import { captureServerError } from '@/lib/analytics.server'

export const onRequest = defineMiddleware(async ({ request, url }, next) => {
  try {
    return await next()
  } catch (error) {
    captureServerError(error, {
      operation: 'request',
      method: request.method,
      path: url.pathname,
    })
    throw error
  }
})
