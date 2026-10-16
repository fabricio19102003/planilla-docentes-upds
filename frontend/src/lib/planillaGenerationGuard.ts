export type DiscountMode = 'attendance' | 'full'
export type PlanillaKind = 'teoricas' | 'practicas'
export type PlanillaConfirmAction = 'generate' | 'approve' | 'reject' | 'publish' | 'unpublish'

export const DISCOUNT_MODE_LABELS: Record<DiscountMode, string> = {
  attendance: 'Con descuentos por asistencia',
  full: 'Sin descuentos (pago completo)',
}

export const PLANILLA_KIND_LABELS: Record<PlanillaKind, string> = {
  teoricas: 'Teóricas',
  practicas: 'Prácticas',
}

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

export const DATES_REASON = 'Completá las fechas de corte'
export const DATE_ORDER_REASON = 'La fecha de inicio no puede ser posterior a la fecha de fin'
export const MODE_REASON = 'Elegí el modo de cálculo'
export const STATUS_LOADING_REASON = 'Cargando el estado de la planilla…'

function isDiscountMode(value: unknown): value is DiscountMode {
  return value === 'attendance' || value === 'full'
}

/** Blank date inputs become undefined; only for read-only queries, never for generation. */
export function optionalDate(value: string): string | undefined {
  return value || undefined
}

/** ISO yyyy-mm-dd → dd/mm/yyyy without going through Date (no timezone shifts). */
export function formatDisplayDate(iso: string | null | undefined): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '')
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '—'
}

function formatPeriod(month: number, year: number): string {
  return `${MONTH_NAMES[month] ?? month} ${year}`
}

function formatCutoff(startDate: string | null | undefined, endDate: string | null | undefined): string {
  return `${formatDisplayDate(startDate)}–${formatDisplayDate(endDate)}`
}

function formatMode(mode: DiscountMode | null | undefined): string {
  return mode ? DISCOUNT_MODE_LABELS[mode] : '—'
}

/**
 * The mode shown/used by the form: the admin's explicit choice for this period,
 * else the stored planilla's mode, else none. Never carries over from another period.
 */
export function resolveDiscountMode(input: {
  manualMode: DiscountMode | null
  storedMode: string | null | undefined
}): DiscountMode | null {
  if (input.manualMode) return input.manualMode
  return isDiscountMode(input.storedMode) ? input.storedMode : null
}

export function getGenerationGuard(input: {
  startDate: string
  endDate: string
  mode: DiscountMode | null
  statusLoading?: boolean
}): { canGenerate: boolean; reasons: string[] } {
  const reasons: string[] = []
  if (input.statusLoading) reasons.push(STATUS_LOADING_REASON)
  if (!input.startDate || !input.endDate) {
    reasons.push(DATES_REASON)
  } else if (input.startDate > input.endDate) {
    reasons.push(DATE_ORDER_REASON)
  }
  if (!input.mode) reasons.push(MODE_REASON)
  return { canGenerate: reasons.length === 0, reasons }
}

export function formatGenerationSummary(input: {
  kind: PlanillaKind
  month: number
  year: number
  startDate: string
  endDate: string
  mode: DiscountMode
}): string {
  return [
    `Se generará: ${PLANILLA_KIND_LABELS[input.kind]}`,
    formatPeriod(input.month, input.year),
    formatCutoff(input.startDate, input.endDate),
    DISCOUNT_MODE_LABELS[input.mode],
  ].join(' · ')
}

export interface ConfirmSummary {
  title: string
  confirmLabel: string
  tone: 'default' | 'destructive'
  rows: Array<{ label: string; value: string }>
  consequence: string | null
  warning: string | null
}

function formatBs(value: number): string {
  return value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function buildConfirmSummary(input: {
  action: PlanillaConfirmAction
  kind: PlanillaKind
  month: number
  year: number
  startDate: string | null | undefined
  endDate: string | null | undefined
  mode: DiscountMode | null | undefined
  docentes?: number | null
  totalPayment?: number | null
  hasStoredPlanilla?: boolean
}): ConfirmSummary {
  const kindLabel = PLANILLA_KIND_LABELS[input.kind]
  const period = formatPeriod(input.month, input.year)

  const rows = [
    { label: 'Planilla', value: kindLabel },
    { label: 'Período', value: period },
    { label: 'Corte', value: formatCutoff(input.startDate, input.endDate) },
    { label: 'Modo', value: formatMode(input.mode) },
  ]
  if (typeof input.docentes === 'number' && Number.isFinite(input.docentes)) {
    rows.push({ label: 'Docentes', value: String(input.docentes) })
  }
  if (typeof input.totalPayment === 'number' && Number.isFinite(input.totalPayment)) {
    rows.push({ label: 'Total (Bs)', value: formatBs(input.totalPayment) })
  }

  const base = { rows, consequence: null, warning: null, tone: 'default' as const }
  switch (input.action) {
    case 'generate':
      return {
        ...base,
        title: `Generar planilla de ${kindLabel}`,
        confirmLabel: 'Generar',
        warning: input.hasStoredPlanilla
          ? `Ya existe una planilla para ${period}. Al generar se va a reemplazar la planilla generada.`
          : null,
      }
    case 'approve':
      return {
        ...base,
        title: `Aprobar planilla de ${kindLabel}`,
        confirmLabel: 'Aprobar',
        consequence: 'La planilla quedará aprobada y lista para publicar.',
      }
    case 'reject':
      return {
        ...base,
        title: `Rechazar planilla de ${kindLabel}`,
        confirmLabel: 'Rechazar',
        tone: 'destructive',
        consequence: 'La planilla quedará rechazada y vas a tener que regenerarla.',
      }
    case 'publish':
      return {
        ...base,
        title: `Publicar planilla de ${kindLabel}`,
        confirmLabel: 'Publicar',
        consequence: `Los docentes verán sus montos a facturar de ${period}.`,
      }
    case 'unpublish':
      return {
        ...base,
        title: `Despublicar planilla de ${kindLabel}`,
        confirmLabel: 'Despublicar',
        tone: 'destructive',
        consequence: `Los docentes dejarán de ver sus montos a facturar de ${period}.`,
      }
  }
}
