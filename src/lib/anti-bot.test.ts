import assert from 'node:assert/strict'
import { MARK_COUNT, paceFault } from './anti-bot'

/** A believable human run: ~500ms per tube, jittered. */
const human = (() => {
  const jitter = [0, 180, -90, 260, -140, 60, 310, -70, 120, -200]
  let t = 0
  return jitter.map((j) => (t += 520 + j))
})()

assert.equal(paceFault(human[MARK_COUNT - 1] + 40, human), null)

// wrong number of marks / junk values
assert.equal(paceFault(6000, human.slice(1)), 'mark-count')
assert.equal(paceFault(6000, human.map(() => NaN)), 'mark-junk')

// a fast clock with honest-looking marks: the marks give it away
assert.equal(paceFault(50, human), 'marks-past-clock')

// script speed
assert.equal(
  paceFault(500, Array.from({ length: MARK_COUNT }, (_, i) => (i + 1) * 50)),
  'gap-too-fast',
)

// slow enough, but metronome-regular
assert.equal(
  paceFault(6000, Array.from({ length: MARK_COUNT }, (_, i) => (i + 1) * 600)),
  'gaps-too-uniform',
)

console.log('anti-bot ok')
