import { db } from '@/lib/db'
import { runs, user } from '@/lib/db/schema'
import { asc, eq, sql } from 'drizzle-orm'

/**
 * The cheat-free board with one row per user — their fastest run — ordered
 * fastest-first. `DISTINCT ON (userId)` picks the best run; the outer query
 * re-sorts by time since DISTINCT ON forces a userId-first sort.
 *
 * Fresh builder per call — drizzle's builders mutate, so they can't be shared.
 */
export const bestRunPerUser = () => {
  const best = db
    .selectDistinctOn([runs.userId], {
      userId: runs.userId,
      name: user.name,
      image: user.image,
      timeMs: runs.timeMs,
      mouselessTool: runs.mouselessTool,
    })
    .from(runs)
    .innerJoin(user, eq(runs.userId, user.id))
    .where(eq(runs.cheats, 0))
    .orderBy(runs.userId, asc(runs.timeMs))
    .as('best')

  return db.select().from(best).orderBy(asc(best.timeMs))
}

/** How many users have a cheat-free run — the length of the deduped board. */
export const boardSize = () =>
  db
    .select({ n: sql<number>`count(distinct ${runs.userId})::int` })
    .from(runs)
    .where(eq(runs.cheats, 0))
