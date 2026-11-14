// Pure helpers behind the student Inicio: today's next class (in Bolivia time) and small display rules.

import type { ScheduleEntry } from './studentScheduleState.ts'

const BOLIVIA_TIME_ZONE = 'America/La_Paz'

const clockFormatter = new Intl.DateTimeFormat('en-US', {
  weekday: 'long',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: BOLIVIA_TIME_ZONE,
})

/** Lowercase English weekday (the backend value) and minutes since midnight, both in America/La_Paz. */
export function boliviaClock(now: Date): { weekday: string; minutes: number } {
  const parts = clockFormatter.formatToParts(now)
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? ''
  return { weekday: part('weekday').toLowerCase(), minutes: Number(part('hour')) * 60 + Number(part('minute')) }
}

function toMinutes(time: string): number {
  const [hours, minutes] = time.split(':')
  return Number(hours) * 60 + Number(minutes)
}

export interface TodayClass {
  entry: ScheduleEntry
  state: 'in_progress' | 'upcoming'
  /** Minutes until it starts (upcoming) or until it ends (in progress). */
  minutes: number
}

export interface TodayClasses {
  next: TodayClass | null
  /** The classes of today after `next`, in time order. */
  later: ScheduleEntry[]
  /** Classes scheduled for today, finished or not. */
  total: number
}

/** The class in progress or the next one today, ignoring publications that have not taken effect yet. */
export function nextClassToday(entries: ScheduleEntry[], now: Date): TodayClasses {
  const clock = boliviaClock(now)
  const today = entries
    .filter((entry) => !entry.is_upcoming && entry.weekday === clock.weekday)
    .sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time) || toMinutes(a.end_time) - toMinutes(b.end_time))
  // A class is over at its end time.
  const index = today.findIndex((entry) => toMinutes(entry.end_time) > clock.minutes)
  if (index === -1) return { next: null, later: [], total: today.length }
  const entry = today[index]
  const started = toMinutes(entry.start_time) <= clock.minutes
  return {
    next: started
      ? { entry, state: 'in_progress', minutes: toMinutes(entry.end_time) - clock.minutes }
      : { entry, state: 'upcoming', minutes: toMinutes(entry.start_time) - clock.minutes },
    later: today.slice(index + 1),
    total: today.length,
  }
}

export function countdownLabel({ state, minutes }: Pick<TodayClass, 'state' | 'minutes'>): string {
  if (state === 'in_progress') return 'En curso'
  if (minutes < 60) return `En ${minutes} min`
  const rest = minutes % 60
  return rest === 0 ? `En ${minutes / 60} h` : `En ${Math.floor(minutes / 60)} h ${rest} min`
}

export function formatAverage(average: number | null): string {
  return average === null ? '—' : average.toFixed(1).replace('.', ',')
}

/** Label of the hero link to Rematrícula: the open-window actions, or a plain "Ver mi rematrícula". */
export function rematriculaCta(window: { is_open: boolean } | null | undefined, request: { status: string } | null | undefined): string {
  if (!window?.is_open) return 'Ver mi rematrícula'
  return request ? 'Ver o editar mi solicitud' : 'Solicitar rematrícula'
}
