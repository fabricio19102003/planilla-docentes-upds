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

export const SCHEDULE_TIMES = Array.from({ length: 30 }, (_, index) => {
  const minutes = 7 * 60 + index * 30
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
})

export const SCHEDULE_END_TIMES = [...SCHEDULE_TIMES.slice(1), '22:00']

export interface ScheduleBlockForm {
  offering_id: string
  group_id: string
  classroom_id: string
  activity_type: ScheduleActivityType
  weekday: ScheduleWeekday
  start_time: string
  end_time: string
}

export const EMPTY_SCHEDULE_BLOCK: ScheduleBlockForm = {
  offering_id: '', group_id: '', classroom_id: '', activity_type: 'theory',
  weekday: 'monday', start_time: '07:00', end_time: '08:00',
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
  const [hours, currentMinutes] = value.split(':').map(Number)
  const total = Math.min(hours * 60 + currentMinutes + minutes, 22 * 60)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
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
