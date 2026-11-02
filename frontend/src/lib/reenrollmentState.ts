// Shared types and pure helpers for re-enrollment: staff inbox, windows and student portal accounts.

export type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'outline'
export type RequestStatusValue = 'pendiente' | 'realizada' | 'observada'
export type ObservationReason = 'documentos_migracion' | 'pago_pendiente' | 'otro'

export interface PortalAccount {
  is_active: boolean
  must_change_password: boolean
  temporary_issued_at: string | null
  last_login: string | null
}

export interface TemporaryCredential {
  student_id: number
  document_number: string
  full_name: string
  temporary_password: string
}

export interface ReenrollmentWindow {
  id: number
  term_code: string
  starts_on: string
  ends_on: string
  is_open: boolean
  requests?: Record<RequestStatusValue, number>
}

export interface CurriculumItem {
  code: string | null
  name: string
  semester: number
  is_elective: boolean
}

export interface Scholarship {
  category: 'fundador' | 'desafio' | 'sin_beca'
  label: string
  average: number | null
  never_failed: boolean
  cuota: number
  cuotas: number
  total: number
}

export interface RecursadoFee {
  per_subject: number
  subjects: number
  charged_subjects: number
  total: number
}

export interface Eligibility {
  last_term: string | null
  graded_term: string | null
  primary_semester: number | null
  target_semester: number | null
  regular: CurriculumItem[]
  recursado: CurriculumItem[]
  pending: CurriculumItem[]
  scholarship: Scholarship
  recursado_fee: RecursadoFee
}

export interface GroupOption {
  id: number
  code: string
  shift: string
  semester: number
  capacity: number | null
  taken: number
  free: number | null
  is_full: boolean
}

export interface GroupRef { id: number; code: string; shift: string }

export interface ReenrollmentRequest {
  id: number
  window_id: number
  term_code: string
  target_semester: number
  status: RequestStatusValue
  main_group: GroupRef
  items: { kind: 'recursado' | 'pendiente'; subject_code: string; subject_name: string; semester: number; group: GroupRef }[]
  observation_reason: ObservationReason | null
  observation_label: string | null
  observation_message: string | null
  snapshot: Pick<Eligibility, 'scholarship' | 'recursado_fee' | 'regular' | 'recursado' | 'pending'>
  submitted_at: string
  handled_at: string | null
}

export interface InboxRow {
  id: number
  student_id: number
  document_number: string
  full_name: string
  is_foreign: boolean
  target_semester: number
  main_group_code: string
  main_group_shift: string
  status: RequestStatusValue
  recursado_count: number
  pending_count: number
  scholarship_label: string | null
  submitted_at: string
}

export interface Inbox {
  window: ReenrollmentWindow | null
  items: InboxRow[]
  total: number
  page: number
  page_size: number
}

export const INBOX_PAGE_SIZE = 25

export const OBSERVATION_REASONS: { value: ObservationReason; label: string }[] = [
  { value: 'documentos_migracion', label: 'Documentos de migración' },
  { value: 'pago_pendiente', label: 'Pago pendiente' },
  { value: 'otro', label: 'Otro' },
]

const REQUEST_STATUSES: Record<RequestStatusValue, { label: string; variant: BadgeVariant }> = {
  pendiente: { label: 'Pendiente', variant: 'warning' },
  realizada: { label: 'Realizada', variant: 'success' },
  observada: { label: 'Observada', variant: 'error' },
}

export function requestStatus(status: RequestStatusValue) {
  return REQUEST_STATUSES[status]
}

export function accountStatus(account: PortalAccount | null): { label: string; variant: BadgeVariant } {
  if (!account) return { label: 'Sin cuenta', variant: 'outline' }
  if (!account.is_active) return { label: 'Deshabilitada', variant: 'error' }
  if (account.must_change_password) return { label: 'Con clave temporal', variant: 'warning' }
  return { label: 'Activa', variant: 'success' }
}

function csvCell(value: string): string {
  // A leading = + - @ makes spreadsheets evaluate the cell as a formula.
  const safe = /^[=+\-@]/.test(value) ? `'${value}` : value
  return /[",\r\n]/.test(safe) ? `"${safe.replaceAll('"', '""')}"` : safe
}

export function credentialsCsv(credentials: TemporaryCredential[]): string {
  const rows = [['Documento', 'Nombre', 'Clave temporal'],
    ...credentials.map((c) => [c.document_number, c.full_name, c.temporary_password])]
  return '\uFEFF' + rows.map((row) => row.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

export function formatBs(amount: number): string {
  return `${amount.toLocaleString('es-BO').replaceAll(',', '.')} Bs`
}

export interface InboxFilters {
  status: RequestStatusValue | ''
  semester: string
  search: string
  foreign: 'all' | 'national' | 'foreign'
  page: number
}

export function inboxQueryParams(filters: InboxFilters): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {}
  if (filters.status) params.status = filters.status
  if (filters.semester) params.semester = Number(filters.semester)
  if (filters.search.trim()) params.search = filters.search.trim()
  if (filters.foreign !== 'all') params.foreign = filters.foreign === 'foreign'
  return { ...params, page: filters.page, page_size: INBOX_PAGE_SIZE }
}

export function windowState(window: ReenrollmentWindow, today: string): { label: string; variant: BadgeVariant } {
  if (window.is_open) return { label: 'Abierta', variant: 'success' }
  return today < window.starts_on ? { label: 'Programada', variant: 'info' } : { label: 'Cerrada', variant: 'outline' }
}
