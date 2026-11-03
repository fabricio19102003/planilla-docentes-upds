import type { BiometricUpload } from '@/api/types'

export const MONTHLY_CLOSE_STEP_KEYS = ['biometrico', 'asistencia', 'planilla', 'aprobacion', 'publicacion'] as const

export type MonthlyCloseStepKey = (typeof MONTHLY_CLOSE_STEP_KEYS)[number]
export type MonthlyCloseState = 'done' | 'current' | 'pending'

export interface MonthlyCloseStep {
  key: MonthlyCloseStepKey
  label: string
  href: string
  state: MonthlyCloseState
  /** One-line status shown under the label. */
  detail: string
}

export interface MonthlyCloseInput {
  month: number | null
  year: number | null
  /** Recent biometric uploads, as the dashboard receives them. */
  uploads: Pick<BiometricUpload, 'month' | 'year' | 'status'>[]
  /** `total_slots` of the latest attendance summary, null when there is none. */
  attendanceSlots: number | null
  planilla: { status: string } | null | undefined
  publication: { status: string } | null | undefined
}

const MONTH_NAMES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

const STEP_LABELS: Record<MonthlyCloseStepKey, string> = {
  biometrico: 'Biométrico',
  asistencia: 'Asistencia',
  planilla: 'Planilla',
  aprobacion: 'Aprobación',
  publicacion: 'Publicación',
}

const STEP_HREFS: Record<MonthlyCloseStepKey, string> = {
  biometrico: '/upload',
  asistencia: '/attendance',
  planilla: '/planilla',
  aprobacion: '/planilla',
  publicacion: '/planilla',
}

/**
 * Derives the five monthly-close steps for the billing period.
 * A step is done when it has its own evidence or any later step is done (a published month
 * cannot be missing its biométrico, even when the recent-uploads list no longer shows it).
 * The first step that is not done is the current one; the rest are pending.
 */
export function deriveMonthlyClose(input: MonthlyCloseInput): MonthlyCloseStep[] {
  const { month, year, planilla, publication } = input
  const hasPeriod = month != null && year != null
  const period = hasPeriod ? `${MONTH_NAMES[month - 1]} ${year}` : null

  const hasUpload = hasPeriod && input.uploads.some(
    (upload) => upload.month === month && upload.year === year && upload.status === 'PROCESSED',
  )
  const slots = input.attendanceSlots ?? 0
  const rejected = planilla?.status === 'rejected'
  const approved = planilla?.status === 'approved'
  const published = publication?.status === 'published'

  const evidence: Record<MonthlyCloseStepKey, boolean> = {
    biometrico: hasUpload,
    asistencia: slots > 0,
    planilla: planilla != null && !rejected,
    aprobacion: approved,
    publicacion: published,
  }

  const details: Record<MonthlyCloseStepKey, { done: string; todo: string }> = {
    biometrico: {
      done: `${period} cargado`,
      todo: period ? `Sin archivo de ${period}` : 'Sin datos cargados',
    },
    asistencia: { done: `${slots} horarios procesados`, todo: 'Sin procesar' },
    planilla: { done: 'Generada', todo: rejected ? 'Rechazada · regenerar' : 'Sin generar' },
    aprobacion: {
      done: 'Aprobada',
      todo: rejected ? 'Rechazada' : planilla ? 'Pendiente de aprobación' : 'Esperando planilla',
    },
    publicacion: { done: 'Publicada', todo: 'Sin publicar' },
  }

  const lastDone = MONTHLY_CLOSE_STEP_KEYS.reduce((last, key, index) => (evidence[key] ? index : last), -1)

  return MONTHLY_CLOSE_STEP_KEYS.map((key, index) => {
    const state: MonthlyCloseState = index <= lastDone ? 'done' : index === lastDone + 1 ? 'current' : 'pending'
    return {
      key,
      label: STEP_LABELS[key],
      href: STEP_HREFS[key],
      state,
      detail: state === 'done' ? details[key].done : details[key].todo,
    }
  })
}
