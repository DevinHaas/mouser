import assert from 'node:assert/strict'
import { previewLines } from './rank-preview'

const rows = [
  { name: 'a', timeMs: 1000 },
  { name: 'b', timeMs: 3000 },
]

// run slots in at rank 2; the row it displaces shifts down to 3
const mid = previewLines({ rank: 2, startRank: 1, rows, best: null }, 2000)
assert.equal(mid.beaten, false)
assert.deepEqual(mid.lines.map((l) => [l.rank, l.name]), [
  [1, 'a'],
  [2, 'CURRENT RUN'],
  [3, 'b'],
])

// slower than everything shown: appended at the end
const last = previewLines({ rank: 3, startRank: 1, rows, best: null }, 5000)
assert.deepEqual(last.lines.map((l) => [l.rank, l.name]), [
  [1, 'a'],
  [2, 'b'],
  [3, 'CURRENT RUN'],
])

// a better personal best stands: ranks untouched, no CURRENT RUN row
const pb = previewLines({ rank: 2, startRank: 1, rows, best: 1500 }, 2000)
assert.equal(pb.beaten, true)
assert.deepEqual(pb.lines.map((l) => [l.rank, l.name]), [
  [1, 'a'],
  [2, 'b'],
])

// a worse personal best still lists the run
assert.equal(previewLines({ rank: 2, startRank: 1, rows, best: 9000 }, 2000).beaten, false)

console.log('rank-preview ok')
