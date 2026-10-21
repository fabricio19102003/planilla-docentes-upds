import type { ClashKind, FreeSlot, ScheduleClash } from '@/api/types'

const CLASH_LABELS: Record<ClashKind, string> = {
  teacher: 'Docente',
  group: 'Grupo',
  classroom: 'Aula',
  split_group: 'Grupo dividido',
}

const WEEKDAY_LABELS: Record<string, string> = {
  lunes: 'Lunes', martes: 'Martes', miercoles: 'Miércoles', jueves: 'Jueves',
  viernes: 'Viernes', sabado: 'Sábado', domingo: 'Domingo',
}

export const clashLabel = (kind: ClashKind) => CLASH_LABELS[kind]
export const weekdayLabel = (weekday: string) => WEEKDAY_LABELS[weekday] ?? weekday

const groupName = (semester: number | null, group: string | null) =>
  semester === null ? `${group ?? ''}` : `${semester}.º ${group ?? ''}`

/** One sentence that says who or what is double booked. */
export function clashDescription(clash: ScheduleClash) {
  const [left, right] = clash.blocks
  if (clash.kind === 'teacher') {
    const name = left.teacher_name || left.teacher_ci || 'El docente'
    return `${name} tiene dos clases a la vez: ${left.subject_name} (${groupName(left.semester, left.group_code)}) y ${right.subject_name} (${groupName(right.semester, right.group_code)}).`
  }
  if (clash.kind === 'classroom') {
    return `${clash.classroom_code} está ocupada por dos clases: ${groupName(left.semester, left.group_code)} y ${groupName(right.semester, right.group_code)}.`
  }
  if (clash.kind === 'split_group') {
    return `${groupName(clash.semester, clash.group_code)} tiene teoría y práctica de ${left.subject_name} a la vez (grupo dividido).`
  }
  return `${groupName(clash.semester, clash.group_code)} tiene dos clases a la vez: ${left.subject_name} y ${right.subject_name}.`
}

export interface ConflictsFilters {
  period: string
  source: 'current' | 'draft'
  draftId: number | null
  date: string
  threshold: number
}

/** Query string for /schedule-conflicts, or null while the filters are incomplete. */
export function conflictsParams(filters: ConflictsFilters) {
  if (!filters.period || !filters.date || !(filters.threshold > 0)) return null
  if (filters.source === 'draft') {
    if (!filters.draftId) return null
    return { academic_period: filters.period, source: 'draft' as const, draft_id: filters.draftId, date: filters.date, load_threshold: filters.threshold }
  }
  return { academic_period: filters.period, source: 'current' as const, date: filters.date, load_threshold: filters.threshold }
}

/** Free slots of one group (`group:<semester>|<code>`) or classroom (`room:<code>`). */
export function filterFreeSlots(free: { groups: FreeSlot[]; rooms: FreeSlot[] }, selection: string): FreeSlot[] {
  if (selection.startsWith('group:')) {
    const [semester, code] = selection.slice('group:'.length).split('|')
    return free.groups.filter((item) => String(item.semester) === semester && item.group_code === code)
  }
  if (selection.startsWith('room:')) {
    const code = selection.slice('room:'.length)
    return free.rooms.filter((item) => item.classroom_code === code)
  }
  return []
}

export interface DesignationLoadForm {
  period: string
  effectiveFrom: string
  file: File
}

export function loadFormData(form: DesignationLoadForm, digest?: string) {
  const data = new FormData()
  data.append('academic_period', form.period)
  data.append('effective_from', form.effectiveFrom)
  data.append('workbook', form.file)
  if (digest) data.append('digest', digest)
  return data
}
