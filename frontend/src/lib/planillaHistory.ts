import type { PlanillaDataStatus } from '@/api/types'

type HistoricalPayment = {
  total_payment: string | null
  data_status: PlanillaDataStatus
}

export function getHistoricalPaymentState(item: HistoricalPayment) {
  if (item.data_status === 'legacy_unavailable') {
    return { snapshotAvailable: false, amount: null, display: 'Regeneración requerida' }
  }
  const amount = item.total_payment === null || item.total_payment.trim() === ''
    ? null
    : Number(item.total_payment)
  if (amount === null || !Number.isFinite(amount)) {
    return { snapshotAvailable: false, amount: null, display: 'Monto no disponible' }
  }
  return {
    snapshotAvailable: true,
    amount,
    display: amount.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  }
}

export function getVisiblePlanillaDetail<T>(
  data: T | undefined,
  isPlaceholderData: boolean,
  enabled: boolean,
): T | undefined {
  return enabled && !isPlaceholderData ? data : undefined
}
