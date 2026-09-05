import type { PodiumEntry } from '@/components/podium'

/**
 * Placeholder podium rows for when fewer than 3 real runs exist.
 * ponytail: delete this file (and the padTop3 call) once the board fills up.
 */
const MOCK = [
  { name: 'torvalds', timeMs: 61230, image: 'https://avatars.githubusercontent.com/u/1024025?v=4' },
  { name: 'gaearon', timeMs: 74980, image: 'https://avatars.githubusercontent.com/u/810438?v=4' },
  { name: 'sindresorhus', timeMs: 88410, image: 'https://avatars.githubusercontent.com/u/170270?v=4' },
  { name: 'yyx990803', timeMs: 95120, image: 'https://avatars.githubusercontent.com/u/499550?v=4' },
]

export type Row = { name: string; timeMs: number; image: string | null }

/** Real rows first, mock rows filling the rest, re-sorted by time. */
export function padTop3(rows: Row[]): PodiumEntry[] {
  const filled: Row[] = [...rows]
  for (const m of MOCK) {
    if (filled.length >= 3) break
    filled.push(m)
  }
  return filled
    .sort((a, b) => a.timeMs - b.timeMs)
    .slice(0, 3)
    .map((r, i) => ({ ...r, rank: (i + 1) as 1 | 2 | 3 }))
}
