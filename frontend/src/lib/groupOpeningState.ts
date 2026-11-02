// Types and pure helpers for the group opening suggestions page.

import type { BadgeVariant, ReenrollmentWindow } from './reenrollmentState.ts'

export const MAX_GROUP_SIZE = 200
const SIZE_PROBLEM = `El tamaño de grupo debe ser un número entero entre 1 y ${MAX_GROUP_SIZE}.`

export type DifferenceStatus = 'faltan' | 'sobran' | 'correcto'

export interface GroupOpeningRow {
  semester: number
  shift: string
  requests: number
  retakers: number
  suggested_groups: number
  existing_groups: number
  existing_capacity: number
  groups_without_capacity: number
  difference: number
  status: DifferenceStatus
  label: string
}

export interface GroupOpeningTotals {
  requests: number
  retakers: number
  suggested_groups: number
  existing_groups: number
  existing_capacity: number
  groups_without_capacity: number
  missing_groups: number
  leftover_groups: number
}

export interface GroupOpening {
  window: ReenrollmentWindow | null
  group_size: number
  rows: GroupOpeningRow[]
  totals: GroupOpeningTotals
}

const SHIFT_LABELS: Record<string, string> = { M: 'M Mañana', T: 'T Tarde', N: 'N Noche' }

export function shiftLabel(shift: string): string {
  return SHIFT_LABELS[shift] ?? shift
}

export function groupSizeProblem(raw: string): string | null {
  const text = raw.trim()
  if (!/^\d+$/.test(text)) return SIZE_PROBLEM
  const value = Number(text)
  return value >= 1 && value <= MAX_GROUP_SIZE ? null : SIZE_PROBLEM
}

export function groupSizePayload(raw: string): { group_size: number } {
  const problem = groupSizeProblem(raw)
  if (problem) throw new Error(problem)
  return { group_size: Number(raw.trim()) }
}

const DIFFERENCE_VARIANTS: Record<DifferenceStatus, BadgeVariant> = { faltan: 'error', sobran: 'warning', correcto: 'success' }

export function differenceBadge(row: GroupOpeningRow): { label: string; variant: BadgeVariant } {
  return { label: row.label, variant: DIFFERENCE_VARIANTS[row.status] }
}

export function capacityLabel(row: GroupOpeningRow): string {
  if (row.existing_groups === 0) return '—'
  if (row.groups_without_capacity === 0) return String(row.existing_capacity)
  if (row.existing_capacity === 0) return 'Sin capacidad'
  return `${row.existing_capacity} + ${row.groups_without_capacity} sin capacidad`
}

/** The chosen window, else the open one, else the first (the list comes newest first). */
export function activeWindowId(windows: Pick<ReenrollmentWindow, 'id' | 'is_open'>[], selected: number | undefined): number | undefined {
  if (selected !== undefined && windows.some((w) => w.id === selected)) return selected
  return (windows.find((w) => w.is_open) ?? windows[0])?.id
}

export function groupOpeningQueryParams(windowId: number | undefined): Record<string, number> {
  return windowId === undefined ? {} : { window_id: windowId }
}
