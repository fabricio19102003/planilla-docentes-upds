import { formatMinutes, timelinePosition, toMinutes } from './classroomReservations.ts'

/** Bookable day window, same as the backend (`day_start` / `day_end`). */
export const GRID_DAY_START = '06:30'
export const GRID_DAY_END = '23:05'

export type RoomTypeFilter = 'all' | 'classroom' | 'laboratory'

interface GridRoom {
  id: number
  code: string
  classroom_type: 'classroom' | 'laboratory'
}

interface GridReservation {
  start_time: string
  classroom: { id: number; code: string }
}

const startOf = (value: { start_time: string }) => toMinutes(value.start_time) ?? 0

/** Vertical placement as window percentages, clamped so a block never leaves the grid. */
export function blockPosition(start: string, end: string, dayStart = GRID_DAY_START, dayEnd = GRID_DAY_END) {
  const windowStart = toMinutes(dayStart) ?? 0
  const windowEnd = toMinutes(dayEnd) ?? 0
  const from = Math.min(Math.max(toMinutes(start) ?? windowStart, windowStart), windowEnd)
  const to = Math.min(Math.max(toMinutes(end) ?? windowStart, windowStart), windowEnd)
  return timelinePosition(formatMinutes(from), formatMinutes(to), dayStart, dayEnd)
}

/** One gridline per full hour inside the window. */
export function gridHourMarks(dayStart = GRID_DAY_START, dayEnd = GRID_DAY_END): { time: string; top: number }[] {
  const first = Math.ceil((toMinutes(dayStart) ?? 0) / 60)
  const last = Math.floor((toMinutes(dayEnd) ?? 0) / 60)
  return Array.from({ length: Math.max(last - first + 1, 0) }, (_, index) => {
    const time = formatMinutes((first + index) * 60)
    return { time, top: timelinePosition(time, dayEnd, dayStart, dayEnd).top }
  })
}

export function filterRoomsByType<T extends Pick<GridRoom, 'classroom_type'>>(rooms: T[], filter: RoomTypeFilter): T[] {
  return filter === 'all' ? rooms : rooms.filter((room) => room.classroom_type === filter)
}

/** Reservations by room id, each list in start order. */
export function groupReservationsByRoom<T extends GridReservation>(reservations: T[]): Map<number, T[]> {
  const groups = new Map<number, T[]>()
  for (const reservation of reservations) {
    const list = groups.get(reservation.classroom.id)
    if (list) list.push(reservation)
    else groups.set(reservation.classroom.id, [reservation])
  }
  for (const list of groups.values()) list.sort((a, b) => startOf(a) - startOf(b))
  return groups
}

/** Start time first, then room code (numeric-aware: room 2 before room 10). */
export function sortDayReservations<T extends GridReservation>(reservations: T[]): T[] {
  return [...reservations].sort(
    (a, b) => startOf(a) - startOf(b) || a.classroom.code.localeCompare(b.classroom.code, 'es', { numeric: true }),
  )
}

/** Moves a YYYY-MM-DD date by whole days, independent of the local time zone. */
export function shiftDate(date: string, days: number): string {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

/** Long weekday name in Spanish ("martes") for a YYYY-MM-DD date. */
export function weekdayName(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  return new Intl.DateTimeFormat('es-BO', { weekday: 'long', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, day)))
}
