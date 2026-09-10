import { defineAction } from 'astro:actions'
import { z } from 'astro:schema'
import { auth } from '@/lib/auth'
import { db } from '@/lib/db'
import { runs, user } from '@/lib/db/schema'
import { and, asc, count, eq, lt, min } from 'drizzle-orm'
import { padTop3 } from '@/lib/mock-leaderboard'
import { bestRunPerUser } from '@/lib/leaderboard-query'
import { paceFault, turnstileOk } from '@/lib/anti-bot'
import { captureServerError, captureServerInfo } from '@/lib/analytics.server'

export const server = {
  logGame: defineAction({
    input: z.object({
      event: z.enum(['game_started', 'game_finished']),
      mode: z.enum(['ranked', 'training']),
      elapsedMs: z.number().int().min(0),
      cheats: z.number().int().min(0),
    }),
    handler: ({ event, mode, elapsedMs, cheats }) => {
      captureServerInfo(event, { mode, elapsed_ms: elapsedMs, cheats })
    },
  }),

  /** Podium rows for the start-screen leaderboard dock. */
  topThree: defineAction({
    handler: async () => {
      const rows = await bestRunPerUser()
        .limit(3)
        .catch((error) => {
          captureServerError(error, { operation: 'load_top_three' })
          return []
        })
      return padTop3(rows)
    },
  }),

  /**
   * Ranks the finished run against the cheat-free board, then saves it when
   * logged in. Ranking happens before the insert so the run never counts itself.
   *
   * Screened for bots first: a run that moves faster than hands can, or that
   * fails its background Turnstile challenge, is simply not counted — no row,
   * no rank preview. See @/lib/anti-bot.
   */
  submitRun: defineAction({
    input: z.object({
      timeMs: z.number().int().positive(),
      cheats: z.number().int().min(0),
      marks: z.array(z.number()).max(64),
      token: z.string().nullable(),
    }),
    handler: async ({ timeMs, cheats, marks, token }, ctx) => {
      const rejected =
        paceFault(timeMs, marks) ??
        ((await turnstileOk(token, ctx.request.headers.get('cf-connecting-ip')))
          ? null
          : 'turnstile')
      if (rejected) return { saved: false, preview: null, rejected }

      const session = await auth.api.getSession({ headers: ctx.request.headers })
      const clean = eq(runs.cheats, 0)

      // ponytail: cheated runs are off the board — nothing to rank.
      const preview = cheats > 0 ? null : await (async () => {
        const [{ n: faster }] = await db
          .select({ n: count() })
          .from(runs)
          .where(and(clean, lt(runs.timeMs, timeMs)))

        const offset = Math.max(0, faster - 2)
        const window = await db
          .select({ name: user.name, timeMs: runs.timeMs })
          .from(runs)
          .innerJoin(user, eq(runs.userId, user.id))
          .where(clean)
          .orderBy(asc(runs.timeMs))
          .limit(5)
          .offset(offset)

        const best = session
          ? await db
              .select({ t: min(runs.timeMs) })
              .from(runs)
              .where(and(clean, eq(runs.userId, session.user.id)))
          : []

        return { rank: faster + 1, startRank: offset + 1, rows: window, best: best[0]?.t ?? null }
      })()

      if (!session) return { saved: false, preview, rejected: null }
      await db.insert(runs).values({
        userId: session.user.id,
        timeMs,
        cheats,
        mouselessTool: session.user.mouselessTool ?? null,
      })
      return { saved: true, preview, rejected: null }
    },
  }),
}
