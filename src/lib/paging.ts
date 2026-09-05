export const PAGE_SIZE = 50
/** Ranks 1-3 live on the 3D podium, so the list starts at 4. */
export const PODIUM = 3

/** Page math for the leaderboard list (ranks 4+). `page` is 1-based. */
export function paging(totalRuns: number, page: number) {
  const p = Math.max(1, Number.isFinite(page) ? Math.floor(page) : 1)
  const listed = Math.max(0, totalRuns - PODIUM)
  const pages = Math.max(1, Math.ceil(listed / PAGE_SIZE))
  const clamped = Math.min(p, pages)
  return {
    page: clamped,
    pages,
    offset: PODIUM + (clamped - 1) * PAGE_SIZE,
    firstRank: PODIUM + (clamped - 1) * PAGE_SIZE + 1,
  }
}
