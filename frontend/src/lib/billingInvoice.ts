// What the teacher must do with a published billing amount.
// Teachers without retention invoice the payable amount; teachers with RC-IVA
// retention do not invoice and sign a retention letter at rectorado instead.

export const RETENTION_LETTER_PATH = '/portal/retention-letter'

export interface InvoiceAmounts {
  gross_payment: number | null
  retention_amount: number | null
  net_payment: number | null
  has_retention?: boolean
}

export interface InvoiceInstruction {
  kind: 'invoice' | 'retention_letter'
  headline: string
  amount: number
  note: string
}

export function invoiceInstruction(billing: InvoiceAmounts): InvoiceInstruction | null {
  if (billing.net_payment === null || billing.gross_payment === null) return null

  const hasRetention = Boolean(billing.has_retention) || (billing.retention_amount ?? 0) > 0
  if (hasRetention) {
    return {
      kind: 'retention_letter',
      headline: 'Líquido pagable — no emite factura',
      amount: billing.net_payment,
      note: 'Pasá por rectorado a firmar tu carta de retención.',
    }
  }
  return {
    kind: 'invoice',
    headline: 'Monto a facturar',
    amount: billing.net_payment,
    note: 'Emití tu factura por este monto.',
  }
}
