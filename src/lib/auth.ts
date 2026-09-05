import { betterAuth } from 'better-auth'
import { drizzleAdapter } from 'better-auth/adapters/drizzle'
import { db } from './db'
import * as schema from './db/schema'

export const auth = betterAuth({
  secret: import.meta.env.BETTER_AUTH_SECRET,
  baseURL: import.meta.env.BETTER_AUTH_URL,
  database: drizzleAdapter(db, { provider: 'pg', schema }),
  emailAndPassword: { enabled: true },
  user: {
    additionalFields: {
      mouselessTool: { type: 'string', required: false, input: true },
    },
  },
  socialProviders: {
    github: {
      clientId: import.meta.env.GITHUB_CLIENT_ID ?? '',
      clientSecret: import.meta.env.GITHUB_CLIENT_SECRET ?? '',
    },
  },
})
