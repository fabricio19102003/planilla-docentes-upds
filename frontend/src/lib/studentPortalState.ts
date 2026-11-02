// Pure helpers for the student portal re-enrollment form.
import type { Eligibility, GroupOption, ReenrollmentRequest, ReenrollmentWindow } from '@/lib/reenrollmentState'

export interface StudentReenrollmentView {
  window: Pick<ReenrollmentWindow, 'is_open'> & Partial<ReenrollmentWindow> | null
  eligibility: Pick<Eligibility, 'target_semester' | 'recursado' | 'pending' | 'scholarship' | 'recursado_fee'> & Partial<Eligibility>
  main_groups: Pick<GroupOption, 'id'>[] | GroupOption[]
  groups_by_semester?: Record<string, GroupOption[]>
  request: Pick<ReenrollmentRequest, 'status'> & Partial<ReenrollmentRequest> | null
}

/** Subject code -> chosen group id, or '' when the student does not take it this term. */
export type GroupChoices = Record<string, number | ''>

const RECURSADO_CHARGED_MAX = 3
const SHIFTS: Record<string, string> = { M: 'Mañana', T: 'Tarde', N: 'Noche' }

export function shiftLabel(shift: string): string {
  return SHIFTS[shift] ?? shift
}

export function groupLabel(group: GroupOption): string {
  const base = `${group.code} · ${shiftLabel(group.shift)}`
  if (group.free === null) return base
  if (group.is_full) return `${base} · sin cupos`
  return `${base} · ${group.free} ${group.free === 1 ? 'cupo libre' : 'cupos libres'}`
}

export function buildSubmission(mainGroupId: number, choices: GroupChoices) {
  return {
    main_group_id: mainGroupId,
    items: Object.entries(choices)
      .filter((entry): entry is [string, number] => entry[1] !== '')
      .map(([subject_code, group_id]) => ({ subject_code, group_id })),
  }
}

export function estimateAmounts(eligibility: StudentReenrollmentView['eligibility'], choices: GroupChoices) {
  const recursadoCodes = new Set(eligibility.recursado.map((subject) => subject.code))
  const recursadoChosen = Object.entries(choices).filter(([code, group]) => group !== '' && recursadoCodes.has(code)).length
  const recursadoCharged = Math.min(recursadoChosen, RECURSADO_CHARGED_MAX)
  const { scholarship } = eligibility
  return {
    scholarshipLabel: scholarship.label,
    cuota: scholarship.cuota,
    cuotas: scholarship.cuotas,
    cuotasTotal: scholarship.total,
    recursadoChosen,
    recursadoCharged,
    recursadoTotal: recursadoCharged * eligibility.recursado_fee.per_subject,
  }
}

/** Why the form cannot be sent yet, in the student's words; null when it can. */
export function submissionProblem(view: StudentReenrollmentView, mainGroupId: number | null): string | null {
  if (view.eligibility.target_semester === null) return 'No encontramos tu historial académico; acercate a Registro.'
  if (!view.window?.is_open) return 'La rematrícula no está abierta.'
  if (view.request?.status === 'realizada') return 'Tu rematrícula ya fue realizada.'
  if (view.main_groups.length === 0) return 'Todavía no hay grupos abiertos para tu semestre; consultá en Registro.'
  if (mainGroupId === null) return 'Elegí el grupo de tu semestre.'
  return null
}
