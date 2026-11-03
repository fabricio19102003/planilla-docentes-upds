/**
 * Ordered series palette for recharts. Every entry is a theme CSS variable, so charts follow the
 * light/dark theme and never carry a raw color.
 */
export const CHART_SERIES_PALETTE = [
  'var(--color-chart-1)',
  'var(--color-tone-violet)',
  'var(--color-tone-cyan)',
  'var(--color-success)',
  'var(--color-warning)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
] as const

/** Color for the series at `index`; wraps around when there are more series than colors. */
export function seriesColor(index: number): string {
  const size = CHART_SERIES_PALETTE.length
  return CHART_SERIES_PALETTE[((index % size) + size) % size]
}
