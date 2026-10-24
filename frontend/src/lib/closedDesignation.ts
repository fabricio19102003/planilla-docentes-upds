export const NO_CLASSES_NOTE = 'Sin clases en este período'

interface PortalRowAmounts {
  period_note?: string | null
  gross_payment: number
  net_payment: number
}

interface PlanillaRowAmounts {
  period_note?: string | null
  base_monthly_hours: number
  payable_hours: number
  calculated_payment: number
  final_payment?: number
}

// The backend only sets period_note on rows with no hours; the amount guard keeps an
// administrative adjustment visible if a zero-hours row was ever paid something.
export function portalRowNote(row: PortalRowAmounts): string | null {
  if (!row.period_note) return null
  return row.gross_payment === 0 && row.net_payment === 0 ? row.period_note : null
}

// Admin detail rows: the dated note comes from the backend; a row with no base and no
// payable hours falls back to the plain note when the endpoint does not provide one.
export function planillaRowNote(row: PlanillaRowAmounts): string | null {
  const note = row.period_note
    ?? (row.base_monthly_hours === 0 && row.payable_hours === 0 ? NO_CLASSES_NOTE : null)
  if (!note) return null
  return (row.final_payment ?? row.calculated_payment) === 0 ? note : null
}
