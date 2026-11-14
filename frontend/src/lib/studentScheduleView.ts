// Pure view selection for the Horario switch (Hoy / Semana / Próximo). Today is read in America/La_Paz.

import { boliviaClock } from './studentHomeState.ts'
import { groupByWeekday, weekdayLabel, type ScheduleDay, type ScheduleEntry } from './studentScheduleState.ts'

export type ScheduleViewMode = 'today' | 'week' | 'upcoming'

const EMPTY_MESSAGES: Record<ScheduleViewMode, string> = {
  today: 'No tenés clases hoy.',
  week: 'No tenés clases en el horario publicado.',
  upcoming: 'No hay un horario próximo publicado.',
}

/** The days to show for a view: today's classes of the current publication, every entry by weekday, or the publication that has not started. */
export function scheduleViewDays(entries: ScheduleEntry[], mode: ScheduleViewMode, now: Date): ScheduleDay[] {
  if (mode === 'week') return groupByWeekday(entries)
  if (mode === 'upcoming') return groupByWeekday(entries.filter((entry) => entry.is_upcoming))
  const { weekday } = boliviaClock(now)
  const today = groupByWeekday(entries.filter((entry) => !entry.is_upcoming && entry.weekday === weekday))
  return today.map((day) => ({ ...day, label: `Hoy · ${weekdayLabel(day.weekday)}` }))
}

export function scheduleViewEmpty(mode: ScheduleViewMode): string {
  return EMPTY_MESSAGES[mode]
}

/** Hoy when there are classes today, so the first thing seen is useful; Semana otherwise. */
export function defaultScheduleMode(entries: ScheduleEntry[], now: Date): ScheduleViewMode {
  return scheduleViewDays(entries, 'today', now).length > 0 ? 'today' : 'week'
}
