export const STEP_MINUTES = 5
export const MIN_PERIODS = 1
export const MAX_PERIODS = 8

export interface BusyRange {
  start_time: string
  end_time: string
  kind: 'class' | 'reservation'
  label: string
  detail: string | null
  mine: boolean
}

export interface TimeRange {
  start: string
  end: string
}

export type DaySegment =
  | ({ type: 'free' } & TimeRange)
  | ({ type: 'busy'; busy: BusyRange } & TimeRange)

const TIME_PATTERN = /^(\d{2}):(\d{2})/

export function toMinutes(time: string): number | null {
  const match = TIME_PATTERN.exec(time)
  if (!match) return null
  return Number(match[1]) * 60 + Number(match[2])
}

export function formatMinutes(total: number): string {
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

/** Start + periods × academic hour as HH:MM; null when the input is incomplete or the day would roll over. */
export function computeEndTime(start: string, periods: number, academicHourMinutes: number): string | null {
  const startMinutes = toMinutes(start)
  if (startMinutes === null || !Number.isInteger(periods) || periods < MIN_PERIODS) return null
  const end = startMinutes + periods * academicHourMinutes
  return end >= 24 * 60 ? null : formatMinutes(end)
}

/** Half-open `[start, end)` overlap: back-to-back ranges do not collide. */
export function rangesOverlap(startA: string, endA: string, startB: string, endB: string): boolean {
  const [a1, a2, b1, b2] = [startA, endA, startB, endB].map((value) => toMinutes(value) ?? NaN)
  return a1 < b2 && b1 < a2
}

export function findOverlap(busy: BusyRange[], start: string, end: string): BusyRange | null {
  return busy.find((range) => rangesOverlap(start, end, range.start_time, range.end_time)) ?? null
}

/** Client-side mirror of the backend checks; the backend stays the authority. */
export function rangeProblem(input: {
  busy: BusyRange[]
  dayStart: string
  dayEnd: string
  start: string
  end: string | null
}): string | null {
  const { busy, dayStart, dayEnd, start, end } = input
  const startMinutes = toMinutes(start)
  if (startMinutes === null) return null
  const endMinutes = end === null ? null : toMinutes(end)
  const windowStart = toMinutes(dayStart) ?? 0
  const windowEnd = toMinutes(dayEnd) ?? 24 * 60
  if (endMinutes === null || startMinutes < windowStart || endMinutes > windowEnd) {
    return `La reserva debe quedar entre las ${dayStart} y las ${dayEnd}.`
  }
  const clash = findOverlap(busy, start, end as string)
  if (!clash) return null
  return clash.kind === 'class'
    ? `El aula está ocupada por una clase de ${clash.start_time} a ${clash.end_time}.`
    : `El aula ya está reservada de ${clash.start_time} a ${clash.end_time}.`
}

function sortedBusy(busy: BusyRange[]): BusyRange[] {
  return [...busy].sort((a, b) => (toMinutes(a.start_time) ?? 0) - (toMinutes(b.start_time) ?? 0))
}

export function freeGaps(busy: BusyRange[], dayStart: string, dayEnd: string): TimeRange[] {
  const windowEnd = toMinutes(dayEnd) ?? 0
  const gaps: TimeRange[] = []
  let cursor = toMinutes(dayStart) ?? 0
  for (const range of sortedBusy(busy)) {
    const start = toMinutes(range.start_time) ?? 0
    if (start > cursor) gaps.push({ start: formatMinutes(cursor), end: formatMinutes(Math.min(start, windowEnd)) })
    cursor = Math.max(cursor, toMinutes(range.end_time) ?? 0)
  }
  if (cursor < windowEnd) gaps.push({ start: formatMinutes(cursor), end: dayEnd })
  return gaps
}

/** Busy ranges and free gaps in chronological order, covering the whole day window. */
export function daySegments(busy: BusyRange[], dayStart: string, dayEnd: string): DaySegment[] {
  const segments: DaySegment[] = [
    ...freeGaps(busy, dayStart, dayEnd).map((gap): DaySegment => ({ type: 'free', ...gap })),
    ...sortedBusy(busy).map((range): DaySegment => ({ type: 'busy', start: range.start_time, end: range.end_time, busy: range })),
  ]
  return segments.sort((a, b) => (toMinutes(a.start) ?? 0) - (toMinutes(b.start) ?? 0))
}

/** Every start time of the window in 5-minute steps; the last one leaves room for one step. */
export function startTimeOptions(dayStart: string, dayEnd: string, step = STEP_MINUTES): string[] {
  const options: string[] = []
  const last = toMinutes(dayEnd) ?? 0
  for (let minutes = toMinutes(dayStart) ?? 0; minutes + step <= last; minutes += step) {
    options.push(formatMinutes(minutes))
  }
  return options
}

/** Vertical position of a range inside the day window, as percentages of the window height. */
export function timelinePosition(start: string, end: string, dayStart: string, dayEnd: string): { top: number; height: number } {
  const windowStart = toMinutes(dayStart) ?? 0
  const total = (toMinutes(dayEnd) ?? 0) - windowStart
  const from = (toMinutes(start) ?? 0) - windowStart
  const to = (toMinutes(end) ?? 0) - windowStart
  return { top: (from / total) * 100, height: ((to - from) / total) * 100 }
}

/** Moves the academic period count by `delta`, never leaving MIN_PERIODS..MAX_PERIODS. */
export function stepPeriods(current: number, delta: number): number {
  return Math.min(MAX_PERIODS, Math.max(MIN_PERIODS, current + delta))
}
