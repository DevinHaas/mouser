export type PreviewRow = { name: string; timeMs: number }

export type Preview = {
  /** Where this run would sit on the cheat-free board, 1-based. */
  rank: number
  /** Rank of `rows[0]`. */
  startRank: number
  rows: PreviewRow[]
  /** The player's best cheat-free time before this run, if any. */
  best: number | null
}

export type PreviewLine = PreviewRow & { key: string; rank: number; self: boolean }

/**
 * Board slice around the finished run. A better personal best already holds the
 * slot, so the run is shown as info only and never inserted into the list.
 */
export function previewLines({ rank, startRank, rows, best }: Preview, timeMs: number) {
  const beaten = best !== null && best <= timeMs
  const self: PreviewLine = { key: 'self', rank, name: 'CURRENT RUN', timeMs, self: true }
  const lines: PreviewLine[] = []
  rows.forEach((r, i) => {
    const at = startRank + i
    if (!beaten && at === rank) lines.push(self)
    lines.push({ ...r, key: `r${at}`, rank: at + (!beaten && at >= rank ? 1 : 0), self: false })
  })
  if (!beaten && !lines.includes(self)) lines.push(self)
  return { beaten, lines }
}
