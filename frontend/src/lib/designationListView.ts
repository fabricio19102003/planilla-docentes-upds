import type { DesignationAdminItem } from '../api/types'
import { semesterNumber } from './academicTones.ts'
import { formatDate } from './designationAdminState.ts'

export type DesignationStatusFilter = 'all' | 'active' | 'finalized'

type KpiItem = Pick<DesignationAdminItem, 'status' | 'monthly_hours' | 'has_contract'>

export interface DesignationKpis {
  total: number
  active: number
  finalized: number
  monthlyHours: number
  withContract: number
}

/** Summary numbers of the listed designations. */
export function designationKpis(items: readonly KpiItem[]): DesignationKpis {
  const active = items.filter((item) => item.status === 'active').length
  return {
    total: items.length,
    active,
    finalized: items.length - active,
    monthlyHours: items.reduce((sum, item) => sum + (item.monthly_hours ?? 0), 0),
    withContract: items.filter((item) => item.has_contract).length,
  }
}

/** Counts shown next to the Todas / Vigentes / Finalizadas quick filter. */
export function statusFilterCounts(items: readonly KpiItem[]): Record<DesignationStatusFilter, number> {
  const { total, active, finalized } = designationKpis(items)
  return { all: total, active, finalized }
}

export function filterByStatus<T extends Pick<DesignationAdminItem, 'status'>>(items: readonly T[], status: DesignationStatusFilter): T[] {
  return status === 'all' ? [...items] : items.filter((item) => item.status === status)
}

const LOWERCASE_PARTICLES = new Set(['de', 'del', 'la', 'las', 'los', 'el', 'y'])

/**
 * Name for display: UPPERCASE names become Title Case, names that already mix cases stay as written.
 * Display only; searches and filters keep using the raw value.
 */
export function displayName(name: string): string {
  const trimmed = name.trim()
  if (!trimmed || trimmed !== trimmed.toUpperCase()) return trimmed
  return trimmed
    .toLowerCase()
    .split(/(\s+)/)
    .map((part, index) => {
      if (index > 0 && LOWERCASE_PARTICLES.has(part)) return part
      return part.replace(/(^|[-'’])(\p{L})/gu, (_match, sep: string, letter: string) => sep + letter.toUpperCase())
    })
    .join('')
}

/** `PRIMERO` → `1.º sem`; anything that is not a known semester keeps its own text. */
export function semesterChipLabel(semester: string): string {
  const n = semesterNumber(semester)
  return n === null ? semester : `${n}.º sem`
}

export interface DesignationFilterValues {
  search: string
  period: string
  semester: string
  type: string
  status: DesignationStatusFilter
}

/** How many filters are set, for the "Limpiar filtros" button. The status filter counts only when it is not "all". */
export function activeFilterCount(filters: DesignationFilterValues, teacherCi: string): number {
  return [
    filters.search.trim() !== '',
    filters.period !== '',
    filters.semester !== '',
    filters.type !== '',
    filters.status !== 'all',
    teacherCi !== '',
  ].filter(Boolean).length
}

export function contractText(item: Pick<DesignationAdminItem, 'contract_start_date' | 'contract_end_date'>): string {
  if (!item.contract_start_date && !item.contract_end_date) return 'Todo el período'
  return `${formatDate(item.contract_start_date) || 'Inicio del período'} – ${formatDate(item.contract_end_date) || 'fin del período'}`
}

export function weeklyHoursOf(item: Pick<DesignationAdminItem, 'weekly_hours' | 'weekly_hours_calculated'>): number | string {
  return item.weekly_hours ?? item.weekly_hours_calculated ?? '—'
}

/** Why the finalize action is blocked, shown as text on touch screens where the `title` tooltip never appears. */
export function blockedReason(item: Pick<DesignationAdminItem, 'actions'>): string | null {
  return item.actions.finalize.allowed ? null : item.actions.finalize.reason
}
