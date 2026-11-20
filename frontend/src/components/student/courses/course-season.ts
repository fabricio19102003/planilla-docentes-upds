// Pure helpers behind the Cursos de verano e invierno cards. No React, so they run under node --test.

export type SeasonTone = 'summer' | 'winter' | 'other'
export type StatusTone = 'ok' | 'info' | 'warn' | 'muted' | 'bad'
export type MeterTone = 'default' | 'warn' | 'bad'
export type BlockReason = 'full' | 'scheduled' | 'expired' | 'closed'

/** Terms are VER/2027 (summer) or INV/2027 (winter); anything else is neutral. */
export function seasonTone(termCode: string): SeasonTone {
  const kind = termCode.split('/')[0]
  if (kind === 'VER') return 'summer'
  return kind === 'INV' ? 'winter' : 'other'
}

const FEW_SEATS = 0.2

export interface SeatsMeter {
  value: number
  max: number
  tone: MeterTone
  label: string
  valueText: string
  few: boolean
}

/** Free seats out of the capacity: "N cupos libres", amber when 20 % or less is left, "Sin cupos" when none. */
export function seatsMeter(course: { free: number; capacity: number; is_full: boolean }): SeatsMeter {
  const max = Math.max(course.capacity, 1)
  const full = course.is_full || course.free <= 0
  const value = full ? 0 : Math.min(course.free, max)
  const valueText = `${value} de ${max} cupos libres`
  if (full) return { value, max, tone: 'bad', label: 'Sin cupos', valueText, few: false }
  const few = value / max <= FEW_SEATS
  return { value, max, tone: few ? 'warn' : 'default', label: value === 1 ? '1 cupo libre' : `${value} cupos libres`, valueText, few }
}

const STATUS_TONE: Record<string, StatusTone> = { success: 'ok', info: 'info', warning: 'warn', outline: 'muted', error: 'bad' }

/** Editorial tone of the status badge, from the Badge variant courseStatus() already returns. */
export function statusTone(variant: string): StatusTone {
  return STATUS_TONE[variant] ?? 'muted'
}

/** Why the "Inscribirme" button is blocked, or null when the student can enroll. */
export function enrollBlockReason(
  course: { is_full: boolean; free: number; is_enrollment_open: boolean; status: string; enrollment_starts_on: string },
  today: string,
): BlockReason | null {
  if (course.status === 'closed') return 'closed'
  if (course.is_full || course.free <= 0) return 'full'
  if (course.is_enrollment_open) return null
  return today < course.enrollment_starts_on ? 'scheduled' : 'expired'
}
