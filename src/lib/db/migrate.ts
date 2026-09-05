import { drizzle } from 'drizzle-orm/neon-http'
import { neon } from '@neondatabase/serverless'
import { migrate } from 'drizzle-orm/neon-http/migrator'

// Standalone migration runner — invoked by `bun run db:migrate` before the server boots.
const url = process.env.DATABASE_URL
if (!url) {
  console.error('DATABASE_URL is not set — cannot run migrations')
  process.exit(1)
}

await migrate(drizzle(neon(url)), { migrationsFolder: './drizzle' })
console.log('migrations applied')
