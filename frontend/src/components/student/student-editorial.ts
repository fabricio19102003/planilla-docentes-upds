// Pure helpers behind the editorial primitives of the student portal upgrade. No React, so they run under node --test.

export const FIGURE_LOCALE = 'es-BO'

export type StepState = 'done' | 'current' | 'pending'

const round = (value: number) => Number(value.toFixed(3))

/** 1200 -> "1.200", 12345.6 with one decimal -> "12.345,6". Non-finite values read as 0. */
export function formatFigure(value: number, decimals = 0): string {
  const safe = Number.isFinite(value) ? value : 0
  return new Intl.NumberFormat(FIGURE_LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: 'always',
  }).format(safe)
}

export function clampPercent(value: number): number {
  return Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0
}

/** Circumference of a ring of `size` px whose stroke is `stroke` px wide (the radius runs along the stroke centre). */
export function ringCircumference(size: number, stroke: number): number {
  return round(2 * Math.PI * ((size - stroke) / 2))
}

/** stroke-dashoffset that leaves `value`% of the ring drawn: 0 is a full ring, the circumference is an empty one. */
export function ringDashOffset(value: number, circumference: number): number {
  return round(circumference * (1 - clampPercent(value) / 100))
}

/** `value` out of `max` as a 0-100 percentage; an empty or invalid max reads as 0. */
export function meterPercent(value: number, max: number): number {
  return max > 0 ? clampPercent((value / max) * 100) : 0
}

/** Segments of a seats bar: `total` defaults to `max`; a non-empty meter always lights at least one segment. */
export function meterSegments(value: number, max: number, segments = max): { filled: number; total: number } {
  const total = max > 0 ? Math.max(0, Math.floor(segments)) : 0
  if (total === 0) return { filled: 0, total: 0 }
  const percent = meterPercent(value, max)
  const filled = percent > 0 ? Math.max(1, Math.round((percent / 100) * total)) : 0
  return { filled: Math.min(total, filled), total }
}

/** State of each step: before `current` is done, `current` is current, after it is pending; `current >= count` means all done. */
export function stepperStates(count: number, current: number): StepState[] {
  return Array.from({ length: Math.max(0, count) }, (_, index) => {
    if (index < current) return 'done'
    return index === current ? 'current' : 'pending'
  })
}
