import type {
  AcademicScheduleAssignment,
  ScheduleActivityType,
  SchedulePublicationDiff,
  ScheduleWeekday,
} from '@/api/types'

export const SCHEDULE_WEEKDAYS: Array<{ value: ScheduleWeekday; label: string }> = [
  { value: 'monday', label: 'Lunes' },
  { value: 'tuesday', label: 'Martes' },
  { value: 'wednesday', label: 'Miércoles' },
  { value: 'thursday', label: 'Jueves' },
  { value: 'friday', label: 'Viernes' },
  { value: 'saturday', label: 'Sábado' },
]

const clock = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
const minutesOf = (value: string) => {
  const [hours, minutes] = value.split(':').map(Number)
  return hours * 60 + minutes
}

export const BLOCK_DAY_START = 6 * 60
export const BLOCK_DAY_END = 23 * 60 + 30
export const BLOCK_STEP_MINUTES = 5
export const BLOCK_DURATION_PRESETS = [45, 90, 135]

/** 30-minute drop cells; blocks can start and end at any 5-minute time inside the day. */
export const SCHEDULE_TIMES = Array.from({ length: 35 }, (_, index) => clock(BLOCK_DAY_START + index * 30))

/** The drop cell that shows a block, i.e. its start rounded down to the half hour. */
export function cellForStart(start: string) {
  return clock(Math.floor(minutesOf(start) / 30) * 30)
}

/** Client-side mirror of the backend block time rules; '' means valid. */
export function blockTimeError(start: string, end: string) {
  if (!/^\d{2}:\d{2}$/.test(start) || !/^\d{2}:\d{2}$/.test(end)) return 'Indique la hora de inicio y de fin.'
  const startMinutes = minutesOf(start)
  const endMinutes = minutesOf(end)
  if (startMinutes >= endMinutes) return 'La hora de inicio debe ser anterior a la hora de fin.'
  if (startMinutes < BLOCK_DAY_START || endMinutes > BLOCK_DAY_END) return 'El bloque debe estar entre las 06:00 y las 23:30.'
  if (startMinutes % BLOCK_STEP_MINUTES || endMinutes % BLOCK_STEP_MINUTES) return 'Las horas deben usar intervalos de 5 minutos.'
  if (endMinutes - startMinutes < 15 || endMinutes - startMinutes > 360) return 'El bloque debe durar entre 15 minutos y 6 horas.'
  return ''
}

/** Duration ÷ academic-hour length, rounded half up, at least 1 (same rule as the backend). */
export function defaultAcademicHours(start: string, end: string, hourLength: number) {
  const minutes = minutesOf(end) - minutesOf(start)
  return Math.max(1, Math.floor((2 * minutes + hourLength) / (2 * hourLength)))
}

export interface ScheduleBlockForm {
  offering_id: string
  group_id: string
  classroom_id: string
  activity_type: ScheduleActivityType
  weekday: ScheduleWeekday
  start_time: string
  end_time: string
  /** Empty = let the server prefill it from the duration. */
  academic_hours: string
}

export const EMPTY_SCHEDULE_BLOCK: ScheduleBlockForm = {
  offering_id: '', group_id: '', classroom_id: '', activity_type: 'theory',
  weekday: 'monday', start_time: '07:00', end_time: '08:00', academic_hours: '',
}

export function scheduleCellId(weekday: ScheduleWeekday, startTime: string) {
  return `schedule-cell|${weekday}|${startTime}`
}

export function parseScheduleCellId(value: string): { weekday: ScheduleWeekday; start_time: string } | null {
  const [prefix, weekday, start_time] = value.split('|')
  if (prefix !== 'schedule-cell' || !SCHEDULE_WEEKDAYS.some((day) => day.value === weekday) || !SCHEDULE_TIMES.includes(start_time)) {
    return null
  }
  return { weekday: weekday as ScheduleWeekday, start_time }
}

export function addMinutes(value: string, minutes: number) {
  return clock(Math.min(minutesOf(value) + minutes, BLOCK_DAY_END))
}

export function scheduleBlockPayload(form: ScheduleBlockForm) {
  return {
    offering_id: Number(form.offering_id),
    group_id: Number(form.group_id),
    classroom_id: Number(form.classroom_id),
    activity_type: form.activity_type,
    weekday: form.weekday,
    start_time: form.start_time,
    end_time: form.end_time,
    ...(form.academic_hours.trim() ? { academic_hours: Number(form.academic_hours) } : {}),
  }
}

export function assignmentForReferenceDate(
  assignments: AcademicScheduleAssignment[], referenceDate: string,
) {
  return assignments.find((assignment) =>
    assignment.effective_from <= referenceDate
    && (assignment.effective_to === null || assignment.effective_to >= referenceDate)
  ) ?? null
}

export function assignmentPayload(
  teacherCi: string, effectiveFrom: string, effectiveTo: string,
) {
  return {
    teacher_ci: teacherCi,
    effective_from: effectiveFrom,
    effective_to: effectiveTo || null,
  }
}

export function replacementWarning(effectiveFrom: string) {
  if (!effectiveFrom) return ''
  const cutover = new Date(`${effectiveFrom}T12:00:00Z`)
  cutover.setUTCDate(cutover.getUTCDate() - 1)
  return `La asignación anterior finalizará el ${cutover.toISOString().slice(0, 10)}.`
}

export function publicationDiffItems(diff: SchedulePublicationDiff) {
  return [
    { key: 'added', label: 'Añadidos', value: diff.added_blocks, className: 'bg-emerald-50' },
    { key: 'removed', label: 'Retirados', value: diff.removed_blocks, className: 'bg-red-50' },
    { key: 'changed', label: 'Cambiados', value: diff.changed_blocks, className: 'bg-sky-50' },
    { key: 'teachers', label: 'Reemplazos', value: diff.teacher_replacements, className: 'bg-amber-50' },
  ] as const
}
