import { formatMinutes, toMinutes, type BusyRange } from './classroomReservations.ts'

/** Start times on the agenda and in the start grid move in quarter hours. */
export const AGENDA_STEP_MINUTES = 15

export type RoomKind = 'all' | 'classroom' | 'laboratory'
export type RoomGroupKey = 'antiguo' | 'nuevo' | 'laboratory' | 'other'

export interface RoomLike {
  code: string
  name: string
  classroom_type: 'classroom' | 'laboratory'
}

export interface ParsedRoomCode {
  building: 'ANTIGUO' | 'NUEVO' | null
  floor: number | null
  room: string | null
}

export interface RoomGroup<T extends RoomLike> {
  key: RoomGroupKey
  title: string
  rooms: T[]
}

export interface OccupancySegment {
  left: number
  width: number
  kind: BusyRange['kind']
  mine: boolean
}

export interface StartOption {
  time: string
  available: boolean
}

const ROOM_CODE_PATTERN = /^COB-(ANTIGUO|NUEVO)-P(\d+)-A(.+)$/
const GROUP_ORDER: RoomGroupKey[] = ['antiguo', 'nuevo', 'laboratory', 'other']
const GROUP_TITLES: Record<RoomGroupKey, string> = {
  antiguo: 'Edificio Antiguo',
  nuevo: 'Edificio Nuevo',
  laboratory: 'Laboratorios',
  other: 'Otros',
}
const BUILDING_LABELS = { ANTIGUO: 'Antiguo', NUEVO: 'Nuevo' } as const
const WEEKDAYS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']
const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
const BOLIVIA_CLOCK = new Intl.DateTimeFormat('en-GB', { timeZone: 'America/La_Paz', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
/** Float noise guard: 90 / 995 * 995 must still read as 90 minutes. */
const EPSILON = 1e-6

export function parseRoomCode(code: string): ParsedRoomCode {
  const match = ROOM_CODE_PATTERN.exec(code)
  if (!match) return { building: null, floor: null, room: null }
  return { building: match[1] as 'ANTIGUO' | 'NUEVO', floor: Number(match[2]), room: match[3] }
}

export function roomGroupKey(room: RoomLike): RoomGroupKey {
  if (room.classroom_type === 'laboratory') return 'laboratory'
  const { building } = parseRoomCode(room.code)
  return building === 'ANTIGUO' ? 'antiguo' : building === 'NUEVO' ? 'nuevo' : 'other'
}

/** "Antiguo · Piso 1", or null when the code does not say where the room is. */
export function roomLocation(room: RoomLike): string | null {
  const { building, floor } = parseRoomCode(room.code)
  return building && floor !== null ? `${BUILDING_LABELS[building]} · Piso ${floor}` : null
}

function normalizeSearch(value: string): string {
  return value.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim()
}

/** Rooms matching the kind and the name/code search, grouped in building order; empty groups are dropped. */
export function groupRooms<T extends RoomLike>(rooms: T[], filter: { query: string; kind: RoomKind }): RoomGroup<T>[] {
  const query = normalizeSearch(filter.query)
  const visible = rooms.filter((room) => {
    if (filter.kind !== 'all' && (filter.kind === 'laboratory') !== (room.classroom_type === 'laboratory')) return false
    return query === '' || normalizeSearch(`${room.name} ${room.code}`).includes(query)
  })
  return GROUP_ORDER
    .map((key) => ({ key, title: GROUP_TITLES[key], rooms: visible.filter((room) => roomGroupKey(room) === key) }))
    .filter((group) => group.rooms.length > 0)
}

/** Busy ranges as left/width percentages of the day window, clipped to it. */
export function occupancyBar(busy: BusyRange[], dayStart: string, dayEnd: string): OccupancySegment[] {
  const windowStart = toMinutes(dayStart) ?? 0
  const total = (toMinutes(dayEnd) ?? 0) - windowStart
  if (total <= 0) return []
  return busy.flatMap((range) => {
    const from = Math.max(toMinutes(range.start_time) ?? 0, windowStart)
    const to = Math.min(toMinutes(range.end_time) ?? 0, windowStart + total)
    if (to <= from) return []
    return [{ left: ((from - windowStart) / total) * 100, width: ((to - from) / total) * 100, kind: range.kind, mine: range.mine }]
  })
}

/** "1 h 30 min", "45 min", "2 h". */
export function formatDuration(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return [hours > 0 ? `${hours} h` : '', minutes > 0 ? `${minutes} min` : ''].filter(Boolean).join(' ') || '0 min'
}

/** Whole day window of 06:30 – 23:05 unless the caller passes another total. */
export function freeTimeLabel(freeMinutes: number, totalMinutes = 995): string {
  if (freeMinutes >= totalMinutes) return 'Libre todo el día'
  return freeMinutes <= 0 ? 'Sin tiempo libre' : `${formatDuration(freeMinutes)} libres`
}

/** Every quarter-hour start of the window with whether `durationMinutes` fits there; `after` (minutes) rules out times up to and including now. */
export function startOptions(input: {
  busy: BusyRange[]
  dayStart: string
  dayEnd: string
  durationMinutes: number
  after?: number | null
  step?: number
}): StartOption[] {
  const { busy, dayStart, dayEnd, durationMinutes, after = null, step = AGENDA_STEP_MINUTES } = input
  const windowEnd = toMinutes(dayEnd) ?? 0
  const ranges = busy.map((range) => [toMinutes(range.start_time) ?? 0, toMinutes(range.end_time) ?? 0] as const)
  const options: StartOption[] = []
  for (let start = Math.ceil((toMinutes(dayStart) ?? 0) / step) * step; start < windowEnd; start += step) {
    const end = start + durationMinutes
    const available = end <= windowEnd
      && (after === null || start > after)
      && !ranges.some(([from, to]) => start < to && from < end)
    options.push({ time: formatMinutes(start), available })
  }
  return options
}

/** Vertical click ratio (0 = day start, 1 = day end) to the quarter hour at or before it, inside the window. */
export function timeAtPosition(ratio: number, dayStart: string, dayEnd: string, step = AGENDA_STEP_MINUTES): string {
  const windowStart = toMinutes(dayStart) ?? 0
  const windowEnd = toMinutes(dayEnd) ?? 0
  const clamped = Math.min(1, Math.max(0, ratio))
  const snapped = Math.floor((windowStart + clamped * (windowEnd - windowStart) + EPSILON) / step) * step
  const first = Math.ceil(windowStart / step) * step
  const last = Math.floor((windowEnd - 1) / step) * step
  return formatMinutes(Math.min(last, Math.max(first, snapped)))
}

/** Local-calendar Date for a `YYYY-MM-DD` key (no time-zone shift). */
export function parseDateKey(key: string): Date {
  const [year, month, day] = key.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function toDateKey(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function isBookableDay(date: Date): boolean {
  return date.getDay() !== 0
}

/** `fromKey` itself unless it is a Sunday, then the Monday after. */
export function nextBookableDate(fromKey: string): string {
  const date = parseDateKey(fromKey)
  while (!isBookableDay(date)) date.setDate(date.getDate() + 1)
  return toDateKey(date)
}

/** "jueves 12 de noviembre". */
export function formatLongDate(key: string): string {
  const date = parseDateKey(key)
  return `${WEEKDAYS[date.getDay()]} ${date.getDate()} de ${MONTHS[date.getMonth()]}`
}

/** Minutes since midnight on the Bolivia clock. */
export function getBoliviaMinutes(now = new Date()): number {
  const parts = BOLIVIA_CLOCK.formatToParts(now)
  const part = (type: string) => Number(parts.find((entry) => entry.type === type)?.value ?? 0)
  return part('hour') * 60 + part('minute')
}
