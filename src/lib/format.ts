/** mm:ss.ms, e.g. 1:23.45 */
export function fmtTime(ms: number) {
  const s = ms / 1000
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}.${String(Math.floor((ms % 1000) / 10)).padStart(2, '0')}`
}
