import { defineConfig } from 'astro/config'
import react from '@astrojs/react'
import node from '@astrojs/node'
import posthog from '@posthog/rollup-plugin'

const sourceMaps = process.env.POSTHOG_API_KEY && process.env.POSTHOG_PROJECT_ID
  ? [posthog({
      personalApiKey: process.env.POSTHOG_API_KEY,
      projectId: process.env.POSTHOG_PROJECT_ID,
      host: process.env.POSTHOG_HOST ?? 'https://eu.i.posthog.com',
    })]
  : []

export default defineConfig({
  site: 'https://mouser.bleat.ch',
  integrations: [react()],
  output: 'server',
  adapter: node({ mode: 'standalone' }),
  vite: { plugins: sourceMaps },
})
