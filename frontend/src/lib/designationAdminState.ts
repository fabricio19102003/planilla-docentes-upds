import type {
  DesignationAdminItem,
  DesignationImportChange,
  DesignationWritePayload,
  ScheduleSlot,
} from '@/api/types'

export const SEMESTER_OPTIONS = [
  'PRIMERO', 'SEGUNDO', 'TERCERO', 'CUARTO', 'QUINTO', 'SEXTO', 'SEPTIMO', 'OCTAVO', 'NOVENO', 'DECIMO',
] as const

export const DAY_OPTIONS = [
  { value: 'lunes', label: 'Lunes', short: 'Lun' },
  { value: 'martes', label: 'Martes', short: 'Mar' },
  { value: 'miercoles', label: 'Miércoles', short: 'Mié' },
  { value: 'jueves', label: 'Jueves', short: 'Jue' },
  { value: 'viernes', label: 'Viernes', short: 'Vie' },
  { value: 'sabado', label: 'Sábado', short: 'Sáb' },
  { value: 'domingo', label: 'Domingo', short: 'Dom' },
] as const

/** Names an admin reads for the fields an import would change. */
export const FIELD_LABELS: Record<string, string> = {
  schedule_json: 'horario',
  semester_hours: 'horas del semestre',
  monthly_hours: 'horas mensuales',
  weekly_hours: 'horas semanales',
  weekly_hours_calculated: 'horas semanales',
  schedule_raw: 'texto del horario',
  designation_type: 'tipo',
  contract_start_date: 'fecha de inicio',
  contract_end_date: 'fecha de fin',
}

export interface SlotForm {
  dia: string
  hora_inicio: string
  hora_fin: string
}

export interface DesignationForm {
  teacherCi: string
  subject: string
  semester: string
  groupCode: string
  academicPeriod: string
  designationType: 'regular' | 'practice'
  slots: SlotForm[]
  monthlyHours: string
  semesterHours: string
  contractStartDate: string
  contractEndDate: string
}

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/

function minutes(value: string) {
  if (!TIME_RE.test(value)) return null
  const [hours, mins] = value.split(':').map(Number)
  return hours * 60 + mins
}

/** Academic hours of one block: 45-minute hours, rounded (same rule as the import). */
export function academicHours(start: string, end: string) {
  const from = minutes(start)
  const to = minutes(end)
  if (from === null || to === null || to <= from) return 0
  return Math.round((to - from) / 45)
}

export function weeklyHours(slots: SlotForm[]) {
  return slots.reduce((sum, slot) => sum + academicHours(slot.hora_inicio, slot.hora_fin), 0)
}

/** Most designations pay four weeks per month and five months per semester; both stay editable. */
export function suggestedMonthlyHours(weekly: number) {
  return weekly * 4
}

export function suggestedSemesterHours(monthly: number) {
  return monthly * 5
}

export function detectDesignationType(subject: string): 'regular' | 'practice' {
  const plain = subject.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase()
  return plain.includes('PRACTICA') ? 'practice' : 'regular'
}

function slotDay(slot: ScheduleSlot) {
  return String(slot.dia ?? slot.day ?? '').toLowerCase()
}

export function formatSlots(slots: ScheduleSlot[] | null | undefined) {
  if (!slots?.length) return 'Sin horario'
  return slots
    .map((slot) => {
      const day = DAY_OPTIONS.find((item) => item.value === slotDay(slot))
      const start = slot.hora_inicio ?? slot.start_time ?? ''
      const end = slot.hora_fin ?? slot.end_time ?? ''
      return `${day?.short ?? slotDay(slot)} ${start}–${end}`
    })
    .join(' · ')
}

export function emptySlot(): SlotForm {
  return { dia: '', hora_inicio: '', hora_fin: '' }
}

export function emptyDesignationForm(academicPeriod: string): DesignationForm {
  return {
    teacherCi: '', subject: '', semester: '', groupCode: '', academicPeriod, designationType: 'regular',
    slots: [emptySlot()], monthlyHours: '', semesterHours: '', contractStartDate: '', contractEndDate: '',
  }
}

export function itemToForm(item: DesignationAdminItem): DesignationForm {
  return {
    teacherCi: item.teacher_ci,
    subject: item.subject,
    semester: item.semester,
    groupCode: item.group_code,
    academicPeriod: item.academic_period,
    designationType: item.designation_type === 'practice' ? 'practice' : 'regular',
    slots: (item.schedule_json ?? []).map((slot) => ({
      dia: slotDay(slot),
      hora_inicio: String(slot.hora_inicio ?? slot.start_time ?? ''),
      hora_fin: String(slot.hora_fin ?? slot.end_time ?? ''),
    })),
    monthlyHours: item.monthly_hours == null ? '' : String(item.monthly_hours),
    semesterHours: item.semester_hours == null ? '' : String(item.semester_hours),
    contractStartDate: item.contract_start_date ?? '',
    contractEndDate: item.contract_end_date ?? '',
  }
}

/** Every problem the admin has to fix before saving, in the order the form shows the fields. */
export function formErrors(form: DesignationForm) {
  const errors: string[] = []
  if (!form.teacherCi) errors.push('Elegí un docente.')
  if (!form.subject.trim()) errors.push('Escribí la materia.')
  if (!form.semester.trim()) errors.push('Elegí el semestre.')
  if (!form.groupCode.trim()) errors.push('Escribí el grupo.')
  if (!form.slots.length) errors.push('Agregá al menos un bloque de horario.')
  form.slots.forEach((slot, index) => {
    const label = `Bloque ${index + 1}`
    if (!slot.dia) errors.push(`${label}: elegí el día.`)
    const start = minutes(slot.hora_inicio)
    const end = minutes(slot.hora_fin)
    if (start === null || end === null) errors.push(`${label}: completá la hora de inicio y de fin.`)
    else if (end <= start) errors.push(`${label}: la hora de fin tiene que ser posterior a la de inicio.`)
    else if (academicHours(slot.hora_inicio, slot.hora_fin) === 0) errors.push(`${label}: el bloque es demasiado corto.`)
  })
  if (form.monthlyHours.trim() === '' || !(Number(form.monthlyHours) >= 0)) errors.push('Indicá las horas mensuales.')
  if (form.semesterHours.trim() !== '' && !(Number(form.semesterHours) >= 0)) errors.push('Las horas del semestre no son válidas.')
  if (form.contractStartDate && form.contractEndDate && form.contractEndDate < form.contractStartDate) {
    errors.push('La fecha de fin no puede ser anterior a la fecha de inicio.')
  }
  return errors
}

export function formToPayload(form: DesignationForm): DesignationWritePayload {
  return {
    teacher_ci: form.teacherCi,
    subject: form.subject.trim(),
    semester: form.semester.trim(),
    group_code: form.groupCode.trim(),
    academic_period: form.academicPeriod,
    designation_type: form.designationType,
    schedule: form.slots.map((slot) => ({ dia: slot.dia, hora_inicio: slot.hora_inicio, hora_fin: slot.hora_fin })),
    monthly_hours: Number(form.monthlyHours),
    semester_hours: form.semesterHours.trim() === '' ? null : Number(form.semesterHours),
    contract_start_date: form.contractStartDate || null,
    contract_end_date: form.contractEndDate || null,
  }
}

export function changeSummary(changes: Pick<DesignationImportChange, 'action'>[]) {
  const summary = { create: 0, update: 0, noop: 0 }
  for (const change of changes) summary[change.action] += 1
  return summary
}

export function changedFieldsText(fields: string[]) {
  return [...new Set(fields.map((name) => FIELD_LABELS[name] ?? name))].join(', ')
}

export function formatDate(value: string | null | undefined) {
  if (!value) return ''
  const [year, month, day] = value.slice(0, 10).split('-')
  return `${day}/${month}/${year}`
}

export interface ProblemDetails {
  title: string
  items: string[]
}

/** Server answer as a title plus the list of reasons (422 `errors`, 409 `blockers` or a plain detail). */
export function errorDetails(error: unknown, fallback: string): ProblemDetails {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return { title: detail, items: [] }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const { message, errors, blockers } = detail as { message: unknown; errors?: unknown[]; blockers?: { message?: unknown }[] }
    const items = [
      ...(Array.isArray(errors) ? errors.map(String) : []),
      ...(Array.isArray(blockers) ? blockers.map((item) => String(item?.message ?? '')) : []),
    ].filter(Boolean)
    return { title: String(message), items }
  }
  return { title: fallback, items: [] }
}

export function regenerateText(items: { planilla: 'regular' | 'practice'; month: number; year: number }[]) {
  if (!items.length) return ''
  const names = items.map((item) => `${item.planilla === 'practice' ? 'práctica' : 'teoría'} ${item.month}/${item.year}`)
  return `Regenerá la planilla de ${names.join(', ')} para que tome el cambio.`
}
