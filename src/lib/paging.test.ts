import assert from 'node:assert/strict'
import { paging } from './paging'

// empty / tiny board: one page, list starts at rank 4
assert.deepEqual(paging(0, 1), { page: 1, pages: 1, offset: 3, firstRank: 4 })
assert.deepEqual(paging(3, 1), { page: 1, pages: 1, offset: 3, firstRank: 4 })
// 53 runs = 50 listed = still one page
assert.equal(paging(53, 1).pages, 1)
// 54 runs = 51 listed = two pages; page 2 starts at rank 54
assert.equal(paging(54, 1).pages, 2)
assert.deepEqual(paging(54, 2), { page: 2, pages: 2, offset: 53, firstRank: 54 })
// junk and out-of-range pages clamp
assert.equal(paging(54, 99).page, 2)
assert.equal(paging(54, NaN).page, 1)
assert.equal(paging(54, -5).page, 1)

console.log('paging ok')
