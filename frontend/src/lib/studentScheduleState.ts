// Types and pure helpers for the student's weekly schedule (published blocks of the main group, recursado/pending groups and intensive courses).

export type ScheduleSource = 'grupo' | 'recursado' | 'pendiente' | 'intensivo'
export type ScheduleStatusCode = 'ok' | 'no_request' | 'not_done' | 'not_published'

export interface ScheduleEntry {
  source: ScheduleSource
  subject_code: string
  subject_name: string
  group_code: string
  weekday: string
  start_time: string
  end_time: string
  classroom: { code: string; name: string }
  activity_type: 'theory' | 'practice'
  teacher_name: string | null
  term_code: string
  effective_from: string
  is_upcoming: boolean
}

export interface UnscheduledCourse {
  source: 'intensivo'
  subject_code: string
  subject_name: string
  term_code: string
}

export interface StudentScheduleView {
  status: { code: ScheduleStatusCode; message: string | null }
  effective_from: string | null
  entries: ScheduleEntry[]
  unscheduled: UnscheduledCourse[]
}

export type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'outline'

// The backend stores lowercase English weekday names (Monday to Saturday for published blocks).
export const WEEKDAY_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const WEEKDAY_LABELS: Record<string, string> = {
  monday: 'Lunes', tuesday: 'Martes', wednesday: 'Miércoles', thursday: 'Jueves',
  friday: 'Viernes', saturday: 'Sábado', sunday: 'Domingo',
}

export function weekdayLabel(weekday: string): string {
  return WEEKDAY_LABELS[weekday] ?? weekday
}

function weekdayRank(weekday: string): number {
  const rank = WEEKDAY_ORDER.indexOf(weekday)
  return rank === -1 ? WEEKDAY_ORDER.length : rank
}

export interface ScheduleDay { weekday: string; label: string; entries: ScheduleEntry[] }

export function groupByWeekday(entries: ScheduleEntry[]): ScheduleDay[] {
  const sorted = [...entries].sort((a, b) =>
    weekdayRank(a.weekday) - weekdayRank(b.weekday)
    || a.start_time.localeCompare(b.start_time)
    || a.end_time.localeCompare(b.end_time)
    || a.subject_name.localeCompare(b.subject_name, 'es'))
  const days: ScheduleDay[] = []
  for (const entry of sorted) {
    const last = days[days.length - 1]
    if (last && last.weekday === entry.weekday) last.entries.push(entry)
    else days.push({ weekday: entry.weekday, label: weekdayLabel(entry.weekday), entries: [entry] })
  }
  return days
}

export function sourceBadge(source: ScheduleSource): { label: string; variant: BadgeVariant } | null {
  if (source === 'recursado') return { label: 'Recursado', variant: 'warning' }
  if (source === 'pendiente') return { label: 'Pendiente', variant: 'info' }
  if (source === 'intensivo') return { label: 'Intensivo', variant: 'success' }
  return null
}

export function activityLabel(activity: ScheduleEntry['activity_type']): string {
  return activity === 'practice' ? 'Práctica' : 'Teoría'
}

export function timeRange(entry: Pick<ScheduleEntry, 'start_time' | 'end_time'>): string {
  return `${entry.start_time} – ${entry.end_time}`
}

export function teacherLabel(name: string | null): string {
  return name ?? 'Docente por asignar'
}

function formatIsoDate(iso: string): string {
  const [year, month, day] = iso.split('-')
  return `${day}/${month}/${year}`
}

/** When what is shown is a publication that has not taken effect yet, say from when it will. */
export function upcomingNote(entries: Pick<ScheduleEntry, 'is_upcoming' | 'effective_from'>[]): string | null {
  const dates = entries.filter((entry) => entry.is_upcoming).map((entry) => entry.effective_from).sort()
  return dates.length ? `Vigente desde ${formatIsoDate(dates[0])}` : null
}

/** Why there is nothing to show, or null when there is something. */
export function emptyMessage(view: Pick<StudentScheduleView, 'status' | 'entries' | 'unscheduled'>): string | null {
  if (view.entries.length > 0) return null
  return view.status.message ?? (view.unscheduled.length ? null : 'No tenés clases en el horario publicado.')
}
