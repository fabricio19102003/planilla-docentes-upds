import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { invoiceInstruction, RETENTION_LETTER_PATH } from '../src/lib/billingInvoice.ts'

const root = resolve(import.meta.dirname, '..')
const billingPage = readFileSync(resolve(root, 'src/pages/BillingPage.tsx'), 'utf8')
const historyPage = readFileSync(resolve(root, 'src/pages/BillingHistoryPage.tsx'), 'utf8')

test('teacher without retention invoices the full amount', () => {
  const result = invoiceInstruction({ gross_payment: 2250, retention_amount: 0, net_payment: 2250 })
  assert.deepEqual(result, {
    kind: 'invoice',
    headline: 'Monto a facturar',
    amount: 2250,
    note: 'Emití tu factura por este monto.',
  })
})

test('teacher with RC-IVA does not invoice and signs the retention letter', () => {
  const result = invoiceInstruction({ gross_payment: 2250, retention_amount: 292.5, net_payment: 1957.5 })
  assert.deepEqual(result, {
    kind: 'retention_letter',
    headline: 'Líquido pagable — no emite factura',
    amount: 1957.5,
    note: 'Pasá por rectorado a firmar tu carta de retención.',
  })
})

test('explicit has_retention flag selects the retention letter even when the amount is zero', () => {
  const result = invoiceInstruction({ gross_payment: 0, retention_amount: 0, net_payment: 0, has_retention: true })
  assert.equal(result.kind, 'retention_letter')
})

test('missing amounts in unavailable history rows yield no instruction', () => {
  assert.equal(invoiceInstruction({ gross_payment: null, retention_amount: null, net_payment: null }), null)
})

test('retention letter link points to the existing portal route', () => {
  assert.equal(RETENTION_LETTER_PATH, '/portal/retention-letter')
})

test('current billing page renders the instruction headline instead of a bare total', () => {
  assert.match(billingPage, /invoiceInstruction\(billing\)/)
  assert.match(billingPage, /instruction\.headline/)
  assert.match(billingPage, /RETENTION_LETTER_PATH/)
})

test('billing history page labels each published month with the instruction', () => {
  assert.match(historyPage, /invoiceInstruction\(billing\)/)
  assert.match(historyPage, /instruction\.headline/)
})
