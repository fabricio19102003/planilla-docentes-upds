// Types and pure helpers for intensive (summer/winter) courses: staff settings and courses, and the student portal.

import { formatBs } from './reenrollmentState.ts'

export type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'outline'
export type CourseStatusValue = 'open' | 'closed'

export interface IntensiveSettings {
  theory_hourly_rate: number | null
  practice_hourly_rate: number | null
  margin_factor: number
  min_price: number
  max_price: number
  is_configured: boolean
}

export interface CoursePrice { amount: number; is_final: boolean }

export interface IntensiveCourse {
  id: number
  term_code: string
  subject: { id: number; code: string; name: string }
  capacity: number
  enrolled: number
  free: number
  is_full: boolean
  enrollment_starts_on: string
  enrollment_ends_on: string
  is_enrollment_open: boolean
  theory_hours: number
  practice_hours: number
  status: CourseStatusValue
  price: CoursePrice
}

export interface AdminIntensiveCourse extends IntensiveCourse {
  teacher: { ci: string; full_name: string }
  teacher_pay: number
  closed_at: string | null
}

export interface EnrolledStudent {
  student_id: number
  document_number: string
  full_name: string
  is_foreign: boolean
  enrolled_at: string
}

export interface AdminIntensiveCourseDetail extends AdminIntensiveCourse { students: EnrolledStudent[] }

export interface StudentIntensiveCourse extends IntensiveCourse { teacher_name: string }
export interface StudentIntensiveEnrollment extends StudentIntensiveCourse { enrolled_at: string }
export interface StudentIntensiveView { courses: StudentIntensiveCourse[]; enrollments: StudentIntensiveEnrollment[] }

export interface CourseFilters { term_code: string; status: CourseStatusValue | '' }

const TERM = /^(VER|INV)\/[0-9]{4}$/
const WHOLE = /^[0-9]+$/
const DECIMAL = /^[0-9]+([.,][0-9]+)?$/
const MAX_CAPACITY = 1000
const MAX_HOURS = 1000

export function isValidTerm(code: string): boolean {
  return TERM.test(code)
}

export function termLabel(code: string): string {
  const [kind, year] = code.split('/')
  if (!TERM.test(code)) return code
  return `${kind === 'VER' ? 'Verano' : 'Invierno'} ${year}`
}

export function courseQueryParams(filters: CourseFilters): Record<string, string> {
  const params: Record<string, string> = {}
  if (filters.term_code.trim()) params.term_code = filters.term_code.trim()
  if (filters.status) params.status = filters.status
  return params
}

export function seatsLabel(course: Pick<IntensiveCourse, 'enrolled' | 'capacity'>): string {
  return `${course.enrolled} / ${course.capacity}`
}

export function priceLabel(price: CoursePrice): string {
  return `${formatBs(price.amount)} (${price.is_final ? 'fijo' : 'estimado'})`
}

export function studentPriceNote(price: CoursePrice): string {
  return price.is_final ? 'Precio fijo' : 'Estimado: baja si se inscriben más'
}

type StatusInput = Pick<IntensiveCourse, 'status' | 'is_enrollment_open' | 'enrollment_starts_on'>

/** The server only says whether enrollment is open now; the date tells apart "not yet" from "over". */
export function courseStatus(course: StatusInput, today: string): { label: string; variant: BadgeVariant } {
  if (course.status === 'closed') return { label: 'Cerrado', variant: 'outline' }
  if (course.is_enrollment_open) return { label: 'Inscripción abierta', variant: 'success' }
  return today < course.enrollment_starts_on
    ? { label: 'Programado', variant: 'info' }
    : { label: 'Inscripción vencida', variant: 'warning' }
}

// ── Settings ─────────────────────────────────────────────────────────────────

export interface SettingsForm {
  theory_hourly_rate: string
  practice_hourly_rate: string
  margin_factor: string
  min_price: string
  max_price: string
}

export interface SettingsPayload {
  theory_hourly_rate: number
  practice_hourly_rate: number
  margin_factor: number
  min_price: number
  max_price: number
}

function text(value: number | null): string {
  return value === null ? '' : String(value)
}

export function settingsFormFrom(settings: IntensiveSettings): SettingsForm {
  return {
    theory_hourly_rate: text(settings.theory_hourly_rate), practice_hourly_rate: text(settings.practice_hourly_rate),
    margin_factor: text(settings.margin_factor), min_price: text(settings.min_price), max_price: text(settings.max_price),
  }
}

function decimals(value: string): number {
  return (value.trim().split(/[.,]/)[1] ?? '').length
}

function toNumber(value: string): number {
  return Number(value.trim().replace(',', '.'))
}

/** Mirrors the API: rates above 0 (2 decimals), factor 1 or more (3 decimals), 0 < minimum <= maximum. */
export function settingsProblem(form: SettingsForm): string | null {
  const rates: [string, string][] = [['teoría', form.theory_hourly_rate], ['práctica', form.practice_hourly_rate]]
  for (const [name, value] of rates) {
    if (!value.trim()) return `Indicá la tarifa por hora de ${name}.`
    if (!DECIMAL.test(value.trim()) || toNumber(value) <= 0) return `La tarifa por hora de ${name} debe ser un número mayor a 0.`
    if (decimals(value) > 2) return `La tarifa por hora de ${name} admite hasta 2 decimales.`
  }
  const factor = form.margin_factor
  if (!DECIMAL.test(factor.trim()) || toNumber(factor) < 1) return 'El factor de margen debe ser 1 o más (ej: 1.10).'
  if (decimals(factor) > 3) return 'El factor de margen admite hasta 3 decimales.'
  if (!WHOLE.test(form.min_price.trim()) || Number(form.min_price) <= 0) return 'El precio mínimo debe ser un entero mayor a 0.'
  if (!WHOLE.test(form.max_price.trim()) || Number(form.max_price) <= 0) return 'El precio máximo debe ser un entero mayor a 0.'
  if (Number(form.min_price) > Number(form.max_price)) return 'El precio mínimo no puede superar al máximo'
  return null
}

export function settingsPayload(form: SettingsForm): SettingsPayload {
  return {
    theory_hourly_rate: toNumber(form.theory_hourly_rate), practice_hourly_rate: toNumber(form.practice_hourly_rate),
    margin_factor: toNumber(form.margin_factor), min_price: Number(form.min_price), max_price: Number(form.max_price),
  }
}

// ── Course form ──────────────────────────────────────────────────────────────

export interface CourseForm {
  term_code: string
  subject_code: string
  teacher_ci: string
  capacity: string
  enrollment_starts_on: string
  enrollment_ends_on: string
  theory_hours: string
  practice_hours: string
}

export interface CourseCreatePayload {
  term_code: string
  subject_code: string
  teacher_ci: string
  capacity: number
  enrollment_starts_on: string
  enrollment_ends_on: string
  theory_hours?: number
  practice_hours?: number
}

export type CourseUpdatePayload = Omit<Required<CourseCreatePayload>, 'term_code' | 'subject_code'>

export function emptyCourseForm(): CourseForm {
  return {
    term_code: '', subject_code: '', teacher_ci: '', capacity: '', enrollment_starts_on: '', enrollment_ends_on: '',
    theory_hours: '', practice_hours: '',
  }
}

export function courseFormFrom(course: AdminIntensiveCourse): CourseForm {
  return {
    term_code: course.term_code, subject_code: course.subject.code, teacher_ci: course.teacher.ci,
    capacity: String(course.capacity), enrollment_starts_on: course.enrollment_starts_on,
    enrollment_ends_on: course.enrollment_ends_on, theory_hours: String(course.theory_hours),
    practice_hours: String(course.practice_hours),
  }
}

/** On create, empty hours are valid: the server prefills them from the curriculum. Term and subject are fixed on edit. */
export function courseFormProblem(form: CourseForm, mode: 'create' | 'edit'): string | null {
  if (mode === 'create') {
    if (!isValidTerm(form.term_code.trim())) return 'El período va como VER/AAAA o INV/AAAA (ej: VER/2027).'
    if (!form.subject_code) return 'Elegí la materia.'
  }
  if (!form.teacher_ci) return 'Elegí el docente.'
  if (!WHOLE.test(form.capacity.trim()) || Number(form.capacity) < 1 || Number(form.capacity) > MAX_CAPACITY) {
    return `Los cupos son un entero entre 1 y ${MAX_CAPACITY}.`
  }
  if (!form.enrollment_starts_on || !form.enrollment_ends_on) return 'Indicá las fechas de inscripción.'
  if (form.enrollment_ends_on < form.enrollment_starts_on) return 'La fecha de fin debe ser igual o posterior a la de inicio'
  const hours = [form.theory_hours.trim(), form.practice_hours.trim()]
  const required = mode === 'edit'
  if (hours.some((value) => (value === '' ? required : !WHOLE.test(value) || Number(value) > MAX_HOURS))) {
    return `Las horas son enteros entre 0 y ${MAX_HOURS}.`
  }
  if (hours.every((value) => value !== '') && hours.every((value) => Number(value) === 0)) {
    return 'Las horas de teoría y práctica no pueden ser ambas cero'
  }
  return null
}

function optionalHours(value: string): number | undefined {
  return value.trim() === '' ? undefined : Number(value)
}

export function coursePayload(form: CourseForm): CourseCreatePayload {
  const payload: CourseCreatePayload = {
    term_code: form.term_code.trim(), subject_code: form.subject_code, teacher_ci: form.teacher_ci,
    capacity: Number(form.capacity), enrollment_starts_on: form.enrollment_starts_on,
    enrollment_ends_on: form.enrollment_ends_on,
  }
  const theory = optionalHours(form.theory_hours)
  const practice = optionalHours(form.practice_hours)
  if (theory !== undefined) payload.theory_hours = theory
  if (practice !== undefined) payload.practice_hours = practice
  return payload
}

export function courseUpdatePayload(form: CourseForm): CourseUpdatePayload {
  return {
    teacher_ci: form.teacher_ci, capacity: Number(form.capacity), enrollment_starts_on: form.enrollment_starts_on,
    enrollment_ends_on: form.enrollment_ends_on, theory_hours: Number(form.theory_hours),
    practice_hours: Number(form.practice_hours),
  }
}
