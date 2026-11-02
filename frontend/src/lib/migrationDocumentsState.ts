// Shared types and pure helpers for the migration documents of foreign students.
import type { BadgeVariant } from './reenrollmentState.ts'

export type DocumentState = 'present' | 'missing' | 'expired'

export interface MigrationDocumentType {
  id: number
  name: string
  requires_expiry: boolean
  active: boolean
  position: number
}

export interface StudentDocumentRow {
  type_id: number
  name: string
  requires_expiry: boolean
  state: DocumentState
  expires_on: string | null
  notes: string | null
}

export interface ExpiredDocument { name: string; expires_on: string }

export interface PendingDocuments {
  applies: boolean
  regularizado: boolean
  missing: string[]
  expired: ExpiredDocument[]
}

/** Status of one student as staff see it (inbox detail and student card). */
export interface MigrationStatus extends PendingDocuments {
  student_id?: number
  documents: StudentDocumentRow[]
}

export const MAX_NAME_LENGTH = 120
export const MAX_NOTES_LENGTH = 1000

const DOCUMENT_BADGES: Record<DocumentState, { label: string; variant: BadgeVariant }> = {
  present: { label: 'Presentado', variant: 'success' },
  missing: { label: 'Falta', variant: 'error' },
  expired: { label: 'Vencido', variant: 'warning' },
}

export function documentBadge(state: DocumentState) {
  return DOCUMENT_BADGES[state]
}

export function inboxRegularizadoBadge(regularizado: boolean | null): { label: string; variant: BadgeVariant } | null {
  if (regularizado === null) return null
  return regularizado ? { label: 'Regularizado', variant: 'success' } : { label: 'No regularizado', variant: 'error' }
}

export function regularizadoBadge(status: Pick<PendingDocuments, 'applies' | 'regularizado'>) {
  return inboxRegularizadoBadge(status.applies ? status.regularizado : null)
}

/** dd/mm/yyyy from an ISO date, without going through Date (no time zone shifts). */
export function formatExpiry(value: string | null): string {
  if (!value) return '—'
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

export function pendingLabels(status: Pick<PendingDocuments, 'missing' | 'expired'>): string[] {
  return [...status.missing, ...status.expired.map((item) => `${item.name} (vencido el ${formatExpiry(item.expires_on)})`)]
}

/** Why "Marcar como realizada" is not offered; the API answers 409 with the same text. */
export function completeBlockReason(status: PendingDocuments | undefined): string | null {
  if (!status || !status.applies || status.regularizado) return null
  return `Documentos migratorios pendientes: ${pendingLabels(status).join(', ')}`
}

export function typeNameProblem(name: string): string | null {
  const trimmed = name.trim()
  if (!trimmed) return 'El nombre del documento es obligatorio'
  if (trimmed.length > MAX_NAME_LENGTH) return `El nombre del documento no puede superar los ${MAX_NAME_LENGTH} caracteres`
  return null
}

function isRealDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

export function documentFormProblem(requiresExpiry: boolean, expiresOn: string, notes: string): string | null {
  if (requiresExpiry) {
    if (!expiresOn.trim()) return 'La fecha de vencimiento es obligatoria para este documento'
    if (!isRealDate(expiresOn.trim())) return 'La fecha de vencimiento no es válida'
  }
  if (notes.trim().length > MAX_NOTES_LENGTH) return `Las notas no pueden superar los ${MAX_NOTES_LENGTH} caracteres`
  return null
}

export function documentPayload(requiresExpiry: boolean, expiresOn: string, notes: string) {
  return {
    expires_on: requiresExpiry ? expiresOn.trim() : null,
    notes: notes.trim() || null,
  }
}

/** New zero-based position for a one-step move, or null when it cannot move that way. */
export function movePosition(types: { id: number; position: number }[], id: number, direction: 'up' | 'down'): number | null {
  const ordered = [...types].sort((a, b) => a.position - b.position)
  const index = ordered.findIndex((item) => item.id === id)
  if (index === -1) return null
  const target = direction === 'up' ? index - 1 : index + 1
  return target < 0 || target >= ordered.length ? null : target
}
