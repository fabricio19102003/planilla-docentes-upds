import type { DesignationChangeTeacherImpact, TeacherDesignationSummary } from '@/api/types'

export interface TeacherChangeForm {
  period: string
  effectiveFrom: string
  incomingCi: string
  outgoingCi: string
  /** null means every designation of the outgoing teacher still active on the date. */
  designationId: number | null
}

/** Designations that are still running on the change date (the ones a change can move). */
export function activeDesignations(items: TeacherDesignationSummary[], effectiveFrom: string) {
  return items.filter((item) => !item.contract_end_date || item.contract_end_date >= effectiveFrom)
}

export function changeRequestBody(form: TeacherChangeForm) {
  if (!form.period || !form.effectiveFrom || !form.incomingCi || !form.outgoingCi) return null
  const base = {
    academic_period: form.period,
    effective_from: form.effectiveFrom,
    incoming_teacher_ci: form.incomingCi,
  }
  return form.designationId === null
    ? { ...base, scope: 'teacher' as const, outgoing_teacher_ci: form.outgoingCi }
    : { ...base, scope: 'designation' as const, designation_id: form.designationId }
}

/** Last day paid to the outgoing teacher (the day before the change), as YYYY-MM-DD. */
export function outgoingUntil(effectiveFrom: string) {
  const [year, month, day] = effectiveFrom.split('-').map(Number)
  const previous = new Date(Date.UTC(year, month - 1, day - 1))
  return previous.toISOString().slice(0, 10)
}

export function impactRows(teachers: DesignationChangeTeacherImpact[]) {
  return teachers.map((item) => ({
    ...item,
    hours_delta: item.hours_after - item.hours_before,
    amount_delta: Math.round((item.amount_after - item.amount_before) * 100) / 100,
  }))
}

export function impactTotals(teachers: DesignationChangeTeacherImpact[]) {
  const before = Math.round(teachers.reduce((sum, item) => sum + item.amount_before, 0) * 100) / 100
  const after = Math.round(teachers.reduce((sum, item) => sum + item.amount_after, 0) * 100) / 100
  return { before, after, delta: Math.round((after - before) * 100) / 100 }
}

/** Bolivian format without depending on the runtime's Intl data: Bs 1.234,50. */
export function formatBs(value: number) {
  const sign = value < 0 ? '-' : ''
  const [whole, cents] = Math.abs(value).toFixed(2).split('.')
  return `${sign}Bs ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${cents}`
}

/** Server reason for a failed request: a plain detail, or a message followed by every blocker. */
export function apiErrorText(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const { message, blockers } = detail as { message: unknown; blockers?: { message?: unknown }[] }
    const reasons = Array.isArray(blockers) ? blockers.map((item) => String(item?.message ?? '')).filter(Boolean) : []
    return [String(message), ...reasons].join(' ')
  }
  return fallback
}
