/** Duration of the dashboard count-up, between the 600 and 800 ms the spec asks for. */
export const COUNT_UP_DURATION_MS = 700

/** Decelerating curve: fast at the start, settling on the target. Clamped to 0..1. */
export function easeOutCubic(t: number): number {
  const clamped = Math.min(1, Math.max(0, t))
  return 1 - (1 - clamped) ** 3
}

/** Linear interpolation; `progress` 1 returns `to` exactly (no float drift). */
export function interpolate(from: number, to: number, progress: number): number {
  if (progress >= 1) return to
  return from + (to - from) * progress
}

/** Value shown `elapsedMs` after the animation started, counting from 0 up to `target`. */
export function countUpFrame(target: number, elapsedMs: number, durationMs: number = COUNT_UP_DURATION_MS): number {
  return interpolate(0, target, easeOutCubic(elapsedMs / durationMs))
}

/** The number to animate to, or null when the value is not a finite number and must render unchanged. */
export function countUpTarget(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
